import bpy
from .. import log

from bpy.types import (Panel, Operator, PropertyGroup)
from bpy.props import (PointerProperty, StringProperty)

import bmesh
import random
from mathutils import kdtree

bl_info = {
    "name": "WPSync – Copy Weights Across Meshes",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Sidebar (N) > Edit Tab > WPSync Panel\n"
        "Operators: Assign IDs, Set Prox SRC/DEST, Copy Prox"
    ),
    "description": (
        "Keeps different mesh objects with overlapping deforming areas in sync.\n"
        "Provides tools to assign unique vertex IDs, mark source and destination\n"
        "proximity groups, and transfer weights between meshes that share the same armature.\n"
        "TODO skin to cloth workflow"
    ),
    "warning": "",
    "doc_url": "",
    "category": "Rigging",
}


class PG_WPSyncProperties(PropertyGroup):
    """WPSync's properties."""
    suffix: StringProperty(
        name="Suffix",
        description="Marker suffix for proximity transfer groups",
        default=""
    )


class WPSyncPanel(Panel):
    bl_label = "WPSync"
    bl_idname = "SCENE_PT_wpsync_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Edit"

    def draw(self, context):
        layout = self.layout
        props = context.scene.wp_sync_props

        row = layout.row()
        row.operator(WPSyncAssignIDsButton.bl_idname,
                     text="Assign IDs", icon="GROUP_VERTEX")
        
        # only in mesh edit mode
        if context.mode == 'EDIT_MESH':
            layout.prop(props, 'suffix', text="Suffix")
            row = layout.row(align=True)
            row.operator(WPSyncSetSrc.bl_idname, text="Set SRC")
            row.operator(WPSyncSetDest.bl_idname, text="Set DEST")
        
        row = layout.row()
        row.operator(WPSyncTransferProx.bl_idname,
                     text="Copy Prox", icon="COPY_ID")
        

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            return True
        else:
            return False


class WPSyncAssignIDsButton(Operator):
    ''' Creates an attribute for vertices and assigns an unique number. '''
    bl_idname = "object.wpsync_assign_ids"
    bl_label = "add ID attribute to vertices"
    
    @classmethod
    def poll(cls, context):
        global evaluation_valid
        return context.object is not None and\
            context.object.type == 'MESH' # and\
            # context.scene.wp_sync_props.source != ''

    def execute(self, context):
        obj: Any = bpy.context.active_object
        # mode = obj.mode

        # we need to switch from Edit mode to Object mode so the selection gets updated
        # bpy.ops.object.mode_set(mode='OBJECT')
        
        srcname = context.scene.wp_sync_props.source
        log.info(srcname)
        
        mesh = obj.data
        
        if not srcname in mesh.attributes:
            mesh.attributes.new(srcname, 'FLOAT', 'POINT')

        attribute = mesh.attributes[srcname]
        i = 1.0
        for item in attribute.data:
            if item.value == 0:
                value = random.uniform(1,9) + i
                item.value = value
            i = i + 10

        # bpy.ops.object.mode_set(mode=mode)
        # since we make no modification, no undo entry needed
        return {'CANCELLED'}
    
    
class WPSyncSetSrc(Operator):
    """Assign selected verts to a XFER_PROX_SRC_⋯ group"""
    bl_idname = "object.wpsync_set_prox_src"
    bl_label = "Set Prox SRC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object
                and context.active_object.type == 'MESH'
                and context.mode == 'EDIT_MESH')

    def execute(self, context):
        obj = context.active_object
        props = context.scene.wp_sync_props
        suffix = props.suffix.strip()
        if not suffix:
            self.report({'ERROR'}, "Suffix cannot be empty")
            return {'CANCELLED'}

        # gather selected vert indices in edit mode
        bm = bmesh.from_edit_mesh(obj.data)
        sel_idxs = [v.index for v in bm.verts if v.select]
        if not sel_idxs:
            self.report({'WARNING'}, "No vertices selected")
            return {'CANCELLED'}

        # switch to object mode to assign groups
        bpy.ops.object.mode_set(mode='OBJECT')
        grp_name = MARK_XFER_PROX_SRC + suffix
        vgroup = obj.vertex_groups.get(
            grp_name) or obj.vertex_groups.new(name=grp_name)
        vgroup.add(sel_idxs, 1.0, 'REPLACE')
        obj.data.update()

        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class WPSyncSetDest(Operator):
    """Assign selected verts to a XFER_PROX_DEST_⋯ group"""
    bl_idname = "object.wpsync_set_prox_dest"
    bl_label = "Set Prox DEST"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object
                and context.active_object.type == 'MESH'
                and context.mode == 'EDIT_MESH')

    def execute(self, context):
        obj = context.active_object
        props = context.scene.wp_sync_props
        suffix = props.suffix.strip()
        if not suffix:
            self.report({'ERROR'}, "Suffix cannot be empty")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        sel_idxs = [v.index for v in bm.verts if v.select]
        if not sel_idxs:
            self.report({'WARNING'}, "No vertices selected")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='OBJECT')
        grp_name = MARK_XFER_PROX_DEST + suffix
        vgroup = obj.vertex_groups.get(
            grp_name) or obj.vertex_groups.new(name=grp_name)
        vgroup.add(sel_idxs, 1.0, 'REPLACE')
        obj.data.update()

        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


def get_armature_from_mod(mesh_obj):
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE':
            return mod.object
    return None
    

MARK_XFER_PROX_SRC = 'XFER_PROX_SRC_'
MARK_XFER_PROX_DEST = 'XFER_PROX_DEST_'
PROX_THRESHOLD = 0.0005


