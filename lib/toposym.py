from collections import deque
from enum import Enum
from typing import Any

import bpy
from bmesh.types import BMesh, BMEdge, BMFace, BMVert
from mathutils import kdtree, Vector

# from ..util.timed import timed


class TopoSymType(Enum):
    VERTEX_SOURCE = 1 | 32
    VERTEX_CENTER = 2 | 32
    VERTEX_TARGET = 3 | 32
    VERTEX_SYMMETRIZED = 4 | 32
    VERTEX_ASYMMETRIC = 5 | 32
    VERTEX_CENTER_ERRORS = 6 | 32
    
    FACE_SOURCE = 7 | 64
    FACE_TARGET = 8 | 64
    FACE_SYMMETRIZED = 9 | 64
    FACE_ASYMMETRIC = 10 | 64
    FACE_UNREACHABLE = 11 | 64
    FACE_INITIAL_SYM = 12 | 64
    
    EDGE_NONMANIFOLD = 12 | 128
    
    def get_mode(self):
        if self.value & 32:
            return (True, False, False)
        elif self.value & 64:
            return (False, False, True)
        else:
            return (False, True, False)


class TopoSym:
    def __init__(self, mesh: BMesh, mirror_axis_index=0, mirror_axis_sign=1,\
                 eps: float = 1e-5, shape_key_index: int = -1, limit_steps: int = -1, search_unreachable=True) -> None:
        """
        Initializes the topological resymmetrization process. Symmetry partners are determined.

        Parameters:
        :param mesh:               The Blender BMesh object to be analyzed and resymmetrized.
        :param mirror_axis_index:  The index of the local axis used as the symmetry axis 
                                     (0 for X, 1 for Y, 2 for Z).
        :param mirror_axis_sign:   The direction/side sign (1 or -1) indicating the 
                                     source and target sides relative to the axis.
        :param eps:                Center Epsilon; the tolerance value used to classify vertices 
                                     as being on the center line.
        :param shape_key_index:    An index > 0 indicates an active shape key. In this case
                                     the Basis needs to be used for classification.
        :param limit_steps:        The maximum number of face-mapping iterations to perform. 
                                     If set to -1, the algorithm runs until all reachable faces 
                                     are processed. Debugging purpose.
        :param search_unreachable: If unreachable faces remain, search for symmetric parts
                                     by mirrored location and symmetrize from there.
        """

        self._mirror_axis_index = mirror_axis_index
        self._mirror_axis_sign = mirror_axis_sign
        
        self._mesh: BMesh = mesh
        self._shape_key_index = shape_key_index
        
        if limit_steps == -1:
            limit_steps = 1 << 31

        # Array of VertexInfo objects, parallel to bmesh array.
        # Holds classification and symmetry result data.
        self._vertex_infos: list[VertexInfo] = []

        # Cache of certain types
        self._center_infos: list[VertexInfo] = []
        self._target_infos: list[VertexInfo] = []
        self._source_infos: list[VertexInfo] = []
        self._bad_center_infos: list[VertexInfo] = []
        
        self._non_manifold_edges: list[BMEdge] = []

        self._classify_vertices(eps)
        self._check_center_vertex_valence()

        # check and attempt to symmetrize vertices that directly connect source-target.
        # This also handles edge-only support connections.
        self._extend_noncentered()
        
        
        # Face-related data and processing
        self._face_infos: list[FaceInfo] = []

        # Populate the search FIFO.
        # Usage of this deque: append / popleft
        fifo: deque[FaceInfo] = deque()

        # unconnected, used if search_unreachable
        self._unconnected_targets_sorted = None
        self._unconnected_target_index = 0
        self._source_faces_kdtree = None
        self._eps = eps

        targets = []

        for face in mesh.faces:
            face_info = FaceInfo(face, self._vertex_infos)
            self._face_infos.append(face_info)

            if face_info.is_target:
                targets.append(face_info)
            
            # initials first
            if face_info.is_initial_sym:
                fifo.append(face_info)

        fifo.extend(targets)

        fifo_search_count = len(fifo) + 2
        while len(fifo) > 0 and limit_steps > 0:
            if fifo_search_count == 0:
                if not search_unreachable:
                    return
                else:
                    result = self._search_unconnected(fifo)
                    if not result:
                        return
                    # found something, rerun the search.
                    fifo_search_count = len(fifo) + 2


            face_info = fifo.popleft()
            fifo_search_count -= 1

            if face_info.is_target and not face_info.is_symmetrized:
                # cannot propagate from not-yet-symmetrized faces - re-add to fifo
                fifo.append(face_info)

            elif face_info.is_mapping_finished:
                # drop
                continue

            # center-related or freshly symmetrized faces. Keep going untilface
            # no more neighbours can be mapped.
            elif face_info.is_sym_source or face_info.is_symmetrized:
                while True:
                    next_face: FaceInfo | None = face_info.map_next(
                        mirror_axis_sign, mirror_axis_index, self._vertex_infos, self._face_infos, self._non_manifold_edges)
                    if not next_face:
                        # continue search in fifo
                        break
                    else:
                        # A face was mapped, new paths to already searched faces may have opened, reset the count
                        # so all remaining faces can be searched again
                        fifo_search_count = len(fifo) + 2
                        limit_steps -= 1

                        if limit_steps <= 0:
                            break

                        if not face_info.is_asymmetric and not face_info.is_mapping_finished:
                            fifo.append(face_info)

                        face_info = next_face

    def _search_unconnected(self, fifo: deque['FaceInfo']):
        """
        Try to find a new symmetric face pair among currently unreachable faces.

        Returns True if a new seed face was found and added to the FIFO,
        False if nothing could be found.
        """
        # --- one-time initialization ---
        if not self._unconnected_targets_sorted:
            # Build sorted list of target faces (by distance to mirror plane)

            # sort by distance of face center to mirror plane
            def face_plane_dist(fi: FaceInfo) -> float:
                center = self._get_sk_face_center(fi.face)
                return abs(center[self._mirror_axis_index])

            self._unconnected_targets_sorted = sorted(
                fifo, key=face_plane_dist)
            self._unconnected_target_index = 0

            # Build KD-tree from source-side faces (is_sym_source)
            src_faces = [fi for fi in self._face_infos
                         if fi.is_sym_source and not fi.is_asymmetric]

            if src_faces:
                kd = kdtree.KDTree(len(src_faces))
                for i, fi in enumerate(src_faces):
                    center = self._get_sk_face_center(fi.face)
                    kd.insert((center.x, center.y, center.z), i)
                kd.balance()

                # src_faces still needed to resolve index
                self._source_faces_kdtree = (kd, src_faces)
            else:
                self._source_faces_kdtree = None

        # If we have no KD-tree or no targets, nothing to do
        if not self._source_faces_kdtree or not self._unconnected_targets_sorted:
            return False

        kd, src_faces = self._source_faces_kdtree
        # scan targets from last index
        while self._unconnected_target_index < len(self._unconnected_targets_sorted):
            tgt_fi = self._unconnected_targets_sorted[self._unconnected_target_index]
            self._unconnected_target_index += 1

            # Skip if already symmetrized or asymmetric
            if tgt_fi.is_symmetrized or tgt_fi.is_asymmetric:
                continue

            face = tgt_fi.face

            # mirrored center on source side
            c = self._get_sk_face_center(face)
            c[self._mirror_axis_index] *= -1.0

            # query KD-tree for nearby source faces
            # use a small radius around mirrored center
            candidates = kd.find_range((c.x, c.y, c.z), self._eps)
            if not candidates:
                continue

            good_matches: list[FaceInfo] = []

            # vertex mapping key = target BMVert
            position_mapping_result: dict[BMVert, BMVert] = {}

            for _, idx, _ in candidates:
                src_fi = src_faces[idx]
                src_face = src_fi.face

                # basic checks: same vertex count
                if len(src_face.verts) != len(face.verts):
                    continue

                # per-vertex position check (mirrored)
                ok = True
                position_mapping = {}

                for v_tgt in face.verts:
                    vt = self._get_sk_coordinate(v_tgt).copy()
                    vt[self._mirror_axis_index] *= -1.0

                    # find a vertex on src_face close to vt
                    found = False
                    for v_src in src_face.verts:
                        if (self._get_sk_coordinate(v_src) - vt).length <= self._eps:
                            # optional: valence check
                            if len(v_src.link_edges) != len(v_tgt.link_edges):
                                ok = False
                                break
                            position_mapping[v_tgt] = v_src
                            found = True
                            break
                    if not found or not ok:
                        ok = False
                        break

                # vertex order check
                if ok:
                    # Extract loop vertex indices
                    # BMVert objects
                    tgt_loop = [l.vert for l in face.loops]
                    # BMVert objects
                    src_loop = [l.vert for l in src_face.loops]

                    # Build mirrored target loop using the position_mapping
                    mirrored_tgt_loop = []
                    for v_tgt in tgt_loop:
                        mirrored_tgt_loop.append(position_mapping[v_tgt])

                    if ok:
                        # Convert to vertex indices for comparison
                        mirrored_ids = [v.index for v in mirrored_tgt_loop]
                        src_ids = [v.index for v in src_loop]

                        def loops_match(a, b):
                            """Check if loop a matches loop b under cyclic rotation."""
                            if len(a) != len(b):
                                return False
                            n = len(a)
                            for i in range(n):
                                if all(a[(i + j) % n] == b[j] for j in range(n)):
                                    return True
                            return False

                        # Check forward winding
                        if not loops_match(mirrored_ids, src_ids):
                            # Check reversed winding (mirroring flips orientation)
                            if not loops_match(list(reversed(mirrored_ids)), src_ids):
                                ok = False

                    if ok:
                        position_mapping_result = position_mapping
                        good_matches.append(src_fi)

            # ambiguous or none → skip
            if len(good_matches) != 1:
                continue

            src_fi = good_matches[0]

            for tgt_bmvert, src_bmvert in position_mapping_result.items():
                self._vertex_infos[tgt_bmvert.index].set_partner(
                    self._vertex_infos[src_bmvert.index])

            # We found a unique symmetric source face for this target.
            # Mark them as a new symmetry seed and push target into FIFO.

            # mark as symmetric source/seed

            tgt_fi.is_symmetrized = True  # initial symmetrized face

            return True

        # nothing found
        return False

    def _get_sk_coordinate(self, vertex: BMVert):
        return vertex.co if self._shape_key_index <= 0 else vertex[self._mesh.verts.layers.shape[0]]

    def _get_sk_face_center(self, face: BMFace):
        """Return the face center using shape key coordinates if active."""
        if self._shape_key_index <= 0:
            # Basis → use built‑in center
            return face.calc_center_median()

        # Shape key active → compute center manually from basis
        layer = self._mesh.verts.layers.shape[0]
        acc = None
        count = 0

        for v in face.verts:
            co = v[layer]
            acc = co.copy() if acc is None else (acc + co)
            count += 1

        return acc / count



    # @timed
    def _classify_vertices(self, eps: float):
        # If a shape key is active, we need to use the Basis key for classification.
        # Build lists of types of vertices.
        for v in self._mesh.verts:
            info = VertexInfo(v)
            val = self._get_sk_coordinate(v)[self._mirror_axis_index]
            if abs(val) <= eps:
                info.mark_center()
                self._center_infos.append(info)
            elif (val * self._mirror_axis_sign) > eps:
                info.mark_source()
                self._source_infos.append(info)
            else:
                info.mark_target()
                self._target_infos.append(info)

            self._vertex_infos.append(info)

    # API
    #
    # |  |
    # V  V

    # @timed
    def apply_symmetry(self, only_selected=False):
        '''
        Symmetrizes target side with source. Since v.co is set 
        it means the current shape key is updated if any.
        '''
        if only_selected:
            for info in self._target_infos:
                if info.partner and info.get_is_target() and not info.is_asymmetric:
                    target = info.vert
                    if target.select:
                        target.co = info.partner.vert.co.copy()
                        target.co[self._mirror_axis_index] *= -1
        else:
            for info in self._target_infos:
                if info.partner and info.get_is_target() and not info.is_asymmetric:
                    target = info.vert
                    target.co = info.partner.vert.co.copy()
                    target.co[self._mirror_axis_index] *= -1
                    
    def get_symmetry_mapping(self) -> dict[int, int]:
        '''
        Returns a dictionary containing the symmetry mapping.
        key: source vertex index
        value: target vertex index
        '''
        dict = {}
        for v_info in self._target_infos:
            if v_info.is_symmetrized and not v_info.is_asymmetric and v_info.partner is not None:
                dict[v_info.partner.vert.index] = v_info.vert.index

        return dict

    def get_center_verts(self) -> list[int]:
        result = []

        for info in self._center_infos:
            result.append(info.vert.index)

        return result

    def select_in_bmesh(self, type: TopoSymType, deselect: bool = True):
        '''
        Selects the specified geometry classification.
        If 'deselect' is true, the current selection is cleared.
        '''

        # should be faster than looping through everything
        # Assumes that the bmesh is from the current edit mode object...
        if deselect:
            bpy.ops.mesh.select_all(action='DESELECT')
        
        
        if type == TopoSymType.FACE_ASYMMETRIC:
            for face in self._face_infos:
                if face.is_asymmetric:
                    face.face.select_set(True)
                    
        elif type == TopoSymType.FACE_SOURCE:
            for face in self._face_infos:
                if face.is_sym_source:
                    face.face.select_set(True)
                    
        elif type == TopoSymType.FACE_TARGET:
            for face in self._face_infos:
                if face.is_target:
                    face.face.select_set(True)
                    
        elif type == TopoSymType.FACE_SYMMETRIZED:
            for face in self._face_infos:
                if face.is_symmetrized:
                    face.face.select_set(True)
                    
        elif type == TopoSymType.FACE_UNREACHABLE:
            for face in self._face_infos:
                if face.is_target and (not face.is_symmetrized) and (not face.face.hide):
                    face.face.select_set(True)
                    
        elif type == TopoSymType.VERTEX_ASYMMETRIC:
            for vertex in self._vertex_infos:
                if vertex.is_asymmetric and not vertex.vert.hide:
                    vertex.vert.select_set(True)

        elif type == TopoSymType.VERTEX_CENTER:
            for vertex in self._vertex_infos:
                if vertex.get_is_center():
                    vertex.vert.select_set(True)

        elif type == TopoSymType.VERTEX_CENTER_ERRORS:
            for vertex in self._bad_center_infos:
                vertex.vert.select_set(True)
                
        elif type == TopoSymType.VERTEX_SOURCE:
            for vertex in self._source_infos:
                if vertex.get_is_source():
                    vertex.vert.select_set(True)
                    
        elif type == TopoSymType.VERTEX_TARGET:
            for vertex in self._target_infos:
                vertex.vert.select_set(True)
                    
        elif type == TopoSymType.VERTEX_SYMMETRIZED:
            for vertex in self._vertex_infos:
                if vertex.is_symmetrized:
                    vertex.vert.select_set(True)
                    
        elif type == TopoSymType.EDGE_NONMANIFOLD:
            for edge in self._non_manifold_edges:
                edge.select_set(True)
            pass
        elif type == TopoSymType.FACE_INITIAL_SYM:
            for face in self._face_infos:
                if face.is_initial_sym:
                    face.face.select_set(True)
    
    
    def get_count(self, type: TopoSymType) -> int:
        '''
        Returns the count of geometry found of 
        the specified classification.
        '''

        # --- Vertex types ---
        if type == TopoSymType.VERTEX_CENTER_ERRORS:
            return len(self._bad_center_infos)

        elif type == TopoSymType.VERTEX_CENTER:
            return len(self._center_infos)

        elif type == TopoSymType.VERTEX_ASYMMETRIC:
            count = 0
            for vertex in self._vertex_infos:
                if vertex.is_asymmetric and not vertex.vert.hide:
                    count += 1
            return count

        elif type == TopoSymType.VERTEX_SOURCE:
            count = 0
            for vertex in self._vertex_infos:
                if vertex.get_is_source():
                    count += 1
            return count

        elif type == TopoSymType.VERTEX_TARGET:
            return len(self._target_infos)
            # count = 0
            # for vertex in self._vertex_infos:
            #     if vertex.get_is_target():
            #         count += 1
            # return count

        elif type == TopoSymType.VERTEX_SYMMETRIZED:
            count = 0
            for vertex in self._target_infos:
                if vertex.is_symmetrized:
                    count += 1
            return count

        # --- Face types ---
        elif type == TopoSymType.FACE_ASYMMETRIC:
            count = 0
            for face in self._face_infos:
                if face.is_asymmetric:
                    count += 1
            return count

        elif type == TopoSymType.FACE_SOURCE:
            count = 0
            for face in self._face_infos:
                if face.is_sym_source:
                    count += 1
            return count

        elif type == TopoSymType.FACE_TARGET:
            count = 0
            for face in self._face_infos:
                if face.is_target:
                    count += 1
            return count

        elif type == TopoSymType.FACE_SYMMETRIZED:
            count = 0
            for face in self._face_infos:
                if face.is_symmetrized:
                    count += 1
            return count

        elif type == TopoSymType.FACE_UNREACHABLE:
            count = 0
            for face in self._face_infos:
                if face.is_target and (not face.is_symmetrized) and (not face.face.hide):
                    count += 1
            return count

        elif type == TopoSymType.FACE_INITIAL_SYM:
            count = 0
            for face in self._face_infos:
                if face.is_initial_sym:
                    count += 1
            return count

        # --- Edge types ---
        elif type == TopoSymType.EDGE_NONMANIFOLD:
            return len(self._non_manifold_edges)

    # NOAPI
    #
    # |  |
    # V  V

    # @timed
    def _extend_noncentered(self):
        # When source side verts reach out directly to target verts without a center in between,
        # they can be directly symmetrized
        # s-t
        # | |
        # s-t

        count = 0
        count_asym = 0
        infos = self._vertex_infos

        for info in self._source_infos:
            opp = [infos[n.index]
                   for n in info.neighbors() if infos[n.index].get_is_target()]
            # one target neighbor
            if len(opp) == 1 and not opp[0].vert.hide:
                opp[0].set_partner(info)
                count += 1
            # source side vert with multiple target side neighbors, cannot be symmetric
            elif len(opp) > 1:
                count_asym += 1
                info.mark_asymmetric()
                for partner in opp:
                    partner.mark_asymmetric()
    
    def _check_center_vertex_valence(self):
        # Populate the list of center verts with more than two center neighbors
        center_set = {ci.vert for ci in self._center_infos}

        for info in self._center_infos:
            # Count how many of this vertex's neighbors are also center vertices
            count = sum(1 for n in info.neighbors() if n in center_set)
            if count > 2:
                print("bad center valence")
                self._bad_center_infos.append(info)


