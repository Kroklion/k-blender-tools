import bpy

from bpy.types import (
    UIList,
    Operator,
    Object,
    Action,
    Scene,
    ID
)

from .data import get_reference_object

# Module‑level feature flags
HAS_ACTION_SLOTS = False

# UI Lists
class AS_UL_ObjectActions(UIList):
    """Actions associated with the active object."""

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        action_ref: AS_ActionListItem = item
        row = layout.row(align=True)

        # Checkbox for selection
        row.prop(action_ref, "selected", text="")

        # Action name
        if action_ref.action:
            row.label(text=action_ref.action.name)
        else:
            row.label(text="(missing)")


class AS_OT_ObjectActionsSelectAll(bpy.types.Operator):
    """Select all object actions"""
    bl_idname = "as_actions.object_select_all"
    bl_label = "Select All"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = get_reference_object(context)
        return obj is not None and len(obj.as_actions) > 0

    def execute(self, context):
        obj = get_reference_object(context)
        for item in obj.as_actions:
            item.selected = True
        return {'FINISHED'}


class AS_OT_ObjectActionsSelectNone(bpy.types.Operator):
    """Deselect all object actions"""
    bl_idname = "as_actions.object_select_none"
    bl_label = "Select None"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = get_reference_object(context)
        return obj is not None and len(obj.as_actions) > 0

    def execute(self, context):
        obj = get_reference_object(context)
        for item in obj.as_actions:
            item.selected = False
        return {'FINISHED'}


class AS_OT_ObjectActionsMoveUp(bpy.types.Operator):
    """Move selected object actions up"""
    bl_idname = "as_actions.object_move_up"
    bl_label = "Move Up"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = get_reference_object(context)
        return obj is not None and len(obj.as_actions) > 1

    def execute(self, context):
        obj = get_reference_object(context)
        actions = obj.as_actions

        # Selected indices
        selected = [i for i, item in enumerate(actions) if item.selected]

        # If nothing selected → use active index
        if not selected:
            idx = obj.as_actions_index
            if idx > 0:
                actions.move(idx, idx - 1)
                obj.as_actions_index = idx - 1
            return {'FINISHED'}

        # Move selected items up (ascending order)
        for i in selected:
            if i > 0:
                actions.move(i, i - 1)

        # Update active index
        obj.as_actions_index = max(0, obj.as_actions_index - 1)

        return {'FINISHED'}


class AS_OT_ObjectActionsMoveDown(bpy.types.Operator):
    """Move selected object actions down"""
    bl_idname = "as_actions.object_move_down"
    bl_label = "Move Down"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = get_reference_object(context)
        return obj is not None and len(obj.as_actions) > 1

    def execute(self, context):
        obj = get_reference_object(context)
        actions = obj.as_actions
        n = len(actions)

        # Selected indices
        selected = [i for i, item in enumerate(actions) if item.selected]

        # If nothing selected → use active index
        if not selected:
            idx = obj.as_actions_index
            if idx < n - 1:
                actions.move(idx, idx + 1)
                obj.as_actions_index = idx + 1
            return {'FINISHED'}

        # Move selected items down (reverse order)
        for i in reversed(selected):
            if i < n - 1:
                actions.move(i, i + 1)

        # Update active index
        obj.as_actions_index = min(n - 1, obj.as_actions_index + 1)

        return {'FINISHED'}


class AS_OT_ObjectActionsSortAZ(bpy.types.Operator):
    """Sort object actions alphabetically"""
    bl_idname = "as_actions.object_sort_az"
    bl_label = "Sort A–Z"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = get_reference_object(context)
        return obj is not None and len(obj.as_actions) > 1

    def execute(self, context):
        obj = get_reference_object(context)
        actions = obj.as_actions

        # Capture current state
        old_items = [
            (item.action, item.selected)
            for item in actions
        ]
        active_action = actions[obj.as_actions_index].action

        # Sort by action name (case‑insensitive)
        sorted_items = sorted(
            old_items,
            key=lambda pair: pair[0].name.lower() if pair[0] else ""
        )

        # Rebuild list
        actions.clear()
        for act, selected in sorted_items:
            new_item = actions.add()
            new_item.action = act
            new_item.selected = selected

        # Restore active index
        for i, item in enumerate(actions):
            if item.action == active_action:
                obj.as_actions_index = i
                break

        return {'FINISHED'}


