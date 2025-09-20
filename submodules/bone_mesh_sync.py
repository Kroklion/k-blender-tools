from mathutils import Matrix
import bmesh
import bpy
bl_info = {
    "name": "Bone ↔ Mesh Sync via Reference Vertices",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Object > Create reference vertices\n"
        "3D View > Object > Update bone positions"
    ),
    "description": (
        "Synchronize bone positions with mesh geometry using reference vertices.\n"
        "Creates reference points at bone heads and tails,\n"
        "allowing bones to follow mesh edits."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Rigging",
}


REF_LAYER_NAME = "bone_ref_name"
REF_LAYER_TYPE = "bone_ref_type"  # b'HEAD' or b'TAIL'


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
        return bm, False


def write_bmesh(mesh_obj, bm, was_editmode):
    me = mesh_obj.data
    if was_editmode:
        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=True)
    else:
        bm.to_mesh(me)
        me.update()
        bm.free()


def clear_existing_refs(bm):
    vlayer_name = bm.verts.layers.string.get(REF_LAYER_NAME)
    vlayer_type = bm.verts.layers.string.get(REF_LAYER_TYPE)
    if not vlayer_name or not vlayer_type:
        return 0
    to_delete = [v for v in bm.verts if v[vlayer_name] and v[vlayer_type]]
    if to_delete:
        bmesh.ops.delete(bm, geom=to_delete, context='VERTS')
    return len(to_delete)


def create_ref_layers(bm):
    vlayer_name = bm.verts.layers.string.get(REF_LAYER_NAME)
    vlayer_type = bm.verts.layers.string.get(REF_LAYER_TYPE)
    if not vlayer_name:
        vlayer_name = bm.verts.layers.string.new(REF_LAYER_NAME)
    if not vlayer_type:
        vlayer_type = bm.verts.layers.string.new(REF_LAYER_TYPE)
    return vlayer_name, vlayer_type


def add_ref_vertex(bm, co_mesh_space, bone_name_bytes, role_bytes, vlayer_name, vlayer_type):
    v = bm.verts.new(co_mesh_space)
    v[vlayer_name] = bone_name_bytes
    v[vlayer_type] = role_bytes
    return v


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
    bl_label = "Create reference vertices"
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
        removed = clear_existing_refs(bm)

        vlayer_name, vlayer_type = create_ref_layers(bm)

        # Create vertices at bone tails and optionally heads
        mw_mesh_inv = mesh_obj.matrix_world.inverted()
        mw_arm = arm_obj.matrix_world

        # Use rest pose positions from Armature data bones
        for bone in arm_obj.data.bones:
            # Tail
            world_tail = mw_arm @ bone.tail_local
            mesh_tail = mw_mesh_inv @ world_tail
            add_ref_vertex(bm, mesh_tail, bone.name.encode(
                'utf-8'), b"TAIL", vlayer_name, vlayer_type)

            # Head if not connected to parent
            if not bone.use_connect:
                world_head = mw_arm @ bone.head_local
                mesh_head = mw_mesh_inv @ world_head
                add_ref_vertex(bm, mesh_head, bone.name.encode(
                    'utf-8'), b"HEAD", vlayer_name, vlayer_type)

        write_bmesh(mesh_obj, bm, was_editmode)

        self.report(
            {'INFO'}, f"Reference vertices created. Removed {removed} old refs.")
        return {'FINISHED'}


class BONE_SYNC_OT_update_bones(bpy.types.Operator):
    bl_idname = "bone_sync.update_bone_positions"
    bl_label = "Update bone positions"
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

        # Read reference vertices from mesh
        bm, was_editmode = ensure_bmesh(mesh_obj, for_write=False)
        vlayer_name = bm.verts.layers.string.get(REF_LAYER_NAME)
        vlayer_type = bm.verts.layers.string.get(REF_LAYER_TYPE)
        if not vlayer_name or not vlayer_type:
            if not was_editmode:
                bm.free()
            self.report(
                {'ERROR'}, "No reference layers found. Run 'Create reference vertices' first.")
            return {'CANCELLED'}

        # Build mapping: { bone_name: {"HEAD": world_co, "TAIL": world_co} }
        refs = {}
        mw_mesh = mesh_obj.matrix_world
        for v in bm.verts:
            name_b = v[vlayer_name]
            type_b = v[vlayer_type]
            if not name_b or not type_b:
                continue
            bone_name = name_b.decode('utf-8', errors='ignore')
            role = type_b.decode('utf-8', errors='ignore')
            world_co = mw_mesh @ v.co
            refs.setdefault(bone_name, {})[role] = world_co

        if not was_editmode:
            bm.free()

        if not refs:
            self.report({'ERROR'}, "No reference vertices found on the mesh.")
            return {'CANCELLED'}

        # Switch to Armature Edit Mode and apply positions
        prev_active = context.view_layer.objects.active
        prev_mode = get_mode(prev_active)
        # Ensure armature is active
        for obj in context.selected_objects:
            obj.select_set(False)
        set_active(context, arm_obj)

        try:
            switch_mode('EDIT')
            arm_inv = arm_obj.matrix_world.inverted()

            for eb in arm_obj.data.edit_bones:
                data = refs.get(eb.name)
                if not data:
                    continue
                if "HEAD" in data:
                    eb.head = arm_inv @ data["HEAD"]
                if "TAIL" in data:
                    eb.tail = arm_inv @ data["TAIL"]

        finally:
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

