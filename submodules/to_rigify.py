import os
from .. import log
from bpy.types import Operator
import bpy
import json
import bpy, os, json, requests
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator, Panel, PropertyGroup, AddonPreferences
from collections import defaultdict

bl_info = {
    "name": "Rigify Bone Mapper (Experimental)",
    "author": "",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": (
        "3D View > Sidebar (N) > Rigify Tab\n"
        "Operators: Export Metarig Bones, Scan Imported Rig,\n"
        "Generate Mapping via LLM, Apply Mapping, Transfer Mesh Weights"
    ),
    "description": (
        "Experimental tools to assist in mapping bones from an imported rig\n"
        "to a Rigify metarig. Includes operators to export/import bone lists,\n"
        "generate mapping prompts, apply mappings to metarigs, and transfer\n"
        "mesh weights to the Rigify rig."
    ),
    "warning": "Experimental – may be unstable",
    "doc_url": "",
    "category": "Rigging",
}


#  Operators

class RBM_OT_ExportMetarigBones(Operator):
    """Export current metarig bone names to JSON"""
    bl_idname = "rbm.export_metarig"
    bl_label  = "Export Metarig Bones"
    
    filepath: StringProperty(subtype="FILE_PATH")
    
    def execute(self, context):
        # fail if the blend file isn't saved
        if not bpy.data.filepath:
            self.report(
                {'ERROR'}, "Please save your .blend file before scanning bones")
            return {'CANCELLED'}
        
        arm = context.object
        names = [b.name for b in arm.data.bones]
        names.sort()
        
        dir  = os.path.dirname(bpy.data.filepath) or os.getcwd()
        path = bpy.path.ensure_ext(os.path.join(dir, "metarig_bones.json"), ".json")
        with open(path, "w") as f:
            json.dump(names, f, indent=2)
        self.report({'INFO'}, f"Metarig bone list → {path}")
        return {'FINISHED'}


class RBM_OT_ScanImportedBones(Operator):
    """Gather names and direct parent names from the active Armature"""
    bl_idname = "rbm.scan_imported"
    bl_label = "Scan Imported Rig"

    def execute(self, context):
        # fail if the blend file isn't saved
        if not bpy.data.filepath:
            self.report(
                {'ERROR'}, "Please save your .blend file before scanning bones")
            return {'CANCELLED'}

        arm = context.object
        if arm.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object is not an Armature")
            return {'CANCELLED'}

        bones_info = []
        for bone in arm.data.bones:
            bones_info.append({
                "name":   bone.name,
                "parent": bone.parent.name if bone.parent else None
            })

        bones_info.sort(key=lambda e: e["name"])

        directory = os.path.dirname(bpy.data.filepath)
        filepath = bpy.path.ensure_ext(
            os.path.join(directory, "imported_bones.json"),
            ".json"
        )

        with open(filepath, "w") as f:
            json.dump(bones_info, f, indent=2)

        self.report({'INFO'}, f"Imported bones → {filepath}")
        return {'FINISHED'}

