from bpy.props import FloatProperty, BoolProperty
import bmesh
import bpy
from mathutils.kdtree import KDTree

bl_info = {
    "name": "Mesh Edit Utilities",
    "author": "",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Edit Mode (Mesh) > Vertex Menu\n"
        " - Zero X Selected Vertices\n"
        " - Center Selected X in Edit Mode\n"
        "3D View > Edit Mode (Mesh) > Merge Menu\n"
        " - Merge Coincident Edges"
    ),
    "description": (
        "Adds mesh editing tools in Edit Mode:\n"
        "• Zero X Selected Vertices – set X coordinate of selected verts to 0\n"
        "• Merge Coincident Edges – Merges only selected edges that are coincident.\n"
        "  Useful for imports of file formats that only support UV island mesh connectivity."
    ),
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}


class MESH_OT_zero_x_selected(bpy.types.Operator):
    bl_idname = "mesh.zero_x_selected"
    bl_label = "Zero X Selected Vertices"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.edit_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        count = 0

        for v in bm.verts:
            if v.select:
                v.co.x = 0.0
                count += 1

        bmesh.update_edit_mesh(me, destructive=False)
        self.report({'INFO'}, f"Zeroed X on {count} verts")
        return {'FINISHED'}
    

# --- MESH_OT_edge_merge --- START
def faces_are_identical(f1, f2, threshold=1e-5):
    """Return True if two faces are coincident in 3D space within threshold, allowing reversed winding."""
    if len(f1.verts) != len(f2.verts):
        return False

    coords1 = [v.co for v in f1.verts]
    coords2 = [v.co for v in f2.verts]

    # every vertex of f1 must match some vertex of f2 within threshold
    for c1 in coords1:
        if not any((c1 - c2).length <= threshold for c2 in coords2):
            return False
    return True


def endpoints_match(v1a, v1b, v2a, v2b, thr):
    """Check if two edges overlap by endpoints within threshold (either alignment)."""
    return ((v1a.co - v2a.co).length <= thr and (v1b.co - v2b.co).length <= thr) or \
           ((v1a.co - v2b.co).length <= thr and (v1b.co - v2a.co).length <= thr)


def collect_candidate_edges(bm):
    """
    Return list of edges that are:
    - selected
    - have ≤1 adjacent face
    """
    return [e for e in bm.edges if e.select and len(e.link_faces) <= 1]


def build_edge_kdtree(edges):
    """
    Build KD-tree over selected candidate edges using midpoints.
    Returns (kd, midpoints).
    """
    kd = KDTree(len(edges))
    midpoints = []
    for i, e in enumerate(edges):
        v1, v2 = e.verts
        mid = (v1.co + v2.co) * 0.5
        kd.insert(mid, i)
        midpoints.append(mid)
    kd.balance()
    return kd, midpoints


def detect_overlapping_edge_groups(edges, kd, midpoints, threshold):
    """
    Return groups (list of lists) of edges whose midpoints are within threshold.
    Each group may contain more than two edges; filtering comes next.
    Also returns candidate_count for stats.
    """
    groups = []
    candidate_count = 0

    for i, e in enumerate(edges):
        nearby = kd.find_range(midpoints[i], threshold)
        group_indices = sorted(
            {idx for (_co, idx, _dist) in nearby})  # unique + sorted

        # Only emit the group once: when the current edge is the group's smallest index
        if len(group_indices) > 1 and i == group_indices[0]:
            group = [edges[idx] for idx in group_indices]
            groups.append(group)
            candidate_count += len(group)

    return groups, candidate_count


def filter_to_valid_pairs(groups, threshold):
    """
    From groups of nearby edges, keep only true overlapping edge pairs.
    Rules:
    - If exactly one pair overlaps -> keep it.
    - If multiple pairs overlap and all share the same two vertex positions (duplicate edges) -> keep just one.
    - If multiple pairs overlap with >2 unique vertex positions (cross-like case) -> discard entire group.
    Returns valid_pairs and discarded_groups_count for stats.
    """
    valid_pairs = []
    discarded_groups = 0

    def vkey(v):
        # rounded coord tuple key to stabilize uniqueness test
        return (round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6))

    for group in groups:
        overlaps = []
        n = len(group)
        for i in range(n):
            for j in range(i + 1, n):
                e1, e2 = group[i], group[j]
                v1a, v1b = e1.verts
                v2a, v2b = e2.verts
                if endpoints_match(v1a, v1b, v2a, v2b, threshold):
                    overlaps.append((e1, e2))

        if len(overlaps) == 0:
            continue
        elif len(overlaps) == 1:
            valid_pairs.append(overlaps[0])
        else:
            discarded_groups += 1
            continue

    return valid_pairs, discarded_groups


