import bmesh
import bpy

bl_info = {
    "name": "Weight Paint Mask Tools",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Weight Paint Mode > Weights Menu\n"
        "Hotkeys:\n"
        "  M : Mask From Bones\n"
        "  Ctrl + Numpad + : Grow Mask\n"
        "  Ctrl + Numpad - : Shrink Mask"
    ),
    "description": (
        "Adds tools for masking in Weight Paint mode:\n"
        "• Mask From Bones – hide mesh not affected by selected bones\n"
        "• Mask Grow – expand the current mask selection\n"
        "• Mask Shrink – contract the current mask selection"
    ),
    "warning": "",
    "doc_url": "",
    "category": "Paint",
}

class OBJECT_OT_weight_mask_mesh_from_bone(bpy.types.Operator):
    bl_idname = "object.weight_paint_invert_selection"
    bl_label = "Mask From Bones"
    bl_description = "Hide mesh not affected by selected bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        # must be a mesh in Weight Paint mode with an Armature modifier
        return (
            obj and obj.type == 'MESH' and
            context.mode == 'PAINT_WEIGHT' and
            any(mod.type == 'ARMATURE' for mod in obj.modifiers)
        )

    def execute(self, context):
        mesh_obj = context.object

        # find Armature object from modifiers
        arm_obj = None
        for mod in mesh_obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                arm_obj = mod.object
                break

        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'WARNING'}, "No valid Armature modifier found")
            return {'CANCELLED'}

        # gather names of selected pose bones
        sel_bones = [pb.name for pb in arm_obj.pose.bones if pb.bone.select]
        if not sel_bones:
            self.report({'WARNING'}, "No pose bones selected on Armature")
            return {'CANCELLED'}

        # switch to Edit Mode on the mesh
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(mesh_obj.data)

        # unhide all, then deselect everything
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action='DESELECT')
        bm.verts.ensure_lookup_table()

        # match those bone names to vertex groups
        vg_indices = [
            mesh_obj.vertex_groups[name].index
            for name in sel_bones
            if name in mesh_obj.vertex_groups
        ]
        if not vg_indices:
            self.report(
                {'WARNING'}, "No vertex groups match selected bone names")
            # still proceed, so you get an empty selection

        # select verts whose weight in any of those groups is > 0
        for v in bm.verts:
            has_weight = False
            for g in mesh_obj.data.vertices[v.index].groups:
                if g.group in vg_indices and g.weight > 0.0:
                    has_weight = True
                    break
            v.select = has_weight

        bmesh.update_edit_mesh(mesh_obj.data)

        bpy.ops.mesh.hide(unselected=True)

        # return to Weight Paint
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

        return {'FINISHED'}


class WEIGHTPAINT_OT_mask_grow(bpy.types.Operator):
    """Grow the weight-paint mask"""
    bl_idname = "select.weight_paint_mask_grow"
    bl_label = "Mask Grow"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        print("poll")
        return context.mode == 'PAINT_WEIGHT' and obj and obj.type == 'MESH'

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT')

        # select all visible vertices
        bpy.ops.mesh.select_all(action='SELECT')

        # reveal hidden verts without selecting them
        bpy.ops.mesh.reveal(select=False)

        # grow selection by one ring
        bpy.ops.mesh.select_more()

        # hide everything except the newly-grown selection
        bpy.ops.mesh.select_all(action='INVERT')
        bpy.ops.mesh.hide()

        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}


class WEIGHTPAINT_OT_mask_shrink(bpy.types.Operator):
    """Shrink the weight-paint mask"""
    bl_idname = "object.weight_paint_mask_shrink"
    bl_label = "Mask Shrink"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return context.mode == 'PAINT_WEIGHT' and obj and obj.type == 'MESH'

    def execute(self, context):
        bpy.ops.object.mode_set(mode='EDIT')

        # select all visible vertices
        bpy.ops.mesh.select_all(action='SELECT')

        # shrink selection by one ring
        bpy.ops.mesh.select_less()

        # hide the ring that was cut off
        bpy.ops.mesh.select_all(action='INVERT')
        bpy.ops.mesh.hide()

        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(
        OBJECT_OT_weight_mask_mesh_from_bone.bl_idname)
    self.layout.operator(
        WEIGHTPAINT_OT_mask_shrink.bl_idname)
    self.layout.operator(
        WEIGHTPAINT_OT_mask_grow.bl_idname)


addon_keymaps = []


def add_hotkeys():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        name = '3D View'

        if name not in kc.keymaps:
            _ = kc.keymaps.new(name, space_type='VIEW_3D')

        km = kc.keymaps[name]
        plus = km.keymap_items.new(WEIGHTPAINT_OT_mask_grow.bl_idname,
                                  'NUMPAD_PLUS', 'PRESS', ctrl=True)
        addon_keymaps.append((km, plus))

        minus = km.keymap_items.new(WEIGHTPAINT_OT_mask_shrink.bl_idname,
                                  'NUMPAD_MINUS', 'PRESS', ctrl=True)
        addon_keymaps.append((km, minus))
        
        mask = km.keymap_items.new(OBJECT_OT_weight_mask_mesh_from_bone.bl_idname,
                                   'M', 'PRESS')
        addon_keymaps.append((mask, minus))
    
    
def remove_hotkeys():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
        addon_keymaps.clear()


def register():
    bpy.utils.register_class(OBJECT_OT_weight_mask_mesh_from_bone)
    bpy.types.VIEW3D_MT_paint_weight.append(menu_func)

    bpy.utils.register_class(WEIGHTPAINT_OT_mask_grow)
    bpy.utils.register_class(WEIGHTPAINT_OT_mask_shrink)
    
    add_hotkeys()


def unregister():
    remove_hotkeys()

    bpy.utils.unregister_class(WEIGHTPAINT_OT_mask_shrink)
    bpy.utils.unregister_class(WEIGHTPAINT_OT_mask_grow)

    bpy.types.VIEW3D_MT_paint_weight.remove(menu_func)
    bpy.utils.unregister_class(OBJECT_OT_weight_mask_mesh_from_bone)


if __name__ == "__main__":
    register()
