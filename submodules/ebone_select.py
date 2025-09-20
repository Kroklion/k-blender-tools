import bpy
from .. import log

bl_info = {
    "name": "Edit Bone Select/Deselect Shortcuts",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Edit Mode (Armature)\n"
        "Alt + Numpad + : Select Child Bones\n"
        "Alt + Shift + Numpad + : Select Parent Bones\n"
        "Alt + Numpad - : Deselect Child Bones\n"
        "Alt + Shift + Numpad - : Deselect Parent Bones"
    ),
    "description": (
        "Adds convenient shortcuts in Armature Edit Mode to quickly select or\n"
        "deselect parent and child bones using Numpad +/- with Alt and Shift modifiers.\n"
        "Key bindings may be changed at Preferences > Keymap > 3D View > 3D View (Global)."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Rigging",
}


addon_keymaps = []


def get_edit_bones(context):
    obj = context.object
    if obj and obj.type == 'ARMATURE' and obj.mode == 'EDIT':
        return obj.data.edit_bones
    return None


class ARMATURE_OT_select_child(bpy.types.Operator):
    bl_idname = "armature.select_child_ebones"
    bl_label = "Select Child Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        log.info("armature.select_child_ebones")
        ebones = get_edit_bones(context)
        if not ebones:
            return {'CANCELLED'}
        # Gather children to select
        to_select = set()
        for bone in ebones:
            if bone.select:
                to_select.update(bone.children)
        for child in to_select:
            child.select = True
        return {'FINISHED'}
    
    @classmethod
    def poll(cls, context):
        # Ensure we are in an armature in Edit Armature Mode.
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            return False
        if context.mode != 'EDIT_ARMATURE':
            return False
        return True


class ARMATURE_OT_select_parent(bpy.types.Operator):
    bl_idname = "armature.select_parent_ebones"
    bl_label = "Select Parent Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ebones = get_edit_bones(context)
        if not ebones:
            return {'CANCELLED'}
        to_select = set()
        for bone in ebones:
            if bone.select and bone.parent:
                to_select.add(bone.parent)
        for parent in to_select:
            parent.select = True
        return {'FINISHED'}
    
    @classmethod
    def poll(cls, context):
        # Ensure we are in an armature in Edit Armature Mode.
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            return False
        if context.mode != 'EDIT_ARMATURE':
            return False
        return True


class ARMATURE_OT_deselect_child(bpy.types.Operator):
    bl_idname = "armature.deselect_child_ebones"
    bl_label = "Deselect Child Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ebones = get_edit_bones(context)
        if not ebones:
            return {'CANCELLED'}
        to_deselect = set()
        for bone in ebones:
            if bone.select: 
                keep = False
                for subbone in bone.children:
                   if subbone.select:
                       keep = True
                       break
                if not keep:
                    to_deselect.add(bone)
                
        for bone in to_deselect:
            bone.select = False
            bone.select_head = False
            bone.select_tail = False
        return {'FINISHED'}
    
    @classmethod
    def poll(cls, context):
        # Ensure we are in an armature in Edit Armature Mode.
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            return False
        if context.mode != 'EDIT_ARMATURE':
            return False
        return True


class ARMATURE_OT_deselect_parent(bpy.types.Operator):
    bl_idname = "armature.deselect_parent_ebones"
    bl_label = "Deselect Parent Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ebones = get_edit_bones(context)
        if not ebones:
            return {'CANCELLED'}
        to_deselect = set()
        
        for bone in ebones:
            if bone.select:
                if not bone.parent or not bone.parent.select:
                    to_deselect.add(bone)
                    
        for bone in to_deselect:
            bone.select = False
            bone.select_head = False
            bone.select_tail = False
        return {'FINISHED'}
    
    @classmethod
    def poll(cls, context):
        # Ensure we are in an armature in Edit Armature Mode.
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            return False
        if context.mode != 'EDIT_ARMATURE':
            return False
        return True


classes = (
    ARMATURE_OT_select_child,
    ARMATURE_OT_select_parent,
    ARMATURE_OT_deselect_child,
    ARMATURE_OT_deselect_parent,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Keymaps
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        name = '3D View'
        
        if name not in kc.keymaps:
            _ = kc.keymaps.new(name, space_type='VIEW_3D')

        km = kc.keymaps[name]
        
        
        kmi = km.keymap_items.new(
            ARMATURE_OT_select_child.bl_idname, type='NUMPAD_PLUS', value='PRESS', alt=True)
        addon_keymaps.append((km, kmi))
        
        kmi = km.keymap_items.new(
            ARMATURE_OT_select_parent.bl_idname, type='NUMPAD_PLUS', value='PRESS', alt=True, shift=True)
        addon_keymaps.append((km, kmi))
        
        kmi = km.keymap_items.new(
            ARMATURE_OT_deselect_child.bl_idname, type='NUMPAD_MINUS', value='PRESS', alt=True)
        addon_keymaps.append((km, kmi))
        
        kmi = km.keymap_items.new(
            ARMATURE_OT_deselect_parent.bl_idname, type='NUMPAD_MINUS', value='PRESS', alt=True, shift=True)
        addon_keymaps.append((km, kmi))


def unregister():
    # Remove keymaps
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
