bl_info = {
    "name": "PhysicalMouse Encryptor",
    "author": "PhysicalMouse",
    "version": (1, 0),
    "blender": (4, 5, 0),
    "location": "Compositor > Sidebar > PME",
    "description": "Encrypts/Decrypts an image by slicing and reassembling nodes！",
    "warning": "Encryption and decryption cannot be used consecutively in a single project！",
    "doc_url": "",
    "category": "Compositor",
}

import bpy

def create_crypt_group(name, slices_x, slices_y):
    """
    Creates the node group that slices, swaps, and reassembles the image pieces.
    """
    if name in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[name])

    group = bpy.data.node_groups.new(name, 'CompositorNodeTree')
    group.interface.new_socket(name="Image", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')

    input_node = group.nodes.new('NodeGroupInput')
    input_node.location = (-200, 0)
    output_node = group.nodes.new('NodeGroupOutput')

    total_slices = slices_x * slices_y
    if total_slices <= 1:
        group.links.new(input_node.outputs['Image'], output_node.inputs['Image'])
        return group

    translated_slice_outputs = []
    node_grid_x_spacing = 400
    node_grid_y_spacing = 300

    for i in range(total_slices):
        orig_col = i % slices_x   
        orig_row = i // slices_x
        target_i = (total_slices - 1) - i
        target_col = target_i % slices_x
        target_row = target_i // slices_x

        crop_node = group.nodes.new(type="CompositorNodeCrop")
        crop_node.inputs['Alpha Crop'].default_value = True
    

        rtp_x = group.nodes.new(type="CompositorNodeRelativeToPixel")
        rtp_x.reference_dimension = 'X'
        rtp_x.inputs['Value'].default_value = orig_col / slices_x
        
        rtp_y = group.nodes.new(type="CompositorNodeRelativeToPixel")
        rtp_y.reference_dimension = 'Y'
        rtp_y.inputs['Value'].default_value = orig_row / slices_y
        
        rtp_w = group.nodes.new(type="CompositorNodeRelativeToPixel")
        rtp_w.reference_dimension = 'X'
        rtp_w.inputs['Value'].default_value = 1.0 / slices_x

        rtp_h = group.nodes.new(type="CompositorNodeRelativeToPixel")
        rtp_h.reference_dimension = 'Y'
        rtp_h.inputs['Value'].default_value = 1.0 / slices_y

        translate_node = group.nodes.new(type="CompositorNodeTranslate")
        translate_node.wrap_axis = 'BOTH'
        translate_node.use_relative = False

        delta_x_rel = (target_col - orig_col) / slices_x
        delta_y_rel = (target_row - orig_row) / slices_y
        
        rtp_dx = group.nodes.new(type="CompositorNodeRelativeToPixel")
        rtp_dx.reference_dimension = 'X'
        rtp_dx.inputs['Value'].default_value = delta_x_rel
        
        rtp_dy = group.nodes.new(type="CompositorNodeRelativeToPixel")
        rtp_dy.reference_dimension = 'Y'
        rtp_dy.inputs['Value'].default_value = delta_y_rel

        for rtp_node in [rtp_x, rtp_y, rtp_w, rtp_h, rtp_dx, rtp_dy]:
            group.links.new(input_node.outputs['Image'], rtp_node.inputs['Image'])
        group.links.new(input_node.outputs['Image'], crop_node.inputs['Image'])
        
        group.links.new(rtp_x.outputs['Value'], crop_node.inputs['X'])
        group.links.new(rtp_y.outputs['Value'], crop_node.inputs['Y'])
        group.links.new(rtp_w.outputs['Value'], crop_node.inputs['Width'])
        group.links.new(rtp_h.outputs['Value'], crop_node.inputs['Height'])
        
        group.links.new(crop_node.outputs['Image'], translate_node.inputs['Image'])
        
        group.links.new(rtp_dx.outputs['Value'], translate_node.inputs['X'])
        group.links.new(rtp_dy.outputs['Value'], translate_node.inputs['Y'])

        translated_slice_outputs.append(translate_node.outputs['Image'])

        column_x = (i % slices_x) * node_grid_x_spacing
        row_y = (i // slices_x) * -node_grid_y_spacing
        
        rtp_x.location = (column_x, row_y)
        rtp_y.location = (column_x, row_y - 40)
        rtp_w.location = (column_x, row_y - 80)
        rtp_h.location = (column_x, row_y - 120)
        crop_node.location = (column_x + 180, row_y - 40)
        
        rtp_dx.location = (column_x, row_y - 200)
        rtp_dy.location = (column_x, row_y - 240)
        translate_node.location = (column_x + 180, row_y - 220)

    last_socket = translated_slice_outputs[0]
    
    chain_start_x = (slices_x * node_grid_x_spacing) / 2
    chain_y = (slices_y * -node_grid_y_spacing)
    
    for i in range(1, total_slices):
        alpha_over = group.nodes.new(type="CompositorNodeAlphaOver")
        alpha_over.location = (chain_start_x + i * 200, chain_y)
        group.links.new(translated_slice_outputs[i], alpha_over.inputs[1])
        group.links.new(last_socket, alpha_over.inputs[2])
        last_socket = alpha_over.outputs['Image']

    group.links.new(last_socket, output_node.inputs['Image'])
    output_node.location = (chain_start_x + total_slices * 200, chain_y)
    
    return group

class PME_Properties(bpy.types.PropertyGroup):
    slices_x: bpy.props.IntProperty(
        name="Horizontal Slices",
        description="Number of slices along the X-axis",
        default=10, min=1, max=100
    )
    slices_y: bpy.props.IntProperty(
        name="Vertical Slices",
        description="Number of slices along the Y-axis",
        default=10, min=1, max=100
    )

class PME_OT_GenerateGroup(bpy.types.Operator):
    """Operator to generate the encryption/decryption node group."""
    bl_idname = "pme.generate_group"
    bl_label = "Generate Crypt Group"
    bl_description = "Creates the node group for image encryption/decryption"
    bl_options = {'REGISTER', 'UNDO'}

    # FIX: Add a StringProperty to accept the group name from the UI call.
    name: bpy.props.StringProperty(
        name="Group Base Name",
        description="The base name for the generated node group",
        default="PME_Crypt"
    )

    def execute(self, context):
        scene = context.scene
        pme_props = scene.pme_props
        
        if not scene.use_nodes:
            scene.use_nodes = True
        
        tree = scene.node_tree
        
        # FIX: Use the 'name' property passed from the operator.
        base_name = self.name
        group_name = f"{base_name}_{pme_props.slices_x}x{pme_props.slices_y}"
        
        crypt_group = create_crypt_group(group_name, pme_props.slices_x, pme_props.slices_y)
        
        if not crypt_group:
            self.report({'ERROR'}, "Failed to create the node group.")
            return {'CANCELLED'}
            
        group_node = tree.nodes.new(type='CompositorNodeGroup')
        group_node.node_tree = crypt_group
        group_node.name = group_name
        group_node.location = (0, 0)
        
        self.report({'INFO'}, f"Generated node group: {group_name}")
        
        return {'FINISHED'}

class PME_PT_Panel(bpy.types.Panel):
    """Creates a Panel in the Compositor sidebar."""
    bl_label = "PhysicalMouse Encryptor"
    bl_idname = "PME_PT_MainPanel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'PME'
    bl_context = "CompositorNodeTree"

    def draw(self, context):
        layout = self.layout
        props = context.scene.pme_props

        layout.label(text="Slicing Configuration:")
        row = layout.row()
        row.prop(props, "slices_x")
        row = layout.row()
        row.prop(props, "slices_y")
        
        layout.separator()
        
        op = layout.operator(PME_OT_GenerateGroup.bl_idname, text="Generate Node Group", icon='NODETREE')
        # This line now works correctly because the 'name' property exists on the operator.
        op.name = "PME_Crypt"

# --- REGISTRATION ---

classes = (
    PME_Properties,
    PME_OT_GenerateGroup,
    PME_PT_Panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pme_props = bpy.props.PointerProperty(type=PME_Properties)

def unregister():
    del bpy.types.Scene.pme_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()