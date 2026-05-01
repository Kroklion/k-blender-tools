from bmesh.types import BMesh
from bpy.types import Object
import bmesh
import bpy

bl_info = {
    "name": "Bone ↔ Mesh Sync via Reference Vertices",
    "author": "",
    "version": (2, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Object > Create Reference Vertices\n"
        "3D View > Object > Update Bone Positions"
    ),
    "description": (
        "Synchronize bone positions with mesh geometry using reference vertices.\n"
        "Creates reference points at bone heads and tails,\n"
        "allowing bones to follow mesh edits.\n"
        "Multiple bones sharing the same location use a single vertex."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Rigging",
}


# Single layer that stores multiple bone references per vertex.
# Format (UTF-8 string stored as bytes):
#   "Bone.001:HEAD|Bone.002:TAIL|Bone.003:HEAD"
REF_LAYER_DATA = "bone_ref_data"

# Epsilon for spatial hashing (location identity)
LOCATION_EPSILON = 1e-6


def get_active_mesh_object(context):
    obj = context.active_object
    if not obj or obj.type != 'MESH':
        return None
    return obj


def get_armature_from_mesh(mesh_obj):
    # Find first Armature modifier with a valid object
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE' and getattr(mod, "object", None) and mod.object.type == 'ARMATURE':
            return mod.object
    return None


def get_selected_armature(context):
    for obj in context.selected_objects:
        if obj.type == 'ARMATURE':
            return obj
    return None


def ensure_bmesh(mesh_obj, for_write=True):
    me = mesh_obj.data
    if mesh_obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(me)
        if for_write:
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
        return bm, True
    else:
        bm = bmesh.new()
        bm.from_mesh(me)
        if for_write:
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
        return bm, False


def write_bmesh(mesh_obj, bm, was_editmode):
    if was_editmode:
        bmesh.update_edit_mesh(
            mesh_obj.data, loop_triangles=False, destructive=True)
    else:
        bm.to_mesh(mesh_obj.data)
        mesh_obj.data.update()


def clear_existing_refs(mesh_obj: Object, mesh: BMesh, was_editmode: bool):
    """
    Delete all vertices that carry reference data.
    """
    vlayer_data = mesh.verts.layers.string.get(REF_LAYER_DATA)

    deleted = 0
    if vlayer_data:
        to_delete = [v for v in mesh.verts if v[vlayer_data]]
        deleted = len(to_delete)
        if to_delete:
            bmesh.ops.delete(mesh, geom=to_delete, context='VERTS')
    write_bmesh(mesh_obj, mesh, was_editmode)
    return deleted


def ensure_ref_layer(bm):
    """
    Ensure the reference data layer exists and return it.
    """
    vlayer_data = bm.verts.layers.string.get(REF_LAYER_DATA)
    if not vlayer_data:
        vlayer_data = bm.verts.layers.string.new(REF_LAYER_DATA)
    return vlayer_data


def spatial_key_from_coord(co, eps=LOCATION_EPSILON):
    """
    Compute a hashable key for a coordinate using quantization.
    This gives us a stable identity for locations within a small epsilon.
    """
    return (
        round(co.x / eps),
        round(co.y / eps),
        round(co.z / eps),
    )


def append_ref_to_vertex(v, bone_name, role, vlayer_data):
    """
    Append a bone reference (bone_name:role) to the vertex's data string.
    Stored as UTF-8 bytes in the string layer.
    """
    existing = v[vlayer_data]
    if existing:
        s = existing.decode('utf-8', errors='ignore')
    else:
        s = ""

    entry = f"{bone_name}:{role}"
    if s:
        s = s + "|" + entry
    else:
        s = entry

    v[vlayer_data] = s.encode('utf-8')


def parse_vertex_refs(v, vlayer_data):
    """
    Parse the vertex's reference data into a list of (bone_name, role) tuples.
    """
    data_b = v[vlayer_data]
    if not data_b:
        return []

    s = data_b.decode('utf-8', errors='ignore')
    if not s:
        return []

    result = []
    for token in s.split("|"):
        if not token:
            continue
        if ":" not in token:
            continue
        bone_name, role = token.split(":", 1)
        bone_name = bone_name.strip()
        role = role.strip()
        if bone_name and role:
            result.append((bone_name, role))
    return result


def get_mode(obj):
    return obj.mode if obj else None


def set_active(context, obj):
    view_layer = context.view_layer
    view_layer.objects.active = obj
    if obj:
        obj.select_set(True)


def switch_mode(mode):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)


