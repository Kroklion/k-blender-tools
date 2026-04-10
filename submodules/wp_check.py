from bpy.props import StringProperty, BoolProperty
import re
from typing import Any
import bpy
import bmesh

bl_info = {
    "name": "WPCheck – Vertex Group Weight Inspector",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Sidebar (N) > Edit Tab > WPCheck Panel\n"
        "Available in Edit Mode and Weight Paint Mode"
    ),
    "description": (
        "Provides a panel to inspect and manage vertex group weights of selected\n"
        "vertices. Features include filtering groups, selecting/deselecting,\n"
        "deleting or zeroing weights, and applying math operations to weights."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}


from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    CollectionProperty,
    PointerProperty
)
from bpy.types import (
    Panel,
    Operator,
    PropertyGroup,
    UIList
)

from .. import log


def format_weight(value):
    if value == 0:
        return "0"
    elif value >= 0.001:
        return "{:.3f}".format(value)
    else:
        return "< 0.001"


def get_armature_from_mod(mesh_obj):
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE':
            return mod.object


def toggle_depsgraph_handler(handler_fn, enable: bool):
    """
    Add or remove a depsgraph_update_post handler.
    """

    handlers = bpy.app.handlers.depsgraph_update_post

    if enable:
        if handler_fn not in handlers:
            handlers.append(handler_fn)
    else:
        if handler_fn in handlers:
            handlers.remove(handler_fn)


# Global, so it isn't affected by Blenders undo, as is update_selection_status().
evaluation_valid = False


class WPCheckBoneListItem(PropertyGroup):
    """Item representing a deform bone as a potential destination group."""
    name: StringProperty(
        name="Bone Name", description="Deform bone name", default="")
    bone_index: IntProperty(default=-1)


class WPCheckListItem(PropertyGroup):
    """Group of properties representing an item in the list."""
    name: StringProperty(name="Name", description="Vertex Group", default="")
    group_index: IntProperty(default=-1)
    selected: BoolProperty(default=False)
    maximum_value: StringProperty(
        name="Max Value", description="Maximum weight value that was found in the group", default="-")


class PG_WPCheckProperties(PropertyGroup):
    """WPCheck's properties."""
    list: CollectionProperty(type=WPCheckListItem)
    index: IntProperty()

    deform_list: CollectionProperty(type=WPCheckBoneListItem)
    deform_index: IntProperty()

    include_zero: BoolProperty(
        name="Show 0",
        description="Also show groups with zero influence",
        default=False,
    )
    only_deform: BoolProperty(
        name="Only Deform",
        description="Only show groups with associated armature bones",
        default=True,
    )
    
    operand: FloatProperty(
        name="Operand",
        description="Value to use in the math operation",
        default=0.0
    )
    operation: EnumProperty(
        name="Operation",
        items=[
            ('ADD', "Add",       "weight + operand"),
            ('SUB', "Subtract",  "weight - operand"),
            ('MUL', "Multiply",  "weight * operand"),
            ('DIV', "Divide",    "weight / operand"),
            ('ASSIGN', "Assign", "weight = operand")
        ],
        default='ADD'
    )
    
    show_deform_box: BoolProperty(
        name="Deform Bones",
        description="Show/hide deform bones transfer box",
        default=False
    )

    bone_move_mode: EnumProperty(
        name="Mode",
        description="How to apply weights when moving to destination group",
        items=[
            ('ADD', "Add", "Add source weight to destination"),
            ('REPLACE', "Replace", "Replace destination weight with source weight"),
        ],
        default='ADD')

    # Values determining evaluation to be hidden
    # evaluation_valid: BoolProperty(default=False)

    # ignore changes
    last_operand: FloatProperty(default=0)
    last_operation: StringProperty(default="")
    last_show_deform_box: BoolProperty()

    last_index: IntProperty(default=-1)
    last_deform_index: IntProperty(default=-1)
    last_bone_move_mode: StringProperty(default="")
    last_selected_vgroup: IntProperty(default=-1)

    last_groups_selected_count: IntProperty(default=0)
    last_selection_checksum: StringProperty(default='-1')

    # These trigger re-evaluate
    last_only_deform: BoolProperty(default=False)
    last_include_zero: BoolProperty(default=False)

    last_mode: StringProperty(default="")

    # to restore on next eval
    last_highlighted_vgroup_name: StringProperty(default="")
    last_highlighted_bone_name: StringProperty(default="")

