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
        "3D View > Edit Mode (Mesh) > Select\n"
        " - Select UV Island Borders"
    ),
    "description": (
        "Adds mesh selection tools in Edit Mode:\n"
        "• Merge by Distance Preview – highlight verts within merge threshold\n"
        "• Select UV Island Borders – Selects all vertices that enclose the UV islands\n"
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


class MESH_OT_select_uv_island_borders(bpy.types.Operator):
    bl_idname = "mesh.select_uv_island_borders"
    bl_label = "Select UV Island Borders"
    bl_description = "Select vertices that lie on the real borders or holes of UV islands"
    bl_options = {'REGISTER', 'UNDO'}

    add_selection: bpy.props.BoolProperty(
        name="Add Selection",
        description="Additionally select resulting edges, otherwise replace selection",
        default=False
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj is not None and
            obj.type == 'MESH' and
            context.mode == 'EDIT_MESH'
        )

    def execute(self, context):
        obj = context.active_object
        me = obj.data

        bm = bmesh.from_edit_mesh(me)
        uv_layer = bm.loops.layers.uv.active

        if uv_layer is None:
            self.report({'WARNING'}, "Mesh has no UV map")
            return {'CANCELLED'}

        # Clear selection
        if not self.add_selection:
            bpy.ops.mesh.select_all(action='DESELECT')

        border_edges = []

        bm.edges.ensure_lookup_table()

        for e in bm.edges:
            loops = list(e.link_loops)

            # If no loops → edge not part of any face → ignore
            if not loops:
                continue

            ref_vert = loops[0].vert
            ref_uv1 = loops[0][uv_layer].uv
            ref_uv2 = loops[0].link_loop_next[uv_layer].uv

            add_edge = True

            for loop in loops[1:]:
                uv1 = loop[uv_layer].uv
                uv2 = loop.link_loop_next[uv_layer].uv

                if ref_vert.index == loop.vert.index:
                    if ref_uv1 == uv1 and ref_uv2 == uv2:
                        add_edge = False
                        break
                else:  # reversed
                    if ref_uv1 == uv2 and ref_uv2 == uv1:
                        add_edge = False
                        break

            if add_edge:
                border_edges.append(e)

        # Select edges
        for e in border_edges:
            e.select = True
            e.verts[0].select = True
            e.verts[1].select = True

        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)
        return {'FINISHED'}


def select_menu_func(self, context):
    self.layout.operator(MESH_OT_select_uv_island_borders.bl_idname)


def merge_menu_func(self, context):
    layout = self.layout
    layout.separator()  # optional: draws a line to group your item
    layout.operator(
        MESH_OT_merge_by_distance_preview.bl_idname,
        text="Merge by Distance Preview",
        icon='AUTOMERGE_ON'
    )

classes = [
    MESH_OT_merge_by_distance_preview,
    MESH_OT_select_uv_island_borders
]


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.VIEW3D_MT_edit_mesh_merge.append(merge_menu_func)
    bpy.types.VIEW3D_MT_select_edit_mesh.append(select_menu_func)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_merge.remove(merge_menu_func)
    bpy.types.VIEW3D_MT_select_edit_mesh.remove(select_menu_func)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
