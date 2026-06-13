from bmesh.types import BMesh
from bpy.props import (
    StringProperty,
    IntProperty,
    CollectionProperty,
)
from bpy.types import (
    Operator,
    Panel,
    PropertyGroup,
    UIList,
)
import bmesh
import bpy
bl_info = {
    "name": "Selections Manager",
    "author": "Generated",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Item",
    "description": (
        "Store and restore mesh selection states using custom element layers.\n"
        "Shows and Hides the selections.\n"
    ),
    "category": "Mesh",
}


# Prefix used for custom layers
LAYER_PREFIX = "__SSM__"  # Selection States Manager prefix
MODE_TOKEN = "::mode="


# ---------- Utilities ----------

def get_bmesh_and_mesh(context):
    obj = context.edit_object
    if not obj or obj.type != 'MESH':
        return None, None
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    return bm, me


def encode_layer_name(user_name: str, mode: str) -> tuple[str, str, str]:
    # base name, without domain suffix
    safe_name = user_name.replace("::", "_")
    return (
        f"{LAYER_PREFIX}{safe_name}{MODE_TOKEN}{mode}_v",
        f"{LAYER_PREFIX}{safe_name}{MODE_TOKEN}{mode}_e",
        f"{LAYER_PREFIX}{safe_name}{MODE_TOKEN}{mode}_f"
    )


def detect_current_mode(context):
    # context.tool_settings.mesh_select_mode is a tuple (v,e,f)
    v, e, f = context.tool_settings.mesh_select_mode
    if v and not e and not f:
        return "VERT"
    if e and not v and not f:
        return "EDGE"
    if f and not v and not e:
        return "FACE"
    return "VERT"


def set_selection_mode(context, mode: str):
    if mode == "VERT":
        context.tool_settings.mesh_select_mode = (True, False, False)
    elif mode == "EDGE":
        context.tool_settings.mesh_select_mode = (False, True, False)
    elif mode == "FACE":
        context.tool_settings.mesh_select_mode = (False, False, True)


def ensure_int_layer(bm: BMesh, names: tuple[str, str, str]):
    v_name, e_name, f_name = names
    v_layer = bm.verts.layers.int.get(v_name)
    if v_layer is None:
        v_layer = bm.verts.layers.int.new(v_name)

    e_layer = bm.edges.layers.int.get(e_name)
    if e_layer is None:
        e_layer = bm.edges.layers.int.new(e_name)

    f_layer = bm.faces.layers.int.get(f_name)
    if f_layer is None:
        f_layer = bm.faces.layers.int.new(f_name)

    return v_layer, e_layer, f_layer


# ---------- Property Group for UI list ----------

class SSM_Item(PropertyGroup):
    display_name: StringProperty(name="Name")
    layer_name_v: StringProperty(name="LayerNameVertex")
    layer_name_e: StringProperty(name="LayerNameEdge")
    layer_name_f: StringProperty(name="LayerNameFace")
    mode: StringProperty(name="Mode")


# ---------- UI List ----------

class VIEW3D_UL_selstates(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # item is SSM_Item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=item.display_name)
            row.label(text=item.mode)
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.display_name)


# ---------- Operators ----------

class SSM_OT_add_selection(Operator):
    bl_idname = "mesh.ssm_add_selection"
    bl_label = "Add Selection State"
    bl_description = "Store the current selection as a named selection state"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(name="Selection Name", default="NewState")

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=300)

    def execute(self, context):
        bm, mesh = get_bmesh_and_mesh(context)
        if bm is None:
            self.report({'ERROR'}, "No edit mesh found")
            return {'CANCELLED'}

        mode = detect_current_mode(context)
        layer_names = encode_layer_name(self.name, mode)

        v_layer, e_layer, f_layer = ensure_int_layer(bm, layer_names)

        # Store selection on all element types
        for v in bm.verts:
            v[v_layer] = 1 if v.select else 0
        for e in bm.edges:
            e[e_layer] = 1 if e.select else 0
        for f in bm.faces:
            f[f_layer] = 1 if f.select else 0

        bmesh.update_edit_mesh(
            mesh=mesh, loop_triangles=False, destructive=False)

        # Update mesh collection for UI
        # check if already exists
        ssm_item: None | SSM_Item = None
        for item in mesh.ssm_items:
            if item.display_name == self.name:
                ssm_item = item

        if not ssm_item:
            ssm_item = mesh.ssm_items.add()
            ssm_item.display_name = self.name
            # index to end where it was appended
            mesh.ssm_index = len(mesh.ssm_items) - 1

        ssm_item.mode = mode
        ssm_item.layer_name_v, ssm_item.layer_name_e, ssm_item.layer_name_f = layer_names

        return {'FINISHED'}


