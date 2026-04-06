# k-blender-tools

**k-blender-tools** is a modular Blender add‑on designed to streamline rigging, weight painting, and mesh editing workflows.  
It provides a flexible extension system where submodules can be enabled or disabled individually in the add‑on preferences.  
Each submodule is self‑contained and exposes its own operators, panels, and hotkeys.

---

## 📑 Quick Reference

| Submodule                   | Purpose                                           | Location / Hotkeys |
|-----------------------------|---------------------------------------------------|--------------------|
| **bone_mesh_sync.py**       | Sync bones to mesh via reference vertices         | 3D View > Object Menu > Bone Sync |
| **ebone_align.py**          | Flatten bone chain and adjust roll                | Edit Armature Menu |
| **ebone_rotate.py**         | Rotate edit bones around head                     | 3D View > Sidebar > Edit Tab > Rotate Edit Bones |
| **ebone_slide.py**          | Slide edit bone endpoints                         | Shift + V (Edit Armature Menu) |
| **cursor_rotation_snap.py** | Snap cursor/active with rotation                  | 3D View > Object > Snap Menu |
| **cursor_presets.py**       |	Save and restore 3D Cursor transforms	            | Sidebar > View Tab > 3D Cursor Panel |
| **drivers.py**              | Driver related: Drive Shape Keys from Active      | 3D View > Object Menu |
| **ebone_select.py**         | Extend/Reduce parent/child bones selection        | Alt + Numpad + / Alt+Shift+Numpad+ / Alt+Numpad- / Alt+Shift+Numpad- |
| **mesh_edit.py**            | Mesh edit utilities (zero X, merge coincident edges) | Vertex Menu / Merge Menu |
| **mesh_select.py**          | Mesh selection utilities (Merge Preview, select UV Island Borders) | Merge Menu / Select Menu |
| **tris_to_quads_edges.py**  | Selects edges that 'Tris to Quads' would dissolve | Face Menu |
| **shape_tools.py**          | Tools related to shape keys                       | Properties Editor > Object Data Properties (Mesh) > Shape Keys > 'Shape Key Specials' dropdown |
| **to_rigify.py** (Experimental) | Map imported rigs to Rigify metarigs          | Sidebar > Rigify Tab |
| **vgroup_show_hide.py**     | Show/Hide/Solo vertex groups                      | Properties > Object Data > Vertex Groups Panel |
| **weights_active_to_selected.py** | Copy active vertex weights to selected      | Vertex Menu |
| **wp_check.py**             | Inspect and manage vertex group weights           | Sidebar > Edit Tab > WPCheck Panel |
| **wp_copy.py**              | Sync overlapping deforming meshes (WPSync)        | Sidebar > Edit Tab > WPSync Panel |
| **wp_mask.py**              | Weight paint masking tools                        | M (Mask From Bones), Ctrl+Numpad+ (Grow), Ctrl+Numpad- (Shrink) |
| **select_mode_toggle.py**   | Cycle selection/masking modes with Mouse Button 5 | Edit Mode (Vertex/Edge/Face), Weight/Vertex/Texture Paint Modes |
| **centerline_align.py**     | Align mesh to global axis using best-fit plane    | View3D > Edit Mode > Mesh > Align Selected to Plane |
| **shape_key_edit_hint.py**  | Show on‑screen hint when editing non‑Basis shape keys | 3D View (Edit/Sculpt Modes) |
| **resymmetrize.py**         | Resymmetrizes vertex positions using topology     | Edit Mode > Mesh > Topology Resymmetrize |

---

## ✨ Features

- Modular architecture: enable/disable submodules separately in Preferences.
- Each submodule declares its own `bl_info` metadata.
- Tools for rigging, weight painting, vertex group management, and mesh editing.
- Hotkeys and menu entries integrated into Blender’s standard UI.
- Integrated **logging system** with configurable log level in the add‑on preferences (Off, Error, Warning, Info, Debug).

---

## ⚙️ Installation

### For Blender 4.2+ Users

1. **Download:**  
   Download the repository as a ZIP file (Code → Download ZIP).

2. **Install the Add-on:**  
   In Blender, navigate to:
   - **Edit > Preferences > Add-ons > Add-Ons Settings** (click the dropdown symbol)
   - Select **Install from Disk** and point to the downloaded ZIP file.

### For Older Blender Versions

This add-on has mainly been tested on Blender 4.4. It also loads in Blender 3.6 and may be compatible with other older versions. Functionality was not tested though. To install:

1. **Download:**
   As above
2. **Install the Add-on:**  
   In Blender, navigate to:
   - **Edit > Preferences > Add-ons**
   - Select **Install...** and point to the downloaded ZIP file.

---

## 📦 Submodules

