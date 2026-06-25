import bpy
import bmesh
from mathutils import Vector

# To be run in Blenders scripting tab

# ------------------------------------------------------------
# Utility: clean scene and create cube + 3 shape keys
# ------------------------------------------------------------


def setup_scene():
    if bpy.context.active_object:
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object

    # Add Basis + 2 more keys
    bpy.ops.object.shape_key_add(from_mix=False)  # Basis
    bpy.ops.object.shape_key_add(from_mix=False)  # Key1
    bpy.ops.object.shape_key_add(from_mix=False)  # Key2

    # Modify Key1 and Key2 differently
    modify_vertex(obj, 1, Vector((0.3, 0, 0)))
    modify_vertex(obj, 2, Vector((-0.4, 0, 0)))

    return obj


# ------------------------------------------------------------
# Modify vertex 0 in a given shape key
# ------------------------------------------------------------
def modify_vertex(obj, key_index, delta):
    obj.active_shape_key_index = key_index
    bpy.ops.object.mode_set(mode='EDIT')

    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    bm.verts.ensure_lookup_table()

    v = bm.verts[0]
    v.select = True
    v.co += delta

    bmesh.update_edit_mesh(me)
    bpy.ops.object.mode_set(mode='OBJECT')


# ------------------------------------------------------------
# Read vertex 0 position in a shape key
# ------------------------------------------------------------
def get_vertex_position(obj, key_index):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()

    layer = bm.verts.layers.shape[key_index]
    pos = bm.verts[0][layer].copy()

    bm.free()
    return pos


# ------------------------------------------------------------
# Run operator with parameters
# ------------------------------------------------------------
def run_op(obj, mode, behavior, target_key="Basis", new_name="NewKey"):
    bpy.ops.object.mode_set(mode='EDIT')

    # Select vertex 0
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        v.select = False
    bm.verts[0].select = True
    bmesh.update_edit_mesh(me)

    # Run operator
    result = bpy.ops.mesh.transfer_selected_shapekey(
        copy_mode=mode,
        copy_behavior=behavior,
        target_key=target_key,
        new_key_name=new_name
    )
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')
    return result


# ------------------------------------------------------------
# Test functions (6 total)
# ------------------------------------------------------------
def test_target_copy():
    obj = setup_scene()
    obj.active_shape_key_index = 1
    target = obj.data.shape_keys.key_blocks[2].name
    run_op(obj, "TARGET", "COPY", target_key=target)

    src = get_vertex_position(obj, 1)
    dst = get_vertex_position(obj, 2)
    print("TARGET COPY:", "PASS" if src == dst else "FAIL")


def test_target_move():
    obj = setup_scene()
    obj.active_shape_key_index = 1
    target = obj.data.shape_keys.key_blocks[2].name
    run_op(obj, "TARGET", "MOVE", target_key=target)

    src = get_vertex_position(obj, 1)
    ref = get_vertex_position(obj, 0)
    print("TARGET MOVE:", "PASS" if src == ref else "FAIL")


def test_all_copy():
    obj = setup_scene()
    obj.active_shape_key_index = 1
    run_op(obj, "ALL", "COPY")

    src = get_vertex_position(obj, 1)
    dst2 = get_vertex_position(obj, 2)
    print("ALL COPY:", "PASS" if src == dst2 else "FAIL")


def test_all_move():
    obj = setup_scene()
    obj.active_shape_key_index = 1
    run_op(obj, "ALL", "MOVE")

    src = get_vertex_position(obj, 1)
    ref = get_vertex_position(obj, 0)
    print("ALL MOVE:", "PASS" if src == ref else "FAIL")


def test_new_copy():
    obj = setup_scene()
    obj.active_shape_key_index = 1
    run_op(obj, "NEW", "COPY", new_name="GeneratedKey")

    new_index = obj.data.shape_keys.key_blocks.find("GeneratedKey")
    src = get_vertex_position(obj, 1)
    dst = get_vertex_position(obj, new_index)
    print("NEW COPY:", "PASS" if src == dst else "FAIL")


def test_new_move():
    obj = setup_scene()
    obj.active_shape_key_index = 1
    run_op(obj, "NEW", "MOVE", new_name="GeneratedKey")

    src = get_vertex_position(obj, 1)
    ref = get_vertex_position(obj, 0)
    print("NEW MOVE:", "PASS" if src == ref else "FAIL")


# ------------------------------------------------------------
# Run all tests
# ------------------------------------------------------------
test_target_copy()
test_target_move()
test_all_copy()
test_all_move()
test_new_copy()
test_new_move()

print("\nAll tests executed.")
