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
    bl_label = "Reset Selection to Reference"
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
        return obj.active_shape_key_index != 0 and keys.use_relative

    def execute(self, context):
        obj = context.active_object
        me = obj.data

        keys = getattr(me, "shape_keys", None)
        if not keys or not keys.key_blocks:
            self.report({'ERROR'}, "Object has no shape keys.")
            return {'CANCELLED'}

        if not keys.use_relative:
            self.report(
                {'ERROR'}, "Absolute shape keys are not supported by this operator.")
            return {'CANCELLED'}

        basis_key = keys.key_blocks[0]
        active_key = obj.active_shape_key

        if active_key == basis_key:
            self.report({'WARNING'}, "Active key is Basis; nothing to reset.")
            return {'CANCELLED'}

        # Determine the correct reference to copy from
        relative_key = getattr(active_key, "relative_key", None)
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
    bl_label = "Select Differences to Reference"
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
        return obj.active_shape_key_index != 0 and keys.use_relative

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

        if not keys.use_relative:
            self.report(
                {'ERROR'}, "Absolute shape keys are not supported by this operator.")
            return {'CANCELLED'}

        basis_key = keys.key_blocks[0]
        active_key = obj.active_shape_key

        if active_key == basis_key:
            self.report(
                {'WARNING'}, "Active key is Basis; nothing to compare.")
            return {'CANCELLED'}

        # Determine reference key
        relative_key = getattr(active_key, "relative_key", None)
        reference_key = relative_key if relative_key else basis_key

        b_mesh = bmesh.from_edit_mesh(me)

        changed_count = 0
        if not reduce:
            # Fast deselect all
            bpy.ops.mesh.select_all(action='DESELECT')
            for v in b_mesh.verts:
                src = reference_key.data[v.index].co
                dst = v.co
                if dst != src and not v.hide:
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
    bl_label = "Reduce Selection to Differences"
    bl_description = "Refine the current selection by deselecting vertices that are not affected by the Shape Key."

    def execute(self, context):
        return self._select_differences(context, reduce=True)


class MESH_OT_transfer_selected_to_basis(bpy.types.Operator):
    """
    Transfer selected vertices from the active shape key into the Basis.
    """

    bl_idname = "mesh.transfer_selected_to_basis"
    bl_label = "Selected Verts to Basis"
    bl_description = "Copy selected vertices from the active shape key into the Basis shape key"
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

        return bool(keys and keys.key_blocks and obj.active_shape_key_index != 0 and keys.use_relative)

    def execute(self, context):
        obj = context.active_object
        me = obj.data
        keys = me.shape_keys

        if not keys or not keys.key_blocks:
            self.report({'ERROR'}, "Object has no shape keys.")
            return {'CANCELLED'}

        if not keys.use_relative:
            self.report(
                {'ERROR'}, "Absolute shape keys are not supported by this operator.")
            return {'CANCELLED'}

        basis_key = keys.key_blocks[0]
        active_key = obj.active_shape_key

        if active_key == basis_key:
            self.report(
                {'WARNING'}, "Active key is Basis; nothing to transfer.")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(me)

        # Get bmesh layers for Basis and Active by index
        basis_layer = bm.verts.layers.shape[0]
        active_layer = bm.verts.layers.shape[obj.active_shape_key_index]

        selected = 0
        transferred = 0

        for v in bm.verts:
            if v.select:
                selected += 1
                src = v[active_layer]
                dst = v[basis_layer]
                if dst != src:
                    v[basis_layer] = src.copy()
                    transferred += 1

        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        if selected == 0:
            self.report(
                {'WARNING'}, "No selected vertices. Select some vertices in Edit Mode and try again.")
            return {'CANCELLED'}

        self.report(
            {'INFO'}, f"Transferred {transferred} vertices from '{active_key.name}' into Basis.")
        return {'FINISHED'}