(See the [Quick Reference](#-quick-reference) table above for a summary. Detailed descriptions follow.)

### `bone_mesh_sync.py`
**Sync Bones to Mesh via Reference Vertices**  
- Creates reference vertices at bone heads/tails.
- Proportional editing can be done on the mesh, also affecting these vertices.
- After edit, updates bones to match moved vertices.  
- Location: *3D View > Object Menu > Bone Sync*.  
- Category: Rigging.

### `ebone_align.py`
**Flatten Bone Chain to Plane**  
Projects an entire bone chain onto a plane, ensuring clean planar alignment for rigging, or corrective adjustments.

- Works in **Armature Edit Mode**.
- The plane is defined automatically using:
  - The chain’s **start and end joints**, and  
  - The **center of the intermediate joints**  
  producing a best‑fit plane for the whole chain.
- Optional **roll alignment**:
  - Keep existing roll  
  - Align +Z, –Z, +X, or –X axis of the first bone to the plane normal  
  - Optionally propagate roll alignment to **all bones** in the chain
- Optional: Align to the coordinate system
- Intended for finger rigging. LLMs think there are also other uses:
  - Straightening limbs or tentacles  
  - Fixing twisted imported rigs  
  - Preparing bones for IK setups  
  - Ensuring planar deformation for mechanical rigs
- **Location:** *Armature Edit Mode > Armature > Flatten Bone Chain*  
- **Category:** Rigging

### `ebone_rotate.py`
**Rotate Edit Bones Around Head**  
- Rotate selected edit bones around their heads by fixed or custom angles.  
- Panel: *3D View > Sidebar > Edit Tab > Rotate Edit Bones*.  
- Operators for ±90° around X, Y, Z.  
- Category: Rigging.

### `ebone_select.py`
**Edit Bone Select/Deselect Shortcuts**  
- Hotkeys in Edit Armature Mode:  
  - `Alt + Numpad +` → Extend Child Bones  
  - `Alt + Shift + Numpad +` → Extend Parent Bones  
  - `Alt + Numpad -` → Reduce Child Bones  
  - `Alt + Shift + Numpad -` → Reduce Parent Bones  
- Location: *3D View > Edit Mode (Armature) > Select*.  
- Category: Rigging.

### `ebone_slide.py`
**Edit Bone Slide**  
- Slide selected edit bone endpoints along the bone’s axis.  
- Fine control with `Shift`.  
- Hotkey: `Shift + V`.  
- Location: *3D View > Edit Mode (Armature) > Armature Menu*.  
- Category: Rigging.

### `cursor_rotation_snap.py`
**Cursor Rotation Snap Tools**  
- Snap 3D Cursor to active object, bone, or mesh element with rotation.  
- Orient cursor –Y axis towards active element.  
- Snap active object/bone to cursor with rotation.  
- Location: *3D View > Object > Snap Menu*.  
- Category: 3D View.

### `cursor_presets.py`
**Cursor Presets**
- Save and restore 3D Cursor transforms (location and rotation).
- Manage multiple presets via a list in the 3D Cursor panel.
- Operators:
    - Add Cursor Preset – store current cursor transform.
    - Remove Cursor Preset – delete selected preset.
    - Apply Cursor Preset – restore cursor to stored transform.
- Optionally enable Auto Apply to automatically apply the preset when the selection changes.
- Location: 3D View > Sidebar (N) > View Tab > 3D Cursor Panel.
- Category: 3D View.

### `drivers.py`
**Driver Utilities**  
- Operators:
  - Drive Shape Keys from Active
    - Link matching shape keys on selected objects to the active object using drivers. If multiple objects have shape keys with same name, they can all be changed from the active object. I.e. eyelashes/brows from face.
    - Location: Object mode, Object menu.

### `mesh_edit.py`
**Mesh Edit Utilities**  
- Operators:  
  - Zero X Selected Vertices  
  - Merge Coincident Edges – merge only selected edges that are coincident. Useful for imports of file formats that only support UV island mesh connectivity. Unlike Blenders *Merge By Distance* it will avoid collapsing whole faces or creating non-manifold geometry.

- Location:  
  - *3D View > Edit Mode (Mesh) > Vertex Menu*
  - *3D View > Edit Mode (Mesh) > Merge Menu* or **M** hotkey
- Category: Mesh.

### `mesh_select.py`
**Mesh Selection Utilities**  
- Operators:  
  - Merge by Distance Preview
    - Location: *3D View > Edit Mode (Mesh) > Merge Menu* or **M** hotkey
  - Select UV Island Borders – Selects all edges and vertices that enclose the UV islands."
    - Location: *3D View > Edit Mode (Mesh) > Select*
- Category: Mesh.

### `tris_to_quads_edges.py`
**Tris to Quads (Select Only)**  
Selects edges which Blender’s *Tris to Quads* operator would dissolve—without modifying the mesh. This allows to correct the selection before dissolving the edges.

- Works in **Edit Mode**.
- Using *Invert Selection* afterwards may highlight regions that *did not* convert cleanly.
- Parameters for *Tris to Quads* are forwarded
- Does **not** alter the original mesh.
- **Location:** *3D View > Edit Mode > Face > Tris to Quads (Select Only)*  
- **Category:** Mesh  

### `shape_tools.py`
**Shape Key Tools**
- Provides tools for working with shape keys in Edit Mode:
  - Reset the active shape key to match its reference (Basis or relative key) for selected vertices.
  - Select vertices that differ from the reference shape.
  - Reduce current selection to only vertices that differ from the reference.
  - Transfer selected vertices from the active shape key into the Basis.
  - Transfer selected vertices from the active shape key into the Basis, and update all other shape keys.
  - Move selected verts from active shape key into a new shape key.
  - Copy selected verts from active shape key into a new shape key.
  - Copy selected vertices from the active shape key into the only muted shape key. Mute is used as a workaround to indicate the target shape key.
- Object Mode:
  - Change the current shape key value to 1, keep the shape

- Location:  
  - *Properties Editor > Object Data Properties (Mesh) > Shape Keys > 'Shape Key Specials' dropdown*  
- Category: Mesh.

### `to_rigify.py` (Experimental)
**Rigify Bone Mapper**  
- Experimental tools to map imported rigs to Rigify metarigs.  
- Operators: Export Metarig Bones, Scan Imported Rig, Generate Mapping via LLM, Apply Mapping, Transfer Mesh Weights.  
- Location: *3D View > Sidebar (N) > Rigify Tab*.  
- Category: Rigging.  
- ⚠️ Experimental – may be unstable.

### `vgroup_show_hide.py`
**Vertex Group Show/Hide/Solo**  
- Adds buttons to the Vertex Groups panel: Show, Hide, Solo active group.  
- Location: *Properties > Object Data > Vertex Groups Panel*.  
- Category: Mesh.

### `weights_active_to_selected.py`
**Copy Active Vertex Weights to Selected**  
- Copies deform vertex group weights from the active vertex to all selected vertices. Useful for solid parts on a deformed mesh.
- Location: *3D View > Edit Mode (Mesh) > Vertex Menu*.  
- Category: Mesh.

### `wp_check.py`
**WPCheck – Vertex Group Weight Inspector**  
- Inspect and manage vertex group weights of selected vertices.  
- Features: filter groups, select/deselect, delete/zero, apply math operations, move weight to bone, fill missing weights.
- Location: *3D View > Sidebar (N) > Edit Tab > WPCheck Panel*.  
- Available in Edit Mode and Weight Paint Mode.  
- Category: Mesh.

### `wp_copy.py`
**WPSync – Copy Weights Across Meshes**  
- Keeps overlapping deforming mesh areas in sync.  
- Tools to assign unique vertex IDs, mark source/destination proximity groups, and transfer weights.  
- Location: *3D View > Sidebar (N) > Edit Tab > WPSync Panel*.  
- Category: Rigging.
- ⚠️ Incomplete.

### `wp_mask.py`
**Weight Paint Mask Tools**  
- Used to weight paint only in areas we intend to.
- Operators:  
  - Mask From Bones (`M`)  
  - Mask Grow (`Ctrl + Numpad +`)  
  - Mask Shrink (`Ctrl + Numpad -`)  
- Location: *3D View > Weight Paint Mode > Weights Menu*.  
- Category: Paint.

### `select-mode-toggle.py`

**MB5 Cycle Selection Mode**
- Use Mouse Button 5 to cycle through selection or masking modes depending on context:
  - Edit Mode: Vertex → Edge → Face
  - Weight/Vertex Paint: Face Mask → Vertex Mask → No Mask
  - Texture Paint: Toggle Face Mask
- Location: Edit Mode, Weight Paint, Vertex Paint, Texture Paint.
- Category: 3D View.
- Note: Disabled by default. Can be enabled in add‑on preferences.

### `centerline_align.py`

**Align Mesh to Axis (Best-Fit Plane)**

- Computes a best‑fit plane from the selected vertices.
    Rotates the mesh so the plane’s normal aligns with a chosen global axis (X, Y, or Z).
    Optionally recenters the selection on the origin along that axis.
- Use e.g. when an imported model is not properly aligned:
  - Select the center loop
  - Run the operator
- Location: View3D > Edit Mode > Mesh > Align Selected to Plane.
- Category: Mesh.

### `shape_key_edit_hint.py`
**Shape Key Edit Hint**  
- Displays a large, prominent text overlay in the 3D View when a non‑Basis shape key is active.  
- Works in **Edit Mode** and **Sculpt Mode**.  
- Uses Blender’s theme colors for consistency with the UI.  
- Helps prevent accidental edits to shape keys instead of the base mesh.  
- Location: *3D View (Edit Mode / Sculpt Mode)*.  
- Category: 3D View.  
- Disabled by default (can be enabled in add‑on preferences). 

### `resymmetrize.py`
**Topological Resymmetrization**  
- Restores symmetry on meshes with mostly symmetrical topology by inferring vertex pairs through topological connections. No more fear of destroying symmetry on a progressed model.
- Compared to Blender Built-Ins:
  - **Symmetrize** - Deletes and replaces geometry with a mirrored copy. Deadly if there is already asymmetric data on it such as UVs.
  - **Snap to Symmetry** - Only works reliably when each vertex is still closest to its true symmetric counterpart.
  - **Topology Mirror** (Mirroring Options) - C++ performance and integrated into mesh editing system. Breaks on slightest asymmetry, cannot help with symmetrizing unconnected parts and highlighting asymmetries.
- Works in **Edit Mode**.
- Internally, the algorithm runs in three stages:
  - Classifies vertices by position into source side, center loop, and target side (configurable in the operator panel).
  - Detects initial faces and propagate symmetry from them, creating pair relations
  - Copies mirrored coordinates from the source side to the target side.
- Separate mesh parts (e.g., eyeballs) can be symmetrized by identifying a matching face and linking corresponding edge vertices with temporary helper edges in the correct order. With the option 'Position Based' on, a counterpart will be searched by mirrored position, a face needs to be already symmetric. 
- Limitations:
  - Non-manifold geometry cannot be symmetrized.
  - A center loop is optional (e.g., a cube can still be symmetrized), but if present it must be detected accurately. Vertices must lie exactly on the symmetry axis or within the provided epsilon.
  - Asymmetries are detected by comparing edge counts per vertex. If they differ, the affected face cannot be used for propagation and the vertex will not receive a mirrored position.
  - Overlapping separate parts must be moved apart so they can be classified cleanly as source or target. They can be moved back afterward.
- Debug options:  
  Select elements from different stages of the algorithm. Can be used to highlight asymmetries without applying the symmetry. 
- Respects hidden geometry:
  - Hidden non‑manifold regions on the target side are excluded (you can alternately hide non-manifold parts to eventually symmetrize everything)
  - Hidden target‑side faces are skipped for performance.
  - Hidden elements on the target side can be used to intentionally exclude asymmetrical areas.
- Optionally apply symmetry **only to selected vertices**.
- Performance:<br>
  On a CPU with a ~3360 single‑thread score (popular benchmark site), a 100k‑face mesh (with half the faces on the target side being processed) completes in roughly **1.3 seconds**.<br>
  The first prototype required **1 minute** for a 10k‑face mesh.
- Location: *3D View > Mesh > Topology Resymmetrize*.
- Category: Mesh.

### `action_manager.py`
**Action Slot Assigner**  
Associates actions with objects, provides correction operators, assigns action slots to matching objects

- Assign, organize, and reorder actions directly on the active object
- Choose and apply an action to all objects referenced by action slots
  - For most animation types the slot name and object name need to match
  - NODETREE and MATERIAL types require the slot name to match the material name
  - Not all animation types implemented

- Reorient bones of imported models with existing animations
  1. Preconditions: Bone F-curves are quaternions, interpolation type linear and keyed per frame. Other modes not supported.
  2. Assign all related actions to the armature.
  3. Armature selected, run 'Store Rest Pose' (stores it in a custom property on the bone).
  4. Change rotations/length/roll of bones in armature edit mode. Don't change head location.
  5. Run 'Correct Bone Rotations'. It will adapt all assigned actions so the animations look as before.
  6. Repeat from 3. if needed.
- Operator for correcting keyframe offsets if imported at wrong FPS setting
- Batch rename actions
- Blender versions without Action Slots can still run the other operators.
- **Location:** *3D View > Animation Tab > Action Slots*  
- **Category:** Rigging / Animation  

---

## 🧩 Extension System

- Submodules are discovered dynamically.  
- Each submodule can be toggled on/off in the add‑on preferences.  
- Metadata (`bl_info`) is refreshed at load time.  
- Persistent settings ensure user preferences are remembered across sessions.  
- Integrated **logging system**: configure the log level (Off, Error, Warning, Info, Debug) in the add‑on preferences to control console output.

---

## 📖 License

This project is licensed under the terms of the [GNU General Public License v3.0](LICENSE).

---

## 🤝 Contributions

This project is primarily developed for personal Blender workflows.  
I don’t intend to run a full open‑source project around it, so my time for maintenance will be limited.  
That said, I’m open to **ideas, suggestions, or small contributions** if they align with the goals of the extension.  
Please understand that responses to issues or pull requests may be slow.

---

## 📝 Acknowledgements

LLMs used in development.