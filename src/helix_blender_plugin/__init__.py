bl_info = {
    "name": "Perforce Helix-Blender",
    "author": "Perforce Software",
    "version": (2024, 1, 0),
    "blender": (3, 2, 2),
    "location": "",
    "description": "Helix DAM by Perforce, integrates with Helix Sync & Blender",
    "doc_url": "https://help.perforce.com/helix-core/helix-dam/current/user/Content/HelixDAM-User/integrating-with-Blender.html",
    "tracker_url": "https://www.perforce.com/support",
    "category": "Import-Export",
}

# Details required for internal use
Helix_Blender_build = "0"
DAM_version = "0"
HelixSync_min_version = "2023.4.0 - Build: 2505977"


from . import damUI
import bpy
import logging
import os, platform

classes = (
    damUI.DamLogin,
    damUI.DamHelp,
    damUI.DamAbout,
    damUI.TOPBAR_MT_DAM_menu,
    damUI.TOPBAR_MT_DAM_Editor_menus,
    )


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    bpy.types.TOPBAR_MT_editor_menus.append(damUI.TOPBAR_MT_DAM_menu.draw)
    if platform.system() != "Windows":
        os.chmod(os.path.join(os.path.dirname(__file__),'HelixBlenderPlugin'), 0o775)


def unregister():
    from bpy.utils import unregister_class
    logging.shutdown()
    for cls in reversed(classes):
        unregister_class(cls)
    bpy.types.TOPBAR_MT_editor_menus.remove(damUI.TOPBAR_MT_DAM_menu.draw)

if __name__ == "__main__":
    register()
