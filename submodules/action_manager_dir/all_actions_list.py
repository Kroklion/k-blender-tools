import bpy
from bpy.app.handlers import persistent

from bpy.types import (
    UIList,
    Operator,
)

class AS_UL_AllActions(UIList):
    """All actions in the blend file."""

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
        action: "AS_ActionListItem" = item
        row = layout.row(align=True)
        row.prop(action, "selected", text="")
        row.label(text=action.action.name if action.action else "(missing)")


class AS_OT_SelectAllActions(Operator):
    """Select all actions in the list."""
    bl_idname = "as_actions.select_all"
    bl_label = "Select All"
    bl_description = "Select all actions"

    def execute(self, context):
        props = context.scene.k_action_manager_props
        for item in props.all_actions_list_items:
            item.selected = True
        return {'FINISHED'}


class AS_OT_SelectNoneActions(Operator):
    """Deselect all actions in the list."""
    bl_idname = "as_actions.select_none"
    bl_label = "Select None"
    bl_description = "Deselect all actions"

    def execute(self, context):
        props = context.scene.k_action_manager_props
        for item in props.all_actions_list_items:
            item.selected = False
        return {'FINISHED'}


# Install the depsgraph handler only if the list is visible

def toggled_show_all_actions(self, context):
    handlers = bpy.app.handlers.depsgraph_update_post
    if self.show_all_actions:
        if k_action_manager_depsgraph_handler not in handlers:
            handlers.append(k_action_manager_depsgraph_handler)
            # force an initial sync
            k_action_manager_depsgraph_handler(
                context.scene, context.view_layer.depsgraph)
    else:
        if k_action_manager_depsgraph_handler in handlers:
            handlers.remove(k_action_manager_depsgraph_handler)


# All actions operator menu
class AS_MT_AllActionsMenu(bpy.types.Menu):
    bl_label = "All Actions Menu"
    bl_idname = "AS_MT_AllActionsMenu"

    def draw(self, context):
        layout = self.layout

        # Add to Object
        layout.operator("as_actions.add_to_object",
                        text="Add to Object", icon="ADD")

        # Rename
        layout.operator("as_actions.batch_rename",
                        text="Rename", icon="GREASEPENCIL")

        layout.operator("as_actions.fix_framerate",
                        text="Fix Framerate", icon="TIME")


def rebuild_all_actions_list(props: "PG_KActionManagerProperties"):
    action_list = props.all_actions_list_items

    # Current actions in Blender
    blender_actions = set(bpy.data.actions)

    # Step 1: Keep only valid items and remember selection state
    temp_items = []
    for item in action_list:
        if item.action in blender_actions:
            temp_items.append((item.action, item.selected))

    # Step 2: Add new actions that were not in the list
    existing_actions = {a for (a, _) in temp_items}

    for action in blender_actions:
        if action not in existing_actions:
            temp_items.append((action, False))

    # Step 3: Sort alphabetically by action name
    temp_items.sort(key=lambda pair: pair[0].name)

    # Step 4: Rebuild the collection cleanly
    action_list.clear()

    for action, selected in temp_items:
        new_item = action_list.add()
        new_item.action = action
        new_item.selected = selected


def k_action_manager_depsgraph_handler(scene, depsgraph):
    """Sync the 'All Actions' list with bpy.data.actions."""
    props = scene.k_action_manager_props
    action_list_items = props.all_actions_list_items

    # rebuild only if the list is visible
    if props.show_all_actions:
        rebuild_all_actions_list(props)


@persistent
def k_action_manager_post_load_handler(dummy):
    """Sync the 'All Actions' list after a blend file is loaded."""
    scene = bpy.context.scene
    props = scene.k_action_manager_props
    rebuild_all_actions_list(props)


# Registration
classes = (
    AS_MT_AllActionsMenu,
    AS_UL_AllActions,
    AS_OT_SelectAllActions,
    AS_OT_SelectNoneActions,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.app.handlers.load_post.append(k_action_manager_post_load_handler)


def unregister():
    handlers = bpy.app.handlers

    if k_action_manager_depsgraph_handler in handlers.depsgraph_update_post:
        handlers.depsgraph_update_post.remove(
            k_action_manager_depsgraph_handler)

    if k_action_manager_post_load_handler in handlers.load_post:
        handlers.load_post.remove(k_action_manager_post_load_handler)
        
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
