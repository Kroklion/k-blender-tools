import bpy
import bmesh

# from ..util.timed import timed, timed_reset, timed_print, timed_measure_start, timed_measure_stop
from ..lib.toposym import TopoSym, TopoSymType


bl_info = {
    "name": "Topological Resymmetrizer",
    "author": "",
    "version": (2, 0, 0),
    "blender": (3, 0, 0),
    "location": "Edit Mode; 3D View > Mesh > Topology Resymmetrize",
    "description": (
        "Resymmetrizes vertex positions from one side to the other using topology.\n"
        "Asymmetries (mismatching edge count on vertex) are not modified.\n"
        "Tie related faces with edge-only connections to symmetrize separate parts.\n"
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


class MESH_OT_topology_resymmetrize(bpy.types.Operator):
    bl_idname: str = "mesh.topo_resymmetrize"
    bl_label: str = "Topology Resymmetrize"
    bl_options = {'REGISTER', 'UNDO'}

    axis: bpy.props.EnumProperty(  # pyright:ignore[reportUninitializedInstanceVariable, reportInvalidTypeForm, reportUnknownMemberType]
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
    
    eps: bpy.props.FloatProperty(  # pyright:ignore[reportUninitializedInstanceVariable, reportInvalidTypeForm, reportUnknownMemberType]
        name="Center Epsilon",
        default=1e-5,
        min=0.0
    )

    only_selected: bpy.props.BoolProperty(  # pyright:ignore[reportUninitializedInstanceVariable, reportInvalidTypeForm, reportUnknownMemberType]
        name="Only Selected",
        default=False
    )

    debug: bpy.props.EnumProperty(  # pyright:ignore[reportUninitializedInstanceVariable, reportInvalidTypeForm, reportUnknownMemberType]
        name="Debug",
        items=[
            ('NORMAL', 'Normal', ''),
            (TopoSymType.VERTEX_CENTER.name, 'Center Verts', ''),
            (TopoSymType.VERTEX_SOURCE.name, 'Source Verts', ''),
            (TopoSymType.VERTEX_TARGET.name, 'Target Verts', ''),
            (TopoSymType.VERTEX_SYMMETRIZED.name, 'Sym. Verts', ''),
            (TopoSymType.VERTEX_ASYMMETRIC.name, 'Asym. Verts', ''),

            (TopoSymType.FACE_SOURCE.name, 'Source Faces', ''),
            (TopoSymType.FACE_TARGET.name, 'Target Faces', ''),
            (TopoSymType.FACE_SYMMETRIZED.name, 'Sym. Faces', ''),
            (TopoSymType.FACE_ASYMMETRIC.name, 'Asym. Faces', ''),
            (TopoSymType.FACE_UNREACHABLE.name, 'Unreachable Faces', ''),
            (TopoSymType.FACE_INITIAL_SYM.name, 'Initial Symmetry', ''),
            (TopoSymType.EDGE_NONMANIFOLD.name, 'Nonmanifold Edges', ''),

        ],
        default='NORMAL'
    )

    limit_steps: bpy.props.BoolProperty(  # pyright:ignore[reportUninitializedInstanceVariable, reportInvalidTypeForm, reportUnknownMemberType]
        name="Limit Steps",
        default=False
    )

    steps: bpy.props.IntProperty(  # pyright:ignore[reportUninitializedInstanceVariable, reportInvalidTypeForm, reportUnknownMemberType]
        name="Steps",
        default=1,
        min=0
    )
    
    def draw(self, context):
        self.layout.use_property_split = True
        row = self.layout.row()
        row.prop(self, "axis")
        row = self.layout.row()
        row.prop(self, "eps")

        row = self.layout.row()
        row.prop(self, "only_selected")

        row = self.layout.row()
        row.prop(self, "debug")

        row = self.layout.row()
        row.prop(self, "limit_steps")

        sub = self.layout.row()
        sub.enabled = self.limit_steps
        sub.prop(self, "steps")
        pass

    # @timed
    def execute_timed(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object must be a mesh")
            return {'CANCELLED'}
        
        # timed_measure_start("exec setup")

        # Changing a parameter in the operators panel
        # seems to trigger an UNDO that bumps the object from edit to object mode
        bpy.ops.object.mode_set(mode='EDIT')

        
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        # timed_measure_stop("exec setup")

        # active shape key
        key_index = -1
        keys = obj.data.shape_keys
        if keys and keys.use_relative and keys.key_blocks:
            key_index = obj.active_shape_key_index

        # mirroring parameters
        axis, side_sign = AXIS_DECODE[self.axis]

        # Create the mapping
        toposym = TopoSym(bm, axis, side_sign,
                            self.eps, key_index, self.steps if self.limit_steps else -1)

        if toposym.get_count(TopoSymType.VERTEX_CENTER_ERRORS) > 0:
            toposym.select_in_bmesh(TopoSymType.VERTEX_CENTER_ERRORS)
            self.report(
                {'ERROR'}, "Center loop vert connects to more than two others, check the center loop.")
            return {'CANCELLED'}

        if self.debug != 'NORMAL':
            toposymtype = TopoSymType[self.debug]

            context.tool_settings.mesh_select_mode = toposymtype.get_mode()
            toposym.select_in_bmesh(toposymtype)
        else:
            # apply symmetry if not debugging
            # selection is not changed.
            toposym.apply_symmetry(self.only_selected)
            bm.normal_update()

        bmesh.update_edit_mesh(
            obj.data, loop_triangles=False, destructive=False)
        bm.free()
        
        # Report
        # Summarize topology issues
        asym_v = toposym.get_count(TopoSymType.VERTEX_ASYMMETRIC)
        unreach_f = toposym.get_count(TopoSymType.FACE_UNREACHABLE)
        nonman_e = toposym.get_count(TopoSymType.EDGE_NONMANIFOLD)
        sym_v = toposym.get_count(TopoSymType.VERTEX_SYMMETRIZED)
        targets = toposym.get_count(TopoSymType.VERTEX_TARGET)

        warn = False

        msg_parts = []

        # warning if object rotated in world
        rot = obj.matrix_world.to_euler()
        if (abs(rot.x) > 1e-6 or abs(rot.y) > 1e-6 or abs(rot.z) > 1e-6):
            warn = True
            msg_parts.append(
                "Object is rotated in world space - axes are not matching the viewport")

        if asym_v > 0:
            warn = True
            msg_parts.append(f"{asym_v} asymmetric vertices")
        if unreach_f > 0:
            warn = True
            msg_parts.append(f"{unreach_f} unreachable faces")
        if nonman_e > 0:
            warn = True
            msg_parts.append(f"{nonman_e} non‑manifold edges")

        msg_parts.append(f"Symmetrized {sym_v} of {targets} target vertices.")

        if warn:
            self.report({'WARNING'}, ", ".join(msg_parts))
        else:
            self.report({'INFO'}, ", ".join(msg_parts))


        # Force viewport refresh
        obj.data.update()
        obj.update_tag()
        bpy.context.view_layer.update()

        return {'FINISHED'}
    
    def execute(self, context):
        # timed_reset()
        retval = self.execute_timed(context)
        # timed_print()
        return retval

# Registration

def menu_func(self, context):
    self.layout.operator(MESH_OT_topology_resymmetrize.bl_idname)


def register():
    bpy.utils.register_class(MESH_OT_topology_resymmetrize)
    bpy.types.VIEW3D_MT_edit_mesh.append(menu_func)


def unregister():
    bpy.utils.unregister_class(MESH_OT_topology_resymmetrize)
    bpy.types.VIEW3D_MT_edit_mesh.remove(menu_func)

