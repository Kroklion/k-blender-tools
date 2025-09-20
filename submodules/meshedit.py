import bmesh
import bpy
from mathutils.kdtree import KDTree

bl_info = {
    "name": "Mesh Edit Utilities",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Edit Mode (Mesh) > Vertex Menu\n"
        " - Zero X Selected Vertices\n"
        " - Center Selected X in Edit Mode\n"
        "3D View > Edit Mode (Mesh) > Merge Menu\n"
        " - Merge by Distance Preview"
    ),
    "description": (
        "Adds mesh editing tools in Edit Mode:\n"
        "• Zero X Selected Vertices – set X coordinate of selected verts to 0\n"
        "• Center Selected X – center selection along local X axis\n"
        "• Merge by Distance Preview – highlight verts within merge threshold"
    ),
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}


class MESH_OT_zero_x_selected(bpy.types.Operator):
    bl_idname = "mesh.zero_x_selected"
    bl_label = "Zero X Selected Vertices"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.edit_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        count = 0

        for v in bm.verts:
            if v.select:
                v.co.x = 0.0
                count += 1

        bmesh.update_edit_mesh(me, destructive=False)
        self.report({'INFO'}, f"Zeroed X on {count} verts")
        return {'FINISHED'}
    

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


class MESH_OT_center_selected_x_edit(bpy.types.Operator):
    bl_idname = "mesh.center_selected_x_edit"
    bl_label = "Center Selected X in Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj is not None
            and obj.type == 'MESH'
            and context.mode == 'EDIT_MESH'
        )

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data

        # Build a BMesh representation to read selection
        bm = bmesh.from_edit_mesh(mesh)

        # Collect only the verts that are currently selected
        sel_verts = [v for v in bm.verts if v.select]
        if not sel_verts:
            self.report({'WARNING'}, "No vertices selected")
            return {'CANCELLED'}

        # Compute average X of selected verts in local space
        avg_x = sum(v.co.x for v in sel_verts) / len(sel_verts)
        dx = -avg_x

        # Ensure the mesh is up-to-date before running ops
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)

        # Select all verts so that transform affects the entire mesh
        bpy.ops.mesh.select_all(action='SELECT')

        # Translate in Edit Mode along local X by dx
        bpy.ops.transform.translate(
            value=(dx, 0.0, 0.0),
            orient_type='LOCAL',
            constraint_axis=(True, False, False),
        )
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(MESH_OT_zero_x_selected.bl_idname)
    self.layout.operator(MESH_OT_center_selected_x_edit.bl_idname)
    

def merge_menu_func(self, context):
    layout = self.layout
    layout.separator()  # optional: draws a line to group your item
    layout.operator(
        MESH_OT_merge_by_distance_preview.bl_idname,
        text="Merge by Distance Preview",
        icon='AUTOMERGE_ON'
    )


def register():
    bpy.utils.register_class(MESH_OT_zero_x_selected)
    bpy.utils.register_class(MESH_OT_merge_by_distance_preview)
    bpy.utils.register_class(MESH_OT_center_selected_x_edit)
    
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(menu_func)
    bpy.types.VIEW3D_MT_edit_mesh_merge.append(merge_menu_func)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(menu_func)
    bpy.types.VIEW3D_MT_edit_mesh_merge.remove(merge_menu_func)
    
    bpy.utils.unregister_class(MESH_OT_center_selected_x_edit)
    bpy.utils.unregister_class(MESH_OT_merge_by_distance_preview)
    bpy.utils.unregister_class(MESH_OT_zero_x_selected)


if __name__ == "__main__":
    register()
