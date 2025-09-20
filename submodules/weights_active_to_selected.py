import bpy
import bmesh

bl_info = {
    "name": "Copy Active Vertex Weights to Selected",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Edit Mode (Mesh) > Vertex Menu\n"
        "Operator: Copy Active Vertex Weights"
    ),
    "description": (
        "Copies deform vertex group weights from the active vertex\n"
        "to all other selected vertices in Edit Mode. Useful for\n"
        "weight painting and rigging workflows."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}


class MESH_OT_copy_active_vert_weights(bpy.types.Operator):
    """Copy deform vertex group weights from active vertex to selected vertices"""
    bl_idname = "mesh.copy_active_vert_weights"
    bl_label = "Copy Active Vertex Weights"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (
            obj
            and obj.type == 'MESH'
            and context.mode == 'EDIT_MESH'
            and any(mod.type == 'ARMATURE' for mod in obj.modifiers)
        )

    def execute(self, context):
        obj = context.object
        # gather all bone names from armature modifiers
        bone_names = set()
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object and mod.object.type == 'ARMATURE':
                bone_names.update(b.name for b in mod.object.data.bones)
        if not bone_names:
            self.report({'WARNING'}, "No armature modifier with bones found.")
            return {'CANCELLED'}

        # filter to only deform v-groups matching those bones
        deform_vgs = [vg for vg in obj.vertex_groups if vg.name in bone_names]
        if not deform_vgs:
            self.report(
                {'WARNING'}, "No vertex groups match bones in the Armature.")
            return {'CANCELLED'}

        # read active + selected verts in BMesh
        bm = bmesh.from_edit_mesh(obj.data)
        active_vert = None
        for elem in reversed(bm.select_history):
            if isinstance(elem, bmesh.types.BMVert):
                active_vert = elem
                break
        if not active_vert:
            self.report(
                {'WARNING'}, "No active vertex found. Select one and try again.")
            return {'CANCELLED'}

        active_idx = active_vert.index
        selected_idxs = [
            v.index for v in bm.verts if v.select and v.index != active_idx]

        # record the active vertex's weights (vg.index → weight)
        active_weights = {}
        for vg in deform_vgs:
            try:
                w = vg.weight(active_idx)
            except RuntimeError:
                continue
            active_weights[vg.index] = w

        # flush BMesh changes (none here) and exit to Object Mode
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode='OBJECT')

        # now—outside Edit Mode—apply removal & addition
        changed = 0
        for vid in selected_idxs:
            # remove any deform-group on this vert that the active vert didn't have
            for vg in deform_vgs:
                if vg.index not in active_weights:
                    try:
                        vg.remove([vid])
                    except RuntimeError:
                        pass
            # assign each weight from active
            for vg_index, w in active_weights.items():
                obj.vertex_groups[vg_index].add([vid], w, 'REPLACE')
            changed += 1

        # return into Edit Mode
        bpy.ops.object.mode_set(mode='EDIT')
        self.report(
            {'INFO'}, f"Copied weights from vert {active_idx} → {changed} verts.")
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(
        MESH_OT_copy_active_vert_weights.bl_idname)


def register():
    bpy.utils.register_class(MESH_OT_copy_active_vert_weights)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(menu_func)
    bpy.utils.unregister_class(MESH_OT_copy_active_vert_weights)

