"""
An example demonstrating a qt app with a wgpu viz inside.
If needed, change the PySide6 import to e.g. PyQt6, PyQt5, or PySide2.

# run_example = false
"""

import importlib

# For the sake of making this example Just Work, we try multiple QT libs
for lib in ("PySide6", "PyQt6", "PySide2", "PyQt5"):
    try:
        QtWidgets = importlib.import_module(".QtWidgets", lib)
        break
    except ModuleNotFoundError:
        pass


import wgpu
from wgpu.gui.qt import WgpuWidget

from triangle import _main
import PySide6
from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage
import numpy as np
import imageio

class MyWidget(QtWidgets.QWidget):
    def grab(self, rectangle: PySide6.QtCore.QRect=PySide6.QtCore.QRect(0, 0, -1, -1)):
        print("grabbing screenshot MyWidget")
        return super().grab(*args, **kwargs)


def get_snapshot(canvas, device):
    """Create a snapshot of the currently rendered image."""
    arr = np.zeros((1, 3), dtype=np.uint8)
    arr[0, 0] = 255
    return arr

    # I can't seem to get the texture right here...
    # Prepare
    context = canvas.get_context()
    texture = context.get_current_texture()
    context.get_preferred_format(device.adapter)

    size = texture.size
    bytes_per_pixel = 4

    # Note, with queue.read_texture the bytes_per_row limitation does not apply.
    data = self._device.queue.read_texture(
        {
            "texture": texture,
            "mip_level": 0,
            "origin": (0, 0, 0),
        },
        {
            "offset": 0,
            "bytes_per_row": bytes_per_pixel * size[0],
            "rows_per_image": size[1],
        },
        size,
    )

    return np.frombuffer(data, np.uint8).reshape(size[1], size[0], 4)


class ExampleWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.resize(640, 480)
        self.setWindowTitle("wgpu triangle embedded in a qt app")

        splitter = QtWidgets.QSplitter()

        self.button = QtWidgets.QPushButton("Hello world", self)
        self.button_grab = QtWidgets.QPushButton("Grab", self)
        self.button_grab_manually = QtWidgets.QPushButton("Grab Manually", self)
        self.canvas1 = WgpuWidget(splitter)
        self.canvas2 = WgpuWidget(splitter)

        self._wgpu_adapter = wgpu.gpu.request_adapter()
        self._wgpu_device = self._wgpu_adapter.request_device()
        _main(self.canvas1, self._wgpu_device)
        _main(self.canvas2, self._wgpu_device)

        self.my_widget = MyWidget()

        splitter.addWidget(self.canvas1)
        splitter.addWidget(self.canvas2)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.button, 0)
        layout.addWidget(self.button_grab, 0)
        layout.addWidget(self.button_grab_manually, 0)
        layout.addWidget(self.my_widget)
        layout.addWidget(splitter, 1)
        self.setLayout(layout)

        self.button_grab.clicked.connect(self.grab_screenshot)
        self.button_grab_manually.clicked.connect(self.grab_screenshot_manually)

        self.show()

    def grab_screenshot(self):
        print("grabbing screenshot")
        qpix = self.grab()
        qpix.save("screenshot.png", "PNG")

    def grab_screenshot_manually(self):
        qpix_image = self.grab().toImage()

        if QImage.Format.Format_RGB32 != qpix_image.format():
            # Ok I've never encountered an other format but maybe with HDR
            # displays???
            print("Image format is QImage.Format.Format_RGB32, "
                  "screenshot will not be correct.")

        # QImage::Format_RGB32
        # The image is stored using a 32-bit RGB format (0xffRRGGBB).
        np_image = np.frombuffer(
            qpix_image.bits(), dtype='uint32'
        ).reshape(qpix_image.size().height(), -1)

        r = np.right_shift(
            np.bitwise_and(np_image, 0x00FF_0000),
            16).astype('uint8')
        g = np.right_shift(
            np.bitwise_and(np_image, 0x0000_FF00),
            8).astype('uint8')
        b = np.right_shift(
            np.bitwise_and(np_image, 0x0000_00FF),
            0).astype('uint8')
        np_image = np.stack([r, g, b], axis=-1)

        canvas = self.canvas1
        snapshot = get_snapshot(canvas, self._wgpu_device)
        offset = canvas.mapTo(self, QPoint(0, 0))
        qt_pixel_ratio = int(canvas.get_pixel_ratio())
        y_start = offset.y() * qt_pixel_ratio
        x_start = offset.x() * qt_pixel_ratio

        canvas_height = canvas.size().height() * qt_pixel_ratio
        canvas_width = canvas.size().width() * qt_pixel_ratio

        np_image[
            y_start:y_start + canvas_height, # min(canvas_height, snapshot.shape[0]),
            x_start:x_start + canvas_width, # min(canvas_width, snapshot.shape[1]),
        ] = [(255, 0, 0)]
        # With pygfx, i use the snapshot and I resize it appropriately with
        # many self made heuristics
        # I have alot of "safety slicing" to ensure that some image gets output
        # but it shouldn't be necessary if I fully understood qt + wgpu/pygfx
        # snapshot[
        #     :min(canvas_height, snapshot.shape[0]),
        #     :min(canvas_width, snapshot.shape[1]),
        # ]

        # Repeat for all canvases
        canvas = self.canvas2
        snapshot = get_snapshot(canvas, self._wgpu_device)
        offset = canvas.mapTo(self, QPoint(0, 0))
        qt_pixel_ratio = int(canvas.get_pixel_ratio())
        y_start = offset.y() * qt_pixel_ratio
        x_start = offset.x() * qt_pixel_ratio

        canvas_height = canvas.size().height() * qt_pixel_ratio
        canvas_width = canvas.size().width() * qt_pixel_ratio

        np_image[
            y_start:y_start + canvas_height, # min(canvas_height, snapshot.shape[0]),
            x_start:x_start + canvas_width, # min(canvas_width, snapshot.shape[1]),
        ] = [(0, 0, 255)]

        imageio.imwrite("screenshot_manually.png", np_image, compress_level=3)
        print(f"Wrote screenshot_manually.png")


app = QtWidgets.QApplication([])
example = ExampleWidget()

# Enter Qt event loop (compatible with qt5/qt6)
app.exec() if hasattr(app, "exec") else app.exec_()
