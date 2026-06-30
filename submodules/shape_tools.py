from bpy.props import EnumProperty, StringProperty
import bmesh
import bpy
from bpy.types import Operator

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
        "- Reduce current selection to only vertices that differ from the reference.\n"
        "- Transfer selected vertices from the active shape key into the Basis, and update all other shape keys.\n"
        "- Copy/Move selected vertices from the active shape key into specific/all/new shape key(s).\n"
        "Object mode:\n"
        "- Normalize: Change the current shape key value to 1, keep the shape\n"
    ),
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}


class MESH_OT_reset_active_shapekey_to_reference(Operator):
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


class MESH_OT_select_shapekey_differences(Operator):
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


class MESH_OT_transfer_selected_to_basis_propagate(Operator):
    """
    Transfer selected vertices from the active shape key into the Basis,
    and apply the resulting delta to all other shape keys.
    """

    bl_idname = "mesh.transfer_selected_to_basis_propagate"
    bl_label = "Selected Verts to Basis (Propagate)"
    bl_description = (
        "Copy selected vertices from the active shape key into the Basis, "
        "and adapt all other shape keys."
    )
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

        basis_key = keys.key_blocks[0]
        active_key = obj.active_shape_key
        active_index = obj.active_shape_key_index

        if active_key == basis_key:
            self.report(
                {'WARNING'}, "Active key is Basis; nothing to transfer.")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(me)

        # BMesh shape layers
        basis_layer = bm.verts.layers.shape[0]
        active_layer = bm.verts.layers.shape[active_index]

        # Collect all other shape layers
        other_layers = [
            bm.verts.layers.shape[i]
            for i in range(len(bm.verts.layers.shape))
            if i not in (0, active_index)
        ]

        selected = 0
        transferred = 0

        for v in bm.verts:
            if not v.select:
                continue

            selected += 1

            old_basis = v[basis_layer]
            new_basis = v[active_layer]

            if old_basis == new_basis:
                continue

            # Compute delta
            delta = new_basis - old_basis

            # Apply to Basis
            v[basis_layer] = new_basis.copy()
            transferred += 1

            # Apply delta to all other shape keys
            for layer in other_layers:
                v[layer] = v[layer] + delta

        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        if selected == 0:
            self.report({'WARNING'}, "No selected vertices.")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Transferred {transferred} vertices to Basis and propagated delta to other shape keys."
        )
        return {'FINISHED'}


# Blender bug
workaround_keep_references = []


def shape_key_items(self, context):
    obj = context.active_object
    if not obj or obj.type != 'MESH':
        return []
    me = obj.data
    keys = getattr(me, "shape_keys", None)
    if not keys or not keys.key_blocks:
        return []

    active_index = obj.active_shape_key_index

    items = []
    workaround_keep_references.clear()

    for i, kb in enumerate(keys.key_blocks):
        if i == active_index:
            continue  # exclude currently active shape key
        entry = (kb.name, kb.name, '')
        workaround_keep_references.append(entry)
        items.append(entry)

    return items


