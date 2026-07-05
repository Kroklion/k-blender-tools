from ..lib.toposym import TopoSym, TopoSymType
from mathutils import Vector
from bpy.props import StringProperty, BoolProperty, FloatProperty
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
        "- Generate mirrored and combined variants from one given shape key\n"
        "Object mode:\n"
        "- Normalize: Change the current shape key value to 1, keep the shape\n"
        "- Zero all shape key values\n"
        "- Bake shape key from viewport state\n"
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


class OBJECT_OT_normalize_active_shapekey_value(Operator):
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


class OBJECT_OT_zero_all_shapekey_values(Operator):
    """
    Set all shape key values of the active mesh object to 0.
    """

    bl_idname = "object.zero_all_shapekey_values"
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


class OBJECT_OT_add_shape_key_from_viewport(Operator):
    """Add a new shape key to all selected mesh objects using the current viewport geometry"""
    bl_idname = "object.add_shape_key_from_viewport"
    bl_label = "Add Shape Key From Viewport"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(
        name="Shape Key Name",
        description="Name for the new shape key (Blender will auto-increment if needed)",
        default="NewShapeKey"
    )

    difference_threshold: FloatProperty(
        name="Difference Threshold",
        description="Minimum distance from Basis to consider a vertex different",
        default=1e-5,
        min=0.0,
        soft_max=0.01
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name", expand=True)
        layout.prop(self, "difference_threshold", expand=True)

    def invoke(self, context, event):
        self.new_key_name = "New Key"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        # Ensure we operate in Object mode
        prev_mode = context.mode
        if prev_mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                self.report({'WARNING'}, "Could not switch to Object mode.")
                return {'CANCELLED'}

        depsgraph = context.evaluated_depsgraph_get()
        selected = [o for o in context.selected_objects if o.type == 'MESH']

        if not selected:
            self.report({'WARNING'}, "No mesh objects selected.")
            return {'CANCELLED'}

        created = []
        skipped = []
        errors = []

        # Optionally derive base name from active object's active shape key
        base_name = self.name

        for obj in selected:
            try:
                # Evaluate object with modifiers applied
                eval_obj = obj.evaluated_get(depsgraph)

                # Create a temporary mesh from the evaluated object
                # API: to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
                try:
                    temp_mesh = eval_obj.to_mesh(
                        preserve_all_data_layers=True, depsgraph=depsgraph)
                except TypeError:
                    # Fallback for older API signatures
                    temp_mesh = eval_obj.to_mesh()

                if temp_mesh is None:
                    errors.append(
                        (obj.name, "Failed to obtain evaluated mesh."))
                    continue

                # Ensure the object has a mesh with same vertex count
                src_vcount = len(temp_mesh.vertices)
                dst_vcount = len(obj.data.vertices)

                if src_vcount != dst_vcount:
                    skipped.append(
                        (obj.name, f"vertex count mismatch ({src_vcount} != {dst_vcount})"))
                    # cleanup temp mesh
                    try:
                        if hasattr(eval_obj, "to_mesh_clear"):
                            eval_obj.to_mesh_clear()
                        else:
                            bpy.data.meshes.remove(temp_mesh)
                    except Exception:
                        pass
                    continue

                # Ensure object has shape keys (adds Basis if needed)
                if obj.data.shape_keys is None:
                    # Add a basis key
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.shape_key_add(from_mix=False)

                keys = obj.data.shape_keys

                # Determine new key name (let Blender auto-increment if needed)
                new_name = base_name

                # Add new shape key (must be done in Object mode)
                bpy.context.view_layer.objects.active = obj
                new_key = obj.shape_key_add(name=new_name)

                # Fill the new key's coordinates from the evaluated mesh
                keys = obj.data.shape_keys
                basis = keys.key_blocks[0]  # Basis is always index 0

                kb = keys.key_blocks[new_key.name]
                for i, v in enumerate(temp_mesh.vertices):
                    basis_co = basis.data[i].co
                    delta = v.co - basis_co

                    if delta.length > self.difference_threshold:
                        # Vertex is meaningfully different → store evaluated position
                        kb.data[i].co = v.co
                    else:
                        # Vertex is effectively identical → snap to Basis
                        kb.data[i].co = basis_co

                created.append((obj.name, new_key.name))

                # cleanup temp mesh
                try:
                    if hasattr(eval_obj, "to_mesh_clear"):
                        eval_obj.to_mesh_clear()
                    else:
                        bpy.data.meshes.remove(temp_mesh)
                except Exception:
                    pass

            except Exception as e:
                errors.append((obj.name, str(e)))
                # Attempt to cleanup temp mesh if present
                try:
                    if 'temp_mesh' in locals() and temp_mesh:
                        if hasattr(eval_obj, "to_mesh_clear"):
                            eval_obj.to_mesh_clear()
                        else:
                            bpy.data.meshes.remove(temp_mesh)
                except Exception:
                    pass
                continue

        # Restore previous mode
        try:
            if prev_mode != 'OBJECT':
                bpy.ops.object.mode_set(mode=prev_mode)
        except Exception:
            pass

        # Reporting
        msg_lines = []
        if created:
            msg_lines.append("Created shape keys:")
            for obj_name, key_name in created:
                msg_lines.append(f"  {obj_name}: {key_name}")
        if skipped:
            msg_lines.append("Skipped objects:")
            for obj_name, reason in skipped:
                msg_lines.append(f"  {obj_name}: {reason}")
        if errors:
            msg_lines.append("Errors:")
            for obj_name, err in errors:
                msg_lines.append(f"  {obj_name}: {err}")

        # Compose a short report
        if created:
            self.report(
                {'INFO'}, f"Added shape keys to {len(created)} objects.")
        elif skipped and not errors:
            self.report(
                {'WARNING'}, "No shape keys created; objects skipped due to vertex count mismatch.")
        elif errors and not created:
            self.report(
                {'ERROR'}, "Failed to create shape keys; see console for details.")
        else:
            self.report({'INFO'}, "Operation completed.")

        # Print detailed log to system console / Info area
        for line in msg_lines:
            print(line)

        return {'FINISHED'}


AXIS_DECODE = {
    '-X': (0, -1),
    'X': (0, 1),
    '-Y': (1, -1),
    'Y': (1, 1),
    '-Z': (2, -1),
    'Z': (2, 1),
}


class MESH_OT_shape_key_side_derive(bpy.types.Operator):
    bl_idname = "mesh.topo_shapekey_derive"
    bl_label = "Derive Side Shape Keys"
    bl_options = {'REGISTER', 'UNDO'}

    axis: bpy.props.EnumProperty(
        name="Local Axis",
        items=[
            ('-X', "-X to X", ""),
            ('X', "X to -X", ""),
            ('-Y', "-Y to Y", ""),
            ('Y', "Y to -Y", ""),
            ('-Z', "-Z to Z", ""),
            ('Z', "Z to -Z", ""),
        ],
        default='-X'
    )

    eps: bpy.props.FloatProperty(
        name="Center Epsilon",
        default=1e-5,
        min=0.0
    )

    # Only available in Edit mode
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object must be a mesh")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        # Determine active shape key index (if any)
        keys = obj.data.shape_keys
        if not keys or not keys.use_relative or not keys.key_blocks:
            self.report(
                {'ERROR'}, "Object must have relative shape keys and an active shape key")
            bm.free()
            return {'CANCELLED'}

        active_index = obj.active_shape_key_index
        if active_index < 0:
            self.report({'ERROR'}, "No active shape key selected")
            bm.free()
            return {'CANCELLED'}

        active_key = keys.key_blocks[active_index]
        active_name = active_key.name

        # decode axis and sign
        axis_idx, side_sign = AXIS_DECODE[self.axis]

        # Build TopoSym to get mapping
        # Use key_index = active_index so TopoSym can consider it if needed
        toposym = TopoSym(bm, axis_idx, side_sign, self.eps,
                          active_index, -1, search_unreachable=False)
        mapping = toposym.get_symmetry_mapping()  # dict: source -> target

        # Prepare for shape key edits: must be in Object mode to add/modify shape keys
        bpy.ops.object.mode_set(mode='OBJECT')

        # Re-fetch keys after mode change
        keys = obj.data.shape_keys
        if not keys or not keys.use_relative or not keys.key_blocks:
            self.report({'ERROR'}, "Shape keys unavailable after mode switch")
            return {'CANCELLED'}

        basis = keys.key_blocks[0]
        n_verts = len(obj.data.vertices)

        # Helper to ensure a key exists (create or overwrite)
        def ensure_key(name):
            kb = keys.key_blocks.get(name)
            if kb is None:
                kb = obj.shape_key_add(name=name, from_mix=False)
            return kb

        # Utility: read deltas from a source key relative to basis
        def compute_deltas(key_block):
            deltas = [Vector((0.0, 0.0, 0.0)) for _ in range(n_verts)]
            for i in range(n_verts):
                deltas[i] = key_block.data[i].co - basis.data[i].co
            return deltas

        # Utility: write deltas into a key block (overwrite)
        def write_deltas(key_block, deltas):
            for i in range(n_verts):
                key_block.data[i].co = basis.data[i].co + deltas[i]

        # Determine side of a vertex using basis position
        def vertex_side(i):
            coord = basis.data[i].co[axis_idx] * side_sign
            if coord < -self.eps:
                return 'L'
            elif coord > self.eps:
                return 'R'
            else:
                return 'C'  # center

        # Parse active name suffix
        suffix = None
        base_name = active_name
        for suf in ('.L', '.R', '.RL'):
            if active_name.endswith(suf):
                suffix = suf
                base_name = active_name[:-len(suf)]
                break

        if suffix is None:
            self.report(
                {'ERROR'}, "Active shape key must end with .L, .R or .RL")
            return {'CANCELLED'}

        # Compute deltas of the active key
        active_deltas = compute_deltas(active_key)

        # Prepare zero deltas
        zero_deltas = [Vector((0.0, 0.0, 0.0)) for _ in range(n_verts)]

        # Helper to mirror a delta across the chosen axis
        def mirror_delta(delta: Vector):
            m = delta.copy()
            m[axis_idx] *= -1.0
            return m

        # Build arrays for L, R, RL results
        L_deltas = [Vector((0.0, 0.0, 0.0)) for _ in range(n_verts)]
        R_deltas = [Vector((0.0, 0.0, 0.0)) for _ in range(n_verts)]
        RL_deltas = [Vector((0.0, 0.0, 0.0)) for _ in range(n_verts)]

        # Case: active is .L -> create/overwrite .R and .RL
        if suffix == '.L':
            # Fill L_deltas directly from active (source indices)
            for s in range(n_verts):
                L_deltas[s] = active_deltas[s]

            # Mirror L into R using mapping
            for s, t in mapping.items():
                # s is source, t is target
                mirrored = mirror_delta(L_deltas[s])
                R_deltas[t] = mirrored

            # RL is sum of both sides (L + R)
            for i in range(n_verts):
                RL_deltas[i] = L_deltas[i] + R_deltas[i]

            # Ensure keys and write
            key_R = ensure_key(f"{base_name}.R")
            key_R.data.foreach_set("co", [c for v in [
                                   basis.data[i].co + R_deltas[i] for i in range(n_verts)] for c in v])
            key_R = keys.key_blocks[f"{base_name}.R"]  # re-fetch

            key_RL = ensure_key(f"{base_name}.RL")
            key_RL.data.foreach_set("co", [c for v in [
                                    basis.data[i].co + RL_deltas[i] for i in range(n_verts)] for c in v])
            key_RL = keys.key_blocks[f"{base_name}.RL"]

            # Also ensure .L exists and matches active (overwrite)
            key_L = ensure_key(f"{base_name}.L")
            key_L.data.foreach_set("co", [c for v in [
                                   basis.data[i].co + L_deltas[i] for i in range(n_verts)] for c in v])

        # Case: active is .R -> create/overwrite .L and .RL
        elif suffix == '.R':
            # Fill R_deltas directly from active
            for s in range(n_verts):
                R_deltas[s] = active_deltas[s]

            # Mirror R into L using mapping (reverse mapping: find source that maps to t)
            # mapping is source->target, so for each source s mapping[s]=t, mirrored R at s goes to L at t
            for s, t in mapping.items():
                mirrored = mirror_delta(R_deltas[s])
                L_deltas[t] = mirrored

            # RL is sum
            for i in range(n_verts):
                RL_deltas[i] = L_deltas[i] + R_deltas[i]

            # Write keys
            key_L = ensure_key(f"{base_name}.L")
            key_L.data.foreach_set("co", [c for v in [
                                   basis.data[i].co + L_deltas[i] for i in range(n_verts)] for c in v])
            key_L = keys.key_blocks[f"{base_name}.L"]

            key_RL = ensure_key(f"{base_name}.RL")
            key_RL.data.foreach_set("co", [c for v in [
                                    basis.data[i].co + RL_deltas[i] for i in range(n_verts)] for c in v])
            key_RL = keys.key_blocks[f"{base_name}.RL"]

            key_R = ensure_key(f"{base_name}.R")
            key_R.data.foreach_set("co", [c for v in [
                                   basis.data[i].co + R_deltas[i] for i in range(n_verts)] for c in v])

        # Case: active is .RL -> split into .L and .R (other side reset to reference)
        else:  # suffix == '.RL'
            # For RL active, we want to assign each side its side-only deltas.
            # For each vertex i:
            #  - if vertex is left: L gets RL_delta at i; R gets mirrored RL_delta at mapped counterpart
            #  - if vertex is right: R gets RL_delta at i; L gets mirrored RL_delta at mapped counterpart
            #  - center vertices: both reset to zero
            for i in range(n_verts):
                rl_delta = active_deltas[i]
                side = vertex_side(i)
                if side == 'L':
                    L_deltas[i] = rl_delta
                    # map to counterpart
                    t = mapping.get(i)
                    if t is not None:
                        R_deltas[t] = mirror_delta(rl_delta)
                elif side == 'R':
                    R_deltas[i] = rl_delta
                    t = mapping.get(i)
                    if t is not None:
                        L_deltas[t] = mirror_delta(rl_delta)
                else:  # center
                    L_deltas[i] = Vector((0.0, 0.0, 0.0))
                    R_deltas[i] = Vector((0.0, 0.0, 0.0))

            # Write L and R keys
            key_L = ensure_key(f"{base_name}.L")
            key_L.data.foreach_set("co", [c for v in [
                                   basis.data[i].co + L_deltas[i] for i in range(n_verts)] for c in v])
            key_R = ensure_key(f"{base_name}.R")
            key_R.data.foreach_set("co", [c for v in [
                                   basis.data[i].co + R_deltas[i] for i in range(n_verts)] for c in v])

            # Optionally ensure RL remains as active (overwrite with original)
            key_RL = keys.key_blocks.get(f"{base_name}.RL")
            if key_RL is None:
                key_RL = ensure_key(f"{base_name}.RL")
            key_RL.data.foreach_set("co", [c for v in [
                                    basis.data[i].co + active_deltas[i] for i in range(n_verts)] for c in v])

        # Force updates
        obj.data.update()
        obj.update_tag()
        bpy.context.view_layer.update()

        self.report({'INFO'}, "Derived shape keys updated")
        return {'FINISHED'}


# Add entries to the Shape Key Specials menu
def shapekey_specials_menu(self, context):
    self.layout.separator()
    self.layout.operator(
        OBJECT_OT_zero_all_shapekey_values.bl_idname, icon='X')
    self.layout.operator(
        OBJECT_OT_normalize_active_shapekey_value.bl_idname, icon='NORMALIZE_FCURVES')
    self.layout.operator(
        OBJECT_OT_add_shape_key_from_viewport.bl_idname,
        icon='OUTLINER_OB_MESH'
    )
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
        MESH_OT_transfer_selected_to_basis_propagate.bl_idname,
        icon='MOD_ARRAY')
    self.layout.operator(
        MESH_OT_transfer_selected_shapekey.bl_idname,
        icon='COPYDOWN'
    )
    self.layout.operator(
        MESH_OT_shape_key_side_derive.bl_idname,
        icon='SHAPEKEY_DATA'
    )


classes = (
    MESH_OT_reset_active_shapekey_to_reference,
    MESH_OT_reduce_selection_to_shapekey_differences,
    MESH_OT_select_shapekey_differences,
    MESH_OT_transfer_selected_shapekey,
    MESH_OT_transfer_selected_to_basis_propagate,
    OBJECT_OT_normalize_active_shapekey_value,
    OBJECT_OT_zero_all_shapekey_values,
    OBJECT_OT_add_shape_key_from_viewport,
    MESH_OT_shape_key_side_derive
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.MESH_MT_shape_key_context_menu.append(shapekey_specials_menu)


def unregister():
    bpy.types.MESH_MT_shape_key_context_menu.remove(shapekey_specials_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

