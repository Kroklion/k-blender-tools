import bpy
import bmesh
import math

bl_info = {
    "name": "Tris to Quads (Select Only)",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D View > Edit Mode > Mesh > Faces",
    "description": (
        "A wrapper around Blender's Tris to Quads operator."
        "Instead of changing the mesh, onle selects the edges that would be dissolved."
        "Allows to apply manual corrections before dissolving."
    ),
    "category": "Mesh"
}


# Module‑level feature flags
HAS_TOPOLOGY_INFLUENCE = False


class MESH_OT_tris_to_quads_edges(bpy.types.Operator):
    bl_idname = "mesh.tris_to_quads_edges"
    bl_label = "Tris to Quads (Select only)"
    bl_options = {'REGISTER', 'UNDO'}

    face_threshold: bpy.props.FloatProperty(
        name="Max Face Angle",
        description="Maximum angle between faces to consider them part of the same quad",
        subtype='ANGLE',
        unit='ROTATION',
        default=math.radians(40)
    )

    shape_threshold: bpy.props.FloatProperty(
        name="Max Shape Angle",
        description="Maximum angle between edges to consider them part of the same quad",
        subtype='ANGLE',
        unit='ROTATION',
        default=math.radians(60)
    )

    # 4.4+
    topology_influence: bpy.props.FloatProperty(
        name="Topology Influence",
        description="How much topology affects quad detection",
        default=2.0
    )

    uvs: bpy.props.BoolProperty(
        name="Compare UVs",
        description="Compare UV coordinates when detecting quads",
        default=True
    )

    vcols: bpy.props.BoolProperty(
        name="Compare Vertex Colors",
        description="Compare vertex colors when detecting quads",
        default=False
    )

    seam: bpy.props.BoolProperty(
        name="Compare Seams",
        description="Compare seam flags when detecting quads",
        default=False
    )

    sharp: bpy.props.BoolProperty(
        name="Compare Sharp",
        description="Compare sharp edges when detecting quads",
        default=False
    )

    materials: bpy.props.BoolProperty(
        name="Compare Materials",
        description="Compare material indices when detecting quads",
        default=False
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'
    
    def draw(self, context):
        layout = self.layout

        layout.prop(self, "face_threshold")
        layout.prop(self, "shape_threshold")

        if HAS_TOPOLOGY_INFLUENCE:
            layout.prop(self, "topology_influence")

        layout.prop(self, "uvs")
        layout.prop(self, "vcols")
        layout.prop(self, "seam")
        layout.prop(self, "sharp")
        layout.prop(self, "materials")


    def execute(self, context):
        obj = context.object

        # Save selection state
        bm = bmesh.from_edit_mesh(obj.data)

        # Build original edge set (vertex index pairs)
        orig_edges = {tuple(sorted((e.verts[0].index, e.verts[1].index)))
                      for e in bm.edges}

        # Duplicate mesh in memory
        bpy.ops.object.mode_set(mode='OBJECT')
        
        temp_mesh = obj.data.copy()

        # Create temporary object for new mesh
        temp_obj = bpy.data.objects.new(obj.name + '_temporary', temp_mesh)
        context.collection.objects.link(temp_obj)

        # Ensure only temp_obj is selected
        for o in context.selected_objects:
            o.select_set(False)
        temp_obj.select_set(True)
        context.view_layer.objects.active = temp_obj

        # Run tris_to_quads on the duplicate
        bpy.ops.object.mode_set(mode='EDIT')
        kwargs = dict(
            face_threshold=self.face_threshold,
            shape_threshold=self.shape_threshold,
            uvs=self.uvs,
            vcols=self.vcols,
            seam=self.seam,
            sharp=self.sharp,
            materials=self.materials,
        )

        if HAS_TOPOLOGY_INFLUENCE:
            kwargs["topology_influence"] = self.topology_influence

        bpy.ops.mesh.tris_convert_to_quads(**kwargs)

        # Get edges
        temp_bm = bmesh.from_edit_mesh(temp_mesh)
        
        # Is this approach the most efficient possible?
        new_edges = {tuple(sorted((e.verts[0].index, e.verts[1].index)))
                    for e in temp_bm.edges}
        
        # Cleanup temp object
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.data.objects.remove(temp_obj)
        bpy.data.meshes.remove(temp_mesh)
        
        # Select original
        obj.select_set(True)
        context.view_layer.objects.active = obj
        
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(obj.data)

        # Determine dissolved edges
        dissolved = orig_edges - new_edges

        # Switch to edge select mode for result
        bpy.ops.mesh.select_all(action='DESELECT')
        context.tool_settings.mesh_select_mode = (False, True, False)

        # Select dissolved edges
        for e in bm.edges:
            key = tuple(sorted((e.verts[0].index, e.verts[1].index)))
            e.select_set(key in dissolved)

        bmesh.update_edit_mesh(mesh=obj.data, loop_triangles=False, destructive=False)
        bm.free()

        self.report({'INFO'}, f"Selected {len(dissolved)} edges.")
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(
        MESH_OT_tris_to_quads_edges.bl_idname,
        text="Tris to Quads (Select only)"
    )


def register():
    global HAS_TOPOLOGY_INFLUENCE, HAS_DESELECT_JOINED

    # Detect Blender features
    op_rna = bpy.ops.mesh.tris_convert_to_quads.get_rna_type().properties
    HAS_TOPOLOGY_INFLUENCE = "topology_influence" in op_rna

    bpy.utils.register_class(MESH_OT_tris_to_quads_edges)
    bpy.types.VIEW3D_MT_edit_mesh_faces.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_faces.remove(menu_func)
    bpy.utils.unregister_class(MESH_OT_tris_to_quads_edges)


if __name__ == "__main__":
    register()
