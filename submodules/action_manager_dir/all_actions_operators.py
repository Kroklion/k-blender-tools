import bpy

from bpy.props import (
    StringProperty,
)


class AS_OT_BatchRename(bpy.types.Operator):
    bl_idname = "as_actions.batch_rename"
    bl_label = "Rename Selected"
    bl_description = "Batch rename selected actions using regex"
    bl_options = {'REGISTER', 'UNDO'}

    pattern: StringProperty(
        name="Pattern",
        description="Regex pattern to search for",
        default=""
    )
    replacement: StringProperty(
        name="Replace",
        description="Replacement string",
        default=""
    )

    def invoke(self, context, event):
        # This opens a popup dialog with the operator's properties
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "pattern")
        layout.prop(self, "replacement")

    def execute(self, context):
        import re
        props = context.scene.k_action_manager_props

        for item in props.all_actions_list_items:
            if item.selected:
                act = item.action
                if act:
                    new_name = re.sub(self.pattern, self.replacement, act.name)
                    act.name = new_name

        return {'FINISHED'}
    
# needed i.e. for end frame detection


def round_if_close(x, eps=1e-5):
    r = round(x)
    return r if abs(x - r) < eps else x


class AS_OT_FixActionFramerate(bpy.types.Operator):
    """Fix keyframe timing for actions imported at a different FPS"""
    bl_idname = "as_actions.fix_framerate"
    bl_label = "Fix Framerate"
    bl_description = "Scale keyframe times from old FPS to current FPS"
    bl_options = {'REGISTER', 'UNDO'}

    old_fps: bpy.props.FloatProperty(
        name="Old FPS",
        description="The FPS the animation was authored/imported at",
        default=24.0,
        min=1.0,
    )

    new_fps: bpy.props.FloatProperty(
        name="New FPS",
        description="The FPS the animation should play at",
        default=30.0,
        min=1.0,
    )

    start_frame: bpy.props.FloatProperty(
        name="Start Frame",
        description="Frame where the animation begins (usually 1 for FBX)",
        default=1.0,
    )

    def invoke(self, context, event):
        # Prefill new_fps with the actual scene FPS
        scene = context.scene
        self.new_fps = scene.render.fps / scene.render.fps_base

        # Try to detect start frame from selected actions
        props = scene.k_action_manager_props
        for item in props.all_actions_list_items:
            if item.selected and item.action:
                self.start_frame = item.action.frame_range[0]
                break

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "old_fps")
        layout.prop(self, "new_fps")
        layout.prop(self, "start_frame")

    def execute(self, context):
        props = context.scene.k_action_manager_props

        if self.old_fps <= 0 or self.new_fps <= 0:
            self.report({'ERROR'}, "FPS values must be positive")
            return {'CANCELLED'}

        scale = self.new_fps / self.old_fps
        s = self.start_frame

        count = 0

        for item in props.all_actions_list_items:
            if not item.selected:
                continue

            action = item.action
            if action is None:
                continue

            for fcu in action.fcurves:
                for kp in fcu.keyframe_points:
                    # Apply offset + scale
                    new_x = s + (kp.co.x - s) * scale
                    new_l = s + (kp.handle_left.x - s) * scale
                    new_r = s + (kp.handle_right.x - s) * scale

                    # Snap to whole numbers if extremely close
                    kp.co.x = round_if_close(new_x)
                    kp.handle_left.x = round_if_close(new_l)
                    kp.handle_right.x = round_if_close(new_r)

            count += 1

        self.report(
            {'INFO'}, f"Retimed {count} action(s) by factor {scale:.4f}")
        return {'FINISHED'}
    

# Registration
classes = (
    AS_OT_BatchRename,
    AS_OT_FixActionFramerate,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
