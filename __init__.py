import sys
import pkgutil
import importlib
import os

bl_info = {
    "name": "k-blender-tools",
    "author": "Kroklion",
    "version": (0, 1),
    "blender": (3, 0, 0),
    "location": "See Preferences > Addon entry",
    "description": "Collection of tools related to mesh editing, weight painting and rigging.",
    "warning": "",
    "doc_url": "",
    "category": "Convenience",
}


ADDON_NAME = __package__.split('.')[-1]

# Purge old modules on reload
if "bpy" in locals():
    # extension class
    if __name__ in sys.modules:
        print(f"del {__name__}")
        del sys.modules[__name__]
    
    prefix = __name__ + "."
    for mod in [m for m in sys.modules if m.startswith(prefix)]:
        del sys.modules[mod]

import bpy # After purge. Or Blender acts up.

from .settings import WPAddonPreferences, WPSubmoduleItem
from . import log

def discover_submodules():
    submodules_path = os.path.join(__path__[0], "submodules")
    prefs = WPAddonPreferences.get_instance()

    # Build lookup of existing persisted items
    persisted = {item.module: item for item in prefs.submodules}
    discovered = {}

    # Discover modules from filesystem
    for _, name, _ in pkgutil.iter_modules([submodules_path]):
        full_name = f"{__package__}.submodules.{name}"
        try:
            mod = importlib.import_module(full_name)
        except Exception:
            log.error(f"Failed to import submodule '{name}'", exc_info=True)
            continue

        if not (hasattr(mod, "register") and hasattr(mod, "unregister")):
            continue

        bl_info = getattr(mod, "bl_info", {})
        try:
            discovered[name] = {
                "name": bl_info.get("name", name),
                "description": bl_info.get("description", "No description available."),
                "location": bl_info.get("location", "Unknown"),
                "category": bl_info.get("category", "Unknown")
            }
        except Exception:
            log.error(f"Failed to read bl_info of module '{name}'", exc_info=True)
            continue

    # Synchronize: remove stale modules
    for i in reversed(range(len(prefs.submodules))):
        item = prefs.submodules[i]
        if item.module not in discovered:
            prefs.submodules.remove(i)

    # Synchronize: update or add discovered modules
    for module_id, info in discovered.items():
        if module_id in persisted:
            item = persisted[module_id]
            item.name = info["name"]
            item.description = info["description"]
            item.location = info["location"]
            item.category = info["category"]
        else:
            item = prefs.submodules.add()
            item.module = module_id
            item.name = info["name"]
            item.description = info["description"]
            item.location = info["location"]
            item.category = info["category"]
            item.enabled = True  # default activation


def module_activation_cb(item):
    log.debug(f"module_activation_cb: module {item.module}, enabled {item.enabled}")
    switch_module(item, False)

def switch_module(item, deactivate):
    module_id = item.module
    full_module_path = f"{__package__}.submodules.{module_id}"

    try:
        mod = importlib.import_module(full_module_path)
    except Exception:
        log.error(f"Failed to import module '{module_id}'", exc_info=True)
        return
    
    if item.enabled and not deactivate:
        try:
            mod.register()
            item.status = "Active"
            item.error = False
            log.info(f"Module '{module_id}' registered.")
        except Exception:
            log.error(
                f"Failed to register module '{module_id}'", exc_info=True)
            item.status = "Activation failed"
            item.error = True
            
    elif not item.enabled or (item.enabled and deactivate):
        try:
            mod.unregister()
            item.status = "Inactive"
            item.error = False
            log.info(f"Module '{module_id}' unregistered.")
        except Exception:
            log.error(
                f"Failed to unregister module '{module_id}'", exc_info=True)
            item.status = "Deactivation failed"
            item.error = True

def register():
    log.init_logger(ADDON_NAME)
    bpy.utils.register_class(WPSubmoduleItem)
    bpy.utils.register_class(WPAddonPreferences)
    log.setup_preferences_cb(WPAddonPreferences)
    
    discover_submodules()
    
    WPAddonPreferences.register_callback(
        "module_activation", module_activation_cb)
    
    for item in WPAddonPreferences.get_instance().submodules:
        if item.enabled:  # startup, don't attempt to deactivate here
            switch_module(item, False)

    log.info("Add-on registered.")


def unregister():
    log.info("Add-on unregistering.")
    WPAddonPreferences.unregister_callback(
        "module_activation", module_activation_cb)

    # Reverse order is often safer
    for item in reversed(WPAddonPreferences.get_instance().submodules):
        if item.enabled:  # startup, don't attempt to deactivate here
            switch_module(item, True)

    bpy.utils.unregister_class(WPAddonPreferences)
    bpy.utils.unregister_class(WPSubmoduleItem)
    log.uninit_logger(WPAddonPreferences)

