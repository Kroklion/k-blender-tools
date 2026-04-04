import bpy
import bmesh
from mathutils.kdtree import KDTree

bl_info = {
    "name": "Mesh Selection Utilities",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Edit Mode (Mesh) > Merge Menu\n"
        " - Merge by Distance Preview"
    ),
    "description": (
        "Adds mesh selection tools in Edit Mode:\n"
        "• Merge by Distance Preview – highlight verts within merge threshold\n"
    ),
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}

class MESH_OT_merge_by_distance_preview(bpy.types.Operator):
    bl_idname = "mesh.merge_by_distance_preview"
    bl_label = "Preview Merge by Distance"
    bl_description = "Select only vertices within threshold that would be merged"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: bpy.props.FloatProperty(
        name="Distance",
        default=0.001,
        min=0.0,
        precision=4,
        description="Max distance for merging"
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.edit_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)

        # ensure the verts list uses stable indices
        bm.verts.ensure_lookup_table()

        # Build KD-Tree of all verts
        size = len(bm.verts)
        kd = KDTree(size)
        for i, v in enumerate(bm.verts):
            kd.insert(v.co, i)
        kd.balance()

        # Find all verts with neighbors within threshold
        to_select = set()
        for i, v in enumerate(bm.verts):
            hits = kd.find_range(v.co, self.threshold)
            if len(hits) > 1:
                for co, idx, dist in hits:
                    to_select.add(idx)

        # Deselect all, then select only the affected verts
        for v in bm.verts:
            v.select = False
        for idx in to_select:
            bm.verts[idx].select = True

        bmesh.update_edit_mesh(me)
        self.report(
            {'INFO'},
            f"Marked {len(to_select)} vertices within {self.threshold:.6f}"
        )
        return {'FINISHED'}


def merge_menu_func(self, context):
    layout = self.layout
    layout.separator()  # optional: draws a line to group your item
    layout.operator(
        MESH_OT_merge_by_distance_preview.bl_idname,
        text="Merge by Distance Preview",
        icon='AUTOMERGE_ON'
    )
    layout.operator(MESH_OT_edge_merge.bl_idname)


classes = [
    MESH_OT_merge_by_distance_preview,
]


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.VIEW3D_MT_edit_mesh_merge.append(merge_menu_func)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_merge.remove(merge_menu_func)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
