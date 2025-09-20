import bpy
import bmesh
import math
from mathutils import Matrix, Quaternion, Vector

bl_info = {
    "name": "Cursor Rotation Snap",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "Object Mode: 3D View > Object > Snap Menu\n"
        "Snap menu found at different locations in other modes"
    ),
    "description": (
        "Enhanced snapping tools for the 3D Cursor and active elements.\n"
        "Includes snapping the cursor to active objects, bones, or mesh elements\n"
        "with rotation, orienting the cursor to active, and snapping active\n"
        "objects or bones back to the cursor with rotation."
    ),
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}


class VIEW3D_OT_snap_cursor_to_active_with_rotate(bpy.types.Operator):
    """Snap 3D Cursor to Active Object or Bone (with rotation)"""
    bl_idname = "view3d.snap_cursor_to_active_with_rotate"
    bl_label = "Snap Cursor to Active"
    bl_options = {'REGISTER', 'UNDO'}
    
    original_mode = None
    
    def update_cursor(self, context, location, rotation_quat):
        cursor = context.scene.cursor
        cursor.location = location
        cursor.rotation_mode = 'QUATERNION'
        cursor.rotation_quaternion = rotation_quat
        cursor.rotation_mode = self.original_mode  # Restore original mode
        
    def build_rotation_from_negative_y(self, normal: Vector) -> Quaternion:
        # Ensure normal is normalized
        normal = normal.normalized()

        # -Y axis should point along the normal
        y_axis = -normal

        # Choose a fallback axis that's not parallel to Y
        fallback = Vector((0, 0, 1)) if abs(y_axis.dot(
            Vector((0, 0, 1)))) < 0.99 else Vector((1, 0, 0))

        x_axis = fallback.cross(y_axis).normalized()
        z_axis = x_axis.cross(y_axis).normalized()

        rot_matrix = Matrix((x_axis, y_axis, z_axis)).transposed()  # Blender expects column-major

        return rot_matrix.to_quaternion()
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "No active object.")
            return {'CANCELLED'}
        
        self.original_mode = context.scene.cursor.rotation_mode
        
        # Determine what to snap to
        if obj.type == 'ARMATURE' and obj.mode == 'EDIT':
            eb = obj.data.edit_bones.active
            if not eb:
                self.report({'ERROR'}, "No active edit bone.")
                return {'CANCELLED'}

            # Base bone matrix (orientation + head translation)
            mat_base = obj.matrix_world @ eb.matrix

            # Pick head or tail by selection flags
            # If only tail is selected -> snap to tail. Otherwise head.
            target_loc = obj.matrix_world @ (
                eb.tail if eb.select_tail and not eb.select_head else eb.head)
            mat_base.translation = target_loc
            mat_world = mat_base
            self.update_cursor(context, mat_world.to_translation(), mat_world.to_quaternion())
            return {'FINISHED'}
            
        elif obj.type == 'ARMATURE' and obj.mode == 'POSE':
            pb = context.active_pose_bone
            if not pb:
                self.report({'ERROR'}, "No active pose bone.")
                return {'CANCELLED'}
            # pose bone matrix in armature local space
            mat_world = obj.matrix_world @ pb.matrix
            self.update_cursor(context, mat_world.to_translation(), mat_world.to_quaternion())
            return {'FINISHED'}
            
        elif obj.type == 'MESH' and obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            selected_verts = [v for v in bm.verts if v.select]
            if len(selected_verts) == 1:
                v = selected_verts[0]
                loc_world = obj.matrix_world @ v.co
                normal_world = obj.matrix_world.to_3x3() @ v.normal

                # Align -Y to vertex normal
                q = self.build_rotation_from_negative_y(normal_world)

                self.update_cursor(context, loc_world, q)
                return {'FINISHED'}
            
            # Snap to face
            elem = bm.select_history.active
            if not isinstance(elem, bmesh.types.BMFace):
                self.report({'ERROR'}, "Select one vertex or face.")
                return {'CANCELLED'}
            
            # world-space center & normal
            center_world = obj.matrix_world @ elem.calc_center_median()
            normal_world = obj.matrix_world.to_3x3() @ elem.normal
            q = self.build_rotation_from_negative_y(normal_world)

            self.update_cursor(context, center_world, q)
            return {'FINISHED'}
            
        else:
            # just an object
            mat_world = obj.matrix_world.copy()
            self.update_cursor(context, mat_world.to_translation(), mat_world.to_quaternion())
            return {'FINISHED'}
    

