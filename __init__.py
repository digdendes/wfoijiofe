#----------------------------------------------------------
# File __init__.py
#----------------------------------------------------------
 
#    Addon info
# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    'name': "D3T Splint Module",
    'author': "Patrick R. Moore",
    'version': (0,2,1),
    'blender': (2, 7, 9),
    'api': "3c04373",
    'location': "3D View -> Tool Shelf",
    'description': "Dental Design CAD Tool Package",
    'warning': "",
    'wiki_url': "",
    'tracker_url': "",
    'category': '3D View'}


#we need to add the odc subdirectory to be searched for imports
#http://stackoverflow.com/questions/918154/relative-paths-in-python
import sys, os, platform, inspect, imp
sys.path.append(os.path.join(os.path.dirname(__file__)))
print(os.path.join(os.path.dirname(__file__)))


import bpy
from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty, FloatProperty
from bpy.app.handlers import persistent
#from . 

import odcutils

from . import addon_updater_ops


#addon preferences
class D3SplintAddonPreferences(AddonPreferences):
    bl_idname = __name__

    addons = bpy.context.user_preferences.addons
    
    folderpath = os.path.dirname(os.path.abspath(__file__))
    cork_folder =os.path.join(folderpath,'cork\\')
    
    if platform.system() == "Windows":
        cork_exe =os.path.join(folderpath,'cork\\win\\wincork.exe')
        if not os.path.exists(cork_exe):
            cork_exe = ''
            print('Cork Unsupported')
    elif "Mac" in platform.system():
        cork_exe =os.path.join(folderpath,'cork\\mac\\cork')
        if not os.path.exists(cork_exe):
            cork_exe = ''
            print('Cork Unsupported')
    elif "Linux" in platform.system():
        cork_exe =os.path.join(folderpath,'cork\\linux\\cork.exe')
        if not os.path.exists(cork_exe):
            cork_exe = ''
            print('Cork Unsupported')
    else:
        cork_exe = ''
        print('Cork Unsupported')
    
    
    cork_lib = bpy.props.StringProperty(
        name="Cork Exe",
        default=cork_exe,
        #default = '',
        subtype='FILE_PATH')
    
    dev = bpy.props.BoolProperty(name="Development Mode",
                                 default=False)

    debug = IntProperty(
            name="Debug Level",
            default=1,
            min = 0,
            max = 4,
            )
    
    auto_check_update = bpy.props.BoolProperty(
        name = "Auto-check for Update",
        description = "If enabled, auto-check for updates using an interval",
        default = False,
        )
    updater_intrval_months = bpy.props.IntProperty(
        name='Months',
        description = "Number of months between checking for updates",
        default=0,
        min=0
        )
    updater_intrval_days = bpy.props.IntProperty(
        name='Days',
        description = "Number of days between checking for updates",
        default=7,
        min=0,
        )
    updater_intrval_hours = bpy.props.IntProperty(
        name='Hours',
        description = "Number of hours between checking for updates",
        default=0,
        min=0,
        max=23
        )
    updater_intrval_minutes = bpy.props.IntProperty(
        name='Minutes',
        description = "Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59
        )

    show_occlusal_mod = bpy.props.BoolProperty(
        name = "Show Occlusal Mod",
        description = "Shows some beta Settings",
        default = False,
        )
    
    show_survey_functions = bpy.props.BoolProperty(
        name = "Show Survey Tools",
        description = "Shows Buttons for Survey Tools",
        default = False,
        )
    
    ##########################################
    ###### Operator Defaults      ############
    ##########################################
    
    default_jaw_type = bpy.props.EnumProperty(name = 'Jaw Type', 
                                              items = [('MAXILLA', 'MAXILLA', 'MAXILLA'),('MANDIBLE', 'MANDIBLE', 'MANDIBLE')],
                                              default = "MAXILLA",
                                              description = 'Appliance is on upper or lower jaw')
    
    
    #behavior_mode = EnumProperty(name="How Active Tooth is determined by operator", description="'LIST' is more predictable, 'ACTIVE' more like blender, 'ACTIVE_SELECTED' is for advanced users", items=behavior_enum, default='0')

    def draw(self, context):
        layout = self.layout
        layout.label(text="D3Splint Preferences and Settings")
        #layout.prop(self, "mat_lib")
        
        row = layout.row()
        row.operator("opendental.d3t_critiacal_settings", text = 'Set Mandatory Settings')
        addon_updater_ops.update_settings_ui(self, context)


