import bpy

from .X4ComponentExporterPanel import X4ComponentExporterPanel

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

def register():
    from bpy.utils import register_class

    register_class(X4ComponentExporterPanel)

def unregister():
    from bpy.utils import unregister_class

    unregister_class(X4ComponentExporterPanel)