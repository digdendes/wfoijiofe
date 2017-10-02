# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#

#import odc_public
#from  odc_public import odcutils, load_post_method

#from . import odcutils, load_post_method

'''
Template for classes and properties from Cycles Addon

class CyclesStyleClass(bpy.types.PropertyGroup):
    @classmethod
    def (cls):
        bpy.types.ParticleSettings.cycles = PointerProperty(
                name="Cycles Hair Settings",
                description="Cycles hair settings",
                type=cls,
                )
        cls.root_width = FloatProperty(

    @classmethod
    def unregister(cls):
        del bpy.types.ParticleSettings.cycles
'''


import bpy
#we need to add the odc subdirectory to be searched for imports
#http://stackoverflow.com/questions/918154/relative-paths-in-python
import sys, os, inspect
from odcmenus import button_data
from odcmenus import menu_utils

#enums
rest_types=['CONTOUR','PONTIC','COPING','ANATOMIC COPING']
rest_enum = []
for index, item in enumerate(rest_types):
    rest_enum.append((str(index), rest_types[index], str(index)))
    
teeth = ['11','12','13','14','15','16','17','18','21','22','23','24','25','26','27','28','31','32','33','34','35','36','37','38','41','42','43','44','45','46','47','48']    
teeth_enum=[]
for index, item in enumerate(teeth):
    teeth_enum.append((str(index), item, str(index)))
    
def index_update(self,context):
    #perhaps do some magic here to only call it later?
    bpy.ops.ed.undo_push(message="Changed active tooth index")
    
#classes
class D3SplintProps(bpy.types.PropertyGroup):
    
    @classmethod
    def register(cls):
        bpy.types.Scene.d3splint_props = bpy.props.PointerProperty(type=cls)
        
        cls.master = bpy.props.StringProperty(
                name="Master Model",
                default="")
        cls.opposing = bpy.props.StringProperty(
                name="Opposing Model",
                default="")
        
        cls.bone = bpy.props.StringProperty(
                name="Bone Model",
                default="")
        
        cls.register_II = bpy.props.BoolProperty(
                name="2nd Registration",
                default=False)
        
        cls.work_log = bpy.props.StringProperty(name="Work Log", default = "")
        cls.work_log_path = bpy.props.StringProperty(name="Work Log File", subtype = "DIR_PATH", default = "")
        
        ###Toolbar show/hide booleans for tool options###
        cls.show_teeth = bpy.props.BoolProperty(
                name="Tooth Panel",
                default=False)
        
        cls.show_bridge = bpy.props.BoolProperty(
                name="Bridge Panel",
                default=False)
        
        cls.show_implant = bpy.props.BoolProperty(
                name="Implant Panel",
                default=False)
        
        cls.show_splint = bpy.props.BoolProperty(
                name="Splint Panel",
                default=True)
        
        cls.show_ortho = bpy.props.BoolProperty(
                name="Ortho Panel",
                default=False)
        #implant panel
        #bridge panel
        #splint panel       
    @classmethod
    def unregister(cls):
        del bpy.types.Scene.d3splint_props    
              
