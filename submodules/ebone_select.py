import bpy
from .. import log

bl_info = {
    "name": "Edit Bone Select/Deselect Shortcuts",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Edit Mode (Armature) > Select\n"
        "Alt + Numpad + : Extend Child Bones\n"
        "Alt + Shift + Numpad + : Extend Parent Bones\n"
        "Alt + Numpad - : Reduce Child Bones\n"
        "Alt + Shift + Numpad - : Reduce Parent Bones"
    ),
    "description": (
        "Adds selection options in Armature Edit Mode to extend or\n"
        "reduce parent and child bones of all currently selected bones.\n"
        "Key bindings may be changed at Preferences > Keymap > 3D View > 3D View (Global)."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Rigging",
}


addon_keymaps = []


def poll_check(context):
    # Ensure we are in an armature in Edit Armature Mode.
    obj = context.active_object
    if not obj or obj.type != 'ARMATURE':
        return False
    if context.mode != 'EDIT_ARMATURE':
        return False
    return True


def get_edit_bones(context):
    obj = context.object
    if obj and obj.type == 'ARMATURE' and obj.mode == 'EDIT':
        return obj.data.edit_bones
    return None


class ARMATURE_OT_extend_children(bpy.types.Operator):
    bl_idname = "armature.select_child_ebones"
    bl_label = "Extend Child Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ebones = get_edit_bones(context)
        if not ebones:
            return {'CANCELLED'}
        # Gather children to select
        to_select = []
        for bone in ebones:
            if bone.select or bone.select_head or bone.select_tail:
                to_select.extend(bone.children)

        # select them
        for child in to_select:
            child.select = True
            child.select_head = True
            child.select_tail = True
        return {'FINISHED'}
    
    @classmethod
    def poll(cls, context):
        return poll_check(context)


class ARMATURE_OT_extend_parents(bpy.types.Operator):
    bl_idname = "armature.select_parent_ebones"
    bl_label = "Extend Parent Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ebones = get_edit_bones(context)
        if not ebones:
            return {'CANCELLED'}
        to_select = []
        for bone in ebones:
            if (bone.select or bone.select_head or bone.select_tail) and bone.parent:
                to_select.append(bone.parent)

        for parent in to_select:
            parent.select = True
            parent.select_head = True
            parent.select_tail = True
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return poll_check(context)


class ARMATURE_OT_reduce_children(bpy.types.Operator):
    bl_idname = "armature.deselect_child_ebones"
    bl_label = "Reduce Child Bones"
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
        return poll_check(context)


class ARMATURE_OT_reduce_parents(bpy.types.Operator):
    bl_idname = "armature.deselect_parent_ebones"
    bl_label = "Reduce Parent Bones"
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
        return poll_check(context)


classes = (
    ARMATURE_OT_extend_children,
    ARMATURE_OT_reduce_children,
    ARMATURE_OT_reduce_parents,
    ARMATURE_OT_extend_parents
)


def menu_func(self, context):
    self.layout.operator(ARMATURE_OT_extend_parents.bl_idname)
    self.layout.operator(ARMATURE_OT_reduce_parents.bl_idname)
    self.layout.operator(ARMATURE_OT_extend_children.bl_idname)
    self.layout.operator(ARMATURE_OT_reduce_children.bl_idname)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.VIEW3D_MT_select_edit_armature.append(menu_func)

    # Keymaps
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        name = '3D View'
        
        if name not in kc.keymaps:
            _ = kc.keymaps.new(name, space_type='VIEW_3D')

        km = kc.keymaps[name]

        kmi = km.keymap_items.new(
            ARMATURE_OT_extend_children.bl_idname, type='NUMPAD_PLUS', value='PRESS', alt=True)
        addon_keymaps.append((km, kmi))
        
        kmi = km.keymap_items.new(
            ARMATURE_OT_reduce_children.bl_idname, type='NUMPAD_MINUS', value='PRESS', alt=True)
        addon_keymaps.append((km, kmi))
        
        kmi = km.keymap_items.new(
            ARMATURE_OT_extend_parents.bl_idname, type='NUMPAD_PLUS', value='PRESS', alt=True, shift=True)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new(
            ARMATURE_OT_reduce_parents.bl_idname, type='NUMPAD_MINUS', value='PRESS', alt=True, shift=True)
        addon_keymaps.append((km, kmi))


def unregister():
    bpy.types.VIEW3D_MT_select_edit_armature.remove(menu_func)

    # Remove keymaps
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
