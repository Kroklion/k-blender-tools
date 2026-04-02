import bpy

from .data import get_reference_object

class AS_OT_StoreRestPose(bpy.types.Operator):
    """Store the current rest pose matrices on all bones of the active armature"""
    bl_idname = "as_actions.store_rest_pose"
    bl_label = "Store Rest Pose"
    bl_description = "Store each bone's current rest matrix into a custom property"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = get_reference_object(context)
        return obj is not None and obj.type == 'ARMATURE'

    def execute(self, context):
        arm = get_reference_object(context)
        for bone in arm.data.bones:
            bone["stored_rest_matrix"] = bone.matrix_local.copy()

        self.report(
            {'INFO'}, f"Stored rest matrices for {len(arm.data.bones)} bones")
        return {'FINISHED'}


class AS_OT_CorrectBoneRotations(bpy.types.Operator):
    """Correct animations for edit bone rerotation"""
    bl_idname = "as_actions.correct_bone_rotations"
    bl_label = "Correct Bone Rotations"
    bl_description = "Apply rest-pose correction to quaternion F-curves for all associated actions"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = get_reference_object(context)
        return obj is not None and obj.type == 'ARMATURE' and len(obj.as_actions) > 0

    def execute(self, context):
        arm = get_reference_object(context)
        actions = arm.as_actions

        for item in actions:
            action = item.action
            if action is None:
                continue

            self.correct_action(arm, action)

        self.report(
            {'INFO'}, "Corrected quaternion F-curves for all associated actions")
        return {'FINISHED'}

    # Core correction logic

    def correct_action(self, arm, action):
        from mathutils import Matrix, Quaternion, Vector

        for bone in arm.pose.bones:
            rbone = arm.data.bones[bone.name]

            # Ensure stored rest matrix exists
            if "stored_rest_matrix" not in rbone:
                continue

            # Old rest matrix (stored earlier)
            M_old = Matrix(rbone["stored_rest_matrix"])

            # New rest matrix (current rest pose)
            M_new = rbone.matrix_local.copy()

            # Convert to quaternions
            Q_oldRest = M_old.to_quaternion()
            Q_newRest = M_new.to_quaternion()

            # Correction quaternion
            Q_corr = Q_newRest.inverted() @ Q_oldRest

            # Rotation (quaternion) F-curves
            rot_fcurves = [
                fc for fc in action.fcurves
                if fc.data_path == f'pose.bones["{bone.name}"].rotation_quaternion'
            ]

            if len(rot_fcurves) >= 4:
                rot_fc_dict = {fc.array_index: fc for fc in rot_fcurves}
                rot_key_times = {kp.co[0]
                                 for kp in rot_fcurves[0].keyframe_points}

                for t in sorted(rot_key_times):
                    w = rot_fc_dict[0].evaluate(t)
                    x = rot_fc_dict[1].evaluate(t)
                    y = rot_fc_dict[2].evaluate(t)
                    z = rot_fc_dict[3].evaluate(t)
                    Q_oldPose = Quaternion((w, x, y, z))

                    Q_newPose = Q_corr @ Q_oldPose @ Q_corr.inverted()

                    rot_fc_dict[0].keyframe_points.insert(
                        t, Q_newPose.w, options={'REPLACE'})
                    rot_fc_dict[1].keyframe_points.insert(
                        t, Q_newPose.x, options={'REPLACE'})
                    rot_fc_dict[2].keyframe_points.insert(
                        t, Q_newPose.y, options={'REPLACE'})
                    rot_fc_dict[3].keyframe_points.insert(
                        t, Q_newPose.z, options={'REPLACE'})

                for fc in rot_fcurves:
                    fc.update()

            # Location F-curves
            loc_fcurves = [
                fc for fc in action.fcurves
                if fc.data_path == f'pose.bones["{bone.name}"].location'
            ]

            if len(loc_fcurves) >= 3:
                loc_fc_dict = {fc.array_index: fc for fc in loc_fcurves}
                loc_key_times = {kp.co[0]
                                 for kp in loc_fcurves[0].keyframe_points}

                for t in sorted(loc_key_times):
                    lx = loc_fc_dict[0].evaluate(t)
                    ly = loc_fc_dict[1].evaluate(t)
                    lz = loc_fc_dict[2].evaluate(t)
                    L_old = Vector((lx, ly, lz))

                    # Rotate location by correction quaternion
                    L_new = Q_corr @ L_old

                    loc_fc_dict[0].keyframe_points.insert(
                        t, L_new.x, options={'REPLACE'})
                    loc_fc_dict[1].keyframe_points.insert(
                        t, L_new.y, options={'REPLACE'})
                    loc_fc_dict[2].keyframe_points.insert(
                        t, L_new.z, options={'REPLACE'})

                for fc in loc_fcurves:
                    fc.update()
            # Scale F-curves (ignored)
            # We intentionally do NOT modify scale:
            # - uniform scale is invariant under rotation
            # - non-uniform scale cannot be corrected meaningfully
            # So: do nothing here.


# Registration
classes = (
    AS_OT_StoreRestPose,
    AS_OT_CorrectBoneRotations
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
