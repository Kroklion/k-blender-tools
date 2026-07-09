import bpy


class MESH_OT_link_shape_key_drivers(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}
    bl_idname = "object.link_shape_key_drivers"
    bl_label = "Drive Shape Keys from Active"
    bl_description = "Link matching shape keys on selected objects to the active object using drivers"
    bl_context = "objectmode"
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and context.mode == 'OBJECT'

    def execute(self, context):
        source = context.active_object
        targets = [obj for obj in context.selected_objects if obj != source]
        
        count = 0

        if not source or not targets:
            self.report(
                {'ERROR'}, "Select a source (active) and at least one target object.")
            return {'CANCELLED'}
        else:
            sk_source = source.data.shape_keys
            if not sk_source:
                self.report({'ERROR'}, f"Source object '{source.name}' has no shape keys.")
                return {'CANCELLED'}
            else:
                for target in targets:
                    sk_target = target.data.shape_keys
                    if not sk_target:
                        continue

                    for index, key in enumerate(sk_source.key_blocks):
                        name = key.name

                        # skip Basis
                        if index == 0:
                            continue

                        if name not in sk_target.key_blocks:
                            continue

                        # Add driver to target shape key
                        drv = sk_target.key_blocks[name].driver_add("value").driver
                        drv.type = 'AVERAGE'  # same as "Copy as New Driver"

                        var = drv.variables.new()
                        var.name = "var"
                        var.type = 'SINGLE_PROP'

                        tgt = var.targets[0]
                        tgt.id = source  # MUST be an Object
                        tgt.data_path = f'data.shape_keys.key_blocks["{name}"].value'
                        count += 1
            self.report(
                {'INFO'}, f"Created {count} drivers.")
            return {'FINISHED'}


def object_menu_func(self, context):
    layout = self.layout
    layout.operator(MESH_OT_link_shape_key_drivers.bl_idname)


classes = (
    MESH_OT_link_shape_key_drivers,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.VIEW3D_MT_object.append(object_menu_func)


def unregister():
    bpy.types.VIEW3D_MT_object.remove(object_menu_func)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
