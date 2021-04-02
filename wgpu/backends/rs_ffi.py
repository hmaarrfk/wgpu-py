import os
import sys
import logging

from .._coreutils import get_resource_filename, logger_set_level_callbacks

from cffi import FFI, __version_info__ as cffi_version_info


logger = logging.getLogger("wgpu")  # noqa


if cffi_version_info < (1, 10):  # no-cover
    raise ImportError(f"{__name__} needs cffi 1.10 or later.")


def get_wgpu_h():
    """Read header file and strip some stuff that cffi would stumble on."""
    lines = []
    with open(get_resource_filename("wgpu.h")) as f:
        for line in f.readlines():
            if not line.startswith(
                (
                    "#include ",
                    "#define WGPU_LOCAL",
                    "#define WGPUColor",
                    "#define WGPUOrigin3d_ZERO",
                    "#if defined",
                    "#endif",
                )
            ):
                lines.append(line)
    return "".join(lines)


def get_wgpu_lib_path():
    """Get the path to the wgpu library, taking into account the
    WGPU_LIB_PATH environment variable.
    """

    # If path is given, use that or fail trying
    override_path = os.getenv("WGPU_LIB_PATH", "").strip()
    if override_path:
        return override_path

    # Load the debug binary if requested
    debug_mode = os.getenv("WGPU_DEBUG", "").strip() == "1"
    build = "debug" if debug_mode else "release"

    # Get lib filename for supported platforms
    if sys.platform.startswith("win"):  # no-cover
        lib_filename = f"wgpu_native-{build}.dll"
    elif sys.platform.startswith("darwin"):  # no-cover
        lib_filename = f"libwgpu_native-{build}.dylib"
    elif sys.platform.startswith("linux"):  # no-cover
        lib_filename = f"libwgpu_native-{build}.so"
    else:  # no-cover
        raise RuntimeError(
            f"No WGPU library shipped for platform {sys.platform}. Set WGPU_LIB_PATH instead."
        )

    # Note that this can be a false positive, e.g. ARM linux.
    embedded_path = get_resource_filename(lib_filename)
    if not os.path.isfile(embedded_path):  # no-cover
        raise RuntimeError(f"Could not find WGPU library in {embedded_path}")
    else:
        return embedded_path


# Configure cffi and load the dynamic library
# NOTE: `import wgpu.backends.rs` is used in pyinstaller tests to verify
# that we can load the DLL after freezing
ffi = FFI()
ffi.cdef(get_wgpu_h())
ffi.set_source("wgpu.h", None)
lib = ffi.dlopen(get_wgpu_lib_path())


def check_expected_version(version_info):
    _version_int = lib.wgpu_get_version()
    version_info_lib = tuple((_version_int >> bits) & 0xFF for bits in (16, 8, 0))
    if version_info_lib != version_info:  # no-cover
        logger.warning(
            f"Expected wgpu-native version {version_info} but got {version_info_lib}"
        )


@ffi.callback("void(int level, const char *)")
def _logger_callback(level, c_msg):
    """Called when Rust emits a log message."""
    msg = ffi.string(c_msg).decode(errors="ignore")  # make a copy
    # todo: We currently skip some false negatives to avoid spam.
    false_negatives = (
        "Unknown decoration",
        "Failed to parse shader",
        "Shader module will not be validated",
    )
    if msg.startswith(false_negatives):
        return
    m = {
        lib.WGPULogLevel_Error: logger.error,
        lib.WGPULogLevel_Warn: logger.warning,
        lib.WGPULogLevel_Info: logger.info,
        lib.WGPULogLevel_Debug: logger.debug,
        lib.WGPULogLevel_Trace: logger.debug,
    }
    func = m.get(level, logger.warning)
    func(msg)


def _logger_set_level_callback(level):
    """Called when the log level is set from Python."""
    if level >= 40:
        lib.wgpu_set_log_level(lib.WGPULogLevel_Error)
    elif level >= 30:
        lib.wgpu_set_log_level(lib.WGPULogLevel_Warn)
    elif level >= 20:
        lib.wgpu_set_log_level(lib.WGPULogLevel_Info)
    elif level >= 10:
        lib.wgpu_set_log_level(lib.WGPULogLevel_Debug)
    elif level >= 5:
        lib.wgpu_set_log_level(lib.WGPULogLevel_Trace)  # extra level
    else:
        lib.wgpu_set_log_level(lib.WGPULogLevel_Off)


# Connect Rust logging with Python logging
lib.wgpu_set_log_callback(_logger_callback)
logger_set_level_callbacks.append(_logger_set_level_callback)
_logger_set_level_callback(logger.level)