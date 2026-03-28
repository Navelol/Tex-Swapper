bl_info = {
    "name": "Animated Texture Swap (Multi-Material)",
    "author": "Evan Pierce",
    "version": (1, 8),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Texture Swap",
    "description": "Swap out multiple Image Texture nodes on multiple materials/meshes",
    "category": "Material",
}

import bpy, os

# -------------------------------------------------------------------
# Runtime storage
# -------------------------------------------------------------------
texture_swap_data = {}

# -------------------------------------------------------------------
# Frame change handler
# -------------------------------------------------------------------
def texture_swap_handler(scene):
    cf = scene.frame_current
    sf = texture_swap_data["start_frame"]
    fps = texture_swap_data["frames_per_swap"]
    if cf < sf:
        return
    idx = (cf - sf) // fps

    for cfg in texture_swap_data["configs"]:
        obj = bpy.data.objects.get(cfg["object_name"])
        if not obj:
            continue
        mat = next((s.material for s in obj.material_slots
                    if s.material and s.material.name == cfg["material_name"]), None)
        if not mat or not mat.use_nodes:
            continue

        for entry in cfg["nodes"]:
            imgs = entry["images"]
            if 0 <= idx < len(imgs):
                node = next(
                    (n for n in mat.node_tree.nodes
                     if n.type == 'TEX_IMAGE' and
                     (n.label == entry["node_name"] or n.name == entry["node_name"])),
                    None
                )
                if node and node.image != imgs[idx]:
                    node.image = imgs[idx]
        mat.node_tree.update_tag()

# -------------------------------------------------------------------
# Per-node mapping
# -------------------------------------------------------------------
class TextureNodeMapping(bpy.types.PropertyGroup):
    node_name: bpy.props.StringProperty(
        name="Node Label / Name",
        description="Label (preferred) or internal name of the Image Texture node"
    )
    folder_path: bpy.props.StringProperty(
        name="Folder",
        description="Directory where this node's sequence lives",
        subtype='DIR_PATH'
    )
    expanded: bpy.props.BoolProperty(default=True)

# -------------------------------------------------------------------
# One config = one mesh + material + its node list
# -------------------------------------------------------------------
def get_materials(self, context):
    items = []
    if self.object_ptr:
        for slot in self.object_ptr.material_slots:
            if slot.material:
                items.append((slot.material.name, slot.material.name, ""))
    return items

class TextureSwapConfig(bpy.types.PropertyGroup):
    object_ptr: bpy.props.PointerProperty(
        name="Mesh Object",
        type=bpy.types.Object,
        poll=lambda self, o: o.type == 'MESH'
    )
    material_enum: bpy.props.EnumProperty(
        name="Material",
        items=get_materials
    )
    node_mappings: bpy.props.CollectionProperty(type=TextureNodeMapping)
    node_mappings_index: bpy.props.IntProperty(default=0)
    expanded: bpy.props.BoolProperty(default=True)

# -------------------------------------------------------------------
# Main settings
# -------------------------------------------------------------------
class TextureSwapSettings(bpy.types.PropertyGroup):
    configs: bpy.props.CollectionProperty(type=TextureSwapConfig)
    configs_index: bpy.props.IntProperty(default=0)

    frames_per_swap:  bpy.props.IntProperty(name="Frames per Swap", default=10, min=1)
    start_frame:      bpy.props.IntProperty(name="Start Frame",      default=1,  min=1)
    shorten_timeline: bpy.props.BoolProperty(name="Shorten Timeline", default=False)

# -------------------------------------------------------------------
# Operators — configs
# -------------------------------------------------------------------
class SCENE_OT_add_swap_config(bpy.types.Operator):
    bl_idname = "scene.add_texture_swap_config"
    bl_label = "Add Mesh Slot"
    def execute(self, context):
        s = context.scene.texture_swap_settings
        s.configs.add()
        s.configs_index = len(s.configs) - 1
        return {'FINISHED'}

class SCENE_OT_remove_swap_config(bpy.types.Operator):
    bl_idname = "scene.remove_texture_swap_config"
    bl_label = "Remove Mesh Slot"
    config_index: bpy.props.IntProperty()
    def execute(self, context):
        s = context.scene.texture_swap_settings
        s.configs.remove(self.config_index)
        s.configs_index = max(0, min(self.config_index, len(s.configs) - 1))
        return {'FINISHED'}