class RBM_OT_CallLLMMap(Operator):
    """Call local Ollama to generate a mapping JSON"""
    bl_idname = "rbm.call_llm"
    bl_label  = "Generate Mapping via LLM"
    
    def execute(self, context):
        dir = os.path.dirname(bpy.data.filepath) or os.getcwd()
        with open(os.path.join(dir, "metarig_bones.json")) as f:
            meta_list = json.load(f)
        with open(os.path.join(dir, "imported_bones.json")) as f:
            imp_list = json.load(f)
            
        # craft prompt embedding the two lists
        prompt = (
            "You are given two lists: the first is Rigify metarig bone names,"
            "the second is bone names and their immediate parents from an imported rig.\n"
            f"Rigify list: {meta_list}\n"
            f"Imported list: {imp_list}\n\n"
            "The bones need to be matched from the imported rig to rigify metarig names."
            "Make sure each imported bone name is mapped at least with a category.\n"
            "\n"
            "Please Output a JSON array where each item is:\n"
            "{\n"
            '  "comment": <reasoning about this mapping if non-trivial and translation if non-English>,\n'
            '  "imported": <name from Imported list>,\n'
            '  "rigify": <Name from Rigify list if mappable, else see below>,\n'
            '  "category": one of ["mappable","cloth","hair","accessory","IK","attach_point","non-human-body","unmappable"]\n'
            "}\n"
            "Additional hints for bone names:\n"
            "- Finger 0 is the thumb in the ValveBiped rig.\n"
            "- Accessory could also be a teddy bear that is worn.\n"
            "- If encountered, Digit11 is the thumb and Digit21 is the index.\n"
            "- When tail-alikes are attached to the head, let's assume braids (hair).\n"
            "- If only one toe available on the foot, map it to the non-indexed toe.\n"
            "- Don't correct 'lft' and 'rght' but keep them. These are assymetrical parts and this naming should prevent Blender from symmetrizing them."
            "\n"
            "If a name is not mappable, please convert the name to Rigify scheme (<meaningful name, don't repeat chain index here>.<number, if part of bone chain>.<L/R location>) "
            'and place it in the "rigify" field. Don''t write a category as item/function, use an identifier from the imported bone.\n'
            "An item has to be created for each imported bone name. Don't aggregate or skip symmetric parts.\n"
            "attach_point is only for bones that can be very clearly identified as such, i.e. 'weapon_attach'.\n"
            "Only map true homologues (e.g. thigh→thigh), do not map thigh→shin. "
            "Mark extras as one of the additional categories. "
            "Mark it as unmappable if it doesn't fit any of the other categories.\n"
            'Only existing imported bones must be mentioned in the "imported" field.\n'
            'If there are more segments in a chain (i.e. spine) than the Rigify rig has, preferrably keep the end segments and drop excess in the middle.\n'
        )
        # dump prompt for debugging
        with open(os.path.join(dir, "bone_mapping_prompt.txt"), "w", encoding="utf-8") as pf:
            _ = pf.write(prompt)
        return {'CANCELLED'}
    
        # build and send request
        payload = {
            "model": "mistral-nemo",    # or another local 12B model
            "prompt": prompt,
            "stream": False,
            "temperature": 0.2,
        }
        print(f"Request posted")
        res = requests.post("http://localhost:11434/api/generate", json=payload)
        print(f"API response: {res.status_code}")
        
        # dump raw response for debugging
        with open(os.path.join(dir, "bone_mapping_raw.txt"), "w", encoding="utf-8") as rf:
            _ = rf.write(f"Status: {res.status_code}\n\n")
            _ = rf.write(res.text)
        
        # handle errors
        if res.status_code != 200:
            self.report(
                {'ERROR'},
                f"LLM request failed [{res.status_code}]: {res.text[:200]}"
            )
            return {'CANCELLED'}
        
        # parse the JSON safely
        try:
            data = res.json()
        except ValueError:
            self.report(
                {'ERROR'},
                "Server returned invalid JSON: " + res.text[:200]
            )
            return {'CANCELLED'}
        
        # extract the generated mapping
        response = data["response"]
        
        
        # TODO the model responds with "Here's a JSON array that ... ```json ... ```"
        # We need to cut this part out
        # Maybe we can also detect if a model directly responds with [ or {
        
        outpath = os.path.join(dir, "bone_mapping.json")
        with open(outpath, "w") as f:
            f.write(response)
        self.report({'INFO'}, f"Mapping JSON → {outpath}")
        return {'FINISHED'}


def assign_bonegroup(arm_obj: bpy.types.Object, groupname: str, bone_names):
    """
    Creates/retrieves a bone collection (new in Blender 4.0) named groupname and
    assigns the specified bones to it.
    """
    # ensure we're in POSE mode
    bpy.ops.object.mode_set(mode='POSE')
    coll = arm_obj.data.collections.get(groupname)
    if not coll:
        coll = arm_obj.data.collections.new(groupname)
    for bn in bone_names:
        bone = arm_obj.data.bones.get(bn)
        if bone:
            coll.assign(bone)


