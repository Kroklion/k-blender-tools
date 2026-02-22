from mathutils import Vector, Matrix
from math import pi
import bpy
bl_info = {
    "name": "Flatten Bone Chain to Plane",
    "author": "",
    "version": (1, 4),
    "blender": (3, 0, 0),
    "location": "Armature Edit Mode > Armature",
    "description": (
        "Projects a selected bone chain onto a plane defined by\n"
        "endpoints and intermediate joint center. Optionally aligns roll."
    ),
    "category": "Rigging",
}


class ARMATURE_OT_flatten_chain(bpy.types.Operator):
    """Project selected bone chain onto a plane defined by endpoints and joint center"""
    bl_idname = "armature.flatten_bone_chain"
    bl_label = "Flatten Bone Chain"
    bl_options = {'REGISTER', 'UNDO'}

    plane_mode: bpy.props.EnumProperty(
        name="Plane Alignment",
        description="Choose alignment of the flattening plane",
        items=[
            ('MEDIAN', "Median", "Use the median of intermediate joints"),
            ('X_POS', "+X", "Align with armature +X"),
            ('Y_POS', "+Y", "Align with armature +Y"),
            ('Z_POS', "+Z", "Align with armature +Z"),
            ('X_NEG', "-X", "Align with armature -X"),
            ('Y_NEG', "-Y", "Align with armature -Y"),
            ('Z_NEG', "-Z", "Align with armature -Z"),
        ],
        default='MEDIAN'
    )
    roll_mode: bpy.props.EnumProperty(
        name="Align Roll",
        description="Align first bone's roll so a chosen axis matches the plane normal",
        items=[
            ('KEEP', "Keep", "Do not change roll"),
            ('Z_POS', "+Z", "Align bone +Z axis"),
            ('Z_NEG', "-Z", "Align bone -Z axis"),
            ('X_POS', "+X", "Align bone +X axis"),
            ('X_NEG', "-X", "Align bone -X axis"),
        ],
        default='KEEP'
    )
    align_all: bpy.props.BoolProperty(
        name="Reroll All",
        description="Apply roll alignment to all bones in the chain",
        default=False,
    )
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'ARMATURE' and context.mode == 'EDIT_ARMATURE'
    

    def execute(self, context):
        obj = context.object

        ebones = obj.data.edit_bones
        selected = [b for b in ebones if b.select]

        if len(selected) < 2:
            self.report({'ERROR'}, "Select a chain of at least two bones")
            return {'CANCELLED'}

        # Find highest parent in selection
        root = selected[0]
        while root.parent in selected:
            root = root.parent

        # Walk down the chain following single-child links
        chain = []
        b = root
        while b and b in selected:
            chain.append(b)
            children_in_sel = [c for c in b.children if c in selected]
            if len(children_in_sel) != 1:
                break
            b = children_in_sel[0]

        if len(chain) < 2:
            self.report(
                {'ERROR'}, "Selection must be a single connected chain")
            return {'CANCELLED'}

        # Define plane points:
        # A = head of first bone
        # B = tail of last bone
        A = chain[0].head.copy()
        B = chain[-1].tail.copy()

        # Collect intermediate joints (heads and tails of bones in between)
        joint_points = []
        for b in chain[1:-1]:
            joint_points.append(b.head.copy())
            joint_points.append(b.tail.copy())

        if not joint_points:
            self.report({'INFO'}, "No intermediate joints to flatten")
            return {'FINISHED'}

        # Determine third point C based on plane_mode
        if self.plane_mode == 'MEDIAN':
            # Use median of intermediate joints
            center = sum(joint_points, Vector()) / len(joint_points)

        else:
            # Axis-aligned modes
            axis_map = {
                'X_POS': Vector((1, 0, 0)),
                'X_NEG': Vector((-1, 0, 0)),
                'Y_POS': Vector((0, 1, 0)),
                'Y_NEG': Vector((0, -1, 0)),
                'Z_POS': Vector((0, 0, 1)),
                'Z_NEG': Vector((0, 0, -1)),
            }
            center = A + axis_map[self.plane_mode]


        # Compute plane normal from A, B, C
        AB = B - A
        AC = center - A
        normal = AB.cross(AC)

        if normal.length < 1e-8:
            # Degenerate: C lies on line AB
            self.report({'WARNING'}, "No definite plane found, skipping")
            return {'CANCELLED'}
            
        normal.normalize()

        # Plane equation: (P - A) · normal = 0
        # For each joint point P, project along normal:
        # P' = P - d * normal, where d = (P - A) · normal

        # Apply to all intermediate joints (heads and tails of middle bones)
        for b in chain[1:-1]:
            for attr in ("head", "tail"):
                P = getattr(b, attr)
                d = (P - A).dot(normal)
                P_new = P - d * normal
                setattr(b, attr, P_new)
                
        if self.roll_mode != 'KEEP':
            bone = chain[0]

            # Base vector = plane normal
            target = normal.copy()

            if self.roll_mode == 'Z_POS':
                pass  # target = normal

            elif self.roll_mode == 'Z_NEG':
                target = -target

            elif self.roll_mode in ('X_POS', 'X_NEG'):
                # Rotate normal so that bone.x_axis would align with it
                # align_roll aligns Z, so rotate normal by +90° around bone.y_axis
                rot90 = Matrix.Rotation(pi/2, 3, bone.y_axis)
                target = rot90 @ target

                if self.roll_mode == 'X_NEG':
                    target = -target

            # Apply roll alignment
            bone.align_roll(target)
            
        if self.align_all:
            # Use Blender's built-in roll propagation
            # Root must be active, all bones selected
            old_active = ebones.active
            for b in ebones:
                b.select = False
            for b in chain:
                b.select = True
            ebones.active = chain[0]

            bpy.ops.armature.calculate_roll(
                type='ACTIVE',
                axis_flip=False,
                axis_only=False
            )
            ebones.active = old_active


        self.report({'INFO'}, f"Flattened {len(chain)} bones.")
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(ARMATURE_OT_flatten_chain.bl_idname)


def register():
    bpy.utils.register_class(ARMATURE_OT_flatten_chain)
    bpy.types.VIEW3D_MT_edit_armature.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_edit_armature.remove(menu_func)
    bpy.utils.unregister_class(ARMATURE_OT_flatten_chain)


if __name__ == "__main__":
    register()