class VertexInfo:
    SRC = 4
    TGT = 2
    CEN = 1

    def __init__(self, v: BMVert):
        self.vert = v
        self.is_symmetrized = False
        self.is_asymmetric = False
        self.is_hidden = False
        self.partner = None
        self.loc_flags = 0

    def neighbors(self):
        # Return a list of neighboring bmesh verts.
        return [e.other_vert(self.vert) for e in self.vert.link_edges]

    def set_partner(self, other_info: 'VertexInfo'):
        # Compare valence (number of edges) before assigning partner
        if len(self.vert.link_edges) != len(other_info.vert.link_edges):
            # Mark both as asymmetric if edge counts differ
            self.mark_asymmetric()
            other_info.mark_asymmetric()
            return

        # Assign a symmetric partner and mark both as symmetrized.
        self.partner = other_info
        other_info.partner = self
        self.is_symmetrized = True
        other_info.is_symmetrized = True

    def mark_asymmetric(self):
        self.is_asymmetric = True

    def mark_center(self):
        self.is_symmetrized = True
        self.partner = self
        self.loc_flags = self.CEN

    def mark_source(self):
        self.partner = self
        self.loc_flags = self.SRC

    def mark_target(self):
        self.loc_flags = self.TGT

    def get_is_target(self) -> bool:
        return (self.loc_flags & self.TGT) > 0

    def get_is_source(self) -> bool:
        return (self.loc_flags & self.SRC) > 0

    def get_is_center(self) -> bool:
        return (self.loc_flags & self.CEN) > 0