class SCENE_OT_move_swap_config(bpy.types.Operator):
    bl_idname = "scene.move_texture_swap_config"
    bl_label = "Move Mesh Slot"
    config_index: bpy.props.IntProperty()
    direction: bpy.props.EnumProperty(items=[('UP','Up',''),('DOWN','Down','')])
    def execute(self, context):
        s = context.scene.texture_swap_settings
        idx = self.config_index
        if self.direction == 'UP' and idx > 0:
            s.configs.move(idx, idx - 1)
            s.configs_index = idx - 1
        elif self.direction == 'DOWN' and idx < len(s.configs) - 1:
            s.configs.move(idx, idx + 1)
            s.configs_index = idx + 1
        return {'FINISHED'}

# -------------------------------------------------------------------
# Operators — node mappings (act on a specific config by index)
# -------------------------------------------------------------------
class SCENE_OT_add_node_mapping(bpy.types.Operator):
    bl_idname = "scene.add_node_mapping"
    bl_label = "Add Node Mapping"
    config_index: bpy.props.IntProperty()
    def execute(self, context):
        s = context.scene.texture_swap_settings
        cfg = s.configs[self.config_index]
        cfg.node_mappings.add()
        cfg.node_mappings_index = len(cfg.node_mappings) - 1
        return {'FINISHED'}

class SCENE_OT_remove_node_mapping(bpy.types.Operator):
    bl_idname = "scene.remove_node_mapping"
    bl_label = "Remove Node Mapping"
    config_index: bpy.props.IntProperty()
    def execute(self, context):
        s = context.scene.texture_swap_settings
        cfg = s.configs[self.config_index]
        idx = cfg.node_mappings_index
        cfg.node_mappings.remove(idx)
        cfg.node_mappings_index = max(0, min(idx, len(cfg.node_mappings) - 1))
        return {'FINISHED'}

# -------------------------------------------------------------------
# Apply operator
# -------------------------------------------------------------------
class OBJECT_OT_apply_texture_swap(bpy.types.Operator):
    bl_idname = "object.apply_texture_swap"
    bl_label = "Apply Texture Swap"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.texture_swap_settings
        if not s.configs:
            self.report({'ERROR'}, "Add at least one Mesh Slot")
            return {'CANCELLED'}

        all_configs = []
        longest = 0

        for i, cfg in enumerate(s.configs):
            if not cfg.object_ptr or not cfg.material_enum:
                self.report({'ERROR'}, f"Slot {i+1} is missing an object or material")
                return {'CANCELLED'}

            entries = []
            for m in cfg.node_mappings:
                node_name = m.node_name.strip()
                folder = bpy.path.abspath(m.folder_path)
                # Validate that a matching node actually exists on the material
                mat_obj = cfg.object_ptr
                mat = next((sl.material for sl in mat_obj.material_slots
                            if sl.material and sl.material.name == cfg.material_enum), None)
                if mat and mat.use_nodes:
                    match = next(
                        (n for n in mat.node_tree.nodes
                         if n.type == 'TEX_IMAGE' and
                         (n.label == node_name or n.name == node_name)),
                        None
                    )
                    if not match:
                        self.report({'WARNING'}, f"Slot {i+1}: no Image Texture node with label or name '{node_name}' found — continuing anyway")

                if not node_name or not os.path.isdir(folder):
                    self.report({'ERROR'}, f"Slot {i+1}: bad node name '{node_name}' or folder not found")
                    return {'CANCELLED'}
                imgs = []
                for fn in sorted(os.listdir(folder)):
                    if fn.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.exr')):
                        try:
                            img = bpy.data.images.load(os.path.join(folder, fn), check_existing=True)
                            imgs.append(img)
                        except Exception:
                            pass
                if not imgs:
                    self.report({'ERROR'}, f"Slot {i+1}: no images found for node '{node_name}'")
                    return {'CANCELLED'}
                entries.append({"node_name": node_name, "images": imgs})
                longest = max(longest, len(imgs))

            all_configs.append({
                "object_name":   cfg.object_ptr.name,
                "material_name": cfg.material_enum,
                "nodes":         entries,
            })

        texture_swap_data.clear()
        texture_swap_data.update({
            "configs":         all_configs,
            "frames_per_swap": s.frames_per_swap,
            "start_frame":     s.start_frame,
            "end_frame":       s.start_frame + s.frames_per_swap * longest - 1,
        })

        if texture_swap_handler not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(texture_swap_handler)

        if s.shorten_timeline:
            context.scene.frame_end = texture_swap_data["end_frame"]

        self.report({'INFO'}, f"Swapping {len(all_configs)} mesh slot(s), ending at frame {texture_swap_data['end_frame']}")
        return {'FINISHED'}