class SSM_OT_remove_selection(Operator):
    bl_idname = "mesh.ssm_remove_selection"
    bl_label = "Remove Selection State"
    bl_description = "Remove the selected stored selection state (deletes the custom layers)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        bm, mesh = get_bmesh_and_mesh(context)
        if bm is None:
            self.report({'ERROR'}, "No edit mesh found")
            return {'CANCELLED'}

        idx = mesh.ssm_index
        if idx < 0 or idx >= len(mesh.ssm_items):
            self.report({'ERROR'}, "No selection state highlighted")
            return {'CANCELLED'}

        ssm_item: SSM_Item = mesh.ssm_items[idx]

        v_layer = bm.verts.layers.int.get(ssm_item.layer_name_v)
        if v_layer is not None:
            bm.verts.layers.int.remove(v_layer)
        e_layer = bm.edges.layers.int.get(ssm_item.layer_name_e)
        if e_layer is not None:
            bm.edges.layers.int.remove(e_layer)
        f_layer = bm.faces.layers.int.get(ssm_item.layer_name_f)
        if f_layer is not None:
            bm.faces.layers.int.remove(f_layer)

        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)

        # update UI list
        mesh.ssm_items.remove(mesh.ssm_index)

        # index to previous if not first
        if mesh.ssm_index > 0:
            mesh.ssm_index -= 1

        return {'FINISHED'}


class SSM_OT_clear_all(Operator):
    bl_idname = "mesh.ssm_clear_all"
    bl_label = "Clear All Selection State Layers"
    bl_description = "Remove all mesh custom layers created by the Selection States Manager"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        bm, mesh = get_bmesh_and_mesh(context)
        if bm is None:
            self.report({'ERROR'}, "No edit mesh found")
            return {'CANCELLED'}

        # Collect all layer names across domains
        vert_layers = list(bm.verts.layers.int.keys())
        edge_layers = list(bm.edges.layers.int.keys())
        face_layers = list(bm.faces.layers.int.keys())

        # Remove only layers with our prefix
        for name in vert_layers:
            if name.startswith(LAYER_PREFIX):
                v = bm.verts.layers.int.get(name)
                if v:
                    bm.verts.layers.int.remove(v)

        for name in edge_layers:
            if name.startswith(LAYER_PREFIX):
                e = bm.edges.layers.int.get(name)
                if e:
                    bm.edges.layers.int.remove(e)

        for name in face_layers:
            if name.startswith(LAYER_PREFIX):
                f = bm.faces.layers.int.get(name)
                if f:
                    bm.faces.layers.int.remove(f)

        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)

        # Clear UI list
        mesh.ssm_items.clear()
        mesh.ssm_index = 0

        self.report({'INFO'}, "All Selection State layers removed")
        return {'FINISHED'}


class Operator_Common(Operator):
    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'
    
    def execute(self, context):
        bm, mesh = get_bmesh_and_mesh(context)
        if bm is None:
            self.report({'ERROR'}, "No edit mesh found")
            return {'CANCELLED'}

        idx = mesh.ssm_index
        if idx < 0 or idx >= len(mesh.ssm_items):
            self.report({'ERROR'}, "No selection state highlighted")
            return {'CANCELLED'}

        ssm_item: SSM_Item = mesh.ssm_items[idx]

        v_layer = bm.verts.layers.int.get(ssm_item.layer_name_v)
        e_layer = bm.edges.layers.int.get(ssm_item.layer_name_e)
        f_layer = bm.faces.layers.int.get(ssm_item.layer_name_f)

        self.execute_logic(context, bm, v_layer, e_layer, f_layer)
        
        # Optionally restore selection mode
        if context.scene.ssm_restore_mode:
            set_selection_mode(context, item.mode)

        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        return {'FINISHED'}


class SSM_OT_restore_absolute(Operator_Common):
    bl_idname = "mesh.ssm_restore_absolute"
    bl_label = "Restore Selection Absolute"
    bl_description = "Replace current selection with the stored selection (and optionally restore selection mode)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute_logic(self, context, bm, v_layer, e_layer, f_layer):
        # Deselect all first
        bpy.ops.mesh.select_all(action='DESELECT')

        # Select only those with value 1
        if v_layer:
            for v in bm.verts:
                if v[v_layer] == 1:
                    v.select = True
        if e_layer:
            for e in bm.edges:
                if e[e_layer] == 1:
                    e.select = True
        if f_layer:
            for f in bm.faces:
                if f[f_layer] == 1:
                    f.select = True
        

class SSM_OT_add_to_selection(Operator_Common):
    bl_idname = "mesh.ssm_add_to_selection"
    bl_label = "Add Stored to Selection"
    bl_description = "Add the stored selection elements to the current selection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute_logic(self, context, bm, v_layer, e_layer, f_layer):
        if v_layer:
            for v in bm.verts:
                if v[v_layer] == 1:
                    v.select = True
        if e_layer:
            for e in bm.edges:
                if e[e_layer] == 1:
                    e.select = True
        if f_layer:
            for f in bm.faces:
                if f[f_layer] == 1:
                    f.select = True


