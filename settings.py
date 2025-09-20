import bpy
from bpy.types import AddonPreferences, PropertyGroup

from . import log


from bpy.props import StringProperty, BoolProperty, CollectionProperty


def update_module_enabled(self, context):
    for callback in WPAddonPreferences.callbacks.get("module_activation", []):
        callback(self)


class WPSubmoduleItem(PropertyGroup):
    module: StringProperty(name="ModuleId")
    name: StringProperty(name="Name")
    description: StringProperty(name="Description", default="")
    location: StringProperty(name="Location", default="")
    enabled: BoolProperty(name="Enabled", default=True, update=update_module_enabled)
    status: StringProperty(name="Status", default="")
    error: BoolProperty(name="Error", default=False)
    category: StringProperty(name="Category", default="")


def update_inner(self, variable_name):
    if variable_name in WPAddonPreferences.callbacks:
        for callback in WPAddonPreferences.callbacks.get(variable_name, []):
            callback(getattr(self, variable_name))
    else:
        log.warning("No callback set for: " + variable_name)

class WPAddonPreferences(AddonPreferences):
    bl_idname = __package__
    
    submodules: CollectionProperty(type=WPSubmoduleItem)
    
    debug_level : bpy.props.EnumProperty(
        name = "Debug Log Level",
        description = "Which log level to write in the console for addon debugging.",
        items = [
            ('CRITICAL', 'Off', ''),
            ('ERROR', 'Error', ''),
            ('WARNING', 'Warning', ''),
            ('INFO', 'Info', ''),
            ('DEBUG', 'Debug', '')
        ],
        update=lambda self, ctx: update_inner(self, 'debug_level')
    )
    
    @staticmethod
    def get_instance(context: bpy.types.Context = None) -> 'WPAddonPreferences':
        prefs = (
            context or bpy.context).preferences.addons[__package__].preferences
        assert isinstance(prefs, WPAddonPreferences)
        return prefs
    
    callbacks = {}
    
    @staticmethod
    def register_callback(prop_name, callback):
        if prop_name not in WPAddonPreferences.callbacks:
            WPAddonPreferences.callbacks[prop_name] = []
        WPAddonPreferences.callbacks[prop_name].append(callback)
        
        if prop_name != "module_activation":
            # call back immediately with initial value
            prefs = WPAddonPreferences.get_instance()
            value = getattr(prefs, prop_name)
            callback(value)
        
    @staticmethod
    def unregister_callback(prop_name, callback):
        if prop_name in WPAddonPreferences.callbacks and callback in WPAddonPreferences.callbacks[prop_name]:
            WPAddonPreferences.callbacks[prop_name].remove(callback)
            if not WPAddonPreferences.callbacks[prop_name]:
                del WPAddonPreferences.callbacks[prop_name]

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'debug_level')

        layout.label(text="Submodules:")
        for item in self.submodules:
            box = layout.box()
            box.alert = item.error
            box.prop(item, "enabled", text=item.name)
            box.label(text=f"Status: {item.status}")
            box.label(text=f"Category: {item.category}")
            for line in item.description.split('\n'):
                box.label(text=line)
            
            if '\n' in item.location:
                box.label(text="Location:")
                for line in item.location.split('\n'):
                    box.label(text=line)
            else:
                box.label(text=f"Location: {item.location}")
            
