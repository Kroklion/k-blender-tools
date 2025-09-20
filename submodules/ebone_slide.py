import bpy
import gpu
import mathutils
from .. import log

bl_info = {
    "name": "Edit Bone Slide",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Edit Mode (Armature) > Armature Menu\n"
        "Shift + V : Slide selected bone endpoints along their own direction"
    ),
    "description": (
        "Allows sliding of selected edit bone endpoints along the bone’s axis\n"
        "in Edit Armature Mode. Supports sliding head, tail, or both endpoints\n"
        "with fine control using Shift. WIP."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Rigging",
}


from gpu_extras.batch import batch_for_shader
# from bpy_extras.view3d_utils import location_3d_to_region_2d


def safe_location_3d_to_region_2d(region, rv3d, coord) -> mathutils.Vector | None:
    """
    Projects a 3D point to 2D region space even if it's behind the camera.
    This computes the normalized device coordinates (NDC) using
    the region view perspective matrix and then maps them to region coordinates.
    """
    vec = rv3d.perspective_matrix @ coord.to_4d()
    if vec.w == 0.0:
        return None  # should not happen, but just in case.
    ndc = vec.xyz / vec.w

    # If the point is behind the camera (w < 0), the ndc values
    # might be inverted. Might want to clamp to the view bounds.
    x = (ndc.x + 1.0) / 2.0 * region.width
    y = (ndc.y + 1.0) / 2.0 * region.height
    return mathutils.Vector((x, y))


