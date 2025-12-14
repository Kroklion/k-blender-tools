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


def draw_callback_px():
    # Get a fresh context every time
    context = bpy.context

    # In some situations (startup, background) this can still be restricted,
    # so use getattr to be safe.
    obj = getattr(context, "object", None)
    if not obj or getattr(obj, "type", None) != 'MESH':
        return

    # Only show in Sculpt or Edit mode
    mode = getattr(obj, "mode", None)
    if mode not in {'EDIT', 'SCULPT'}:
        return

    # Only show if a non-Basis shape key is active
    active_key = getattr(obj, "active_shape_key", None)
    active_index = getattr(obj, "active_shape_key_index", None)
    if active_key and active_index not in (None, 0):
        # Try to use theme color; fall back if unavailable
        prefs = getattr(context, "preferences", None)
        text_color = (1.0, 0.2, 0.2, 0.8)  # default fallback

        if prefs:
            try:
                theme = prefs.themes['Default']
                text_color = theme.view_3d.space.text
            except Exception:
                pass

        font_id = 0
        blf.size(font_id, 40)
        # text_color is (r, g, b, a); ensure it’s 4 components
        if len(text_color) == 3:
            text_color = (*text_color, 0.5)
        blf.color(font_id, *text_color)
        blf.position(font_id, 80, 50, 0)
        blf.draw(font_id, f"🞕 {active_key.name}")


def register():
    global handler
    if handler is None:
        handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_px, (), 'WINDOW', 'POST_PIXEL'
        )


def unregister():
    global handler
    if handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(handler, 'WINDOW')
        handler = None

