import bpy

bl_info = {
    "name": "Cursor Presets",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D View > Sidebar (N) > View Tab > 3D Cursor Panel",
    "description": (
        "Save and restore 3D Cursor transforms. "
        "Allows storing multiple presets of cursor location and rotation, "
        "and applying them later. Includes auto-apply option when switching presets."
    ),
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}


# -------------------------------------------------------------------
# Define a property group to store cursor presets
# -------------------------------------------------------------------
class CursorPreset(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="Preset")
    location: bpy.props.FloatVectorProperty(name="Location", size=3)
    rotation: bpy.props.FloatVectorProperty(name="Rotation", size=3)


# -------------------------------------------------------------------
# UIList to display presets
# -------------------------------------------------------------------
class CURSOR_UL_presets(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # Each row in the list
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon_value=icon)
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name)


# --- Update functions ---
def update_auto_apply(self, context):
    """Called when checkbox changes"""
    if context.scene.auto_apply_cursor:
        apply_current_preset(context)


def update_index(self, context):
    """Called when list index changes"""
    if context.scene.auto_apply_cursor:
        apply_current_preset(context)


def apply_current_preset(context):
    scene = context.scene
    idx = scene.cursor_presets_index
    if scene.cursor_presets and 0 <= idx < len(scene.cursor_presets):
        preset = scene.cursor_presets[idx]
        cursor = scene.cursor
        cursor.location = preset.location
        cursor.rotation_euler = preset.rotation


# -------------------------------------------------------------------
# Operators
# -------------------------------------------------------------------
class CURSOR_OT_add_preset(bpy.types.Operator):
    bl_idname = "cursor_preset.add"
    bl_label = "Add Cursor Preset"

    def execute(self, context):
        scene = context.scene
        cursor = scene.cursor

        new_item = scene.cursor_presets.add()
        new_item.name = f"Preset {len(scene.cursor_presets)}"
        new_item.location = cursor.location
        new_item.rotation = cursor.rotation_euler

        scene.cursor_presets_index = len(scene.cursor_presets) - 1
        return {'FINISHED'}


class CURSOR_OT_remove_preset(bpy.types.Operator):
    bl_idname = "cursor_preset.remove"
    bl_label = "Remove Cursor Preset"

    def execute(self, context):
        scene = context.scene
        idx = scene.cursor_presets_index

        if scene.cursor_presets and idx < len(scene.cursor_presets):
            scene.cursor_presets.remove(idx)
            scene.cursor_presets_index = min(
                max(0, idx - 1), len(scene.cursor_presets) - 1)

        return {'FINISHED'}


class CURSOR_OT_apply_preset(bpy.types.Operator):
    bl_idname = "cursor_preset.apply"
    bl_label = "Apply Cursor Preset"

    def execute(self, context):
        scene = context.scene
        idx = scene.cursor_presets_index

        if scene.cursor_presets and idx < len(scene.cursor_presets):
            preset = scene.cursor_presets[idx]
            cursor = scene.cursor
            cursor.location = preset.location
            cursor.rotation_euler = preset.rotation

        return {'FINISHED'}


# -------------------------------------------------------------------
# Extend the 3D Cursor panel
# -------------------------------------------------------------------
class VIEW3D_PT_cursor_presets(bpy.types.Panel):
    bl_label = "Cursor Presets"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'View'
    # This makes it a child panel of the 3D Cursor panel
    bl_parent_id = "VIEW3D_PT_view3d_cursor"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row()
        row.template_list("CURSOR_UL_presets", "", scene,
                          "cursor_presets", scene, "cursor_presets_index")

        col = row.column(align=True)
        col.operator("cursor_preset.add", icon="ADD", text="")
        col.operator("cursor_preset.remove", icon="REMOVE", text="")

        layout.operator("cursor_preset.apply", text="Apply Selected Preset")
        layout.prop(scene, "auto_apply_cursor")


def draw_cursor_presets(self, context):
    layout = self.layout
    scene = context.scene

    row = layout.row()
    row.template_list("CURSOR_UL_presets", "", scene,
                      "cursor_presets", scene, "cursor_presets_index")

    col = row.column(align=True)
    col.operator("cursor_preset.add", icon="ADD", text="")
    col.operator("cursor_preset.remove", icon="REMOVE", text="")

    layout.operator("cursor_preset.apply", text="Apply Selected Preset")
    layout.prop(scene, "auto_apply_cursor")


# -------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------
classes = (
    CursorPreset,
    CURSOR_UL_presets,
    CURSOR_OT_add_preset,
    CURSOR_OT_remove_preset,
    CURSOR_OT_apply_preset,
    VIEW3D_PT_cursor_presets
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.cursor_presets = bpy.props.CollectionProperty(
        type=CursorPreset)
    bpy.types.Scene.cursor_presets_index = bpy.props.IntProperty(
        default=0,
        update=update_index)

    bpy.types.Scene.auto_apply_cursor = bpy.props.BoolProperty(
        name="Auto Apply Preset",
        description="Automatically apply preset when selection changes",
        default=False,
        update=update_auto_apply)


def unregister():
    bpy.types.VIEW3D_PT_view3d_cursor.remove(draw_cursor_presets)

    del bpy.types.Scene.cursor_presets
    del bpy.types.Scene.cursor_presets_index

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
