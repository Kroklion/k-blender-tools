bl_info = {
    "name": "MB5 Cycle Selection Mode",
    "author": "Copilot",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "Edit/Weight Paint Mode",
    "description": (
        "Use Mouse Button 5 to quickly cycle selection or masking modes:\n"
        "• Edit Mode: Vertex → Edge → Face\n"
        "• Weight/Vertex Paint: Face Mask → Vertex Mask → No Mask\n"
        "• Texture Paint: Toggle Face Mask"
    ),
    "category": "3D View",
    "default-enabled": False
}

import bpy

class MESH_OT_cycle_select_mode(bpy.types.Operator):
    """Cycle between Vertex/Edge/Face in Edit Mode or Masking in Weight Paint"""
    bl_idname = "mesh.cycle_select_mode"
    bl_label = "Cycle Select/Mask Mode"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        mode = context.mode

        if mode == 'EDIT_MESH':
            # --- Edit Mode: cycle vertex/edge/face ---
            ts = context.tool_settings
            sel = ts.mesh_select_mode[:]

            if sel[0]:
                ts.mesh_select_mode = (False, True, False)   # Edge
            elif sel[1]:
                ts.mesh_select_mode = (False, False, True)   # Face
            else:
                ts.mesh_select_mode = (True, False, False)   # Vertex

        elif mode in {'PAINT_WEIGHT', 'VERTEX_PAINT'}:
            # --- Weight/Vertex Paint: cycle 3 states ---
            me = obj.data
            if me.use_paint_mask:
                # Face masking → vertex masking
                me.use_paint_mask = False
                me.use_paint_mask_vertex = True
            elif me.use_paint_mask_vertex:
                # Vertex masking → no masking
                me.use_paint_mask_vertex = False
            else:
                # No masking → face masking
                me.use_paint_mask = True

        elif mode == 'TEXTURE_PAINT':
            # --- Texture Paint: only face masking available ---
            me = obj.data
            if me.use_paint_mask:
                me.use_paint_mask = False
            else:
                me.use_paint_mask = True

        if context.area:
            context.area.tag_redraw()

        return {'FINISHED'}



addon_keymaps = []

def register():
    bpy.utils.register_class(MESH_OT_cycle_select_mode)

    # Add keymap for Edit and Weight Paint modes
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    if kc:
        # Edit Mode
        km = kc.keymaps.new(name='Mesh', space_type='EMPTY')
        kmi = km.keymap_items.new("mesh.cycle_select_mode", 'BUTTON5MOUSE', 'PRESS')
        addon_keymaps.append((km, kmi))

        # Weight Paint Mode
        km = kc.keymaps.new(name='Weight Paint', space_type='EMPTY')
        kmi = km.keymap_items.new("mesh.cycle_select_mode", 'BUTTON5MOUSE', 'PRESS')
        addon_keymaps.append((km, kmi))

        # UV Editor
        km = kc.keymaps.new(name='UV Editor', space_type='EMPTY')
        kmi = km.keymap_items.new(
            "mesh.cycle_select_mode", 'BUTTON5MOUSE', 'PRESS')
        addon_keymaps.append((km, kmi))


def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    bpy.utils.unregister_class(MESH_OT_cycle_select_mode)


if __name__ == "__main__":
    register()
