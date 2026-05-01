import bpy

from bpy.types import (
    Object,
    Scene,
)

from bpy.props import (
    CollectionProperty,
    IntProperty,
    BoolProperty,
    PointerProperty
)
from bpy.types import (
    PropertyGroup,
    Action,
)

from .all_actions_list import toggled_show_all_actions

class AS_ActionListItem(PropertyGroup):
    """Data for the 'All Actions' list"""
    selected: BoolProperty(default=False)
    action: PointerProperty(name="Action", type=Action)


# global data storage for this module
class PG_KActionManagerProperties(PropertyGroup):
    all_actions_list_items: CollectionProperty(type=AS_ActionListItem)
    all_actions_index: IntProperty(default=0)
    show_all_actions: BoolProperty(
        name="All Actions",
        default=True,
        update=toggled_show_all_actions
    )

    show_object_actions: BoolProperty(
        name="Object Actions",
        default=True
    )

    set_timeline_range: BoolProperty(
        name="Set Timeline Range",
        description="Set global timeline range from Action on Apply",
        default=True
    )
    
    pin_object: BoolProperty(
        name="Pin Object Actions",
        description="Display the specified object even if it's not selected",
        default=False
    )
    pinned_object: PointerProperty(
        name="Pinned Object",
        type=Object,
        description="If pinned, always show the actions for this object in the list. Otherwise show the list of the current object."
    )


def get_reference_object(context):
    props = context.scene.k_action_manager_props
    if props.pin_object:
        return props.pinned_object
    else:
        return context.active_object if context.selected_objects else None


# Registration
classes = (
    AS_ActionListItem,
    PG_KActionManagerProperties,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    Object.as_actions = CollectionProperty(type=AS_ActionListItem)
    Object.as_actions_index = IntProperty(default=0)

    Scene.k_action_manager_props = PointerProperty(
        type=PG_KActionManagerProperties)

def unregister():
    del Scene.k_action_manager_props

    del Object.as_actions_index
    del Object.as_actions

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
