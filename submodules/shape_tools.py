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
    """Reset the active shape key's coordinates to its reference for the selected vertices.

    Reference is:
    - If the shape key system is in Relative mode and the active key has a 'relative_key',
      we copy from active.relative_key for the selected verts.
    - Otherwise, we copy from the first key (Basis).

    This makes 'reset' behave correctly even when a key is relative to something other than Basis.
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

        # Gather selection from Edit Mode
        bm = bmesh.from_edit_mesh(me)
        selected_indices = [v.index for v in bm.verts if v.select]

        if not selected_indices:
            self.report(
                {'WARNING'}, "No selected vertices. Select some vertices in Edit Mode and try again.")
            return {'CANCELLED'}

        # Sanity checks
        nv = len(me.vertices)
        if not (len(active_key.data) == len(reference_key.data) == nv):
            self.report(
                {'ERROR'}, "Vertex count mismatch between mesh and shape keys.")
            return {'CANCELLED'}

        # Debug header
        log.debug(f"Object: {obj.name}")
        log.debug(f"Mesh verts: {nv}")
        log.debug(f"Active key: {active_key.name}, Index: {obj.active_shape_key_index}")
        log.debug(f"System use_relative: {use_relative}")
        log.debug(f"Reference key: {reference_key.name}, {'(relative to active)' if relative_key else '(Basis)'}")
        log.debug(f"Active value: {getattr(active_key, 'value', None)}, Active muted: {getattr(active_key, 'mute', None)}")
        log.debug(f"Show only active (object): {getattr(obj, 'show_only_shape_key', None)}")
        log.debug(f"Use shape key edit mode (object): {getattr(obj, 'use_shape_key_edit_mode', None)}")
        log.debug(f"Selected verts count: {len(selected_indices)}, sample: {selected_indices[:20]}, {'...' if len(selected_indices) > 20 else ''}")

        # Apply: copy reference coords into the active key for each selected vertex
        # Note: This sets absolute coords, zeroing the delta relative to the reference.
        changed = 0
        sample_diffs = []
        
        mode = context.object.mode
        bpy.ops.object.mode_set(mode='OBJECT')
        
        for i in selected_indices:
            src = reference_key.data[i].co
            dst = active_key.data[i].co
            if len(sample_diffs) < 10:
                # store a tiny sample of coordinates and deltas for inspection
                sample_diffs.append(src.copy())
                sample_diffs.append(dst.copy())
                sample_diffs.append((i, (dst - src).length))
            if dst != src:
                active_key.data[i].co = src.copy()
                changed += 1
                
        bpy.ops.object.mode_set(mode=mode)

        log.debug(f"Changed verts: {changed}/{len(selected_indices)}")
        if sample_diffs:
            # Print first few before/after magnitudes (distance to reference before write)
            log.debug(f"Sample pre-reset deltas (lengths): {sample_diffs}")

        # Refresh viewport
        me.update()
        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        # Extra hints if nothing seemed to change
        if changed == 0:
            log.debug("No coordinate differences found to overwrite; verts might already match the reference.")

        self.report(
            {'INFO'}, f"Reset {len(selected_indices)} vertices on '{active_key.name}' to '{reference_key.name}'.")
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