class WPCHECK_UL_List(UIList):
    def draw_item(self, context, layout, data, item,
                  icon, active_data, active_propname, index):
        # Only draw if valid
        if not item:
            return

        # Default & Compact modes
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Split the row into 3 parts: name / checkbox / value
            # factor is the relative size of the first column
            split = layout.split(factor=0.6, align=True)

            # --- Column 1: Name (left-aligned by default) ---
            col_name = split.column()
            col_name.label(text=item.name, icon='GROUP_VERTEX')

            # --- Column 2: Selected toggle (centered) ---
            col_toggle = split.column(align=True)
            col_toggle.alignment = 'RIGHT'
            col_toggle.prop(item, 'selected', text='')

            # --- Column 3: Maximum value (right-aligned) ---
            col_value = split.column(align=True)
            col_value.alignment = 'LEFT'
            col_value.label(text=item.maximum_value)

        # Grid mode (optional)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='GROUP_VERTEX')


class WPCHECK_DEFORM_UL_List(UIList):
    def draw_item(self, context, layout, data, item,
                  icon, active_data, active_propname, index):
        # Only draw if valid
        if not item:
            return

        # Default & Compact modes
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row()
            col_name = row.column()
            col_name.label(text=item.name, icon='BONE_DATA')

        # Grid mode (optional)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='GROUP_VERTEX')


class WPCheckPanel(Panel):
    bl_label = "WPCheck"
    bl_idname = "SCENE_PT_wpcheck_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Edit"

    def draw(self, context):
        global evaluation_valid
        props = context.scene.wp_check_props
        layout = self.layout
        obj = context.active_object

        # Only show deform filter and bones if armature present
        has_armature = get_armature_from_mod(obj) is not None

        # Top row: include_zero + only_deform side by side
        row = layout.row(align=True)
        row.prop(props, "include_zero")
        if has_armature:
            row.prop(props, "only_deform")

        # Evaluate button
        row.operator(WPCheckEvaluateButton.bl_idname,
                    text="Evaluate",
                    icon='GROUP_VERTEX')

        # If evaluation succeeded, show the list + actions
        if evaluation_valid:
            # Vertex group list
            layout.template_list(
                "WPCHECK_UL_List",
                "Assigned VGroups",
                props, "list",
                props, "index",
            )

            # Determine if any item is selected
            any_selected = any(item.selected for item in props.list)

            # Select / Deselect All
            row = layout.row(align=True)
            row.operator(WPCheckSelectAllButton.bl_idname, text="All")
            row.operator(WPCheckDeselectAllButton.bl_idname, text="None")

            # Delete / Zero actions
            row = layout.row(align=True)
            row.enabled = any_selected
            row.operator(WPCheckDeleteButton.bl_idname, text="Delete")
            row.operator(WPCheckZeroButton.bl_idname, text="Zero")
            row.operator(WPCheckBatchRename.bl_idname, text="Rename")

            # Math box (operand + operation + apply)
            box = layout.box()
            box.enabled = any_selected
            box.prop(props, "operand")
            box.prop(props, "operation")
            box.operator("object.wpcheck_math", text="Apply")

            # Collapsible destination deform bones box
            if has_armature:
                dest_box = layout.box()
                dest_box.prop(props, "show_deform_box",
                              icon="TRIA_DOWN" if props.show_deform_box else "TRIA_RIGHT", emboss=False)

                if props.show_deform_box:
                    dest_box.template_list(
                        "WPCHECK_DEFORM_UL_List",  # reuse UIList layout or define new if you prefer
                        "DeformBones",
                        props, "deform_list",
                        props, "deform_index",
                    )

                    # Transfer mode dropdown
                    dest_box.prop(props, "bone_move_mode")

                    # Move weights operator
                    row = dest_box.row(align=True)
                    row.operator("object.wpcheck_move_to_selected",
                                 icon='ARROW_LEFTRIGHT')
                    row = dest_box.row(align=True)
                    row.operator("object.wpcheck_fill_missing",
                                 icon='ADD')


    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == 'MESH' and (obj.mode == 'EDIT' or obj.mode == 'WEIGHT_PAINT'):
            return True
        else:
            return False


