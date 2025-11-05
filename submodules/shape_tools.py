import bmesh
import bpy

from .. import log

bl_info = {
    "name": "Reset Active Shape Key to Reference (Selected Verts)",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D View > Edit Mode (Mesh) > Vertex Menu",
    "description": (
        "Resets the active shape key to match its reference (relative key or Basis)\n"
        "for the selected vertices in Edit Mode."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}

class MESH_OT_reset_active_shapekey_to_reference(bpy.types.Operator):
    """
    Reset the active shape key's coordinates to its reference for the selected vertices.

    Reference is:
    - If the shape key system is in Relative mode and the active key has a 'relative_key',
      we copy from active.relative_key for the selected verts.
    - Otherwise, we copy from the first key (Basis).

    """

    bl_idname = "mesh.reset_active_shapekey_to_reference"
    bl_label = "Reset Active Shape Key to Reference (Selected Verts)"
    bl_description = "Reset the active shape key to its reference (relative key or Basis) for selected vertices"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """Keep poll lightweight—no BMesh calls here."""
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        if context.mode != 'EDIT_MESH':
            return False

        me = obj.data
        keys = getattr(me, "shape_keys", None)
        if not keys or not keys.key_blocks:
            return False

        # Allow running whenever a non-Basis key is active
        return obj.active_shape_key_index != 0

    def execute(self, context):
        obj = context.active_object
        me = obj.data

        keys = getattr(me, "shape_keys", None)
        if not keys or not keys.key_blocks:
            self.report({'ERROR'}, "Object has no shape keys.")
            return {'CANCELLED'}

        basis_key = keys.key_blocks[0]
        active_key = obj.active_shape_key

        if active_key == basis_key:
            self.report({'WARNING'}, "Active key is Basis; nothing to reset.")
            return {'CANCELLED'}

        # Determine the correct reference to copy from
        use_relative = bool(getattr(keys, "use_relative", True))
        relative_key = getattr(active_key, "relative_key",
                               None) if use_relative else None
        reference_key = relative_key if relative_key else basis_key

        # !!! The bmesh vertices represent the active shape key !!!
        b_mesh = bmesh.from_edit_mesh(me)

        selected = 0
        applied = 0

        for bmesh_vert in b_mesh.verts:
            if bmesh_vert.select:
                selected += 1
                i = bmesh_vert.index
                src = reference_key.data[i].co
                dst = b_mesh.verts[i].co
                if dst != src:
                    applied += 1
                    b_mesh.verts[i].co = src.copy()

        # Refresh viewport
        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        if selected == 0:
            self.report(
                {'WARNING'}, "No selected vertices. Select some vertices in Edit Mode and try again.")
            return {'CANCELLED'}

        self.report(
            {'INFO'}, f"Reset {applied} vertices on '{active_key.name}' to '{reference_key.name}'.")
        return {'FINISHED'}


# Menu entry in Mesh Edit Mode > Vertices
def menu_func(self, context):
    self.layout.operator(
        MESH_OT_reset_active_shapekey_to_reference.bl_idname,
        icon='LOOP_BACK',
        text="Reset Active Shape Key to Reference (Selected Verts)"
    )


classes = (
    MESH_OT_reset_active_shapekey_to_reference,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