class BONE_SYNC_OT_create_refs(bpy.types.Operator):
    bl_idname = "bone_sync.create_reference_vertices"
    bl_label = "Create Reference Vertices"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mesh_obj = get_active_mesh_object(context)
        if not mesh_obj:
            self.report({'ERROR'}, "Select one mesh object.")
            return {'CANCELLED'}

        arm_obj = get_armature_from_mesh(mesh_obj)
        if not arm_obj:
            self.report(
                {'ERROR'}, "No Armature modifier found on the selected mesh.")
            return {'CANCELLED'}

        # Prepare bmesh
        bm, was_editmode = ensure_bmesh(mesh_obj, for_write=True)

        # Remove existing reference vertices
        removed = clear_existing_refs(mesh_obj, bm, was_editmode)

        # Ensure reference data layer
        vlayer_data = ensure_ref_layer(bm)

        # Spatial index: one vertex per unique location
        spatial_index = {}

        mw_mesh_inv = mesh_obj.matrix_world.inverted()
        mw_arm = arm_obj.matrix_world

        # Use rest pose positions from Armature data bones
        for bone in arm_obj.data.bones:
            # Tail
            world_tail = mw_arm @ bone.tail_local
            mesh_tail = mw_mesh_inv @ world_tail
            key_tail = spatial_key_from_coord(mesh_tail)

            v_tail = spatial_index.get(key_tail)
            if v_tail is None:
                v_tail = bm.verts.new(mesh_tail)
                spatial_index[key_tail] = v_tail
            append_ref_to_vertex(v_tail, bone.name, "TAIL", vlayer_data)

            # Head if not connected to parent
            if not bone.use_connect:
                world_head = mw_arm @ bone.head_local
                mesh_head = mw_mesh_inv @ world_head
                key_head = spatial_key_from_coord(mesh_head)

                v_head = spatial_index.get(key_head)
                if v_head is None:
                    v_head = bm.verts.new(mesh_head)
                    spatial_index[key_head] = v_head
                append_ref_to_vertex(v_head, bone.name, "HEAD", vlayer_data)

        write_bmesh(mesh_obj, bm, was_editmode)

        self.report(
            {'INFO'}, f"Reference vertices created. Removed {removed} old refs.")
        return {'FINISHED'}


class BONE_SYNC_OT_update_bones(bpy.types.Operator):
    bl_idname = "bone_sync.update_bone_positions"
    bl_label = "Update Bone Positions"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mesh_obj = get_active_mesh_object(context)
        if not mesh_obj:
            self.report({'ERROR'}, "Select one mesh object.")
            return {'CANCELLED'}

        # Prefer explicitly selected armature if present
        prefer_stripped = False

        arm_obj = get_selected_armature(context)
        if not arm_obj:
            arm_obj = get_armature_from_mesh(mesh_obj)
        else:
            prefer_stripped = True

        if not arm_obj:
            self.report(
                {'ERROR'}, "No Armature modifier found in mesh modifier or selection.")
            return {'CANCELLED'}

        print(f"armature {arm_obj.name}")

        # Read reference vertices from mesh
        bm, was_editmode = ensure_bmesh(mesh_obj, for_write=True)
        vlayer_data = bm.verts.layers.string.get(REF_LAYER_DATA)
        if not vlayer_data:
            if not was_editmode:
                bm.free()
            self.report(
                {'ERROR'}, "No reference layer found. Run 'Create Reference Vertices' first.")
            return {'CANCELLED'}

        # Build mapping: { bone_name: {"HEAD": world_co, "TAIL": world_co} }
        refs = {}
        mw_mesh = mesh_obj.matrix_world

        for v in bm.verts:
            entries = parse_vertex_refs(v, vlayer_data)
            if not entries:
                continue

            world_co = mw_mesh @ v.co
            for bone_name, role in entries:
                bone_dict = refs.setdefault(bone_name, {})
                bone_dict[role] = world_co

        if not refs:
            self.report({'ERROR'}, "No reference vertices found on the mesh.")
            return {'CANCELLED'}

        print(refs)

        # Switch to Armature Edit Mode and apply positions
        prev_active = context.view_layer.objects.active
        prev_mode = get_mode(prev_active)

        # Ensure armature is active
        for obj in context.selected_objects:
            obj.select_set(False)
        set_active(context, arm_obj)

        try:
            switch_mode('EDIT')

            # Disable armature mirror temporarily
            prev_mirror = arm_obj.data.use_mirror_x
            arm_obj.data.use_mirror_x = False

            arm_inv = arm_obj.matrix_world.inverted()

            for eb in arm_obj.data.edit_bones:

                name = eb.name
                if prefer_stripped and not name.startswith("DEF-"):
                    name = 'DEF-' + eb.name

                data = refs.get(name)

                if not data:
                    data = refs.get(eb.name)

                if not data:
                    print(f"Not found: {eb.name}")
                    continue

                if "HEAD" in data:
                    eb.head = arm_inv @ data["HEAD"]
                if "TAIL" in data:
                    eb.tail = arm_inv @ data["TAIL"]

            # fix for visual glitch
            for eb in arm_obj.data.edit_bones:
                eb.select = False
                eb.select_head = False
                eb.select_tail = False

            clear_existing_refs(mesh_obj, bm, was_editmode)

        finally:
            # Restore mirror setting
            arm_obj.data.use_mirror_x = prev_mirror

            # Restore previous selection and mode
            for obj in context.scene.objects:
                obj.select_set(False)
            if prev_active:
                set_active(context, prev_active)
            if prev_mode:
                switch_mode(prev_mode)

        self.report(
            {'INFO'}, "Bone positions updated from reference vertices.")
        return {'FINISHED'}


def draw_bone_sync_menu(self, context):
    layout = self.layout
    layout.separator()
    layout.operator(BONE_SYNC_OT_create_refs.bl_idname, icon='MESH_DATA')
    layout.operator(BONE_SYNC_OT_update_bones.bl_idname, icon='ARMATURE_DATA')


classes = (
    BONE_SYNC_OT_create_refs,
    BONE_SYNC_OT_update_bones,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_object.append(draw_bone_sync_menu)


def unregister():
    bpy.types.VIEW3D_MT_object.remove(draw_bone_sync_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
