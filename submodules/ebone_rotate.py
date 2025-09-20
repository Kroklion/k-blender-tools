import bpy
import math
from mathutils import Quaternion, Vector

bl_info = {
    "name": "Rotate Edit Bones Around Head",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D View > Sidebar > Edit Tab > Rotate Edit Bones",
    "description": (
        "Provides operators and a panel to rotate selected edit bones\n"
        "around their heads by fixed or custom angles along X, Y, or Z axes."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Rigging",
}


class ARMATURE_OT_rotate_around_head(bpy.types.Operator):
    bl_idname = "armature.rotate_ebones_around_head"
    bl_label = "Rotate Edit Bones"
    bl_description = "Rotate selected bones around their head"
    bl_options = {'REGISTER', 'UNDO'}

    axis: bpy.props.EnumProperty(
        name="Axis",
        items=[
            ('X', "X", "Rotate around head X"),
            ('Y', "Y", "Rotate around head Y"),
            ('Z', "Z", "Rotate around head Z"),
        ],
        default='Y'
    )
    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Rotation angle in degrees",
        default=90.0,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'ARMATURE' and context.mode == 'EDIT_ARMATURE'
    
    def execute(self, context):
        ebones = context.object.data.edit_bones
        angle = math.radians(self.angle)
        
        base = {
            'X': Vector((1, 0, 0)),
            'Y': Vector((0, 1, 0)),  # along the bone (roll)
            'Z': Vector((0, 0, 1)),
        }[self.axis]
        

        for eb in ebones:
            if not eb.select:
                continue

            R_local = Quaternion(base, angle).to_matrix().to_4x4()

            # M maps bone-local -> armature; right-multiply to rotate in bone-local space
            M = eb.matrix.copy()
            eb.matrix = M @ R_local

        # ---- force Blender to notice the matrix changes ----
        arm = context.object.data
        arm.update_tag()                  # mark armature-ID dirty
        context.view_layer.update()      # push depsgraph update
        for area in context.screen.areas:  # redraw the 3D view
            if area.type == 'VIEW_3D':
                area.tag_redraw()
            
        return {'FINISHED'}


class ARMATURE_PT_rotate_ebones_panel(bpy.types.Panel):
    bl_label = "Rotate Edit Bones"
    bl_idname = "ARMATURE_PT_rotate_ebones_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Edit"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'ARMATURE' and context.mode == 'EDIT_ARMATURE'

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        for sign, deg in (('+', 90), ('−', -90)):
            row = col.row(align=True)
            op = row.operator("armature.rotate_ebones_around_head",
                              text=f"X {sign}90°")
            op.axis = 'X'
            op.angle = deg
            op = row.operator("armature.rotate_ebones_around_head",
                              text=f"Y {sign}90°")
            op.axis = 'Y'
            op.angle = deg
            op = row.operator("armature.rotate_ebones_around_head",
                              text=f"Z {sign}90°")
            op.axis = 'Z'
            op.angle = deg


classes = [
    ARMATURE_OT_rotate_around_head,
    ARMATURE_PT_rotate_ebones_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