def selected_vertices_checksum(obj):
    """
    Returns a fast, simple checksum of selected vertex indices.
    Works in Edit mode (bmesh) and Weight Paint mode (object data).
    """

    if obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj.data)
        verts = (v.index for v in bm.verts if v.select)

    elif obj.mode == 'WEIGHT_PAINT':
        mesh = obj.data
        verts = (v.index for v in mesh.vertices if v.select)

    else:
        # Unsupported mode
        return -1

    checksum = 0

    for idx in verts:
        checksum = ((checksum * 33) ^ idx) & 0xFFFFFFFFFFFFFFFF

    return checksum


class WPCheckEvaluateButton(Operator):
    ''' Scans selected vertices and lists the assigned vertex groups '''
    bl_idname = "object.wpcheck_evaluate"
    bl_label = "Evaluate weights of selected verts"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        global evaluation_valid
        props = context.scene.wp_check_props

        toggle_depsgraph_handler(update_selection_status, False)
        evaluation_valid = False

        obj = bpy.context.active_object
        if not obj or not obj.type == 'MESH':
            log.warning("No active object or not of type mesh")
            return {'CANCELLED'}
        
        # Sync to obj (expensive)
        if obj.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='EDIT')
            # update_edit_mesh is not enough, newly added vgroups will be "undead":
            # presemt on vertices but missing in vgroups list
            # bmesh.update_edit_mesh(obj.data)

        mode = obj.mode
        props.last_mode = mode

        checksum = selected_vertices_checksum(obj)

        props.last_selection_checksum = str(checksum)
        
        # populate selection data as found when triggering 'Evaluate'
        # user selections
        props.last_operand = props.operand
        props.last_operation = props.operation

        props.last_only_deform = props.only_deform
        props.last_include_zero = props.include_zero
        props.last_bone_move_mode = props.bone_move_mode
        props.last_selected_vgroup = obj.vertex_groups.active_index


        props.last_groups_selected_count = 0
        
        # build dictionary of all vgroups - key = index, value = name
        vgroups = {}
        for vgroup in obj.vertex_groups:
            vgroups[vgroup.index] = vgroup.name
        log.info(f"Total vgroups: {len(vgroups)}")

        # set of deform bones
        deform_bones = set()
        link = get_armature_from_mod(obj)
        if link:
            armature = link.data
            for bone in armature.bones:
                if bone.use_deform:
                    deform_bones.add(bone.name)
        else:
            log.info("No armature on obj")

        selected_verts = [v for v in obj.data.vertices if v.select]

        if not selected_verts:
            log.warning("No vertices selected")
            self.report({'WARNING'}, "No vertices selected")
            return {'CANCELLED'}

        log.debug(f"Vertices selected: {len(selected_verts)}")

        used_vgroups: dict[Any, Any] = {}  # resulting groups
        for v in selected_verts:
            for group in v.groups:
                used_vgroups[group.group] = vgroups[group.group]

        # verify actual presence of vgroups
        if not used_vgroups:
            log.warning("No vertex groups on vertices")
            self.report({'WARNING'}, "No vertex groups on vertices")
            return {'CANCELLED'}

        # store maximum influence
        influences = {key: 0.0 for key in used_vgroups}

        for v in selected_verts:
            for group_elem in v.groups:
                if influences[group_elem.group] < group_elem.weight:
                    influences[group_elem.group] = group_elem.weight


        # copy to prop list
        prop_list = props.list
        last_selected_name = prop_list[props.index].name if len(
            prop_list) > props.index else None

        props.index = 0
        prev_selection = {item.name: item.selected for item in prop_list}

        prop_list.clear()
        i = 0
        for index, name in used_vgroups.items():
            if not props.include_zero and influences[index] == 0.0:
                continue
            if (props.only_deform and not name in deform_bones) and link:
                continue

            prop_list.add()
            prop_list[i].name = name
            prop_list[i].group_index = index
            prop_list[i].maximum_value = format_weight(influences[index])
            # restore previous selection state if group name matches
            prop_list[i].selected = prev_selection.get(name, False)

            # restore list index from name
            if name == last_selected_name:
                props.index = i
            i += 1

        props.last_index = props.index

        # Populate destination deform bones list
        last_deform_name = props.deform_list[props.deform_index].name if len(
            props.deform_list) > props.deform_index else None


        props.deform_list.clear()
        props.deform_index = 0

        j = 0
        if deform_bones:
            for bname in sorted(deform_bones):
                item = props.deform_list.add()
                item.name = bname
                item.bone_index = j

                # restore list index from name
                if bname == last_deform_name:
                    props.deform_index = j

                j += 1

        props.last_deform_index = props.deform_index

        # populate selection count
        props.last_groups_selected_count = 0
        for item in props.list:
            if item.selected:
                props.last_groups_selected_count += 1

        evaluation_valid = True
        log.debug(f"Eval complete.")

        toggle_depsgraph_handler(update_selection_status, True)
        
        # since we make no modification in the scene, no undo entry needed
        return {'CANCELLED'}


