import asyncio

import cffi
import wgpu.wgpu_ffi


ffi = cffi.FFI()


def ffi_code_from_spirv_module(m):
    data = m.to_bytes()
    x = ffi.new("uint8_t[]", data)
    y = ffi.cast("uint32_t *", x)
    return dict(bytes=y, length=len(data) // 4)


# # todo: stop when window is closed ...
# async def drawer():
#     while True:
#         await asyncio.sleep(0.1)
#         # print("draw")
#         drawFrame()
#
# asyncio.get_event_loop().create_task(drawer())


class Renderer:
    def __init__(self):
        ffi = wgpu.wgpu_ffi.ffi

        # todo: this context is not really a context, its just an API, maybe keep it that way, or make it a context by including device_id
        ctx = wgpu.wgpu_ffi.RsWGPU()
        self._ctx = ctx

        self._surface_size = 0, 0
        # backends = 1 | 2 | 4 | 8  # modern, but Dx12 is still buggy
        backends = 2 | 4  # Vulkan or Metal
        # on HP laptop: 2 and 8 are available, but 2 does not work. 8 works, but it wants zero bind groups :/
        # 1 => Backend::Empty,
        # 2 => Backend::Vulkan,
        # 4 => Backend::Metal,
        # 8 => Backend::Dx12,
        # 16 => Backend::Dx11,
        # 32 => Backend::Gl,

        # Initialize adapter id. It will be set from the callback that we pass
        # to request_adapter_async. At the moment, the callback will be called
        # directly (in-line), but this will change in the future when wgpu also
        # introduces the concept of an event loop, to support JS Futures.
        adapter_id = None

        @ffi.callback("void(uint64_t, void *)")
        def request_adapter_callback(received, userdata):
            nonlocal adapter_id
            adapter_id = received

        ctx.request_adapter_async(
            ctx.create_RequestAdapterOptions(
                power_preference=ctx.PowerPreference_Default
            ),
            backends,
            request_adapter_callback,
            ffi.NULL,  # userdata, stub
        )

        device_des = ctx.create_DeviceDescriptor(
            extensions=ctx.create_Extensions(anisotropic_filtering=False),
            limits=ctx.create_Limits(max_bind_groups=0),
        )

        self._device_id = ctx.adapter_request_device(adapter_id, device_des)

    def collect_from_figure(self, figure):

        wobjects = []
        for view in figure.views:
            for ob in view.scene.children:  # todo: and their children, and ...
                wobjects.append(ob)

        assert (
            len(wobjects) == 1
        ), "haha, support only one object in total, no more, no less"

        self.compose_pipeline(wobjects[0])

    def compose_pipeline(self, wobject):
        ctx = self._ctx
        device_id = self._device_id

        # Get description from world object
        pipelinedescription = wobject.describe_pipeline()

        vshader = pipelinedescription["vertex_shader"]  # an SpirVModule
        vs_module = ctx.device_create_shader_module(
            device_id,
            ctx.create_ShaderModuleDescriptor(code=ffi_code_from_spirv_module(vshader)),
        )

        fshader = pipelinedescription["fragment_shader"]
        fs_module = ctx.device_create_shader_module(
            device_id,
            ctx.create_ShaderModuleDescriptor(code=ffi_code_from_spirv_module(fshader)),
        )

        # todo: I think this is where uniforms go
        bind_group_layout = ctx.device_create_bind_group_layout(
            device_id,
            ctx.create_BindGroupLayoutDescriptor(bindings=(), bindings_length=0),
        )

        bind_group = ctx.device_create_bind_group(
            device_id,
            ctx.create_BindGroupDescriptor(
                layout=bind_group_layout, bindings=(), bindings_length=0
            ),
        )

        pipeline_layout = ctx.device_create_pipeline_layout(
            device_id,
            # ctx.create_PipelineLayoutDescriptor(bind_group_layouts=(bind_group, ), bind_group_layouts_length=1)
            ctx.create_PipelineLayoutDescriptor(
                bind_group_layouts=(), bind_group_layouts_length=0
            ),
        )

        # todo: a lot of these functions have device_id as first arg - this smells like a class, perhaps
        # todo: several descriptor args have a list, and another arg to provide the length of that list, because C

        self._render_pipeline = ctx.device_create_render_pipeline(
            device_id,
            ctx.create_RenderPipelineDescriptor(
                layout=pipeline_layout,
                vertex_stage=ctx.create_ProgrammableStageDescriptor(
                    module=vs_module, entry_point="main"
                ),
                # fragment_stage: Some(ctx::ProgrammableStageDescriptor {
                fragment_stage=ctx.create_ProgrammableStageDescriptor(
                    module=fs_module, entry_point="main"
                ),
                primitive_topology=ctx.PrimitiveTopology_TriangleList,
                # rasterization_state: Some(ctx::RasterizationStateDescriptor {
                rasterization_state=ctx.create_RasterizationStateDescriptor(
                    front_face=ctx.FrontFace_Ccw,
                    cull_mode=ctx.CullMode_None,
                    depth_bias=0,
                    depth_bias_slope_scale=0.0,
                    depth_bias_clamp=0.0,
                ),
                # color_states: &[ctx::ColorStateDescriptor {
                color_states=ctx.create_ColorStateDescriptor(
                    format=ctx.TextureFormat_Bgra8UnormSrgb,
                    alpha_blend=ctx.create_BlendDescriptor(
                        src_factor=ctx.BlendFactor_One,
                        dst_factor=ctx.BlendFactor_Zero,
                        operation=ctx.BlendOperation_Add,
                    ),
                    color_blend=ctx.create_BlendDescriptor(
                        src_factor=ctx.BlendFactor_One,
                        dst_factor=ctx.BlendFactor_Zero,
                        operation=ctx.BlendOperation_Add,
                    ),
                    write_mask=ctx.ColorWrite_ALL,  # write_mask: ctx::ColorWrite::ALL,
                ),
                color_states_length=1,
                depth_stencil_state=None,
                vertex_input=ctx.create_VertexInputDescriptor(
                    index_format=ctx.IndexFormat_Uint16,
                    vertex_buffers=(),
                    vertex_buffers_length=0,
                ),
                sample_count=1,
                sample_mask=1,  # todo: or FFFFFFFFFF-ish?
                alpha_to_coverage_enabled=False,
            ),
        )

    def _create_swapchain(self, surface_id, width, height):
        ctx = self._ctx
        device_id = self._device_id

        self._swap_chain = ctx.device_create_swap_chain(
            device_id=device_id,
            surface_id=surface_id,
            desc=ctx.create_SwapChainDescriptor(
                usage=ctx.TextureUsage_OUTPUT_ATTACHMENT,  # usage
                format=ctx.TextureFormat_Bgra8UnormSrgb,  # format: ctx::TextureFormat::Bgra8UnormSrgb,
                width=width,  # width: size.width.round() as u32,
                height=height,  # height: size.height.round() as u32,
                present_mode=ctx.PresentMode_Vsync,  # present_mode: ctx::PresentMode::Vsync,
            ),
        )

    def draw_frame(self, figure):

        # When resizing, re-create the swapchain
        cur_size = figure.get_size()
        if cur_size != self._surface_size:
            self._surface_size = cur_size
            self._create_swapchain(figure._get_surface_id(self._ctx), *cur_size)

        ctx = self._ctx
        device_id = self._device_id
        swap_chain = self._swap_chain

        next_texture = ctx.swap_chain_get_next_texture(swap_chain)
        command_encoder = ctx.device_create_command_encoder(
            device_id, ctx.create_CommandEncoderDescriptor(todo=0)
        )

        rpass = ctx.command_encoder_begin_render_pass(
            command_encoder,
            ctx.create_RenderPassDescriptor(
                color_attachments=(
                    ctx.create_RenderPassColorAttachmentDescriptor(
                        # attachment=next_texture["view_id"],
                        # todo: arg! need struct2dict function in ffi implementation
                        attachment=next_texture["view_id"]
                        if isinstance(next_texture, dict)
                        else next_texture.view_id,
                        resolve_target=None,  # resolve_target: None,
                        load_op=ctx.LoadOp_Clear,  # load_op: ctx::LoadOp::Clear,
                        store_op=ctx.StoreOp_Store,  # store_op: ctx::StoreOp::Store,
                        clear_color=dict(
                            r=0.5, g=255, b=0, a=255
                        ),  # clear_color: ctx::Color::GREEN,
                    ),
                ),
                color_attachments_length=1,
                depth_stencil_attachment=None,  # depth_stencil_attachement
            ),
        )

        ctx.render_pass_set_pipeline(rpass, self._render_pipeline)
        # ctx.render_pass_set_bind_group(rpass, 0, bind_group, [], 0)
        ctx.render_pass_draw(rpass, 3, 1, 0, 0)

        queue = ctx.device_get_queue(device_id)
        ctx.render_pass_end_pass(rpass)
        cmd_buf = ctx.command_encoder_finish(command_encoder, None)
        ctx.queue_submit(queue, [cmd_buf], 1)
        ctx.swap_chain_present(swap_chain)