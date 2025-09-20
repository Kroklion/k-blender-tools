import bpy
from bpy.types import DATA_PT_vertex_groups

bl_info = {
    "name": "Vertex Group Show/Hide/Solo",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "Properties > Object Data > Vertex Groups Panel\n"
        "Adds Show, Hide, and Solo buttons for the selected vertex group"
    ),
    "description": (
        "Adds convenient operators to the Vertex Groups panel to quickly\n"
        "show, hide, or solo geometry under the selected vertex group in Edit Mode."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}


#    Operators

class MESH_OT_vertex_group_show(bpy.types.Operator):
    bl_idname = "mesh.vertex_group_show"
    bl_label = "Show"
    bl_description = "Unhide all mesh elements"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and ob.type == 'MESH'

    def execute(self, context):
        # ensure we're in Edit Mode
        mode = context.object.mode
        if mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        # switch to VERT mode so reveal works on verts/edges/faces
        bpy.ops.mesh.select_mode(type='VERT')
        
        bpy.ops.mesh.select_all(action='SELECT')
        
        # unhide everything
        bpy.ops.mesh.reveal(select=False)
        
        # select those of group
        bpy.ops.object.vertex_group_select()
        
        bpy.ops.mesh.select_all(action='INVERT')
        # hide that selection
        bpy.ops.mesh.hide(unselected=False)
        
        bpy.ops.object.mode_set(mode=mode)
        return {'FINISHED'}


class MESH_OT_vertex_group_hide(bpy.types.Operator):
    bl_idname = "mesh.vertex_group_hide"
    bl_label = "Hide"
    bl_description = "Hide all vertices in the active vertex group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        vg = ob.vertex_groups.active
        return ob and ob.type == 'MESH' and vg

    def execute(self, context):
        # enter Edit Mode
        mode = context.object.mode
        if mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        # ensure we hide only verts
        bpy.ops.mesh.select_mode(type='VERT')
        # clear any selection
        bpy.ops.mesh.select_all(action='DESELECT')
        # select only the active VG verts
        bpy.ops.object.vertex_group_select()
        # hide those selected verts (edges/faces auto‐hide where verts are hidden)
        bpy.ops.mesh.hide(unselected=False)
        
        bpy.ops.object.mode_set(mode=mode)
        return {'FINISHED'}


class MESH_OT_vertex_group_solo(bpy.types.Operator):
    bl_idname = "mesh.vertex_group_solo"
    bl_label = "Solo"
    bl_description = "Show only the active vertex group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        vg = ob.vertex_groups.active
        return ob and ob.type == 'MESH' and vg

    def execute(self, context):
        # enter Edit Mode
        mode = context.object.mode
        if mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='VERT')

        # 1) reveal all
        bpy.ops.mesh.reveal()
        # 2) deselect everything
        bpy.ops.mesh.select_all(action='DESELECT')
        # 3) select only active VG verts
        bpy.ops.object.vertex_group_select()
        # 4) invert selection → now all verts except the group are selected
        bpy.ops.mesh.select_all(action='INVERT')
        # 5) hide that selection
        bpy.ops.mesh.hide(unselected=False)
        
        bpy.ops.object.mode_set(mode=mode)
        return {'FINISHED'}


# store original draw to restore on unregister
original_draw = None

def patched_draw(self, context):
    # call Blender’s original UI
    original_draw(self, context)
    # extra buttons
    row = self.layout.row(align=True)
    row.operator("mesh.vertex_group_show", icon='HIDE_OFF')
    row.operator("mesh.vertex_group_hide", icon='HIDE_ON')
    row.operator("mesh.vertex_group_solo", icon='SOLO_ON')


def register():
    global original_draw
    bpy.utils.register_class(MESH_OT_vertex_group_show)
    bpy.utils.register_class(MESH_OT_vertex_group_hide)
    bpy.utils.register_class(MESH_OT_vertex_group_solo)

    # Monkey-patch the existing Vertex Groups panel
    
    original_draw = DATA_PT_vertex_groups.draw
    DATA_PT_vertex_groups.draw = patched_draw


def unregister():
    # restore original draw
    if original_draw:
        DATA_PT_vertex_groups.draw = original_draw

    bpy.utils.unregister_class(MESH_OT_vertex_group_solo)
    bpy.utils.unregister_class(MESH_OT_vertex_group_hide)
    bpy.utils.unregister_class(MESH_OT_vertex_group_show)

