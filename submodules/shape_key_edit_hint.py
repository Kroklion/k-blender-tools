import bpy
import blf

bl_info = {
    "name": "Shape Key Edit Hint",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D View (Edit Mode / Sculpt Mode)",
    "description": (
        "Displays a prominent on-screen hint when a non-Basis shape key is active\n"
        "while editing or sculpting. Helps prevent accidental edits to shape keys\n"
        "instead of the base mesh."
    ),
    "category": "3D View",
    "default-enabled": False
}


handler = None


def draw_callback_px(self, context):
    obj = context.object
    if not obj or obj.type != 'MESH':
        return

    # Only show in Sculpt or Edit mode
    if obj.mode not in {'EDIT', 'SCULPT'}:
        return

    # Only show if a non-Basis shape key is active
    if obj.active_shape_key and obj.active_shape_key_index != 0:
        # Get theme color for text (use the 3D View theme settings)
        theme = context.preferences.themes['Default']
        text_color = theme.view_3d.space.text  # returns (r,g,b,a)

        font_id = 0
        blf.size(font_id, 40)
        blf.color(font_id, *text_color, 0.8)  # apply theme color
        blf.position(font_id, 80, 50, 0)
        blf.draw(font_id, f"🞕 {obj.active_shape_key.name}")


def register():
    global handler
    if handler is None:
        handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_px, (None, bpy.context), 'WINDOW', 'POST_PIXEL'
        )


def unregister():
    global handler
    if handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(handler, 'WINDOW')
        handler = None

