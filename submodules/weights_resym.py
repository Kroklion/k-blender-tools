import bpy
import bmesh

from ..lib.toposym import TopoSym, TopoSymType

bl_info = {
    "name": "Vertex Weights Symmetrizer",
    "author": "",
    "version": (2, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View (Weight Paint Mode) > Weights > Topology Weight Resymmetrize \n"
    ),
    "description": (
        "Symmetrizes vertex weights based on mesh topology rather than position.\n"
        "Supports active, selected, or all deform bone groups. Mirrors L/R bones \n"
        "and symmetrizes center bones."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}


AXIS_DECODE = {
    "-X": (0, -1),
    "X":  (0,  1),
    "-Y": (1, -1),
    "Y":  (1,  1),
    "-Z": (2, -1),
    "Z":  (2,  1),
}


def find_mirror_name(name: str):
    pairs = [
        (".L", ".R"),
        (".l", ".r"),
        (".left", ".right"),
        (".Left", ".Right")
    ]
    for a, b in pairs:
        if name.endswith(a):
            return name[:-len(a)], a, b, 1
        elif name.endswith(b):
            return name[:-len(b)], b, a, -1
    return None


class MESH_OT_topo_resymmetrize_weights(bpy.types.Operator):
    bl_idname = "mesh.topo_resymmetrize_weights"
    bl_label = "Topology Weight Resymmetrize"
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

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ('ACTIVE_BONE', "Active Bone", ""),
            ('SELECTED_BONES', "Selected Bones", ""),
            ('ACTIVE_GROUP', "Active Group", ""),
            ('ALL_DEFORM_GROUPS', "All Deform Groups", ""),
        ],
        default='ACTIVE_BONE'
    )
    
    position_based_search: bpy.props.BoolProperty(  # pyright:ignore[reportUninitializedInstanceVariable, reportInvalidTypeForm, reportUnknownMemberType]
        name="Position Based",
        description="If checked, for disconnected mesh pieces a position based search is preformed, requires at lease one face to be symmetrized.",
        default=False
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "axis")
        layout.prop(self, "eps")
        layout.prop(self, "mode")
        layout.prop(self, "position_based_search")

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object must be a mesh")
            return {'CANCELLED'}

        # Find armature from modifier
        arm = None
        for m in obj.modifiers:
            if m.type == 'ARMATURE' and m.object:
                arm = m.object
                break

        if not arm:
            self.report({'ERROR'}, "Mesh must have an Armature modifier")
            return {'CANCELLED'}

        # Determine which vertex groups to process
        vgroups = obj.vertex_groups
        if not vgroups:
            self.report({'ERROR'}, "Mesh has no vertex groups")
            return {'CANCELLED'}
        
        initial_mode = obj.mode
        if initial_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
            
        target_groups = set()

        if self.mode == 'ACTIVE_BONE':
            bone = arm.data.bones.active
            if not bone:
                self.report({'ERROR'}, "No active bone")
                return {'CANCELLED'}
            if bone.name in vgroups:
                target_groups.add(bone.name)

        elif self.mode == 'SELECTED_BONES':
            selected = [b.name for b in arm.data.bones if b.select]
            for name in selected:
                if name in vgroups:
                    target_groups.add(name)
            if not target_groups:
                self.report(
                    {'ERROR'}, "No selected bones with matching vertex groups")
                return {'CANCELLED'}

        elif self.mode == 'ACTIVE_GROUP':
            idx = obj.vertex_groups.active_index
            if idx >= 0:
                target_groups.add(vgroups[idx].name)
            else:
                self.report({'ERROR'}, "No active vertex group")
                return {'CANCELLED'}
        elif self.mode == 'ALL_DEFORM_GROUPS':
            for bone in arm.data.bones:
                if bone.use_deform and bone.name in vgroups:
                    target_groups.add(bone.name)

            if not target_groups:
                self.report({'ERROR'}, "No deform bones with matching vertex groups")
                return {'CANCELLED'}

        

        axis, side_sign = AXIS_DECODE[self.axis]

        resolved_groups = []

        # direction: +1 = R→L,  -1 = L→R
        direction = 1 if side_sign > 0 else -1

        for gname in target_groups:
            base = find_mirror_name(gname)

            if base is None:
                # No L/R suffix → treat as center bone
                # Copy weights normally: same group name
                resolved_groups.append((gname, gname))
                continue

            stem, sufA, sufB, name_dir = base

            if direction == name_dir:
                src_name = stem + sufA
                tgt_name = stem + sufB
            else:
                continue

            # If source exists but target does not → skip entirely
            if src_name not in vgroups:
                continue

            # Create target group if missing
            if tgt_name not in vgroups:
                vgroups.new(name=tgt_name)

            resolved_groups.append((src_name, tgt_name))


        bm = bmesh.new()
        bm.from_mesh(obj.data)

        # Build symmetry mapping
        toposym = TopoSym(
            bm,
            axis,
            side_sign,
            self.eps,
            search_unreachable=self.position_based_search
        )

        # Collect mapping: source → target
        mapping: dict[int, int] = toposym.get_symmetry_mapping()
        centers: list[int] = toposym.get_center_verts()
        
        copied = 0


        for src_group, tgt_group in resolved_groups:
            vg_src = vgroups[src_group]
            vg_tgt = vgroups[tgt_group]

            self_mirror = src_group == tgt_group

            for src, tgt in mapping.items():
                copied += self.transfer_weight(vg_src, src, vg_tgt, tgt)

                if not self_mirror:
                    copied += self.transfer_weight(vg_src, tgt, vg_tgt, src)

                    for center_index in centers:
                        copied += self.transfer_weight(
                            vg_src, center_index,
                            vg_tgt, center_index,
                        )


        # Report summary
        sym_v = toposym.get_count(TopoSymType.VERTEX_SYMMETRIZED)
        targets = toposym.get_count(TopoSymType.VERTEX_TARGET)
        asym_v = toposym.get_count(TopoSymType.VERTEX_ASYMMETRIC)

        msg = f"Weight symmetrized {sym_v} of {targets} vertices, weights copied {copied}"
        if asym_v > 0:
            msg += f", {asym_v} asymmetric vertices"

        self.report({'INFO'}, msg)

        # Restore mode if needed
        if initial_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode=initial_mode)

        return {'FINISHED'}

    def transfer_weight(self, vg_src, src_index: int, vg_tgt, tgt_index: int) -> int:
        """Copy a single vertex weight. Returns 1 if the target changed."""

        try:
            weight = vg_src.weight(src_index)
        except RuntimeError:
            weight = 0.0

        try:
            old = vg_tgt.weight(tgt_index)
        except RuntimeError:
            old = 0.0

        if weight != old:
            vg_tgt.add([tgt_index], weight, 'REPLACE')
            return int(1)
        else:
            return int(0)


def menu_func(self, context):
    self.layout.operator(MESH_OT_topo_resymmetrize_weights.bl_idname)


def register():
    bpy.utils.register_class(MESH_OT_topo_resymmetrize_weights)
    bpy.types.VIEW3D_MT_paint_weight.append(menu_func)


def unregister():
    bpy.utils.unregister_class(MESH_OT_topo_resymmetrize_weights)
    bpy.types.VIEW3D_MT_paint_weight.remove(menu_func)