class AS_OT_AddActionToObject(Operator):
    """Add selected Actions from all actions to the active object's list."""
    bl_idname = "as_actions.add_to_object"
    bl_label = "Add"
    bl_description = "Add selected Actions to this object"

    @classmethod
    def poll(cls, context):
        return context.object is not None and len(bpy.data.actions) > 0

    def execute(self, context):
        obj = get_reference_object(context)
        props = context.scene.k_action_manager_props

        added_count = 0

        # all actions that are already added
        added_actions = set()

        for added_item in obj.as_actions:
            if added_item.action:
                added_actions.add(added_item.action)

        for item in props.all_actions_list_items:
            if item.selected and item.action and not item.action in added_actions:
                new_ref: AS_ActionListItem = obj.as_actions.add()
                new_ref.action = item.action
                new_ref.action.use_fake_user = True
                added_count += 1

        if added_count > 0:
            obj.as_actions_index = len(obj.as_actions) - 1

        return {'FINISHED'}


class AS_OT_RemoveActionFromObject(Operator):
    """Remove selected associated Action(s) from the active object."""
    bl_idname = "as_actions.remove_from_object"
    bl_label = "Remove"
    bl_description = "Remove selected Action(s) from this object"
    bl_options = {'UNDO'}   # ensure undo support

    @classmethod
    def poll(cls, context):
        obj = get_reference_object(context)
        return obj is not None and len(obj.as_actions) > 0

    def execute(self, context):
        obj = get_reference_object(context)
        actions = obj.as_actions

        # Collect selected indices
        selected_indices = [
            i for i, item in enumerate(actions)
            if item.selected
        ]

        # If nothing is selected, fall back to highlighted index
        if not selected_indices:
            idx = obj.as_actions_index
            if 0 <= idx < len(actions):
                selected_indices = [idx]
            else:
                return {'CANCELLED'}

        # Remove in reverse order to keep indices valid
        for i in reversed(selected_indices):
            actions.remove(i)

        # Update active index
        if actions:
            # Pick the closest valid index
            obj.as_actions_index = min(selected_indices[0], len(actions) - 1)
        else:
            obj.as_actions_index = -1

        return {'FINISHED'}


def get_id_from_slot(slot) -> ID | None:
    """Return the ID block that a slot targets, or None if unresolved."""
    slot_name: str = getattr(slot, "name_display", "")
    target_type: str = getattr(slot, "target_id_type")

    if not slot_name:
        return None

    if target_type == 'OBJECT':
        # name_display must be object name
        anim_target = bpy.data.objects.get(slot_name)
        return anim_target

    elif target_type == 'ARMATURE':
        # name_display must be object name
        anim_target = bpy.data.objects.get(slot_name)
        if anim_target and hasattr(anim_target, "data") and isinstance(anim_target.data, bpy.types.Armature):
            return anim_target.data

    elif target_type == 'CAMERA':
        # name_display must be object name
        anim_target = bpy.data.objects.get(slot_name)
        if anim_target and isinstance(anim_target.data, bpy.types.Camera):
            return anim_target.data

    elif target_type == 'CURVE':
        # name_display must be object name
        anim_target = bpy.data.objects.get(slot_name)
        if anim_target and isinstance(anim_target.data, bpy.types.Curve):
            return anim_target.data

    elif target_type == 'CURVES':
        # name_display must be object name
        anim_target = bpy.data.objects.get(slot_name)
        if anim_target and isinstance(anim_target.data, bpy.types.Curves):
            return anim_target.data

    elif target_type == 'KEY':
        # name_display must be object name
        anim_target = bpy.data.objects.get(slot_name)
        if anim_target and hasattr(anim_target, "data") and isinstance(anim_target.data, bpy.types.Mesh):
            return anim_target.data.shape_keys

    elif target_type == 'LIGHT':
        # name_display must be object name
        anim_target = bpy.data.objects.get(slot_name)
        if anim_target and isinstance(anim_target.data, bpy.types.Light):
            return anim_target.data

    elif target_type == 'MATERIAL':
        # name_display must be material name
        anim_target = bpy.data.materials.get(slot_name)
        return anim_target

    elif target_type == 'MESH':
        # name_display must be object name
        anim_target = bpy.data.objects.get(slot_name)
        if anim_target and isinstance(anim_target.data, bpy.types.Mesh):
            return anim_target.data

    elif target_type == 'NODETREE':
        # name_display must be material name
        anim_target = bpy.data.materials.get(slot_name)
        return anim_target.node_tree if anim_target else None

    else:
        print(f"get_id_from_slot: Unsupported slot type {target_type}")

    return None


