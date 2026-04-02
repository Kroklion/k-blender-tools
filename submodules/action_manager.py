import bpy

import pkgutil
import importlib
import os
from .. import log

from bpy.types import (
    Panel,
)

from .action_manager_dir.data import get_reference_object

bl_info = {
    "name": "Action Tools",
    "author": "",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Animation tab",
    "description": "Associate actions to objects, contains action-related tools",
    "category": "Animation",
}


# Panel
class AS_PT_ActionAssignmentPanel(Panel):
    bl_label = "Action Slots"
    bl_idname = "AS_PT_action_slots"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Animation"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        obj = get_reference_object(context)
        props = context.scene.k_action_manager_props

        col = layout.column(align=True)

        # Object Actions
        if (context.active_object is not None and context.selected_objects) or props.pin_object:
            box = col.box()
            box.prop(
                props,
                "show_object_actions",
                text="Object Actions",
                icon="TRIA_DOWN" if props.show_object_actions else "TRIA_RIGHT",
                emboss=False
            )

            if props.show_object_actions:
                # object pinning
                row = box.row()

                row.prop(
                    props,
                    "pinned_object",
                    text="",
                    # icon="TRIA_DOWN" if props.show_object_actions else "TRIA_RIGHT",
                    # emboss=False
                )

                row.prop(
                    props,
                    "pin_object",
                    text="",
                    icon="PINNED",
                    # emboss=False
                )

                if obj:

                    row = box.row()

                    # Left: the list
                    row.template_list(
                        "AS_UL_ObjectActions",
                        "",
                        obj,
                        "as_actions",
                        obj,
                        "as_actions_index",
                        rows=3,
                    )

                    # Right: vertical buttons
                    col_buttons = row.column(align=True)

                    # All / None buttons (icon only)
                    col_buttons.operator(
                        "as_actions.object_select_all",
                        text="",
                        icon="CHECKBOX_HLT"
                    )
                    col_buttons.operator(
                        "as_actions.object_select_none",
                        text="",
                        icon="CHECKBOX_DEHLT"
                    )

                    # Dropdown menu (Remove, etc.)
                    col_buttons.menu(
                        "AS_MT_ObjectActionsMenu",
                        text="",
                        icon="DOWNARROW_HLT"
                    )

                    # Spacer to align Apply button visually
                    col_buttons.separator()

                    # Apply button (frequently used)
                    col_buttons.operator(
                        "as_actions.apply",
                        text="",
                        icon="PLAY"
                    )

                    # Timeline range toggle
                    box.prop(props, "set_timeline_range", text="Set Range")

        # All Actions
        box = layout.box()
        box.prop(
            props,
            "show_all_actions",
            icon="TRIA_DOWN" if props.show_all_actions else "TRIA_RIGHT",
            emboss=False
        )

        if props.show_all_actions:
            row = box.row()

            # Left: the list
            row.template_list(
                "AS_UL_AllActions",
                "",
                props,
                "all_actions_list_items",
                props,
                "all_actions_index",
                rows=4,
            )

            # Right: vertical button column
            col_buttons = row.column(align=True)

            # All / None buttons (icon only)
            col_buttons.operator(
                "as_actions.select_all",
                text="",
                icon="CHECKBOX_HLT"
            )
            col_buttons.operator(
                "as_actions.select_none",
                text="",
                icon="CHECKBOX_DEHLT"
            )

            # Dropdown menu button
            col_buttons.menu(
                "AS_MT_AllActionsMenu",
                text="",
                icon="DOWNARROW_HLT"
            )


modules = []


def discover_submodules():
    submodules_path = os.path.join(
        os.path.dirname(__file__), "action_manager_dir")

    # Discover modules from filesystem
    for _, name, _ in pkgutil.iter_modules([submodules_path]):
        full_name = f"{__package__}.action_manager_dir.{name}"
        try:
            mod = importlib.import_module(full_name)
        except Exception:
            log.error(f"Failed to import submodule '{name}'", exc_info=True)
            continue

        if not (hasattr(mod, "register") and hasattr(mod, "unregister")):
            continue
        modules.append(mod)


# Registration
classes = (
    AS_PT_ActionAssignmentPanel,
)


def register():
    discover_submodules()

    for mod in modules:
        mod.register()

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    for mod in reversed(modules):
        mod.unregister()


if __name__ == "__main__":
    register()