class FaceInfo:
    # @timed
    def __init__(self, face: BMFace, vertex_infos: list[VertexInfo]):
        self.face: BMFace = face
        # all verts sym source or center
        self.is_sym_source = False
        # from extend/center detect, or mismatching edge count during propagate phase
        self.is_asymmetric = False
        # at least one target vert and not hidden
        self.is_target = False
        # when no further edges can be used to propagate
        self.is_mapping_finished = False
        # all verts are symmetrized
        self.is_symmetrized = False
        # is a candidate to propagate symmetry from
        self.is_initial_sym = False

        self.is_hidden = False

        # sorted list of edges to be mapped, by distance to mirror plane
        self.edge_list = None
        self.edge_index = 0  # this optimization might not be worth it

        # categorize face
        # create vertex list in loop order
        verts: list[BMVert] = [l.vert for l in self.face.loops]

        # counts changes between symm. types
        relations = [0] * 8
        counts = [0] * 8
        hidden_count = 0
        # those already found symmetric from a previous phase (e.g. edge support connections)
        symmetric_count = 0
        asymmetric_count = 0

        # count verts type
        vertices_count = len(verts)
        for i in range(0, vertices_count):
            vert = verts[i]
            vinfo = vertex_infos[vert.index]
            counts[vinfo.loc_flags] += 1

            next = vertex_infos[verts[(i + 1) % vertices_count].index]
            relations[vinfo.loc_flags | next.loc_flags] += 1

            if vert.hide:
                hidden_count += 1
            if vinfo.is_symmetrized and vinfo.get_is_target():
                symmetric_count += 1

            if vinfo.is_asymmetric and vinfo.get_is_target():
                asymmetric_count += 1

        # evaluate results

        # Target / Center
        if counts[VertexInfo.TGT] > 0 and counts[VertexInfo.SRC] == 0:
            self.is_target = True

        # Source only
        elif counts[VertexInfo.CEN] == 0 and counts[VertexInfo.TGT] == 0 and counts[VertexInfo.SRC] > 0:
            self.is_sym_source = True

        # Source + Center
        elif counts[VertexInfo.CEN] > 0 and counts[VertexInfo.TGT] == 0 and counts[VertexInfo.SRC] > 0:
            self.is_sym_source = True
            # can be used for propagating only if a dual center edge is present
            if relations[VertexInfo.CEN] > 0:
                self.is_initial_sym = True

        # hidden is not going to contribute
        elif hidden_count > 0 or face.hide:
            self.is_hidden = True
            self.is_target = False
            return

        # Special symmetry case:
        #  c
        # / \
        # s t
        # | |
        # s-t
        elif counts[VertexInfo.CEN] == 1\
                and counts[VertexInfo.SRC] == counts[VertexInfo.TGT]\
                and relations[VertexInfo.SRC | VertexInfo.TGT] == 1:
            self.map_special_symmetry(verts, vertex_infos)
            self.is_initial_sym = True
            self.is_symmetrized = True

        # Special symmetry case:
        #  c
        # / \
        # s t
        # s t
        # \ /
        #  c
        elif counts[VertexInfo.CEN] == 2\
                and counts[VertexInfo.SRC] == counts[VertexInfo.TGT]\
                and relations[VertexInfo.SRC | VertexInfo.TGT] == 0\
                and relations[VertexInfo.CEN | VertexInfo.TGT] == 2\
                and relations[VertexInfo.CEN | VertexInfo.SRC] == 2:

            self.map_special_symmetry(verts, vertex_infos)
            self.is_initial_sym = True
            self.is_symmetrized = True

        # s-t
        # | |
        # s-t
        elif counts[VertexInfo.CEN] == 0\
                and counts[VertexInfo.SRC] == counts[VertexInfo.TGT]\
                and relations[VertexInfo.SRC | VertexInfo.TGT] == 2:
            self.is_initial_sym = True
            self.is_symmetrized = True
            pass

        # unknown or bad combination
        else:
            # print(f"Face {face.index} asym")
            self.is_target = False
            self.is_asymmetric = True
            return

        # symmetrized from previous stage?
        if (symmetric_count + counts[VertexInfo.SRC] + counts[VertexInfo.CEN] >= vertices_count)\
                and (counts[VertexInfo.SRC] + counts[VertexInfo.CEN] != vertices_count):
            self.is_target = False
            self.is_symmetrized = True
            self.is_initial_sym = True

        if asymmetric_count > 0:
            # print(f"Face {face.index} asym from verts")
            self.is_target = False
            self.is_symmetrized = False
            self.is_asymmetric = True
            self.is_initial_sym = False

    def map_special_symmetry(self, face_verts: list[BMVert], vertex_infos: list[VertexInfo]):
        vertices_count = len(face_verts)

        # find the first center
        center_idx = -1

        for i in range(0, vertices_count):
            vert = vertex_infos[face_verts[i].index]
            if vert.get_is_center():
               center_idx = i
               break

        iterations = 0
        if vertices_count % 2 == 0:
            # even - 2 centers, rest / 2
            iterations = (vertices_count-2)//2
        else:
            # odd - 1 center vertex
            iterations = (vertices_count-1)//2

        for step in range(1, iterations + 1):
            below_idx = (center_idx - step) % vertices_count
            above_idx = (center_idx + step) % vertices_count
            below_vinfo = vertex_infos[face_verts[below_idx].index]
            above_vinfo = vertex_infos[face_verts[above_idx].index]

            if below_vinfo.get_is_target():
                below_vinfo.set_partner(above_vinfo)
            else:
                above_vinfo .set_partner(below_vinfo)

    # @timed
    def map_next(self, mirror_axis_sign: int, axis: int, vertex_infos: list[VertexInfo], face_infos: list['FaceInfo'], non_manifold_edges: list[BMEdge]):
        if not (self.is_symmetrized or self.is_sym_source):
            raise Exception("map_next on non-symmetrized face")

        # asym check, might have been marked by initial step
        for v in self.face.verts:
            vi = vertex_infos[v.index]
            if vi.is_asymmetric:
                self.is_asymmetric = True
                return None

        if self.edge_list is None:
            self.edge_list: list[BMEdge] | None = sorted(
                self.face.edges,
                # sort by distance to axis plane (so it will work its way outward in circles)
                # must use coords from sym side since target ones are still unchanged
                key=lambda e: min(mirror_axis_sign * vertex_infos[v.index].partner.vert.co[axis] for v in e.verts))


        # look for an usable edge
        for edge in self.edge_list:
            # this edge is from a propagatable face. Find the connected face.
            active_link_faces: list[BMFace] = []
            for link_face in edge.link_faces:
                if not link_face.hide:
                    active_link_faces .append(link_face)
            
            if len(active_link_faces) != 2:
                # non-manifold or border edge, cannot use
                if len(active_link_faces) > 2:
                    non_manifold_edges.append(edge)
                continue

            next_face_info = None
            # identify the other face on that edge
            if active_link_faces[0].index == self.face.index:
                next_face_info = face_infos[active_link_faces[1].index]
            else:
                next_face_info = face_infos[active_link_faces[0].index]

            if next_face_info.is_symmetrized or next_face_info.is_asymmetric or next_face_info.is_mapping_finished or not next_face_info.is_target:
                # not usable
                continue

            # print(f"next: {self.face.index} -> {next_face_info.face.index}")

            # find the symmetry source side face of next_face_info
            next_source_side_face_info = None
            se_edge = None

            if vertex_infos[edge.verts[0].index].get_is_center() and vertex_infos[edge.verts[1].index].get_is_center():
                # both verts are center: source is ourself
                # s-c-t
                # | | |
                # s-c-t
                next_source_side_face_info = self
            else:
                # get source
                # sn-------se-s  |  t-----te-------tn
                # |        |  |  |  |      |       |
                # | next_s |  |  |  | self | next  |
                # sn-------se-s  |  t-----te-------tn
                se_vert_0 = vertex_infos[edge.verts[0].index].partner
                se_vert_1 = vertex_infos[edge.verts[1].index].partner

                se_edge = self.find_edge_between(
                    se_vert_0.vert, se_vert_1.vert)

                if se_edge is None:
                    # not sure if this can occur, the verts were marked symmetric after all
                    # if it does, mismatching edge count on verts should mark this asymmetric at another place
                    continue

                active_s_link_faces: list[BMFace] = []
                for link_face in se_edge.link_faces:
                    if not link_face.hide:
                        active_s_link_faces.append(link_face)

                if len(active_s_link_faces) == 1:
                    # border edge
                    # TODO This makes that face asymmetric, figure out what to set
                    continue

                if len(active_s_link_faces) > 2:
                    # non-manifold, cannot use
                    # TODO hidden status
                    non_manifold_edges.append(se_edge)
                    continue

                # identify the source side for self on that edge
                self_vert_partners = set(
                    vertex_infos[v.index].partner.vert.index for v in self.face.verts)

                set0 = set(
                    v.index for v in active_s_link_faces[0].verts)

                if self_vert_partners == set0:
                    # must be the other one
                    next_source_side_face_info = face_infos[active_s_link_faces[1].index]
                else:
                    set1 = set(
                        v.index for v in active_s_link_faces[1].verts)
                    if self_vert_partners == set1:
                        next_source_side_face_info = face_infos[active_s_link_faces[0].index]
                    else:
                        # probably internal error
                        print(
                            f"edge: {se_edge.index}, ref: {self_vert_partners}, set0 {set0}, set1 {set1}")
                        continue

            # assert number of vertices is same
            v_count = len(next_face_info.face.loops)
            if v_count != len(next_source_side_face_info.face.loops):
                next_face_info.is_asymmetric = True
                next_face_info.is_initial_sym = False
                continue

            # print(
                # f"map tgt {next_face_info.face.index} to src {next_source_side_face_info.face.index}")

            # align the vertices
            # 0   s-1   t-2
            # 1   se1   t-1
            # 2   se2   te2
            # 3   s+1   te1
            # 4   s+2   t+1
            # edge, se_edge
            direction = 1
            offset = 0

            edge_v0 = edge.verts[0].index
            edge_v1 = edge.verts[1].index

            source_edge_v0 = vertex_infos[edge.verts[0].index].partner.vert.index
            source_edge_v1 = vertex_infos[edge.verts[1].index].partner.vert.index

            # print(f"e {edge_v0}/{edge_v1}, se {source_edge_v0}/{source_edge_v1}")

            tgt_loop = [l.vert.index for l in next_face_info.face.loops]
            src_loop = [
                l.vert.index for l in next_source_side_face_info.face.loops]

            tgt_v0_idx = 0
            src_v0_idx = 0

            for i in range(0, v_count):
                if src_loop[i] == source_edge_v0:
                    src_v0_idx = i
                    if src_loop[(i+1) % v_count] != source_edge_v1:
                        direction *= -1
                    break

            for i in range(0, v_count):
                if tgt_loop[i] == edge_v0:
                    tgt_v0_idx = i
                    if tgt_loop[(i+1) % v_count] != edge_v1:
                        direction *= -1

                    if direction == -1:
                        # loop orders are opposing (only valid case?), switch direction, search again
                        tgt_loop.reverse()
                        for i in range(0, v_count):
                            if tgt_loop[i] == edge_v0:
                                tgt_v0_idx = i
                                break
                    break

            offset = src_v0_idx - tgt_v0_idx

            # print(
            #     f"src loop {src_loop}, tgt loop {tgt_loop}, offset {offset}, direction {direction}")

            # map the vertices
            asym = False

            for i in range(0, v_count):
                src = vertex_infos[src_loop[i]]
                tgt = vertex_infos[tgt_loop[(i-offset) % v_count]]
                # print(f"{next_face_info.face.index}: {src.vert.index}->{tgt.vert.index}")

                if tgt.is_asymmetric:
                    asym = True

                if len(tgt.vert.link_edges) != len(src.vert.link_edges):
                    tgt.mark_asymmetric()
                    src.mark_asymmetric()
                    asym = True

            if asym:
                next_face_info.is_asymmetric = True
                next_face_info.is_target = False
                continue

            for i in range(0, v_count):
                src = vertex_infos[src_loop[i]]
                tgt = vertex_infos[tgt_loop[(i-offset) % v_count]]

                if (not tgt.get_is_center()) and tgt.get_is_target():
                    tgt.set_partner(src)
                    # print(f"{next_face_info.face.index}: {src.vert.index}->{tgt.vert.index}!")

            next_face_info.is_symmetrized = True
            return next_face_info

        # found nothing in all the edges
        # caller will have to search for another face
        self.is_mapping_finished = True
        return None

    def find_edge_between(self, v0: BMVert, v1: BMVert):
        for e in v0.link_edges:
            if v1 in e.verts:
                return e
        return None

