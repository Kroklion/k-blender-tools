import numpy as np
import mathutils
import bmesh
import bpy
bl_info = {
    "name": "Align Mesh to Axis (Best-Fit Plane)",
    "author": "",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Edit Mode > Mesh > Align Selected to Plane",
    "description": (
        "Computes a best-fit plane from the selected vertices and rotates the mesh\n"
        "so that the plane's normal aligns with a chosen global axis (X, Y, or Z).\n"
        "Optionally recenters the selection on the origin along that axis."
    ),
    "category": "Mesh",
}


def best_fit_plane_normal(verts):
    coords = np.array([v.co[:] for v in verts])
    mean = coords.mean(axis=0)
    centered = coords - mean
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    # smallest eigenvector = plane normal
    normal = eigvecs[:, np.argmin(eigvals)]
    return mathutils.Vector(normal).normalized(), mathutils.Vector(mean)


class MESH_OT_align_bestfit_plane(bpy.types.Operator):
    """Align mesh so best-fit plane normal of selection points to global axis"""
    bl_idname = "mesh.align_bestfit_plane"
    bl_label = "Align Selected to Plane"
    bl_options = {'REGISTER', 'UNDO'}

    target_axis: bpy.props.EnumProperty(
        name="Target Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='X'
    )

    recenter: bpy.props.BoolProperty(
        name="Recenter on Axis",
        description="Snap centroid of selection to global origin along chosen axis",
        default=True
    )

    def execute(self, context):
        obj = context.edit_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        sel_verts = [v for v in bm.verts if v.select]
        if len(sel_verts) < 3:
            self.report(
                {'ERROR'}, "Select at least 3 vertices to define a plane")
            return {'CANCELLED'}

        # best-fit plane normal
        n, center = best_fit_plane_normal(sel_verts)

        # target axis vector
        t = mathutils.Vector((1, 0, 0)) if self.target_axis == 'X' else \
            mathutils.Vector((0, 1, 0)) if self.target_axis == 'Y' else \
            mathutils.Vector((0, 0, 1))

        # flip if pointing opposite
        if n.dot(t) < 0:
            n.negate()

        # rotation from n to t
        rot = n.rotation_difference(t).to_matrix()

        # apply rotation to all vertices
        for v in bm.verts:
            v.co = rot @ (v.co - center) + center

        # optional recentering
        if self.recenter:
            # compute average coordinate of selection along target axis
            avg = sum((v.co for v in sel_verts), mathutils.Vector()) / len(sel_verts)

            if self.target_axis == 'X':
                delta = avg.x
                for v in bm.verts:
                    v.co.x -= delta
            elif self.target_axis == 'Y':
                delta = avg.y
                for v in bm.verts:
                    v.co.y -= delta
            else:  # 'Z'
                delta = avg.z
                for v in bm.verts:
                    v.co.z -= delta

        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=True)
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(MESH_OT_align_bestfit_plane.bl_idname)


def register():
    bpy.utils.register_class(MESH_OT_align_bestfit_plane)
    bpy.types.VIEW3D_MT_edit_mesh.append(menu_func)


def unregister():
    bpy.utils.unregister_class(MESH_OT_align_bestfit_plane)
    bpy.types.VIEW3D_MT_edit_mesh.remove(menu_func)