class WPCheckSelectAllButton(bpy.types.Operator):
    """Selects all vertex groups in the list"""
    bl_idname = 'object.wpcheck_select_all'
    bl_label = 'WPCheckSelectAll'
    bl_options: set[str] = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        global evaluation_valid
        return context.object is not None and context.object.type == 'MESH' and evaluation_valid

    def execute(self, context):
        obj = bpy.context.active_object
        if not obj:
            return {'CANCELLED'}

        prop_list = context.scene.wp_check_props.list
        for listitem in prop_list:
            listitem.selected = True

        context.scene.wp_check_props.last_groups_selected_count = len(
            prop_list)

        return {'FINISHED'}


class WPCheckDeselectAllButton(bpy.types.Operator):
    """Deselects all vertex groups in the list"""
    bl_idname = 'object.wpcheck_deselect_all'
    bl_label = 'WPCheckDeselectAll'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        global evaluation_valid
        return context.object is not None and context.object.type == 'MESH' and evaluation_valid

    def execute(self, context):
        obj = bpy.context.active_object
        if not obj:
            return {'CANCELLED'}

        prop_list = context.scene.wp_check_props.list
        for listitem in prop_list:
            listitem.selected = False

        context.scene.wp_check_props.last_groups_selected_count = 0

        return {'FINISHED'}


class WPCheckDeleteButton(bpy.types.Operator):
    """Deletes checked vertex groups from all selected vertices"""
    bl_idname = 'object.wpcheck_delete'
    bl_label = 'Delete'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        global evaluation_valid
        if not evaluation_valid:
            return False

        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        obj = bpy.context.active_object
        if not obj:
            return {'CANCELLED'}

        mode = obj.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        selected_verts = [v for v in obj.data.vertices if v.select]

        # collect groups to delete
        selected_groups = {}

        prop_list = context.scene.wp_check_props.list
        for listitem in prop_list:
            if listitem.selected:
                selected_groups[listitem.group_index] = listitem.name

        if len(selected_groups) == 0:
            return {'CANCELLED'}

        # go through verts and remove groups
        for v in selected_verts:
            for group_elem in v.groups:
                if group_elem.group in selected_groups:
                    obj.vertex_groups[selected_groups[group_elem.group]].remove([
                                                                                v.index])

        # back to previous mode
        bpy.ops.object.mode_set(mode=mode)

        # rerun evaluate
        bpy.ops.object.wpcheck_evaluate()
        return {'FINISHED'}


