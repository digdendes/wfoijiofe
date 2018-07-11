'''
Created on Jul 9, 2018
https://blender.stackexchange.com/questions/8435/how-to-programmatically-load-a-python-script-in-text-editor-and-launch-it

@author: Patrick
'''
import bpy
import time

from d3guard import bl_info
from common_utilities import get_addon

class D3SPLINT_OT_splint_report(bpy.types.Operator):
    '''
    Will add a text object to the .blend file which tells
    the information about a surgical guide and it's various
    details.
    '''
    bl_idname='d3splint.splint_report'
    bl_label="Splint Report"
    bl_options = {'REGISTER','UNDO'}
    
    @classmethod
    def poll(cls, context):
        condition_1 = len(context.scene.odc_splints) > 0
        return condition_1
    
    def execute(self,context):
        sce = context.scene
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n] 
        
        addon = get_addon()
        if 'Report' in bpy.data.texts:
            n = len([t for t in bpy.data.texts if "Report" in t.name])
            Report = bpy.data.texts.new("Report" + "_" + str(n))
        else:
            Report = bpy.data.texts.new("Report")
    
    
        Report.write("D3Splint Appliance Report")
        Report.write("\n")
        Report.write("\n")
        
        Report.write("D3Splint Version: " + str(bl_info["version"]))
        Report.write("\n")
        Report.write('Date and Time: ')
        Report.write(time.asctime())
        Report.write("\n")
        Report.write("\n")
        
        Report.write("#############################\n")
        Report.write("#### Splint Properties ######\n")
        Report.write("#############################\n")
        Report.write("\n")
        Report.write("Splint Jaw Type: " + splint.jaw_type)
        Report.write("\n")
        Report.write("Splint Apliance Type: " + splint.workflow_type)
        Report.write("\n")
        if splint.refractory_model:
            Report.write("Offset Spacer: " + str(splint.passive_value)[0:6])
            Report.write("\n")
            Report.write("Allowed Undercut: " + str(splint.undercut_value)[0:6])
            Report.write("\n")
        else:
            Report.write("Offset Spacer: N/A No Refractory Model")
            Report.write("\n")
            Report.write("Allowed Undercut: N/A No Refractory Model")
            Report.write("\n")
        Report.write("_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _")
        Report.write("\n")
        Report.write("\n")
        
        
        Report.write("#############################\n")
        Report.write("######  Workflow Steps ######\n")
        Report.write("#############################\n")
        
        Report.write("\n")
        ops = splint.ops_string.split(':')
        for i, op in enumerate(ops):
            Report.write(str(i) + ". " + op)
            Report.write("\n")
        Report.write("\n")
        Report.write("#############################\n")
        Report.write("#### Articulator Values #####\n")
        Report.write("#############################\n")
        if 'Articulator' in bpy.data.objects:
            art_arm = bpy.data.objects.get('Articulator')
            
            if art_arm.get('bennet_angle'):
                Report.write("Bennet Angle: " + str(art_arm.get('bennet_angle')))
                Report.write("\n")
            if art_arm.get('intra_condyl_width'):
                Report.write("Inracondylar Width: " + str(art_arm['intra_condyly_width']))
                Report.write("\n")
            if art_arm.get('incisal_guidance'):
                Report.write("Incisal Guidance: " + str(art_arm['incisal_guidance']))
                Report.write("\n")  
            if art_arm.get('canine_guidance'):
                Report.write("Canine Guidance: " + str(art_arm['canine_guidance']))
                Report.write("\n") 
            if art_arm.get('condyle_angle'):
                Report.write("Condyle Angle: " + str(art_arm['condyle_angle']))
                Report.write("\n")  
            if art_arm.get('guidance_delay_ant'):
                Report.write('Anterior Guidance Delay: ' + str(art_arm['guidance_delay_ant']))
                Report.write("\n") 
            if art_arm.get('guidance_delay_lat'):
                Report.write('Canine Guidance Delay: ' + str(art_arm['guidance_delay_lat']))
                Report.write("\n")
        
        screen = context.window.screen
        areas = [area for area in screen.areas]
        types = [area.type for area in screen.areas]
        
        if 'TEXT_EDITOR' not in types:
            
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    break 
            
            #bpy.ops.view3d.toolshelf() #close the first toolshelf               
            override = context.copy()
            override['area'] = area
            bpy.ops.screen.area_split(override, direction='VERTICAL', factor=0.5, mouse_x=-100, mouse_y=-100)
            
            for area in screen.areas:
                if area not in areas:
                    break
            area.type = 'TEXT_EDITOR'
        
        else:
            for area in screen.areas:
                if area.type == 'TEXT_EDITOR':
                    break 
                
        area.spaces[0].text = Report
        override = context.copy()
        override['area'] = area
        bpy.ops.text.jump(override, line=1)
        #colelct existing scren
        #ws = [w for w in context.window_manager.windows]
        #bpy.ops.screen.area_dupli()
        #find the new screen
        #for w in context.window_manager.windows:
        #    if w not in ws:
        #        break
        #Find the new 3d view and change the area into a text editor
        #for area in w.screen.areas:
        #    if area.type == 'VIEW_3D':
        #        break 
        
        #area.type = 'TEXT_EDITOR'
        
        '''
        for splint in sce.odc_splints:
            imp_names = splint.implant_string.split(":")
            imp_names.pop(0)
            Report.write("Splint Name: " + splint.name)
            Report.write("\n")
            Report.write("Number of Implants: %i" % len(imp_names))
            Report.write("\n")
            Report.write("Implants: ")
            Report.write(splint.implant_string)
            Report.write("\n")
            
            
            for name in imp_names:
                imp = sce.odc_implants[name]
                Report.write("\n")
                Report.write("Implant: " + name + "\n")
                
                if imp.implant and imp.implant in bpy.data.objects:
                    implant = bpy.data.objects[imp.implant]
                    V = implant.dimensions
                    width = '{0:.{1}f}'.format(V[0], 2)
                    length = '{0:.{1}f}'.format(V[2], 2)
                    Report.write("Implant Dimensions: " + width + "mm x " + length + "mm")
                    Report.write("\n")
                    
                if imp.inner and imp.inner in bpy.data.objects:
                    inner = bpy.data.objects[imp.inner]
                    V = inner.dimensions
                    width = '{0:.{1}f}'.format(V[0], 2)
                    Report.write("Hole Diameter: " + width + "mm")
                    Report.write("\n")
                else:
                    Report.write("Hole Diameter: NO HOLE")    
                    Report.write("\n")
                    
                    
                if imp.outer and imp.outer in bpy.data.objects and imp.implant and imp.implant in bpy.data.objects:
                    implant = bpy.data.objects[imp.implant]
                    guide = bpy.data.objects[imp.outer]
                    v1 = implant.matrix_world.to_translation()
                    v2 = guide.matrix_world.to_translation()
                    V = v2 - v1
                    depth = '{0:.{1}f}'.format(V.length, 2)
                    print(depth)
                    Report.write("Cylinder Depth: " + depth + "mm")
                    Report.write("\n")
                else:
                    Report.write("Cylinder Depth: NO GUIDE CYLINDER \n")
                    
                if imp.sleeve and imp.sleeve in bpy.data.objects and imp.implant and imp.implant in bpy.data.objects:
                    implant = bpy.data.objects[imp.implant]
                    guide = bpy.data.objects[imp.sleeve]
                    v1 = implant.matrix_world.to_translation()
                    v2 = guide.matrix_world.to_translation()
                    V = v2 - v1
                    depth = '{0:.{1}f}'.format(V.length, 2)
                    Report.write("Sleeve Depth: " + depth + "mm")
                    Report.write("\n")
                else:
                    Report.write("Sleeve Depth: NO SLEEVE")    
                    Report.write("\n")
                    
            Report.write("_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _")
            Report.write("\n")
            Report.write("\n")
        '''
        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(D3SPLINT_OT_splint_report)

def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_splint_report)