class RBM_OT_ApplyMapping(Operator):
    """Read bone_mapping.json, rename & reposition bones accordingly."""
    bl_idname = "rbm.apply_mapping"
    bl_label = "Apply Bone Mapping"

    def execute(self, context):
        log.info("RBM_OT_ApplyMapping called")

        # 1. Load JSON files
        blend_dir = os.path.dirname(bpy.data.filepath) or os.getcwd()
        mapping_path = os.path.join(blend_dir, "bone_mapping.json")
        metarig_path = bpy.path.ensure_ext(
            os.path.join(blend_dir, "metarig_bones"), ".json")
        imported_path = bpy.path.ensure_ext(
            os.path.join(blend_dir, "imported_bones"), ".json")

        try:
            mapping = json.load(open(mapping_path, "r"))
            metarig_bones = set(json.load(open(metarig_path, "r")))
            imported_bones_data = json.load(open(imported_path, "r"))
            imported_bone_names = {b["name"] for b in imported_bones_data}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read JSON files: {e}")
            return {'CANCELLED'}

        # 2. Consistency checks

        # 2.1 "imported" must be unique
        imported_list = [e["imported"] for e in mapping]
        if len(imported_list) != len(set(imported_list)):
            self.report(
                {'ERROR'}, "'imported' entries in mapping are not unique.")
            return {'CANCELLED'}

        # 2.2 "rigify" must be unique
        rigify_list = [e["rigify"] for e in mapping]
        if len(rigify_list) != len(set(rigify_list)):
            self.report(
                {'ERROR'}, "'rigify' entries in mapping are not unique.")
            return {'CANCELLED'}

        # 2.3 Remove entries whose imported bone isn't in imported_bones.json
        clean_mapping = []
        for e in mapping:
            if e["imported"] not in imported_bone_names:
                log.info(
                    f"Removing mapping for unknown imported bone '{e['imported']}'")
                continue
            clean_mapping.append(e)
        mapping = clean_mapping

        # 2.4 For "mappable", rigify must exist in metarig_bones.json
        for e in mapping:
            if e["category"] == "mappable" and e["rigify"] not in metarig_bones:
                self.report({'ERROR'},
                            f"Rigify bone '{e['rigify']}' not found in metarig_bones.json")
                return {'CANCELLED'}

        # 3. Find the two selected armatures: imported rig and metarig
        arms = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if len(arms) != 2:
            self.report(
                {'ERROR'}, "Select exactly two armatures (imported rig + Rigify metarig).")
            return {'CANCELLED'}

        # Assign by matching bone names
        def score_match(obj, names):
            return len({b.name for b in obj.data.bones}.intersection(names))

        # Imported rig will match imported_bone_names
        scores = [(arm, score_match(arm, imported_bone_names)) for arm in arms]
        imported_obj = max(scores, key=lambda x: x[1])[0]
        metarig_obj = [a for a in arms if a != imported_obj][0]

        # 4. Switch to Edit Mode on metarig (must be active)
        bpy.ops.object.mode_set(mode='OBJECT')
        for o in arms:
            o.select_set(True)
        context.view_layer.objects.active = metarig_obj
        bpy.ops.object.mode_set(mode='EDIT')
        meta_editbones = metarig_obj.data.edit_bones
        imp_bones = imported_obj.data.edit_bones

        # Build parent lookup for imported bones
        imported_parent = {b["name"]: b["parent"] for b in imported_bones_data}

        # Build map from imported->rigify for parenting new bones
        imp2rig = {e["imported"]: e["rigify"] for e in mapping}
        
        # prepare a dict of category → [bone_names] for later grouping
        super_copy_map = defaultdict(list)

        # 5. Apply mapping
        for e in mapping:
            imp_name = e["imported"]
            rig_name = e["rigify"]
            cat = e["category"]

            if cat == "mappable":
                eb = meta_editbones[rig_name]
                ib = imp_bones[imp_name]
                # Copy rest-pose transform: head/tail/local matrix
                eb.head = ib.head.copy()
                eb.tail = ib.tail.copy()
                eb.roll = ib.roll
                eb.length = ib.length
                log.info(f"Mapped '{imp_name}' -> '{rig_name}'")

            elif cat in {"cloth", "hair", "accessory"}:
                ib = imp_bones[imp_name]
                if rig_name in meta_editbones:
                    nb = meta_editbones[rig_name]
                else:
                    nb = meta_editbones.new(rig_name)
                nb.head = ib.head.copy()
                nb.tail = ib.tail.copy()
                nb.roll = ib.roll
                nb.length = ib.length
                nb.use_connect = ib.use_connect

                # Set parent if possible
                par_imp = imported_parent.get(imp_name)
                par_rig = imp2rig.get(par_imp)
                if par_rig and par_rig in meta_editbones:
                    nb.parent = meta_editbones[par_rig]
                    
                # mark for super_copy rigify_type assignment
                super_copy_map[cat].append(rig_name)
            else:
                log.info(f"Ignoring mapping '{imp_name}' category '{cat}'")

        # 6. Return to OBJECT mode
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 7. Assign rigify_type in Pose Mode
        if super_copy_map:
            context.view_layer.objects.active = metarig_obj
            bpy.ops.object.mode_set(mode='POSE')
            
            for category, bones in super_copy_map.items():
                for bn in bones:
                    pb = metarig_obj.pose.bones.get(bn)
                    if not pb:
                        continue

                    # set rigify_type
                    pb.rigify_type = "basic.super_copy"
                    log.info(f"Assigned super_copy to pose bone '{bn}'")

                # assign to bone‐group named after category
                assign_bonegroup(metarig_obj, category.capitalize(), bones)
             
            bpy.ops.object.mode_set(mode='OBJECT')

        self.report({'INFO'}, "Bone mapping applied successfully.")
        return {'FINISHED'}