class SSM_OT_deselect_from_selection(Operator_Common):
    bl_idname = "mesh.ssm_deselect_from_selection"
    bl_label = "Deselect Stored from Selection"
    bl_description = "Deselect elements that are part of the stored selection from the current selection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute_logic(self, context, bm, v_layer, e_layer, f_layer):
        if v_layer:
            for v in bm.verts:
                if v[v_layer] == 1:
                    v.select = False
        if e_layer:
            for e in bm.edges:
                if e[e_layer] == 1:
                    e.select = False
        if f_layer:
            for f in bm.faces:
                if f[f_layer] == 1:
                    f.select = False


class SSM_OT_solo_selection(Operator_Common):
    bl_idname = "mesh.ssm_solo_selection"
    bl_label = "Solo Selection"
    bl_description = "Hide all geometry except the stored selection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute_logic(self, context, bm, v_layer, e_layer, f_layer):
        # Hide everything first
        for v in bm.verts:
            v.hide = True
        for e in bm.edges:
            e.hide = True
        for f in bm.faces:
            f.hide = True

        # Unhide only stored elements
        if v_layer:
            for v in bm.verts:
                if v[v_layer] == 1:
                    v.hide = False
        if e_layer:
            for e in bm.edges:
                if e[e_layer] == 1:
                    e.hide = False
        if f_layer:
            for f in bm.faces:
                if f[f_layer] == 1:
                    f.hide = False


class SSM_OT_hide_selection(Operator_Common):
    bl_idname = "mesh.ssm_hide_selection"
    bl_label = "Hide Selection"
    bl_description = "Hide the stored selection but keep other hide states unchanged"
    bl_options = {'REGISTER', 'UNDO'}

    def execute_logic(self, context, bm, v_layer, e_layer, f_layer):
        if v_layer:
            for v in bm.verts:
                if v[v_layer] == 1:
                    v.hide = True
        if e_layer:
            for e in bm.edges:
                if e[e_layer] == 1:
                    e.hide = True
        if f_layer:
            for f in bm.faces:
                if f[f_layer] == 1:
                    f.hide = True


class SSM_OT_unhide_selection(Operator_Common):
    bl_idname = "mesh.ssm_unhide_selection"
    bl_label = "Unhide Selection"
    bl_description = "Unhide the stored selection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute_logic(self, context, bm, v_layer, e_layer, f_layer):
        if v_layer:
            for v in bm.verts:
                if v[v_layer] == 1:
                    v.hide = False
        if e_layer:
            for e in bm.edges:
                if e[e_layer] == 1:
                    e.hide = False
        if f_layer:
            for f in bm.faces:
                if f[f_layer] == 1:
                    f.hide = False


# ---------- Panel ----------

class VIEW3D_PT_selstates_panel(Panel):
    bl_label = "Selection States Manager"
    bl_idname = "VIEW3D_PT_selstates_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        obj = context.edit_object
        if not obj or obj.type != 'MESH':
            layout.label(text="No mesh in edit mode")
            return
        me = obj.data

        row = layout.row()
        row.template_list("VIEW3D_UL_selstates", "", me,
                          "ssm_items", me, "ssm_index", rows=4)

        col = row.column(align=True)
        col.operator("mesh.ssm_add_selection", icon='ADD', text="")
        col.operator("mesh.ssm_remove_selection", icon='REMOVE', text="")
        
        layout.prop(context.scene, "ssm_restore_mode")

        # Buttons for actions
        layout.separator()
        row2 = layout.row(align=True)
        row2.operator("mesh.ssm_restore_absolute", text="Apply")
        row2.operator("mesh.ssm_add_to_selection", text="Add")
        row2.operator("mesh.ssm_deselect_from_selection", text="Subtract")
        
        layout.separator(factor=1.5)
        row = layout.row(align=True)
        row.operator("mesh.ssm_solo_selection", text="Solo")
        row.operator("mesh.ssm_hide_selection", text="Hide")
        row.operator("mesh.ssm_unhide_selection", text="Unhide")



# ---------- Registration ----------

classes = (
    SSM_Item,
    VIEW3D_UL_selstates,
    SSM_OT_add_selection,
    SSM_OT_remove_selection,
    SSM_OT_restore_absolute,
    SSM_OT_add_to_selection,
    SSM_OT_deselect_from_selection,
    SSM_OT_solo_selection,
    SSM_OT_hide_selection,
    SSM_OT_unhide_selection,
    SSM_OT_clear_all,
    VIEW3D_PT_selstates_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Mesh.ssm_items = CollectionProperty(type=SSM_Item)
    bpy.types.Mesh.ssm_index = IntProperty(default=0)
    bpy.types.Scene.ssm_restore_mode = bpy.props.BoolProperty(
        name="Restore Mode",
        description="Restore the selection mode stored with the selection state",
        default=True,
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    if hasattr(bpy.types.Scene, "ssm_restore_mode"):
        del bpy.types.Scene.ssm_restore_mode
    if hasattr(bpy.types.Mesh, "ssm_items"):
        del bpy.types.Mesh.ssm_items
    if hasattr(bpy.types.Mesh, "ssm_index"):
        del bpy.types.Mesh.ssm_index


if __name__ == "__main__":
    register()