class D3SplintRestoration(bpy.types.PropertyGroup):
    
    @classmethod
    def register(cls):
        bpy.types.Scene.odc_splints = bpy.props.CollectionProperty(type = cls)
        bpy.types.Scene.odc_splint_index = bpy.props.IntProperty(name = "Working Splint Index", min=0, default=0, update=index_update)
  
        cls.name = bpy.props.StringProperty(name="Splint Name",default="")
        cls.model = bpy.props.StringProperty(name="Splint Model",default="")
        cls.opposing = bpy.props.StringProperty(name="Opposing Model",default="")
        cls.bone = bpy.props.StringProperty(name="Bone",default="")
        cls.refractory = bpy.props.StringProperty(name="Rrefractory model",default="")
        cls.axis = bpy.props.StringProperty(name="Splint Insertion",default="")
        cls.margin = bpy.props.StringProperty(name="Splint Bez",default="")
        cls.splint = bpy.props.StringProperty(name="Splint Restoration",default="")
        cls.falloff = bpy.props.StringProperty(name="falloff mesh",default="")
        cls.plane = bpy.props.StringProperty(name="Occlusal Plane",default="")
        cls.cut = bpy.props.StringProperty(name="Cut Surface",default="")
        
        #tooth names used to repopulate lists above before saving
        cls.tooth_string = bpy.props.StringProperty(name="teeth in splint names separated by : or \n",default="")
        cls.implant_string = bpy.props.StringProperty(name="implants in splint names separated by : or \n",default="")
        cls.ops_string = bpy.props.StringProperty(name="operators used",default="", maxlen = 2000)
    
        #done
        cls.model_set = bpy.props.BoolProperty(name = 'model_set', default = False)
        #done
        cls.opposing_set = bpy.props.BoolProperty(name = 'opposing_set', default = False)
        #done
        cls.landmarks_set = bpy.props.BoolProperty(name = 'landmarks_set', default = False)
        #done
        cls.curve_max = bpy.props.BoolProperty(name = 'curve_max', default = False)
        #done
        cls.curve_mand = bpy.props.BoolProperty(name = 'curve_mand', default = False)
        #done
        cls.splint_outline = bpy.props.BoolProperty(name = 'splint_outline', default = False)
        #done
        cls.trim_upper = bpy.props.BoolProperty(name = 'trim_upper', default = False)
        #done
        cls.splint_shell = bpy.props.BoolProperty(name = 'splint_shell', default = False)
        #done
        cls.passive_offset = bpy.props.BoolProperty(name = 'passive_offset', default = False)
        #done
        cls.finalize_splint = bpy.props.BoolProperty(name = 'finalize_splint', default = False)
        
        
    @classmethod
    def unregister(cls):
        del bpy.types.Scene.odc_splints
        del bpy.types.Scene.odc_splint_index
            
    def load_components_from_string(self,scene):
        print('no longer loading components')
        #tooth_list = self.tooth_string.split(sep=":")
        #for name in tooth_list:
        #    tooth = scene.odc_teeth.get(name)
        #    if tooth and tooth not in self.teeth:
        #        self.teeth.append(tooth)
    
        #imp_list = self.implant_string.split(sep=":")
        #for name in imp_list:
        #    implant = scene.odc_implants.get(name)
        #    if implant and implant not in self.implants:
        #        self.implants.append(implant)
                
    def save_components_to_string(self):
        print(self.tooth_string)
        print(self.implant_string)
        
        #names = [tooth.name for tooth in self.teeth]
        #names.sort()
        #self.tooth_string = ":".join(names)
        
        #i_names = [implant.name for implant in self.implants]
        #i_names.sort()
        #self.implant_string = ":".join(i_names)
                
    def add_tooth(self,tooth):
        name = tooth.name
        if len(self.tooth_string):
            tooth_list = self.tooth_string.split(sep=":")
            if name not in tooth_list:
                tooth_list.append(name)
                tooth_list.sort()
                self.tooth_string = ":".join(tooth_list)
                self.teeth.append(tooth)           
     
    def cleanup(self):
        print('not implemented')
        
class D3SplintRestorationAdd(bpy.types.Operator):
    '''Be sure to have an object selected to build the splint on!'''
    bl_idname = 'd3splint.add_splint'
    bl_label = "Append Splint"
    bl_options = {'REGISTER','UNDO'}
    
    name = bpy.props.StringProperty(name="Splint Name",default="_Splint")  
    link_active = bpy.props.BoolProperty(name="Link",description = "Link active object as base model for splint", default = True)
    def invoke(self, context, event): 
        
        
        context.window_manager.invoke_props_dialog(self, width=300) 
        return {'RUNNING_MODAL'}
    
    def execute(self, context):

        my_item = context.scene.odc_splints.add()        
        my_item.name = self.name
        
        if self.link_active:
            if context.object:
                my_item.model = context.object.name
            elif context.selected_objects:
                my_item.model = context.selected_objects[0].name
                
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        col = layout.column()
    
        row = col.row()
        row.prop(self, "name", expand=True)
        
        row = col.row()
        row.prop(self, "link_active", text = "Plan splint on active object")
        
        row = col.row()
        row.label('Ensure you have the correct object')
        
        row = col.row()
        row.label('selected.  If not, cancel and retry!')
        
        if context.object != None:
            row = col.row()
            row.label('Active object:' + context.object.name)
          
class D3SplintRestorationRemove(bpy.types.Operator):
    ''''''
    bl_idname = 'd3splint.remove_splint'
    bl_label = "Remove Splint Restoration"
    
    def execute(self, context):

        j = bpy.context.scene.odc_splint_index
        bpy.context.scene.odc_splints.remove(j)
            
        return {'FINISHED'}
    

    
        
def register():
    bpy.utils.register_class(D3SplintProps)
    bpy.utils.register_class(D3SplintRestoration)
    bpy.utils.register_class(D3SplintRestorationAdd)
    bpy.utils.register_class(D3SplintRestorationRemove)
    

def unregister():
    bpy.utils.unregister_class(D3SplintProps)
    D3SplintProps.unregister()
    D3SplintRestoration.unregister()
    bpy.utils.unregister_class(D3SplintRestorationAdd)
    bpy.utils.unregister_class(D3SplintRestorationRemove)
    
    '''
if __name__ == "__main__":
    register()
    '''