class RBM_OT_TransferMeshWeights(Operator):
    """Rebind selected meshes from imported rig to Rigify rig and rename vertex groups"""
    bl_idname = "rbm.transfer_mesh_weights"
    bl_label = "Transfer Mesh Weights"
    bl_options = {'REGISTER', 'UNDO'}

    prefix: bpy.props.StringProperty(
        name="DEF Prefix",
        default=".",
        description="Prefix to apply to the renamed vertex groups"
    )

    def execute(self, context):
        # 1. Load mapping
        blend_dir = os.path.dirname(bpy.data.filepath) or os.getcwd()
        mapping_path = os.path.join(blend_dir, "bone_mapping.json")
        try:
            with open(mapping_path, "r") as f:
                mapping = json.load(f)
            imp2rig = {e["imported"]: e["rigify"] for e in mapping}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read bone_mapping.json: {e}")
            return {'CANCELLED'}

        # 2. Identify the Rigify armature
        armatures = [
            o for o in context.selected_objects if o.type == 'ARMATURE']
        if len(armatures) != 1:
            self.report(
                {'ERROR'}, "Select exactly one Rigify armature and the meshes to retarget.")
            return {'CANCELLED'}
        rigify_arm = armatures[0]

        # 3. Gather mesh objects
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if not meshes:
            self.report({'ERROR'}, "No mesh objects selected.")
            return {'CANCELLED'}

        # 4. Rebind modifiers & rename vertex groups
        for obj in meshes:
            # 4.1 Find or create Armature modifier
            arm_mod = next(
                (m for m in obj.modifiers if m.type == 'ARMATURE'), None)
            if not arm_mod:
                arm_mod = obj.modifiers.new(name="Armature", type='ARMATURE')
            arm_mod.object = rigify_arm

            # 4.2 Rename vertex groups
            for vgroup in obj.vertex_groups:
                old_name = vgroup.name
                if old_name in imp2rig:
                    vgroup.name = self.prefix + imp2rig[old_name]

            log.info(f"Retargeted '{obj.name}' to '{rigify_arm.name}'")

        self.report({'INFO'}, "Mesh weights transferred successfully.")
        return {'FINISHED'}



#  UI

class RBM_PT_Panel(Panel):
    bl_label = "Rigify Bone Mapper"
    bl_idname = "RBM_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Rigify"

    def draw(self, context):
        col = self.layout.column(align=True)
        col.operator("rbm.export_metarig")
        col.operator("rbm.scan_imported")
        col.operator("rbm.call_llm")
        col.operator("rbm.apply_mapping")
        col.operator("rbm.transfer_mesh_weights")

#  Registration

classes = (
    RBM_OT_ExportMetarigBones,
    RBM_OT_ScanImportedBones,
    RBM_OT_CallLLMMap,
    RBM_OT_ApplyMapping,
    RBM_OT_TransferMeshWeights,
    RBM_PT_Panel,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