# -------------------------------------------------------------------
# UI Panel — expanded accordion per mesh slot
# -------------------------------------------------------------------
class VIEW3D_PT_texture_swap(bpy.types.Panel):
    bl_label = "Animated Texture Swap"
    bl_idname = "VIEW3D_PT_texture_swap"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Texture Swap'

    def draw(self, context):
        layout = self.layout
        s = context.scene.texture_swap_settings

        # ── Header row ──────────────────────────────────────────────
        header = layout.row()
        header.label(text="Mesh Slots", icon='MESH_DATA')
        header.operator("scene.add_texture_swap_config", icon='ADD', text="Add Mesh Slot")

        if not s.configs:
            layout.label(text="No mesh slots yet — click Add Mesh Slot", icon='INFO')
        else:
            # ── One box per mesh slot ────────────────────────────────
            for i, cfg in enumerate(s.configs):
                box = layout.box()

                # Slot header: expand toggle + label + move + remove
                slot_header = box.row(align=True)
                icon = 'TRIA_DOWN' if cfg.expanded else 'TRIA_RIGHT'
                slot_header.prop(cfg, "expanded", icon=icon, text="", emboss=False)

                obj_name = cfg.object_ptr.name if cfg.object_ptr else "— no mesh —"
                slot_header.label(text=f"Slot {i+1}:  {obj_name}", icon='OBJECT_DATA')

                # move up/down
                up = slot_header.operator("scene.move_texture_swap_config", icon='TRIA_UP', text="")
                up.config_index = i
                up.direction = 'UP'
                dn = slot_header.operator("scene.move_texture_swap_config", icon='TRIA_DOWN', text="")
                dn.config_index = i
                dn.direction = 'DOWN'

                # remove
                rm = slot_header.operator("scene.remove_texture_swap_config", icon='X', text="")
                rm.config_index = i

                if not cfg.expanded:
                    continue

                # Object + material pickers
                box.prop(cfg, "object_ptr", text="Mesh")
                if cfg.object_ptr:
                    box.prop(cfg, "material_enum", text="Material")

                box.separator(factor=0.5)

                # ── Node mapping sub-list ────────────────────────────
                nm_header = box.row()
                nm_header.label(text="Texture Nodes", icon='NODE_TEXTURE')
                add_nm = nm_header.operator("scene.add_node_mapping", icon='ADD', text="Add Node")
                add_nm.config_index = i

                if not cfg.node_mappings:
                    box.label(text="No nodes yet — click Add Node", icon='INFO')
                else:
                    for j, m in enumerate(cfg.node_mappings):
                        nm_box = box.box()
                        nm_row = nm_box.row(align=True)
                        nm_row.label(
                            text=f"Node {j+1}: {m.node_name or '—'}",
                            icon='TEXTURE'
                        )
                        rm_nm = nm_row.operator("scene.remove_node_mapping", icon='X', text="")
                        rm_nm.config_index = i

                        # Highlight active node mapping
                        is_active = (j == cfg.node_mappings_index)
                        if is_active:
                            nm_box.prop(m, "node_name", text="Node Name")
                            nm_box.prop(m, "folder_path", text="Folder")
                        else:
                            # Click row to select
                            nm_box.label(
                                text=(m.node_name or "unnamed") +
                                     (" — " + (m.folder_path or "no folder"))
                            )

                        # track active index when user interacts with fields
                        # (property changes auto-set via standard Blender selection)

        # ── Global settings ─────────────────────────────────────────
        layout.separator()
        col = layout.column(align=True)
        col.label(text="Global Settings", icon='SETTINGS')
        col.prop(s, "frames_per_swap")
        col.prop(s, "start_frame")
        col.prop(s, "shorten_timeline")
        layout.separator()
        layout.operator("object.apply_texture_swap", icon='PLAY')

# -------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------
classes = (
    TextureNodeMapping,
    TextureSwapConfig,
    TextureSwapSettings,
    SCENE_OT_add_swap_config,
    SCENE_OT_remove_swap_config,
    SCENE_OT_move_swap_config,
    SCENE_OT_add_node_mapping,
    SCENE_OT_remove_node_mapping,
    OBJECT_OT_apply_texture_swap,
    VIEW3D_PT_texture_swap,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.texture_swap_settings = bpy.props.PointerProperty(type=TextureSwapSettings)

def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.texture_swap_settings
    if texture_swap_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(texture_swap_handler)

if __name__ == "__main__":
    register()