class WPSyncTransferProx(Operator):
    ''' move ID to vertices of different object at same global vert position.
        Source: XFER_ID_SRC_
        Destination: XFER_ID_DEST_
    '''
    bl_idname = "object.wpsync_transfer_proximity_ids"
    bl_label = "Copy vertex groups on overlapping verts with destination name."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        log.info("called")
        # ensure we're in Object mode
        active = context.active_object
        prev_mode = active.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        # collect source and dest data: keys are (object, suffix) tuples
        data_src = {}
        data_dest = {}
        
        # ensure selected meshes share the same armature
        armature = get_armature_from_mod(active)
        if not armature:
            self.report({'ERROR'}, "Active mesh has no Armature modifier")
            return {'CANCELLED'}
        for obj in context.selected_objects:
            if obj.type == 'MESH' and get_armature_from_mod(obj) != armature:
                self.report(
                    {'ERROR'},
                    "All selected mesh objects must use the same Armature"
                )
                bpy.ops.object.mode_set(mode=prev_mode)
                return {'CANCELLED'}

        # collect deform bones from that armature
        deform_bones = {
            bone.name: bone
            for bone in armature.data.bones
            if bone.use_deform
        }

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            log.debug(f"Selected object: {obj.name}")
            mesh = obj.data
            for vg in obj.vertex_groups:
                name = vg.name
                if name.startswith(MARK_XFER_PROX_SRC):
                    suffix = name[len(MARK_XFER_PROX_SRC):]
                    idxs = []
                    for v in mesh.vertices:
                        for g in v.groups:
                            if g.group == vg.index and g.weight > 0.0:
                                idxs.append(v.index)
                                break
                    if idxs:
                        data_src[(obj, suffix)] = idxs
                elif name.startswith(MARK_XFER_PROX_DEST):
                    suffix = name[len(MARK_XFER_PROX_DEST):]
                    idxs = []
                    for v in mesh.vertices:
                        for g in v.groups:
                            if g.group == vg.index and g.weight > 0.0:
                                idxs.append(v.index)
                                break
                    if idxs:
                        data_dest[(obj, suffix)] = idxs
                        
        log.debug(f"data_src: {str(data_src)}")
        log.debug(f"data_dest: {str(data_dest)}")
        
        # abort if no markers found
        if not data_src:
            self.report({'ERROR'}, "No XFER_PROX_SRC_ groups found")
            bpy.ops.object.mode_set(mode=prev_mode)
            return {'CANCELLED'}

        if not data_dest:
            self.report({'ERROR'}, "No XFER_PROX_DEST_ groups found")
            bpy.ops.object.mode_set(mode=prev_mode)
            return {'CANCELLED'}
        
        # for each source group, find matching dest groups
        for (src_obj, suffix), src_idxs in data_src.items():
            # build KDTree of source vert world positions
            kd = kdtree.KDTree(len(src_idxs))
            for _, vidx in enumerate(src_idxs):
                co_world = src_obj.matrix_world @ src_obj.data.vertices[vidx].co
                kd.insert(co_world, vidx)
            kd.balance()

            # look for any dest entries with same suffix
            for (dst_obj, d_suffix), dst_idxs in data_dest.items():
                if d_suffix != suffix or dst_obj == src_obj:
                    continue

                # ensure dst mesh has all necessary vgroups
                def ensure_vgroup(obj, name):
                    for g in obj.vertex_groups:
                        if g.name == name:
                            return g
                    return obj.vertex_groups.new(name=name)

                # iterate dest verts, find nearest src vert
                for dst_vidx in dst_idxs:
                    dst_vert = dst_obj.data.vertices[dst_vidx]
                    dst_world = dst_obj.matrix_world @ dst_vert.co
                    # for (co, index, dist) in kd.find_range(co_find, 0.5):
                    co, src_vidx, dist = kd.find(dst_world)
                    if dist > PROX_THRESHOLD:
                        continue

                    # move the dest vert to the exact src position
                    new_local = dst_obj.matrix_world.inverted() @ co
                    dst_vert.co = new_local

                    # copy all deform-group weights from src to dst for this vert
                    src_vert = src_obj.data.vertices[src_vidx]
                    # gather src weights
                    handled = set()
                    
                    for g in src_vert.groups:
                        src_g = src_obj.vertex_groups[g.group]
                        name = src_g.name
                        # skip our marker groups
                        if name.startswith(MARK_XFER_PROX_SRC) or name.startswith(MARK_XFER_PROX_DEST):
                            continue
                        
                        # skip non‐deform groups
                        if name not in deform_bones:
                            continue
                        
                        # TODO The destination may have deform groups that are not on the source.
                        # Set this nonpresent weight to 0
                        
                        weight = g.weight
                        if weight <= 0.0:
                            continue
                        
                        handled.add(name)
                        
                        # assign into dst
                        dst_g = ensure_vgroup(dst_obj, name)
                        dst_g.add([dst_vidx], weight, 'REPLACE')
                        
                    # zero out only deform groups already on dst vert but not in handled
                    for dg in dst_vert.groups:
                        dst_name = dst_obj.vertex_groups[dg.group].name
                        if dst_name in deform_bones and dst_name not in handled:
                            dst_g = ensure_vgroup(dst_obj, dst_name)
                            dst_g.add([dst_vidx], 0.0, 'REPLACE')

                # update destination mesh after edits
                dst_obj.data.update()

        # restore previous mode
        bpy.ops.object.mode_set(mode=prev_mode)
        return {'FINISHED'}


classes = [
    PG_WPSyncProperties,
    WPSyncPanel,
    WPSyncAssignIDsButton,
    WPSyncSetSrc,
    WPSyncSetDest,
    WPSyncTransferProx,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
        bpy.types.Scene.wp_sync_props = PointerProperty(type=PG_WPSyncProperties)

def unregister():
    del bpy.types.Scene.wp_sync_props
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    
