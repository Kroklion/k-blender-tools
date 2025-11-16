import bmesh
import bpy

from .. import log

bl_info = {
    "name": "Shape Key Tools: Reset & Select Differences",
    "author": "",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "Properties Editor > Object Data Properties (Mesh) > Shape Keys > 'Shape Key Specials' dropdown",
    "description": (
        "Provides tools for working with shape keys in Edit Mode:\n"
        "- Reset the active shape key to match its reference (Basis or relative key) for selected vertices.\n"
        "- Select vertices that differ from the reference.\n"
        "- Reduce current selection to only vertices that differ from the reference."
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
    bl_label = "Reset Active Shape Key selection to Reference"
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


class MESH_OT_select_shapekey_differences(bpy.types.Operator):
    """Select only vertices that differ from the base shape"""

    bl_idname = "mesh.select_shapekey_differences"
    bl_label = "Select Shape Key Differences"
    bl_description = "Select vertices of the active shape key that differ from its reference (Basis or relative key)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
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
        # core logic: deselect all, then select only differing verts
        return self._select_differences(context, reduce=False)

    def _select_differences(self, context, reduce):
        obj = context.active_object
        me = obj.data

        keys = getattr(me, "shape_keys", None)
        if not keys or not keys.key_blocks:
            self.report({'ERROR'}, "Object has no shape keys.")
            return {'CANCELLED'}

        basis_key = keys.key_blocks[0]
        active_key = obj.active_shape_key

        if active_key == basis_key:
            self.report(
                {'WARNING'}, "Active key is Basis; nothing to compare.")
            return {'CANCELLED'}

        # Determine reference key
        use_relative = bool(getattr(keys, "use_relative", True))
        relative_key = getattr(active_key, "relative_key",
                               None) if use_relative else None
        reference_key = relative_key if relative_key else basis_key

        b_mesh = bmesh.from_edit_mesh(me)

        changed_count = 0
        if not reduce:
            # Fast deselect all
            bpy.ops.mesh.select_all(action='DESELECT')
            for v in b_mesh.verts:
                src = reference_key.data[v.index].co
                dst = v.co
                if dst != src:
                    changed_count += 1
                    v.select_set(True)
        else:
            for v in b_mesh.verts:
                src = reference_key.data[v.index].co
                dst = v.co
                if dst == src:
                    v.select_set(False)
                elif v.select:
                    changed_count += 1

        b_mesh.select_flush_mode()
        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        if changed_count == 0:
            self.report({'INFO'}, "No differing vertices found.")
            return {'CANCELLED'}

        self.report(
            {'INFO'}, f"Selected {changed_count} differing vertices on '{active_key.name}'.")
        return {'FINISHED'}

# They are separate because operators called from MESH_MT_shape_key_context_menu
# are not showing the redo/adjust panel where 'reduce' had been planned to be a property.


class MESH_OT_reduce_selection_to_shapekey_differences(MESH_OT_select_shapekey_differences):
    """Reduce current selection to only vertices that differ from base (refine selection)"""
    bl_idname = "mesh.reduce_selection_to_shapekey_differences"
    bl_label = "Reduce Selection to Shape Key Differences"
    bl_description = "Refine the current selection by deselecting vertices that are not affected by the Shape Key."

    def execute(self, context):
        return self._select_differences(context, reduce=True)


# Add entries to the Shape Key Specials menu
def shapekey_specials_menu(self, context):
    self.layout.separator()
    self.layout.operator(
        MESH_OT_reset_active_shapekey_to_reference.bl_idname,
        icon='LOOP_BACK',
    )
    self.layout.operator(
        MESH_OT_select_shapekey_differences.bl_idname,
        icon='SELECT_DIFFERENCE',
    )
    self.layout.operator(
        MESH_OT_reduce_selection_to_shapekey_differences.bl_idname,
        icon='SELECT_SUBTRACT')


classes = (
    MESH_OT_reset_active_shapekey_to_reference,
    MESH_OT_reduce_selection_to_shapekey_differences,
    MESH_OT_select_shapekey_differences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.MESH_MT_shape_key_context_menu.append(shapekey_specials_menu)
    # bpy.types.VIEW3D_MT_edit_mesh.append(menu_func)


def unregister():
    bpy.types.MESH_MT_shape_key_context_menu.remove(shapekey_specials_menu)
    # bpy.types.VIEW3D_MT_edit_mesh.remove(menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