def assign_action_to_id(id_block: ID | None, action: Action) -> None:
    """Assign an Action to an ID block's animation_data."""
    if id_block is None:
        return
    ad = id_block.animation_data
    if ad is None:
        ad = id_block.animation_data_create()
    ad.action = action


def assign_action_by_slot(action: Action, slot) -> None:
    """Assign the Action to the object referenced by the slot name, using slot type."""
    anim_target = get_id_from_slot(slot)
    if anim_target:
        assign_action_to_id(anim_target, action)
    else:
        print(
            f"slot assign failed: {slot.name_display}, type {slot.target_id_type}")



class AS_OT_ApplyAction(Operator):
    """Apply selected associated Action to active object and slot targets."""
    bl_idname = "as_actions.apply"
    bl_label = "Apply"
    bl_description = "Assign Action to objects based on slots"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = get_reference_object(context)
        return obj is not None and len(obj.as_actions) > 0

    def execute(self, context):
        global HAS_ACTION_SLOTS
        obj = get_reference_object(context)
        props = context.scene.k_action_manager_props
        scene: Scene = context.scene

        idx = obj.as_actions_index
        if idx < 0 or idx >= len(obj.as_actions):
            return {'CANCELLED'}

        action: Action | None = obj.as_actions[idx].action
        if action is None:
            self.report({'WARNING'}, "Action is missing.")
            return {'CANCELLED'}

        # collect and remove previous slot targets
        if HAS_ACTION_SLOTS and obj.animation_data and obj.animation_data.action:
            prev_action = obj.animation_data.action
            prev_targets: set[ID] = set()

            if prev_action:
                for slot in prev_action.slots:
                    id_block = get_id_from_slot(slot)
                    if id_block is not None:
                        prev_targets.add(id_block)

            for id_block in prev_targets:
                ad = id_block.animation_data
                if ad is not None:
                    ad.action = None

        # assign new action:
        # active object
        assign_action_to_id(obj, action)

        # slot targets
        if HAS_ACTION_SLOTS:
            for slot in action.slots:
                assign_action_by_slot(action, slot)

        # optionally set timeline range
        if props.set_timeline_range:
            start, end = action.frame_range
            scene.frame_start = int(start)
            scene.frame_end = int(end)

        return {'FINISHED'}

class AS_MT_ObjectActionsMenu(bpy.types.Menu):
    bl_label = "Object Actions Menu"
    bl_idname = "AS_MT_ObjectActionsMenu"

    def draw(self, context):
        layout = self.layout

        # Sorting
        layout.operator("as_actions.object_sort_az",
                        text="Sort A–Z", icon="SORTALPHA")

        layout.separator()

        # Reordering
        layout.operator("as_actions.object_move_up",
                        text="Move Up", icon="TRIA_UP")
        layout.operator("as_actions.object_move_down",
                        text="Move Down", icon="TRIA_DOWN")

        layout.separator()

        # Removal
        layout.operator("as_actions.remove_from_object",
                        text="Remove", icon="X")

        layout.separator()
        layout.operator("as_actions.store_rest_pose",
                        text="Store Rest Pose", icon="ARMATURE_DATA")
        layout.operator(
            "as_actions.correct_bone_rotations",
            text="Correct Bone Rotations", icon="BONE_DATA"
        )
        

# Registration
classes = (
    AS_MT_ObjectActionsMenu,
    AS_UL_ObjectActions,
    AS_OT_ObjectActionsSelectAll,
    AS_OT_ObjectActionsSelectNone,
    AS_OT_AddActionToObject,
    AS_OT_RemoveActionFromObject,
    AS_OT_ApplyAction,
    AS_OT_ObjectActionsSortAZ,
    AS_OT_ObjectActionsMoveDown,
    AS_OT_ObjectActionsMoveUp,
)

def register():
    global HAS_ACTION_SLOTS
    HAS_ACTION_SLOTS = True if bpy.types.ActionSlot else False

    for cls in classes:
        bpy.utils.register_class(cls)
        
def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