class MESH_OT_transfer_selected_shapekey(Operator):
    """
    Copy selected vertices from the active shape key into another.
    """

    bl_idname = "mesh.transfer_selected_shapekey"
    bl_label = "Transfer Selected Vertices..."
    bl_description = "Copy/Move selected vertices from the active shape key into a chosen shape key"
    bl_options = {'REGISTER', 'UNDO'}

    target_key: EnumProperty(
        name="Existing",
        description="Choose the shape key to copy into",
        items=shape_key_items
    )

    copy_mode: EnumProperty(
        name="Copy Mode",
        description="Choose how to copy selected vertices",
        items=[
            ('TARGET', "Existing", "Copy to a chosen existing shape key"),
            ('ALL', "All", "Copy to all other shape keys"),
            ('NEW', "New", "Copy to a new shape key"),
        ],
        default='TARGET'
    )

    copy_behavior: EnumProperty(
        name="Behavior",
        description="Copy or move selected vertices",
        items=[
            ('COPY', "Copy", "Copy vertices into target key"),
            ('MOVE', "Move", "Copy and then reset vertices in the source key"),
        ],
        default='COPY'
    )

    new_key_name: StringProperty(
        name="Name",
        description="Name for the new shape key",
        default=""
    )


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

        # Must be relative mode
        if not keys.use_relative:
            return False
        return True

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "copy_mode", expand=True)

        if self.copy_mode == 'TARGET':
            layout.prop(self, "target_key")

        elif self.copy_mode == 'NEW':
            # Prepopulate if empty
            if not self.new_key_name:
                self.new_key_name = context.active_object.active_shape_key.name
            layout.prop(self, "new_key_name")

        layout.prop(self, "copy_behavior", expand=True)


    def invoke(self, context, event):
        self.new_key_name = context.active_object.active_shape_key.name
        return context.window_manager.invoke_props_dialog(self, width=300)


    def execute(self, context):
        obj = context.active_object
        me = obj.data
        keys = me.shape_keys
        bm = None

        original_src_name = obj.active_shape_key.name

        if self.copy_mode == 'NEW':
            result = self.copy_to_new_key(context)
            if result == {'FINISHED'}:
                bm = bmesh.from_edit_mesh(me)

        elif self.copy_mode == 'ALL':
            bm = bmesh.from_edit_mesh(me)
            result = self.copy_to_all_keys(context, bm)

        elif self.copy_mode == 'TARGET':
            bm = bmesh.from_edit_mesh(me)
            result = self.copy_to_existing(context, bm)

        else:
            return {'CANCELLED'}

        if result != {'FINISHED'}:
            return result

        if self.copy_behavior == 'MOVE':
            # Re-fetch because NEW mode may have changed the list
            keys = obj.data.shape_keys
            src_key = keys.key_blocks.get(original_src_name)
            if not src_key:
                self.report(
                    {'ERROR'}, "Original source key not found after operation.")
                return {'CANCELLED'}

            src_index = keys.key_blocks.find(src_key.name)

            # Determine reference key
            ref_key = src_key.relative_key if src_key.relative_key else keys.key_blocks[0]
            ref_index = keys.key_blocks.find(ref_key.name)

            bm = bmesh.from_edit_mesh(me)

            # Layers
            src_layer = bm.verts.layers.shape[src_index]
            ref_layer = bm.verts.layers.shape[ref_index]

            # IMPORTANT RULE:
            # If the source key is the active key → use v.co
            source_is_active = (src_index == obj.active_shape_key_index)
            if source_is_active:
                for v in bm.verts:
                    # Reset active key via v.co
                    if v.select:
                        v.co = v[ref_layer]
            else:
                for v in bm.verts:
                    # Reset non-active key via layer
                    if v.select:
                        v[src_layer] = v[ref_layer].copy()

            bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

            self.report(
                {'INFO'},
                f"Moved vertices: source key '{src_key.name}' reset to '{ref_key.name}'."
            )

        return result

    def copy_to_existing(self, context, bm):
        obj = context.active_object
        me = obj.data
        keys = me.shape_keys

        active_key = obj.active_shape_key
        target_key = keys.key_blocks[self.target_key]


        # Shape layers: find indices for active and target
        try:
            active_index = obj.active_shape_key_index
            key_names = list(keys.key_blocks.keys())
            target_index = key_names.index(self.target_key)
        except Exception:
            self.report({'ERROR'}, "Failed to determine shape key indices.")
            return {'CANCELLED'}

        active_layer = bm.verts.layers.shape[active_index]
        target_layer = bm.verts.layers.shape[target_index]

        selected = 0
        copied = 0

        for v in bm.verts:
            if v.select:
                selected += 1
                src = v[active_layer]
                dst = v[target_layer]
                if dst != src:
                    v[target_layer] = src.copy()
                    copied += 1

        if selected == 0:
            self.report({'WARNING'}, "No selected vertices.")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Copied {copied} vertices from '{active_key.name}' to '{target_key.name}'."
        )
        return {'FINISHED'}

    def copy_to_all_keys(self, context, bm):
        obj = context.active_object
        me = obj.data
        keys = me.shape_keys
        active_index = obj.active_shape_key_index
        active_layer = bm.verts.layers.shape[active_index]

        copied_total = 0

        for i, kb in enumerate(keys.key_blocks):
            if i == active_index:
                continue

            target_layer = bm.verts.layers.shape[i]
            copied = 0

            for v in bm.verts:
                # possible optimization: collect selected first
                if v.select:
                    v[target_layer] = v[active_layer].copy()
                    copied += 1

            copied_total += copied

        self.report(
            {'INFO'}, f"Copied to all other shape keys ({copied_total} vertices total).")
        return {'FINISHED'}

    def copy_to_new_key(self, context):
        obj = context.active_object
        me = obj.data
        keys = me.shape_keys

        src_key = obj.active_shape_key
        src_name = src_key.name
        rel_name = src_key.relative_key.name if src_key.relative_key else keys.key_blocks[
            0].name

        # Switch to Object Mode
        bpy.ops.object.mode_set(mode='OBJECT')

        # Create new key (Blender auto-increments name if needed)
        new_key = obj.shape_key_add(name=self.new_key_name or src_name)

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
            else:
                v.co = v[rel_layer]

        if copied == 0:
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.shape_key_remove(all=False)
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'WARNING'}, "No selected vertices.")
            return {'CANCELLED'}

        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        self.report(
            {'INFO'}, f"Created new shape key '{new_key.name}' with {copied} vertices copied.")
        return {'FINISHED'}