def discard_collapsing_faces(pairs, threshold):
    """
    Remove pairs that would collapse identical faces in 3D space.
    Returns (safe_pairs, prevented_count).
    """
    safe_pairs = []
    prevented = 0

    for e1, e2 in pairs:
        collapse = any(faces_are_identical(f1, f2, threshold)
                       for f1 in e1.link_faces for f2 in e2.link_faces)
        if collapse:
            prevented += 1
        else:
            safe_pairs.append((e1, e2))

    return safe_pairs, prevented


def merge_pairs(bm, pairs, threshold):
    """
    Merge vertices for each overlapping pair using remove_doubles.
    Returns number of vertices collapsed (count delta).
    """
    # Collect all vertices from the edge pairs (limit scope; avoids touching unrelated verts)
    verts = set()
    for e1, e2 in pairs:
        if e1.is_valid:
            verts.update(e1.verts)
        if e2.is_valid:
            verts.update(e2.verts)

    # Ensure lookup tables are valid before counting
    bm.verts.ensure_lookup_table()
    before = len(bm.verts)

    # Execute remove_doubles on the collected verts
    bmesh.ops.remove_doubles(bm, verts=list(verts), dist=threshold)

    # Rebuild lookup tables to reflect topology changes, then count
    bm.verts.ensure_lookup_table()
    after = len(bm.verts)

    # Number of vertices collapsed
    merged_count = before - after
    return merged_count


def select_vertices_from_pairs(bm, pairs):
    """
    Deselect all, then select all vertices contained in the given edge pairs.
    Returns number of vertices selected.
    """
    # Deselect everything first
    bpy.ops.mesh.select_all(action='DESELECT')

    # Collect verts from pairs
    verts = set()
    for e1, e2 in pairs:
        if e1.is_valid:
            verts.update(e1.verts)
        if e2.is_valid:
            verts.update(e2.verts)

    # Select them
    for v in verts:
        if v.is_valid:
            v.select_set(True)

    return len(verts)


class MESH_OT_edge_merge(bpy.types.Operator):
    """Merge overlapping selected edges by distance"""
    bl_idname = "mesh.edge_merge"
    bl_label = "Merge Coincident Edges"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: FloatProperty(
        name="Merge Distance",
        description="Max distance for merging",
        default=1e-5,
        min=1e-7,
        max=0.1,
        precision=6
    )
    select_only: BoolProperty(
        name="Select Only",
        description="Skip merging, only select affected vertices",
        default=False
    )

    def execute(self, context):
        obj = context.edit_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Enter Edit Mode on a mesh")
            return {'CANCELLED'}

        me = obj.data
        bm = bmesh.from_edit_mesh(me)

        # Step 1: collect selected candidate edges (≤1 face)
        candidate_edges = collect_candidate_edges(bm)
        num_selected_candidates = len(candidate_edges)

        if num_selected_candidates == 0:
            self.report({'INFO'}, "No selected edges with ≤1 face")
            return {'CANCELLED'}

        # Step 2: build KD-tree
        kd, midpoints = build_edge_kdtree(candidate_edges)

        # Step 3a: detect groups by midpoint proximity
        groups, candidate_count_in_groups = detect_overlapping_edge_groups(
            candidate_edges, kd, midpoints, self.threshold
        )

        # Step 3b: filter to valid overlapping pairs (handle cross-case/non-manifold)
        valid_pairs, discarded_groups = filter_to_valid_pairs(
            groups, self.threshold)

        # Step 3c: discard pairs that would collapse identical faces
        safe_pairs, prevented_face_collapse = discard_collapsing_faces(
            valid_pairs, self.threshold)
        num_confirmed_pairs = len(safe_pairs)

        # Step 4: perform merges or just select
        removed_verts = 0
        if self.select_only:
            _ = select_vertices_from_pairs(bm, safe_pairs)
        else:
            removed_verts = merge_pairs(bm, safe_pairs, self.threshold)
            bmesh.update_edit_mesh(me)

        # Stats report
        msg = (
            f"Selected candidates: {num_selected_candidates} | "
            f"Grouped candidates: {candidate_count_in_groups} | "
            f"Discarded groups (non-manifold risk): {discarded_groups} | "
            f"Confirmed pairs: {num_confirmed_pairs} | "
            f"Prevented by face-collapse: {prevented_face_collapse} | "
            f"Removed vertices: {removed_verts}"
        )
        self.report({'INFO'}, msg)
        return {'FINISHED'}

# --- MESH_OT_edge_merge --- END


def menu_func_edit_verts(self, context):
    self.layout.operator(MESH_OT_zero_x_selected.bl_idname)

def merge_menu_func(self, context):
    layout = self.layout
    layout.separator()
    layout.operator(MESH_OT_edge_merge.bl_idname)


classes = [
    MESH_OT_zero_x_selected,
    MESH_OT_edge_merge
]

def register():

    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(menu_func_edit_verts)
    bpy.types.VIEW3D_MT_edit_mesh_merge.append(merge_menu_func)

def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(menu_func_edit_verts)
    bpy.types.VIEW3D_MT_edit_mesh_merge.remove(merge_menu_func)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