class MESH_OT_copy_selected_to_new_shapekey(bpy.types.Operator):
    """Copy selected verts from active shape key into a new shape key"""
    bl_idname = "mesh.copy_selected_to_new_shapekey"
    bl_label = "Copy Selected to New Shape Key"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        if context.mode != 'EDIT_MESH':
            return False
        keys = getattr(obj.data, "shape_keys", None)
        return bool(keys and keys.key_blocks and obj.active_shape_key_index != 0)

    def execute(self, context):
        return self._execute(context)

    def _execute(self, context, do_copy=True):
        obj = context.active_object
        me = obj.data
        keys = me.shape_keys

        # Guard against absolute shape keys
        if not keys.use_relative:
            self.report({'ERROR'}, "Absolute shape keys are not supported.")
            return {'CANCELLED'}

        # Remember old active key and its relative
        src_key = obj.active_shape_key
        src_name = src_key.name
        rel_name = src_key.relative_key.name if src_key.relative_key else keys.key_blocks[
            0].name

        # Switch to Object Mode
        bpy.ops.object.mode_set(mode='OBJECT')

        # Create new key (Blender auto-increments name if needed)
        new_key = obj.shape_key_add(name=src_name)

        # Make the new key active
        obj.active_shape_key_index = keys.key_blocks.find(new_key.name)

        # Switch back to Edit Mode
        bpy.ops.object.mode_set(mode='EDIT')

        # Refresh bmesh
        bm = bmesh.from_edit_mesh(me)

        # Resolve layers by name
        src_index = keys.key_blocks.find(src_name)
        rel_index = keys.key_blocks.find(rel_name)

        src_layer = bm.verts.layers.shape[src_index]
        rel_layer = bm.verts.layers.shape[rel_index]

        copied = 0
        for v in bm.verts:
            if v.select:
                v.co = v[src_layer]
                copied += 1
                if not do_copy:
                    v[src_layer] = v[rel_layer]
            else:
                v.co = v[rel_layer]

        if copied == 0:
            # Switch to Object Mode to safely remove
            bpy.ops.object.mode_set(mode='OBJECT')

            # Remove it
            bpy.ops.object.shape_key_remove(all=False)
            bpy.ops.object.mode_set(mode='EDIT')

            self.report(
                {'WARNING'}, "No selected vertices. Select some vertices in Edit Mode and try again.")
            return {'CANCELLED'}

        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        if do_copy:
            self.report(
                {'INFO'},
                f"Copied {copied} selected vertices into new shape key '{new_key.name}'."
            )
        else:
            self.report(
                {'INFO'},
                f"Split {copied} selected vertices into new shape key '{new_key.name}'."
            )
        return {'FINISHED'}


class MESH_OT_move_selected_to_new_shapekey(MESH_OT_copy_selected_to_new_shapekey):
    """Move selected verts from active shape key into a new shape key"""
    bl_idname = "mesh.move_selected_to_new_shapekey"
    bl_label = "Split Selected to New Shape Key"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return self._execute(context, do_copy=False)


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
    self.layout.operator(
        MESH_OT_transfer_selected_to_basis.bl_idname,
        icon='TRIA_DOWN')
    self.layout.operator(
        MESH_OT_copy_selected_to_new_shapekey.bl_idname,
        icon='DUPLICATE')
    self.layout.operator(
        MESH_OT_move_selected_to_new_shapekey.bl_idname,
        icon='SCULPTMODE_HLT')


classes = (
    MESH_OT_reset_active_shapekey_to_reference,
    MESH_OT_reduce_selection_to_shapekey_differences,
    MESH_OT_select_shapekey_differences,
    MESH_OT_transfer_selected_to_basis,
    MESH_OT_move_selected_to_new_shapekey,
    MESH_OT_copy_selected_to_new_shapekey,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.MESH_MT_shape_key_context_menu.append(shapekey_specials_menu)


def unregister():
    bpy.types.MESH_MT_shape_key_context_menu.remove(shapekey_specials_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