class WPCheckZeroButton(bpy.types.Operator):
    """Sets checked vertex group weights from all selected vertices to zero"""
    bl_idname = 'object.wpcheck_zero'
    bl_label = 'Delete'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        global evaluation_valid
        if not evaluation_valid:
            return False

        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        obj = bpy.context.active_object
        if not obj:
            return {'CANCELLED'}

        mode = obj.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        selected_verts = [v for v in obj.data.vertices if v.select]

        # collect groups to delete
        selected_groups = {}
        prop_list = context.scene.wp_check_props.list
        for listitem in prop_list:
            if listitem.selected:
                selected_groups[listitem.group_index] = listitem.name

        if len(selected_groups) == 0:
            return {'CANCELLED'}

        # go through verts and modify groups
        for v in selected_verts:
            for group_elem in v.groups:
                if group_elem.group in selected_groups:
                    group_elem.weight = 0.0

        # back to previous mode
        bpy.ops.object.mode_set(mode=mode)

        # rerun evaluate
        bpy.ops.object.wpcheck_evaluate()
        return {'FINISHED'}
    

class WPCheckMathButton(Operator):
    ''' Executes the selected math operation. '''
    bl_idname = "object.wpcheck_math"
    bl_label = "Apply Operation to Weights"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.wp_check_props
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "No valid mesh")
            return {'CANCELLED'}

        mode = obj.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        # map index → vertex_group
        vgmap = {vg.index: vg for vg in obj.vertex_groups}
        operand = props.operand
        op = props.operation
        verts = [v for v in obj.data.vertices if v.select]

        for item in props.list:
            if not item.selected:
                continue
            vg = vgmap.get(item.group_index)
            if not vg:
                continue

            for v in verts:
                # read existing weight
                w = 0.0
                for g in v.groups:
                    if g.group == item.group_index:
                        w = g.weight
                        break

                # compute
                if op == 'ADD':
                    nw = w + operand
                elif op == 'SUB':
                    nw = w - operand
                elif op == 'MUL':
                    nw = w * operand
                elif op == 'DIV':
                    nw = w / operand if operand != 0 else w
                else:  # ASSIGN
                    nw = operand

                # clamp [0,1]
                nw = max(0.0, min(1.0, nw))
                vg.add([v.index], nw, 'REPLACE')

        bpy.ops.object.mode_set(mode=mode)
        
        # rerun evaluate
        bpy.ops.object.wpcheck_evaluate()
        return {'FINISHED'}


class WPCheckMoveToSelectedButton(Operator):
    """Transfer weights from selected source group (above) to selected deform bone."""
    bl_idname = "object.wpcheck_move_to_selected"
    bl_label = "Move to Deform Bone"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        global evaluation_valid
        props = context.scene.wp_check_props
        obj = context.object
        if not (obj and obj.type == 'MESH' and evaluation_valid):
            return False
        # require a valid source selection
        return len(props.list) > 0 and 0 <= props.index < len(props.list) and len(props.deform_list) > 0

    def execute(self, context):
        props = context.scene.wp_check_props
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "No valid mesh")
            return {'CANCELLED'}

        # Resolve source and destination
        src_item = props.list[props.index]
        dest_item = props.deform_list[props.deform_index] if (
            0 <= props.deform_index < len(props.deform_list)) else None
        if not dest_item:
            self.report({'WARNING'}, "No destination deform bone selected")
            return {'CANCELLED'}

        src_index = src_item.group_index
        dest_name = dest_item.name

        print(dest_item.name)

        # Switch to OBJECT to edit weights
        mode = obj.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        # Selected vertices
        verts = [v for v in obj.data.vertices if v.select]
        if not verts:
            self.report({'WARNING'}, "No vertices selected")
            bpy.ops.object.mode_set(mode=mode)
            return {'CANCELLED'}

        # Ensure destination vertex group exists
        dest_vg = obj.vertex_groups.get(dest_name)
        if not dest_vg:
            dest_vg = obj.vertex_groups.new(name=dest_name)

        # Maps for quick access
        vgmap = {vg.index: vg for vg in obj.vertex_groups}
        src_vg = vgmap.get(src_index)
        if not src_vg:
            self.report(
                {'WARNING'}, f"Source group not found: {src_item.name}")
            bpy.ops.object.mode_set(mode=mode)
            return {'CANCELLED'}

        dest_index = dest_vg.index

        # Transfer per vertex
        for v in verts:
            # read source weight
            w_src = 0.0
            for g in v.groups:
                if g.group == src_index:
                    w_src = g.weight
                    break

            # read current destination weight
            w_dst = 0.0
            for g in v.groups:
                if g.group == dest_index:
                    w_dst = g.weight
                    break

            if props.bone_move_mode == 'ADD':
                new_dst = max(0.0, min(1.0, w_dst + w_src))
            else:  # REPLACE
                new_dst = w_src

            dest_vg.add([v.index], new_dst, 'REPLACE')

            # zero source
            src_vg.add([v.index], 0.0, 'REPLACE')

        # Restore mode and refresh UI
        bpy.ops.object.mode_set(mode=mode)
        bpy.ops.object.wpcheck_evaluate()
        return {'FINISHED'}


