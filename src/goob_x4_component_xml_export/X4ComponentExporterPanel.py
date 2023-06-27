import os

import bpy

from .operators.SerializeToXmlOperator import SerializeToXmlOperator

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       )

bl_info = {
    "name": "Tools",
    "description": "X4 Component Export Utility",
    "author": "GoobleSnorf",
    "version": (0, 0, 1),
    "blender": (3, 5, 1),
    "wiki_url": "my github url here",
    "tracker_url": "my github url here/issues",
    "category": "X4 Util",
    "support": "COMMUNITY"
}

class X4ComponentExporterPanelProperties(bpy.types.PropertyGroup):
    geometrySourceDirectory: bpy.props.StringProperty(
        name="Geometry Source Directory",
        description="Geometry source directory for the output component XML.",
        default=r"extensions\mod_name\assets\asset_path\file_name",
        maxlen=255
    )

class X4ComponentExporterPanel(bpy.types.Panel):
    bl_label = "X4 Component Export"
    bl_idname = "SCENE_PT_X4ComExport"

    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "X4 Util"

    @classmethod
    def poll(self, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        x4_component_exporter = scene.x4_component_exporter

        row = layout.row()
        row.scale_x = 0.5
        row.label(text="Class:")
        #row = layout.row()
        row.scale_x = 2.0

        #   Reuse the existing scene property from the Egosoft tool
        dd = row.prop(context.scene,"classAttr",text="")

        # layout.label(text="Geometry Source:")
        # row = layout.row()

        # file_name_without_extension = os.path.splitext(bpy.context.blend_data.filepath)[0]

        # #   [:-1] to handle string literal with trailing backslash
        # default_geometry_source_path = r"extensions\mod_name\assets\asset_path\ "[:-1] + file_name_without_extension

        layout.prop(
            x4_component_exporter,
            "geometrySourceDirectory"
        )

        layout.operator(
            "object.serialize_to_xml_operator",
            text="Serialize to Component XML"
        )

    def register():
        from bpy.utils import register_class
        
        register_class(SerializeToXmlOperator)

        # register_class(X4ComponentExporterPanel)
        register_class(X4ComponentExporterPanelProperties)

        bpy.types.Scene.x4_component_exporter = PointerProperty(type=X4ComponentExporterPanelProperties)

    def unregister():
        from bpy.utils import unregister_class

        unregister_class(SerializeToXmlOperator)

        # unregister_class(X4ComponentExporterPanel)
        unregister_class(X4ComponentExporterPanelProperties)

        del bpy.types.Scene.x4_component_exporter