class D3Splint_OT_general_preferences(Operator):
    """Change several critical settings for optimal D3Tool use"""
    bl_idname = "opendental.d3t_critiacal_settings"
    bl_label = "Set D3Tool Critical Blender Settings"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        user_preferences = context.user_preferences
        
        #needed to allow articulator drivers to work
        user_preferences.system.use_scripts_auto_execute = True
        
        
        user_preferences.filepaths.use_relative_paths = False
        
        #prevent accidental tweaking when blender responsiveness is slow
        #common problem once the scene gets complex with boolean modifiers
        user_preferences.inputs.tweak_threshold = 200
        
        #make em stick
        bpy.ops.wm.save_userpref()
        
        return {'FINISHED'}
    
class D3Splint_OT_addon_prefs(Operator):
    """Display example preferences"""
    bl_idname = "opendental.odc_addon_pref"
    bl_label = "ODC Preferences Display"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences

        info = ("Path: %s, Number: %d, Boolean %r" %
                (addon_prefs.filepath, addon_prefs.number, addon_prefs.boolean))

        self.report({'INFO'}, info)
        print(info)

        return {'FINISHED'}

@persistent   
def load_post_method(dummy):
    print('loaded bridges')
    #make all the bridges reload their teeth.
    odcutils.scene_verification(bpy.context.scene, debug=True)
    
    print('loaded splints')
    for splint in bpy.context.scene.odc_splints:
        print(splint.tooth_string)
        #splint.load_components_from_string(bpy.context.scene)
@persistent    
def save_pre_method(dummy):
    odcutils.scene_verification(bpy.context.scene, debug=True)
    
    print('prepared splints for save')
    for splint in bpy.context.scene.odc_splints:
        splint.save_components_to_string()

@persistent
def pause_playback(scene):
    if scene.frame_current == scene.frame_end:
        bpy.ops.screen.animation_play()
        #scene.frame_set(scene.frame_current - 1) #prevent replaying
        scene.frame_set(-1)
        scene.frame_set(0)
        
        print('REACHED THE END')

@persistent
def stop_playback(scene):
    if scene.frame_current == scene.frame_end:
        bpy.ops.screen.animation_cancel(restore_frame=False)
        scene.frame_set(scene.frame_current - 1) #prevent replaying
        print('REACHED THE END')

# or restore frames:
@persistent
def stop_playback_restore(scene):
    if scene.frame_current == scene.frame_end + 1:
        bpy.ops.screen.animation_cancel(restore_frame=True)
        print('REACHED THE END')
                               
def register():
    #bpy.utils.register_module(__name__)
    #import the relevant modules
    #from . 
    
    
    
    import d3classes, odcutils, crown, margin, bridge, splint, implant, panel, help, flexible_tooth, bracket_placement, denture_base, occlusion, ortho, curve_partition, articulator, splint_landmark_fns # , odcmenus, bgl_utils
    import healing_abutment, model_work, tracking, import_export, splint_booleans, splint_face_bow
    import meta_modelling, model_labels, splint_occlusal_surfaces
    
    #register them
    d3classes.register()
    odcutils.register()
    curve_partition.register()
    splint.register()
    articulator.register()
    #help.register()
    #denture_base.register()
    occlusion.register()
    splint_landmark_fns.register()
    splint_booleans.register()
    model_work.register()
    import_export.register()
    splint_face_bow.register()
    meta_modelling.register()
    model_labels.register()
    splint_occlusal_surfaces.register()
    panel.register()
    
    #register this module
    bpy.utils.register_class(D3SplintAddonPreferences)
    bpy.utils.register_class(D3Splint_OT_general_preferences)
    bpy.utils.register_class(D3Splint_OT_addon_prefs)
    
    tracking.register(bl_info)
    addon_updater_ops.register(bl_info)
    
    bpy.app.handlers.load_post.append(load_post_method)
    bpy.app.handlers.save_pre.append(save_pre_method)
    bpy.app.handlers.frame_change_pre.append(pause_playback)
    
def unregister():
    #import the relevant modules
    from . import ( d3classes, odcutils, splint, 
                    panel, curve_partition, articulator, 
                    splint_landmark_fns, model_work, tracking, 
                    splint_booleans, import_export,splint_face_bow,
                    meta_modeling)
    
    bpy.app.handlers.save_pre.remove(save_pre_method)
    bpy.app.handlers.load_post.remove(load_post_method)
    bpy.app.handlers.frame_change_pre.remove(pause_playback)
    
    #bpy.utils.unregister_module(__name__)
    bpy.utils.unregister_class(D3SplintAddonPreferences)
    bpy.utils.unregister_class(D3Splint_OT_addon_prefs)
    
    #unregister them
    d3classes.unregister()
    odcutils.unregister()

    splint.unregister()
    articulator.unregister()
    panel.unregister()
    curve_partition.unregister()
    splint_landmark_fns.unregister()
    splint_booleans.unregister()
    model_work.unregister()
    import_export.unregister()
    splint_face_bow.unregister()
    meta_modelling.unregister()
    #unregister this module
 
if __name__ == "__main__":
    register()