class WPCheckFillMissingButton(bpy.types.Operator):
    """Fill missing weights up to 1.0 into the selected deform bone group"""
    bl_idname = "object.wpcheck_fill_missing"
    bl_label = "Fill Missing Weights"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        global evaluation_valid
        props = context.scene.wp_check_props
        obj = context.object
        if not (obj and obj.type == 'MESH' and evaluation_valid):
            return False
        # require at least one source group selected and a destination deform bone selected
        has_sources = any(item.selected for item in props.list)
        has_dest = len(props.deform_list) > 0 and 0 <= props.deform_index < len(
            props.deform_list)
        return has_sources and has_dest

    def execute(self, context):
        props = context.scene.wp_check_props
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "No valid mesh")
            return {'CANCELLED'}

        # resolve destination deform bone group
        dest_item = props.deform_list[props.deform_index]
        dest_name = dest_item.name

        mode = obj.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        verts = [v for v in obj.data.vertices if v.select]
        if not verts:
            self.report({'WARNING'}, "No vertices selected")
            bpy.ops.object.mode_set(mode=mode)
            return {'CANCELLED'}

        # ensure destination vertex group exists
        dest_vg = obj.vertex_groups.get(dest_name)
        if not dest_vg:
            dest_vg = obj.vertex_groups.new(name=dest_name)
        dest_index = dest_vg.index

        # map index → vertex_group for sources
        vgmap = {vg.index: vg for vg in obj.vertex_groups}
        source_indices = [
            item.group_index for item in props.list if item.selected]

        for v in verts:
            # sum weights of all selected source groups
            total = 0.0
            for g in v.groups:
                if g.group in source_indices:
                    total += g.weight
            if total < 1.0:
                missing = 1.0 - total
                # read current destination weight
                w_dst = 0.0
                for g in v.groups:
                    if g.group == dest_index:
                        w_dst = g.weight
                        break
                new_dst = max(0.0, min(1.0, w_dst + missing))
                dest_vg.add([v.index], new_dst, 'REPLACE')

        bpy.ops.object.mode_set(mode=mode)
        bpy.ops.object.wpcheck_evaluate()
        return {'FINISHED'}


class WPCheckBatchRename(bpy.types.Operator):
    """Batch rename selected vertex groups using Regex."""

    bl_idname = "object.wpcheck_batch_rename"
    bl_label = "Batch Rename (Regex)"
    bl_options = {'REGISTER', 'UNDO'}

    search: StringProperty(
        name="Search (Regex)",
        description="Regex pattern to search for in selected vertex group names",
        default=""
    )

    replace: StringProperty(
        name="Replace With",
        description="Replacement string (supports regex groups)",
        default=""
    )

    case_sensitive: BoolProperty(
        name="Case Sensitive",
        default=True
    )

    @classmethod
    def poll(cls, context):
        global evaluation_valid
        return (
            context.object is not None
            and context.object.type == 'MESH' and evaluation_valid
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "search")
        col.prop(self, "replace")
        col.prop(self, "case_sensitive")

        box = col.box()
        box.label(text="Regex Tips:")
        box.label(text="^ = start of name")
        box.label(text="$ = end of name")
        box.label(text="Use \\ to escape special chars e.g. \\.")
        box.label(text="Groups: ( ) and \\1, \\2 ...")

    def execute(self, context):
        obj = context.object
        props = context.scene.wp_check_props

        if not obj or not self.search:
            return {'CANCELLED'}

        # Compile regex
        flags = 0 if self.case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(self.search, flags)
        except re.error as e:
            self.report({'ERROR'}, f"Invalid regex: {e}")
            return {'CANCELLED'}

        # Collect selected groups from the WPCheck list
        selected_groups = {
            item.group_index: item.name
            for item in props.list
            if item.selected
        }

        if not selected_groups:
            self.report({'WARNING'}, "No groups selected in the list")
            return {'CANCELLED'}

        mode = obj.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        renamed_count = 0

        # Rename only selected vertex groups
        for vg in obj.vertex_groups:
            if vg.index in selected_groups:
                new_name = pattern.sub(self.replace, vg.name)
                if new_name != vg.name:
                    vg.name = new_name
                    renamed_count += 1

        self.report({'INFO'}, f"Renamed {renamed_count} vertex groups")

        bpy.ops.object.mode_set(mode=mode)
        bpy.ops.object.wpcheck_evaluate()

        return {'FINISHED'}



