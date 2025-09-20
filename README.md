# WPEdit Extension

**WPEdit Extension** is a modular Blender add‑on designed to streamline rigging, weight painting, and mesh editing workflows.  
It provides a flexible extension system where submodules can be enabled or disabled individually in the add‑on preferences.  
Each submodule is self‑contained and exposes its own operators, panels, and hotkeys.

---

## 📑 Quick Reference

| Submodule                  | Purpose                                           | Location / Hotkeys |
|-----------------------------|---------------------------------------------------|--------------------|
| **bone_mesh_sync.py**       | Sync bones to mesh via reference vertices         | 3D View > Object Menu > Bone Sync |
| **ebone_rotate.py**         | Rotate edit bones around head                     | 3D View > Sidebar > Edit Tab > Rotate Edit Bones |
| **cursor_rotation_snap.py** | Snap cursor/active with rotation                  | 3D View > Object > Snap Menu |
| **ebone_select.py**         | Select/deselect parent/child bones                | Alt + Numpad + / Alt+Shift+Numpad+ / Alt+Numpad- / Alt+Shift+Numpad- |
| **ebone_slide.py**          | Slide edit bone endpoints                         | Shift + V (Edit Armature Menu) |
| **meshedit.py**             | Mesh edit utilities (zero X, center X, merge preview) | Vertex Menu / Merge Menu |
| **shape_tools.py**          | Reset active shape key to reference               | Sidebar > Shape Keys / Vertex Menu |
| **to_rigify.py** (Experimental) | Map imported rigs to Rigify metarigs          | Sidebar > Rigify Tab |
| **vgroup_show_hide.py**     | Show/Hide/Solo vertex groups                      | Properties > Object Data > Vertex Groups Panel |
| **weights_active_to_selected.py** | Copy active vertex weights to selected     | Vertex Menu |
| **wp_check.py**             | Inspect and manage vertex group weights           | Sidebar > Edit Tab > WPCheck Panel |
| **wp_copy.py**              | Sync overlapping deforming meshes (WPSync)        | Sidebar > Edit Tab > WPSync Panel |
| **wp_mask.py**              | Weight paint masking tools                        | M (Mask From Bones), Ctrl+Numpad+ (Grow), Ctrl+Numpad- (Shrink) |

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
- Updates bones to match moved vertices.  
- Location: *3D View > Object Menu > Bone Sync*.  
- Category: Rigging.

### `ebone_rotate.py`
**Rotate Edit Bones Around Head**  
- Rotate selected edit bones around their heads by fixed or custom angles.  
- Panel: *3D View > Sidebar > Edit Tab > Rotate Edit Bones*.  
- Operators for ±90° around X, Y, Z.  
- Category: Rigging.

### `cursor_rotation_snap.py`
**Cursor Rotation Snap Tools**  
- Snap 3D Cursor to active object, bone, or mesh element with rotation.  
- Orient cursor –Y axis towards active element.  
- Snap active object/bone to cursor with rotation.  
- Location: *3D View > Object > Snap Menu*.  
- Category: 3D View.

### `ebone_select.py`
**Edit Bone Select/Deselect Shortcuts**  
- Hotkeys in Edit Armature Mode:  
  - `Alt + Numpad +` → Select Child Bones  
  - `Alt + Shift + Numpad +` → Select Parent Bones  
  - `Alt + Numpad -` → Deselect Child Bones  
  - `Alt + Shift + Numpad -` → Deselect Parent Bones  
- Location: *3D View > Edit Mode (Armature)*.  
- Category: Rigging.

### `ebone_slide.py`
**Edit Bone Slide**  
- Slide selected edit bone endpoints along the bone’s axis.  
- Fine control with `Shift`.  
- Hotkey: `Shift + V`.  
- Location: *3D View > Edit Mode (Armature) > Armature Menu*.  
- Category: Rigging.

### `meshedit.py`
**Mesh Edit Utilities**  
- Use 
- Operators:  
  - Zero X Selected Vertices  
  - Center Selected X in Edit Mode  
  - Merge by Distance Preview  
- Location:  
  - *3D View > Edit Mode (Mesh) > Vertex Menu*  
  - *3D View > Edit Mode (Mesh) > Merge Menu*  
- Category: Mesh.

### `shape_tools.py`
**Reset Active Shape Key to Reference**  
- Resets active shape key to its reference (relative key or Basis) for selected vertices.  
- Location:  
  - *3D View > Sidebar (N) > Shape Keys*  
  - *3D View > Edit Mode (Mesh) > Vertex Menu*  
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
- Copies deform vertex group weights from the active vertex to all selected vertices.  
- Location: *3D View > Edit Mode (Mesh) > Vertex Menu*.  
- Category: Mesh.

### `wp_check.py`
**WPCheck – Vertex Group Weight Inspector**  
- Inspect and manage vertex group weights of selected vertices.  
- Features: filter groups, select/deselect, delete/zero, apply math operations.  
- Location: *3D View > Sidebar (N) > Edit Tab > WPCheck Panel*.  
- Available in Edit Mode and Weight Paint Mode.  
- Category: Mesh.

### `wp_copy.py`
**WPSync – Copy Weights Across Meshes**  
- Keeps overlapping deforming mesh areas in sync.  
- Tools to assign unique vertex IDs, mark source/destination proximity groups, and transfer weights.  
- Location: *3D View > Sidebar (N) > Edit Tab > WPSync Panel*.  
- Category: Rigging.
- ⚠️ Partially incomplete.

### `wp_mask.py`
**Weight Paint Mask Tools**  
- Used to weight paint only in areas we intend to.
- Operators:  
  - Mask From Bones (`M`)  
  - Mask Grow (`Ctrl + Numpad +`)  
  - Mask Shrink (`Ctrl + Numpad -`)  
- Location: *3D View > Weight Paint Mode > Weights Menu*.  
- Category: Paint.

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

Developed as a modular toolkit for Blender rigging, weight painting, and mesh editing workflows. And yes, LLM is used heavily in development.