class VIEW3D_OT_orient_cursor_to_active(bpy.types.Operator):
    """Orient 3D Cursor –Y axis towards Active Element"""
    bl_idname = "view3d.orient_cursor_to_active"
    bl_label = "Orient Cursor to Active"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj and True
        )

    def execute(self, context):
        scene = context.scene
        cursor = scene.cursor
        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "No active object.")
            return {'CANCELLED'}

        # find target world-space coordinate
        target_co = None

        # edit‐armature: head or tail based on selection
        if obj.type == 'ARMATURE' and obj.mode == 'EDIT':
            eb = obj.data.edit_bones.active
            if not eb:
                self.report({'ERROR'}, "No active edit bone.")
                return {'CANCELLED'}
            if eb.select_tail and not eb.select_head:
                target_co = obj.matrix_world @ eb.tail
            else:
                target_co = obj.matrix_world @ eb.head

        # pose‐armature: always head
        elif obj.type == 'ARMATURE' and obj.mode == 'POSE':
            pb = context.active_pose_bone
            if not pb:
                self.report({'ERROR'}, "No active pose bone.")
                return {'CANCELLED'}
            # pb.head is in armature local, so world:
            target_co = obj.matrix_world @ pb.head

        # edit‐mesh: the active history element must be a vertex
        elif obj.type == 'MESH' and obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj.data)
            elem = bm.select_history.active
            if not elem or not isinstance(elem, bmesh.types.BMVert):
                self.report({'ERROR'}, "No active mesh vertex.")
                return {'CANCELLED'}
            target_co = obj.matrix_world @ elem.co

        # fallback: object origin
        else:
            target_co = obj.matrix_world.translation

        # compute direction from cursor to target
        direction = target_co - cursor.location
        if direction.length == 0:
            self.report({'ERROR'}, "Cursor is already at the target!")
            return {'CANCELLED'}
        direction.normalize()

        # want -Y (0,-1,0) → direction
        from_vec = Vector((0.0, -1.0, 0.0))
        rot_quat = from_vec.rotation_difference(direction)

        cursor.rotation_mode = 'QUATERNION'
        cursor.rotation_quaternion = rot_quat

        return {'FINISHED'}
    

class VIEW3D_OT_snap_active_to_cursor_with_rotate(bpy.types.Operator):
    """Snap Active Object or Bone to 3D Cursor (with rotation)"""
    bl_idname = "view3d.snap_active_to_cursor_with_rotate"
    bl_label = "Snap Active to Cursor"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object
        cursor = context.scene.cursor

        # Get target matrix from cursor
        cursor_matrix = cursor.matrix.copy()

        if obj.type == 'ARMATURE' and obj.mode == 'POSE':
            pb = context.active_pose_bone
            if not pb:
                self.report({'ERROR'}, "No active pose bone.")
                return {'CANCELLED'}

            # Convert cursor matrix into pose space
            arm = obj
            inv_arm_matrix = arm.matrix_world.inverted()
            pose_matrix = inv_arm_matrix @ cursor_matrix

            pb.matrix = pose_matrix
            bpy.context.view_layer.update()

        elif obj.mode == 'OBJECT':
            obj.matrix_world = cursor_matrix

        else:
            self.report(
                {'ERROR'}, "Unsupported mode. Switch to Object or Pose Mode.")
            return {'CANCELLED'}

        return {'FINISHED'}
    
def menu_top(self, context):
    self.layout.operator(
        VIEW3D_OT_snap_active_to_cursor_with_rotate.bl_idname,
        text="Selection to Cursor (with Rotation)")

def menu_bottom(self, context):
    self.layout.operator(
        VIEW3D_OT_snap_cursor_to_active_with_rotate.bl_idname,
        text="Cursor to Active (with Rotation)")
    self.layout.operator(
        VIEW3D_OT_orient_cursor_to_active.bl_idname,
        text="Cursor: Orient to Active")
    

def draw_snap_menu(self, context):
    pie = self.layout.menu_pie()
    pie.operator(
        VIEW3D_OT_snap_cursor_to_active_with_rotate.bl_idname,
        text=VIEW3D_OT_snap_cursor_to_active_with_rotate.bl_label,
        icon='CURSOR')


classes = [
    VIEW3D_OT_snap_cursor_to_active_with_rotate,
    VIEW3D_OT_orient_cursor_to_active,
    VIEW3D_OT_snap_active_to_cursor_with_rotate,
]


def register():
    bpy.types.VIEW3D_MT_snap.prepend(menu_top)
    bpy.types.VIEW3D_MT_snap.append(menu_bottom)
    # bpy.types.VIEW3D_MT_snap_pie.append(draw_snap_menu)
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    bpy.types.VIEW3D_MT_snap.remove(menu_top)
    bpy.types.VIEW3D_MT_snap.remove(menu_bottom)
    # bpy.types.VIEW3D_MT_snap_pie.remove(draw_snap_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