class BoneSlideOperator(bpy.types.Operator):
    """Slide bone endpoints along the bone's own direction in Edit Armature Mode."""
    bl_idname = "armature.bone_slide"
    bl_label = "Bone Slide"
    bl_options = {'REGISTER', 'UNDO'}

    # Properties to store the initial mouse position and the accumulated slide:
    initial_mouse_x: bpy.props.IntProperty()
    initial_mouse_y: bpy.props.IntProperty()
    
    accumulated_slide: bpy.props.FloatProperty()
    
    current_mouse_y = 0 # TODO

    # Dictionaries to store the initial bone endpoints and determine move mode:
    initial_positions = {}
    bone_modes = {}
    
    # Handle for the viewport drawing callback:
    _handle = None
    
    nav = {
        'MIDDLEMOUSE',      # orbit
        'SHIFT+MIDDLEMOUSE',  # pan
        'WHEELUPMOUSE',     # zoom
        'WHEELDOWNMOUSE',    # zoom
        'TRACKPADPAN',      # touchpad
        'TRACKPADZOOM',     # touchpad
    }

    def modal(self, context, event):

        key = event.type if not event.shift else f"SHIFT+{event.type}"
        if key in self.nav:
            return {'PASS_THROUGH'}

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            # Revert changes if the user cancels the operation.
            for eb, (head_orig, tail_orig) in self.initial_positions.items():
                eb.head = head_orig.copy()
                eb.tail = tail_orig.copy()
            context.area.tag_redraw()
            context.workspace.status_text_set(None)
            context.area.header_text_set(None)
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            bpy.context.window.cursor_modal_restore()
            return {'CANCELLED'}

        elif event.type == 'MOUSEMOVE':
            # Define a threshold in pixels near the region borders.
            threshold = 5
            
            # Translate mouse position into view area coordinates.
            # mouse_x = event.mouse_x - context.region.x
            mouse_y = event.mouse_y - context.region.y
                        
            # Use region (3D view) dimensions.
            # region_width = context.region.width
            region_height = context.region.height

            warp_needed = False
            new_x, new_y = event.mouse_x, event.mouse_y

            # Check if the cursor is too near left or right boundaries.
            #if mouse_x < threshold or mouse_x > region_width - threshold:
            #    new_x = int(region_width / 2)
            #    warp_needed = True

            # Check if the cursor is too near top or bottom boundaries.
            if mouse_y < threshold or mouse_y > region_height - threshold:
                new_y = int(region_height / 2)
                warp_needed = True

            if warp_needed:
                # Warp the cursor to a new location relative to the view region.
                context.window.cursor_warp(new_x + context.region.x, new_y + context.region.y)
                # Reset your reference point to the new absolute cursor position.
                # self.initial_mouse_x = new_x + context.region.x
                self.initial_mouse_y = new_y + context.region.y
                return {'RUNNING_MODAL'}
        
            # Calculate mouse movement delta from the stored reference.
            dy = event.mouse_y - self.initial_mouse_y

            # Base sensitivities (world units per pixel at init zoom)
            base_factor = 0.002
            fine_base = 0.0002

            rv3d = context.region_data

            zoom_factor = rv3d.view_distance
            
            log.info(f"Zoomf {zoom_factor}")
            
            if event.shift:
                slide_factor = fine_base * zoom_factor
            else:
                slide_factor = base_factor * zoom_factor
                 
            slide_amount = dy * slide_factor + self.accumulated_slide
            self.accumulated_slide = slide_amount

            # Update each bone’s endpoints along its direction.
            for eb, mode in self.bone_modes.items():
                init_head, init_tail = self.initial_positions[eb]
                direction = (init_tail - init_head).normalized()

                if mode == "head_only":
                    eb.head = init_head + direction * slide_amount
                elif mode == "tail_only":
                    eb.tail = init_tail + direction * slide_amount
                elif mode == "both":
                    eb.head = init_head + direction * slide_amount
                    eb.tail = init_tail + direction * slide_amount

            context.area.header_text_set(f"D: {self.accumulated_slide:.4f}m")
            context.area.tag_redraw()
            
            # Update the reference mouse position.
            # self.initial_mouse_x = event.mouse_x
            self.initial_mouse_y = event.mouse_y

            # Update the status bar text.
            status_text = (
                f"LMB/Enter: Confirm  |  ESC/RMB: Cancel  |  SHIFT: Fine Slide"
            )
            context.workspace.status_text_set(status_text)
            
            return {'RUNNING_MODAL'}

        elif event.type in {'LEFTMOUSE', 'RET'}:
            # Confirm the slide operation:
            context.workspace.status_text_set(None)
            context.area.header_text_set(None)
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            bpy.context.window.cursor_modal_restore()
            return {'FINISHED'}

        return {'RUNNING_MODAL'}
    
    def draw_callback_px(self, context, _):
        region = context.region
        # Set up and draw the lines (in yellow).
        if self.line_verts:
            shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
            shader.uniform_float("lineWidth", 1)
            shader.uniform_float("viewportSize", (region.width, region.height))
            shader.uniform_float("color", (0.8, 0.8, 0.0, 1.0))  # Yellow color
            
            batch = batch_for_shader(shader, 'LINES', {"pos": self.line_verts})
            shader.bind()
            batch.draw(shader)

    @classmethod
    def poll(cls, context):
        # Ensure we are in an armature in Edit Armature Mode.
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            return False
        if context.mode != 'EDIT_ARMATURE':
            return False
        return True

    def invoke(self, context, event):
        # Gather all edit bones that have at least one endpoint selected.
        self.initial_positions = {}
        self.bone_modes = {}
        self.line_verts = []
        rv3d = context.region_data
        self.init_view_distance = rv3d.view_distance
        self.init_camera_zoom = rv3d.view_camera_zoom
        self.is_ortho = (rv3d.view_perspective == 'ORTHO')
        
        obj = context.active_object
        for eb in obj.data.edit_bones:
            if eb.select_head or eb.select_tail:
                self.initial_positions[eb] = (eb.head.copy(), eb.tail.copy())
                if eb.select_head and not eb.select_tail:
                    self.bone_modes[eb] = "head_only"
                elif eb.select_tail and not eb.select_head:
                    self.bone_modes[eb] = "tail_only"
                elif eb.select_head and eb.select_tail:
                    self.bone_modes[eb] = "both"

        if not self.initial_positions:
            self.report({'WARNING'}, "No bone endpoints selected.")
            return {'CANCELLED'}

        # Record the initial mouse position and reset the slide accumulator.
        # self.initial_mouse_x = event.mouse_x
        self.initial_mouse_y = event.mouse_y
        self.accumulated_slide = 0
        
        # calculate movement indication lines
        region = context.region
        rv3d = context.region_data
        for eb, mode in self.bone_modes.items():
            # Get stored initial head/tail positions.
            init_head, init_tail = self.initial_positions.get(eb, (None, None))

            # Convert the stored 3D endpoints to world space...
            head_world = obj.matrix_world @ init_head
            tail_world = obj.matrix_world @ init_tail

            # …then project them into 2D screen coordinates.
            p_head = safe_location_3d_to_region_2d(region, rv3d, head_world)
            p_tail = safe_location_3d_to_region_2d(region, rv3d, tail_world)
            
            if p_head.x == p_tail.x:
                # un-computable line
                p1 = mathutils.Vector((p_head.x, 0))
                p2 = mathutils.Vector((p_head.x, region.height))
                self.line_verts.extend([p1, p2])
            else:
                slope = (p_head.y - p_tail.y)/(p_head.x - p_tail.x)
                b = p_head.y - slope * p_head.x

                p1 = mathutils.Vector((0, b))
                p2 = mathutils.Vector((region.width, region.width * slope + b))

                self.line_verts.extend([p1, p2])
        
        # Add the viewport drawing callback.
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback_px, (context, None), 'WINDOW', 'POST_PIXEL'
        )
        
        context.window_manager.modal_handler_add(self)
        bpy.context.window.cursor_modal_set("NONE")
        return {'RUNNING_MODAL'}


def menu_func(self, context):
    self.layout.operator(BoneSlideOperator.bl_idname,
                         text=BoneSlideOperator.bl_label)


addon_keymaps = []

def add_hotkeys():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(
            name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(
            BoneSlideOperator.bl_idname, type='V', value='PRESS', shift=True)
        addon_keymaps.append((km, kmi))
        
def remove_hotkeys():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


def register():
    bpy.utils.register_class(BoneSlideOperator)
    bpy.types.VIEW3D_MT_edit_armature.append(menu_func)
    add_hotkeys()
    
def unregister():
    remove_hotkeys()
    bpy.utils.unregister_class(BoneSlideOperator)
    bpy.types.VIEW3D_MT_edit_armature.remove(menu_func)