# Callback from Blender, active while evaluation valid
def update_selection_status(scene, depsgraph):
    global evaluation_valid
    props = scene.wp_check_props
    obj = bpy.context.active_object
    
    # This is called when the user changed something.
    # If it was a list index, list selection etc. in our menu we should not invalidate.
    # If the filters were changed, rerun evaluate.
    # Else, we need to check if the selection changed which can be heavy on CPU.
    # If selection changed, set evaluation_valid false, hiding the WPCheck panel.

    # The above are determined by comparing to the state that was recorded at evaluation
    # or previous update_selection_status.

    # user choosing groups
    new_selected = 0
    for item in props.list:
        if item.selected:
            new_selected += 1

    keep = False
    filter = False

    if obj and props.last_mode != obj.mode:
        # WEIGHT_PAINT -> EDIT works, but other way around seems to insert intermediate OBJECT mode
        if obj.mode == 'EDIT' or obj.mode == 'WEIGHT_PAINT':
            props.last_mode = obj.mode
            keep = True
        else:
            evaluation_valid = False
            toggle_depsgraph_handler(update_selection_status, False)
            return

    if props.last_groups_selected_count != new_selected:
        props.last_groups_selected_count = new_selected
        keep = True

    if props.last_operand != props.operand:
        props.last_operand = props.operand
        keep = True

    if props.last_operation != props.operation:
        props.last_operation = props.operation
        keep = True

    if props.last_index != props.index:
        props.last_index = props.index
        keep = True

    if props.last_deform_index != props.deform_index:
        props.last_deform_index = props.deform_index
        keep = True

    if props.last_bone_move_mode != props.bone_move_mode:
        props.last_bone_move_mode = props.bone_move_mode
        keep = True

    if props.last_selected_vgroup != obj.vertex_groups.active_index:
        props.last_selected_vgroup = obj.vertex_groups.active_index
        keep = True

    if props.last_only_deform != props.only_deform:
        filter = True

    if props.last_include_zero != props.include_zero:
        filter = True

    if not keep:
        log.info("Checking selection change")
        checksum = selected_vertices_checksum(obj)
        if props.last_selection_checksum == str(checksum):
            keep = True

    if not keep:
        evaluation_valid = False
    log.info(f"Result: {evaluation_valid}")

    if evaluation_valid == False:
        # remove this update to save performance. It's added back when 'Evaluate' is triggered
        toggle_depsgraph_handler(update_selection_status, False)

    if filter:
        toggle_depsgraph_handler(update_selection_status, False)
        bpy.ops.object.wpcheck_evaluate()


classes = [
    WPCheckPanel,
    WPCheckEvaluateButton,
    WPCheckListItem,
    WPCheckBoneListItem,
    WPCHECK_UL_List,
    WPCHECK_DEFORM_UL_List,
    WPCheckSelectAllButton,
    WPCheckDeselectAllButton,
    WPCheckDeleteButton,
    WPCheckZeroButton,
    PG_WPCheckProperties,
    WPCheckMathButton,
    WPCheckMoveToSelectedButton,
    WPCheckFillMissingButton,
    WPCheckBatchRename
]


def register():
    global evaluation_valid
    evaluation_valid = False

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.wp_check_props = PointerProperty(type=PG_WPCheckProperties)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.wp_check_props
    
    toggle_depsgraph_handler(update_selection_status, False)