class MESH_OT_normalize_active_shapekey_value(Operator):
    """
    Normalize the active shape key so that its current visual shape becomes the new 1.0.
    The shape remains visually identical, but the key value is set to 1.
    """

    bl_idname = "mesh.normalize_active_shapekey_value"
    bl_label = "Normalize Shape Key Value"
    bl_description = (
        "Change the current shape key value to 1, keep the shape"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        if context.mode != 'OBJECT':
            return False

        keys = getattr(obj.data, "shape_keys", None)
        if not keys or not keys.key_blocks:
            return False

        # Must not be Basis
        return obj.active_shape_key_index != 0 and keys.use_relative

    def execute(self, context):
        obj = context.active_object
        me = obj.data
        keys = me.shape_keys

        active_key = obj.active_shape_key

        # Determine reference key
        reference = active_key.relative_key if active_key.relative_key else keys.key_blocks[0]

        value = active_key.value
        if value == 0:
            self.report({'ERROR'}, "Active key value is 0; cannot normalize.")
            return {'CANCELLED'}

        # Normalize: new_delta = old_delta / value
        for i, kb in enumerate(active_key.data):
            ref = reference.data[i].co
            cur = kb.co

            delta = cur - ref
            new_delta = delta * value

            kb.co = ref + new_delta

        # Set value to 1
        active_key.value = 1.0

        self.report(
            {'INFO'},
            f"Normalized '{active_key.name}' (value set to 1, shape preserved)."
        )
        return {'FINISHED'}


class MESH_OT_zero_all_shapekey_values(Operator):
    """
    Set all shape key values of the active mesh object to 0.
    """

    bl_idname = "mesh.zero_all_shapekey_values"
    bl_label = "Zero All Shape Key Values"
    bl_description = "Set all shape key values of the active object to 0"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        if context.mode != 'OBJECT':
            return False

        keys = getattr(obj.data, "shape_keys", None)
        return bool(keys and keys.key_blocks)

    def execute(self, context):
        obj = context.active_object
        keys = obj.data.shape_keys

        for kb in keys.key_blocks:
            kb.value = 0.0

        self.report({'INFO'}, "All shape key values set to 0.")
        return {'FINISHED'}




# Add entries to the Shape Key Specials menu
def shapekey_specials_menu(self, context):
    self.layout.separator()
    self.layout.operator(
        MESH_OT_zero_all_shapekey_values.bl_idname, icon='X')
    self.layout.operator(
        MESH_OT_normalize_active_shapekey_value.bl_idname, icon='NORMALIZE_FCURVES')
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
        MESH_OT_transfer_selected_to_basis_propagate.bl_idname,
        icon='MOD_ARRAY')
    self.layout.operator(
        MESH_OT_transfer_selected_shapekey.bl_idname,
        icon='COPYDOWN'
    )


classes = (
    MESH_OT_reset_active_shapekey_to_reference,
    MESH_OT_reduce_selection_to_shapekey_differences,
    MESH_OT_select_shapekey_differences,
    MESH_OT_transfer_selected_shapekey,
    MESH_OT_transfer_selected_to_basis_propagate,
    MESH_OT_normalize_active_shapekey_value,
    MESH_OT_zero_all_shapekey_values
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.MESH_MT_shape_key_context_menu.append(shapekey_specials_menu)


def unregister():
    bpy.types.MESH_MT_shape_key_context_menu.remove(shapekey_specials_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

