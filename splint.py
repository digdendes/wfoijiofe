import time
import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Color
from mathutils.geometry import intersect_point_line
from bpy_extras import view3d_utils
from bpy.props import FloatProperty, BoolProperty, IntProperty, EnumProperty
import bgl
import blf

from mesh_cut import edge_loops_from_bmedges, space_evenly_on_path

#from . 
import odcutils
import bmesh_fns
from odcutils import get_settings, offset_bmesh_edge_loop
import bgl_utils
import common_drawing
import common_utilities
#from . 
import full_arch_methods
from textbox import TextBox
from curve import CurveDataManager, PolyLineKnife
from common_utilities import space_evenly_on_path
from mathutils.bvhtree import BVHTree
import splint_cache
import tracking

'''
https://occlusionconnections.com/gnm-optimized/which-occlusal-plane-do-you-undestand-dont-get-confused/
http://www.claytonchandds.com/pdf/ICCMO/AReviewOfTheOcclusalPlane.pdf
'''
class OPENDENTAL_OT_link_selection_splint(bpy.types.Operator):
    ''''''
    bl_idname='opendental.link_selection_splint'
    bl_label="Link Units to Splint"
    bl_options = {'REGISTER','UNDO'}
    
    clear = bpy.props.BoolProperty(name="Clear", description="Replace existing units with selected, \n else add selected to existing", default=False)
    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        teeth = odcutils.tooth_selection(context)  #TODO:...make this poll work for all selected teeth...
        condition_1 = len(teeth) > 0
        implants = odcutils.implant_selection(context)  
        condition_2 = len(implants) > 0
        return condition_1 or condition_2
    
    def execute(self,context):
        settings = get_settings()
        dbg =settings.debug
        n = context.scene.odc_splint_index
        odc_splint = context.scene.odc_splints[n]
        full_arch_methods.link_selection_to_splint(context, odc_splint, debug=dbg)
        
        return {'FINISHED'}
    
class OPENDENTAL_OT_splint_bone(bpy.types.Operator):
    '''
    Will assign the active object as the bone model
    Only use if making multi tissue support.  eg bone
    and teeth.
    '''
    bl_idname='opendental.bone_model_set'
    bl_label="Splint Bone"
    bl_options = {'REGISTER','UNDO'}
    
    @classmethod
    def poll(cls, context):

        condition_1 = context.object
                
        return condition_1
    
    def execute(self,context):
        settings = get_settings()
        dbg =settings.debug
        n = context.scene.odc_splint_index
        
        if len(context.scene.odc_splints) != 0:
            
            odc_splint = context.scene.odc_splints[n]
            odc_splint.bone = context.object.name
            
        else:
            self.report({'WARNING'}, "there are not guides, bone will not be linked to a guide")
        
        context.scene.odc_props.bone = context.object.name
        
        return {'FINISHED'}

class OPENDENTAL_OT_splint_model(bpy.types.Operator):
    '''
    Will assign the active object as the  model to build
    a splint on.  Needed if an object was not linked
    when splint was planned
    '''
    bl_idname='opendental.model_set'
    bl_label="Set Splint Model"
    bl_options = {'REGISTER','UNDO'}
    
    @classmethod
    def poll(cls, context):

        condition_1 = context.object != None
              
        return condition_1
    
    def execute(self,context):
        settings = get_settings()
        dbg =settings.debug
        n = context.scene.odc_splint_index
        
        if len(context.scene.odc_splints) != 0:
            
            odc_splint = context.scene.odc_splints[n]
            odc_splint.model = context.object.name
            
        else:
            my_item = context.scene.odc_splints.add()        
            my_item.name = 'Splint'
            my_item.model = context.object.name
        
        tracking.trackUsage("D3Splint:StartSplint")
        return {'FINISHED'}    

class OPENDENTAL_OT_splint_opposing(bpy.types.Operator):
    '''
    Will assign the active object as the  opposing model
    '''
    bl_idname='opendental.splint_opposing_set'
    bl_label="Set Splint Opposing"
    bl_options = {'REGISTER','UNDO'}
    
    @classmethod
    def poll(cls, context):

        condition_1 = context.object
        condition_2 = len(context.scene.odc_splints)       
        return condition_1 and condition_2
    
    def execute(self,context):
        settings = get_settings()
        dbg =settings.debug
        n = context.scene.odc_splint_index
        
        if len(context.scene.odc_splints) != 0:
            odc_splint = context.scene.odc_splints[n]
            odc_splint.opposing = context.object.name
            
        else:
            self.report({'ERROR'}, "Please plan a splint first!")
            return {'CANCELLED'}
        
        
        return {'FINISHED'} 
    
class OPENDENTAL_OT_splint_report(bpy.types.Operator):
    '''
    Will add a text object to the .blend file which tells
    the information about a surgical guide and it's various
    details.
    '''
    bl_idname='opendental.splint_report'
    bl_label="Splint Report"
    bl_options = {'REGISTER','UNDO'}
    
    @classmethod
    def poll(cls, context):

        condition_1 = len(context.scene.odc_splints) > 0
        return condition_1
    
    def execute(self,context):

        sce = context.scene
        if 'Report' in bpy.data.texts:
            Report = bpy.data.texts['Report']
            Report.clear()
        else:
            Report = bpy.data.texts.new("Report")
    
    
        Report.write("Open Dental CAD Implant Guide Report")
        Report.write("\n")
        Report.write('Date and Time: ')
        Report.write(time.asctime())
        Report.write("\n")
    
        Report.write("There is/are %i guide(s)" % len(sce.odc_splints))
        Report.write("\n")
        Report.write("_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _")
        Report.write("\n")
        Report.write("\n")
    
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
        
        return {'FINISHED'}
    
class OPENDENTAL_OT_splint_subtract_holes(bpy.types.Operator):
    ''''''
    bl_idname='opendental.splint_subtract_holes'
    bl_label="Subtract Splint Holes"
    bl_options = {'REGISTER','UNDO'}
    
    finalize = bpy.props.BoolProperty(default = True, name = "Finalize", description="Apply all modifiers to splint before adding guides?  may take longer, less risk of crashing")
    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        #TODO..polling
        return True
    
    def execute(self,context):
        settings = get_settings()
        dbg =settings.debug
        n = context.scene.odc_splint_index
        odc_splint = context.scene.odc_splints[n]
        
        layers_copy = [layer for layer in context.scene.layers]
        context.scene.layers[0] = True
        
        if not odc_splint.splint:
            self.report({'ERROR'},'No splint model to add guide cylinders too')
        if dbg:
            start_time = time.time()
        
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        sce = context.scene
        bpy.ops.object.select_all(action='DESELECT')
        
        new_objs = []
        implants = []
        imp_list = odc_splint.implant_string.split(sep=":")
        for name in imp_list:
            implant = context.scene.odc_implants.get(name)
            if implant:
                implants.append(implant)
                
        for space in implants:
            if space.inner:
                Guide_Cylinder = bpy.data.objects[space.inner]
                Guide_Cylinder.hide = True
                new_data = Guide_Cylinder.to_mesh(sce,True, 'RENDER')
                new_obj = bpy.data.objects.new("temp_holes", new_data)
                new_obj.matrix_world = Guide_Cylinder.matrix_world
                new_objs.append(new_obj)
                sce.objects.link(new_obj)
                new_obj.select = True
        
        if len(new_objs):   
            sce.objects.active = new_objs[0]
            bpy.ops.object.join()
            
        else:
            return{'CANCELLED'}
        
        bpy.ops.object.select_all(action='DESELECT')
        Splint = bpy.data.objects[odc_splint.splint]
        Splint.select = True
        Splint.hide = False
        sce.objects.active = Splint
        if self.finalize:
            for mod in Splint.modifiers:
                if mod.type in {'BOOLEAN', 'SHRINKWRAP'}:
                    if mod.type == 'BOOLEAN' and mod.object:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                    elif mod.type == 'SHRINKWRAP' and mod.target:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                else:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
        
        bool_mod = Splint.modifiers.new('OUTER','BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = new_objs[0] #hopefully this is still the object?
        new_objs[0].hide = True   
        
        for i, layer in enumerate(layers_copy):
            context.scene.layers[i] = layer
        context.scene.layers[10] = True
        
        if dbg:
            finish = time.time() - start_time
            print("finished subtracting holes in %f seconds..boy that took a long time" % finish)
        
        return {'FINISHED'}
        
class OPENDENTAL_OT_splint_subtract_sleeves(bpy.types.Operator):
    '''
    '''
    bl_idname='opendental.splint_subtract_sleeves'
    bl_label="Subtract Splint Sleeves"
    bl_options = {'REGISTER','UNDO'}
    
    finalize = bpy.props.BoolProperty(default = True, name = "Finalize", description="Apply all modifiers to splint before adding guides?  may take longer, less risk of crashing")
    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        #TODO..polling
        return True
    
    def execute(self,context):
        settings = get_settings()
        dbg =settings.debug
        n = context.scene.odc_splint_index
        odc_splint = context.scene.odc_splints[n]
        layers_copy = [layer for layer in context.scene.layers]
        context.scene.layers[0] = True
        
        if not odc_splint.splint:
            self.report({'ERROR'},'No splint model to add guide cylinders too')
        if dbg:
            start_time = time.time()
        
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        sce = context.scene
        bpy.ops.object.select_all(action='DESELECT')
        
        implants = []
        imp_list = odc_splint.implant_string.split(sep=":")
        for name in imp_list:
            implant = context.scene.odc_implants.get(name)
            if implant:
                implants.append(implant)
                
        new_objs = []
        for space in implants:
            if space.sleeve:
                Sleeve_Female = bpy.data.objects[space.sleeve]
                Sleeve_Female.hide = True
                new_data = Sleeve_Female.to_mesh(sce,True, 'RENDER')
                new_obj = bpy.data.objects.new("temp_holes", new_data)
                new_obj.matrix_world = Sleeve_Female.matrix_world
                new_objs.append(new_obj)
                sce.objects.link(new_obj)
                new_obj.select = True
        
        if len(new_objs):   
            sce.objects.active = new_objs[0]
            bpy.ops.object.join()
            
        else:
            return{'CANCELLED'}
        
        bpy.ops.object.select_all(action='DESELECT')
        Splint = bpy.data.objects[odc_splint.splint]
        Splint.select = True
        Splint.hide = False
        sce.objects.active = Splint
        if self.finalize:
            for mod in Splint.modifiers:
                if mod.type in {'BOOLEAN', 'SHRINKWRAP'}:
                    if mod.type == 'BOOLEAN' and mod.object:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                    elif mod.type == 'SHRINKWRAP' and mod.target:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                else:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    
        bool_mod = Splint.modifiers.new('Sleeves','BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = new_objs[0] #hopefully this is still the object?
        new_objs[0].hide = True   
        
        for i, layer in enumerate(layers_copy):
            context.scene.layers[i] = layer
        context.scene.layers[11] = True
        
        if dbg:
            finish = time.time() - start_time
            print("finished subtracting Sleeves in %f seconds..boy that took a long time" % finish)
        
        return {'FINISHED'}
    
class OPENDENTAL_OT_splint_add_guides(bpy.types.Operator):
    ''''''
    bl_idname='opendental.splint_add_guides'
    bl_label="Merge Guide Cylinders to Splint"
    bl_options = {'REGISTER','UNDO'}
    
    finalize = bpy.props.BoolProperty(default = True, name = "Finalze",description="Apply all modifiers to splint before adding guides?  may take longer, less risk of crashing")
    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        #TODO..polling
        if not len(context.scene.odc_splints): return False
        n = context.scene.odc_splint_index
        odc_splint = context.scene.odc_splints[n]
        imp_list = odc_splint.implant_string.split(sep=":")
        
        if len(imp_list) == 0: return False
        
        return True
    
    def execute(self,context):
        settings = get_settings()
        dbg = settings.debug
        n = context.scene.odc_splint_index
        odc_splint = context.scene.odc_splints[n]
        
        if not odc_splint.splint:
            self.report({'ERROR'},'No splint model to add guide cylinders too')
        if dbg:
            start_time = time.time()
        
        layers_copy = [layer for layer in context.scene.layers]
        context.scene.layers[0] = True
            
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        sce = context.scene
        bpy.ops.object.select_all(action='DESELECT')
        
        new_objs = []
        
        implants = []
        imp_list = odc_splint.implant_string.split(sep=":")
        for name in imp_list:
            implant = context.scene.odc_implants.get(name)
            if implant:
                implants.append(implant)
        for space in implants:
            if space.outer and space.outer in bpy.data.objects:
                Guide_Cylinder = bpy.data.objects[space.outer]
                Guide_Cylinder.hide = True
                new_data = Guide_Cylinder.to_mesh(sce,True, 'RENDER')
                new_obj = bpy.data.objects.new("temp_guide", new_data)
                new_obj.matrix_world = Guide_Cylinder.matrix_world
                new_objs.append(new_obj)
                sce.objects.link(new_obj)
                new_obj.select = True
        
        if len(new_objs):   
            sce.objects.active = new_objs[0]
            bpy.ops.object.join()
        else:
            return{'CANCELLED'}
        
        bpy.ops.object.select_all(action='DESELECT')
        Splint = bpy.data.objects[odc_splint.splint]
        Splint.select = True
        Splint.hide = False
        sce.objects.active = Splint
        if self.finalize:
            for mod in Splint.modifiers:
                if mod.type in {'BOOLEAN', 'SHRINKWRAP'}:
                    if mod.type == 'BOOLEAN' and mod.object:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                    elif mod.type == 'SHRINKWRAP' and mod.target:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                else:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
        
        bool_mod = Splint.modifiers.new('OUTER','BOOLEAN')
        bool_mod.operation = 'UNION'
        bool_mod.object = new_objs[0] #hopefully this is still the object?
        new_objs[0].hide = True   
        
        for i, layer in enumerate(layers_copy):
            context.scene.layers[i] = layer
        context.scene.layers[11] = True
        
        if dbg:
            finish = time.time() - start_time
            print("finished merging guides in %f seconds..boy that took a long time" % finish)
        
        return {'FINISHED'}

#Depricated, no longer used
class OPENDENTAL_OT_initiate_arch_curve(bpy.types.Operator):
    '''Places a bezier curve to be extruded around the planned plane of occlussion'''
    bl_idname = 'opendental.initiate_arch_curve'
    bl_label = "Arch Plan Curve"
    bl_options = {'REGISTER','UNDO'}
    
    
    @classmethod
    def poll(cls, context):
        if context.object and context.mode == 'OBJECT':
            return True
        else:
            return False
        #return len(context.scene.odc_splints) > 0             

    def execute(self, context):
        
        sce=bpy.context.scene
        ob = context.object
        layers_copy = [layer for layer in context.scene.layers]
        context.scene.layers[0] = True
        
        if ob:

            L = odcutils.get_bbox_center(ob, world=True)
        
        elif sce.odc_props.master:
            ob = bpy.data.objects[sce.odc_props.master]
            L = odcutils.get_bbox_center(ob, world=True)
            
        else:
            L = bpy.context.scene.cursor_location

        bpy.ops.view3d.viewnumpad(type='TOP')
        bpy.ops.object.select_all(action='DESELECT')
        
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        #bpy.context.scene.cursor_location = L
        bpy.ops.curve.primitive_bezier_curve_add(view_align=True, enter_editmode=True, location=L)
        PlanCurve = context.object
        PlanCurve.layers[4] = True
        PlanCurve.layers[0] = True
        PlanCurve.layers[1] = True
        PlanCurve.layers[3] = True
        
        context.tool_settings.use_snap = True
        context.tool_settings.snap_target= 'ACTIVE'
        context.tool_settings.snap_element = 'FACE'
        context.tool_settings.proportional_edit = 'DISABLED'
        context.tool_settings.use_snap_project = False
        
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.curve.handle_type_set(type='AUTOMATIC')
        bpy.ops.curve.select_all(action='DESELECT')
        context.object.data.splines[0].bezier_points[1].select_control_point=True
        bpy.ops.curve.delete()
        bpy.ops.curve.select_all(action='SELECT')
            
        odcutils.layer_management(sce.odc_splints)
        for i, layer in enumerate(layers_copy):
            context.scene.layers[i] = layer
        context.scene.layers[3] = True
        return {'FINISHED'}

def arch_crv_draw_callback(self, context):  
    self.crv.draw(context)
    self.help_box.draw()      
    

class OPENDENTAL_OT_arch_curve(bpy.types.Operator):
    """Draw a line with the mouse to extrude bezier curves"""
    bl_idname = "opendental.draw_arch_curve"
    bl_label = "Arch Curve Generic"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        return True
    
    def modal_nav(self, event):
        events_nav = {'MIDDLEMOUSE', 'WHEELINMOUSE','WHEELOUTMOUSE', 'WHEELUPMOUSE','WHEELDOWNMOUSE'} #TODO, better navigation, another tutorial
        handle_nav = False
        handle_nav |= event.type in events_nav

        if handle_nav: 
            return 'nav'
        return ''
    
    def modal_main(self,context,event):
        # general navigation
        nmode = self.modal_nav(event)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'

        #after navigation filter, these are relevant events in this state
        if event.type == 'G' and event.value == 'PRESS':
            if self.crv.grab_initiate():
                return 'grab'
            else:
                #error, need to select a point
                return 'main'
        
        if event.type == 'MOUSEMOVE':
            self.crv.hover(context, event.mouse_region_x, event.mouse_region_y)    
            return 'main'
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            x, y = event.mouse_region_x, event.mouse_region_y
            self.crv.click_add_point(context, x,y)
            return 'main'
        
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            self.crv.click_delete_point(mode = 'mouse')
            return 'main'
        
        if event.type == 'X' and event.value == 'PRESS':
            self.crv.delete_selected(mode = 'selected')
            return 'main'
            
        if event.type == 'RET' and event.value == 'PRESS':
            context.space_data.show_manipulator = True #TODO..save initial state
            return 'finish'
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            context.space_data.show_manipulator = True  #TODO..save initial state
            return 'cancel' 

        return 'main'
    
    def modal_grab(self,context,event):
        # no navigation in grab mode
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            #confirm location
            self.crv.grab_confirm()
            return 'main'
        
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            #put it back!
            self.crv.grab_cancel()
            return 'main'
        
        elif event.type == 'MOUSEMOVE':
            #update the b_pt location
            self.crv.grab_mouse_move(context,event.mouse_region_x, event.mouse_region_y)
            return 'grab'
        
    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['grab']    = self.modal_grab
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #clean up callbacks
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def invoke(self,context, event):
        
        if context.object:
            ob = context.object
            L = odcutils.get_bbox_center(ob, world=True)
            context.scene.cursor_location = L
        
        context.space_data.show_manipulator = False
        self.crv = CurveDataManager(context,snap_type ='SCENE', snap_object = None, shrink_mod = False, name = 'Plan Curve')
         
        #TODO, tweak the modifier as needed
        help_txt = "DRAW ARCH OUTLINE\n\nLeft Click in scene to draw a curve \nPoints will snap to objects under mouse \nNot clicking on object will make points at same depth as 3D cursor \n Right click to delete a point n\ G to grab  \n ENTER to confirm \n ESC to cancel"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(arch_crv_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        return {'RUNNING_MODAL'}


class OPENDENTAL_OT_splint_buccal_marks(bpy.types.Operator):
    """Draw a line along the facial limits of the splint"""
    bl_idname = "opendental.draw_buccal_curve"
    bl_label = "Mark Buccal Splint Limits"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        return True
    
    def modal_nav(self, event):
        events_nav = {'MIDDLEMOUSE', 'WHEELINMOUSE','WHEELOUTMOUSE', 'WHEELUPMOUSE','WHEELDOWNMOUSE'} #TODO, better navigation, another tutorial
        handle_nav = False
        handle_nav |= event.type in events_nav

        if handle_nav: 
            return 'nav'
        return ''
    
    def modal_main(self,context,event):
        # general navigation
        nmode = self.modal_nav(event)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'

        #after navigation filter, these are relevant events in this state
        if event.type == 'G' and event.value == 'PRESS':
            if self.crv.grab_initiate():
                return 'grab'
            else:
                #error, need to select a point
                return 'main'
        
        if event.type == 'MOUSEMOVE':
            self.crv.hover(context, event.mouse_region_x, event.mouse_region_y)    
            return 'main'
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            x, y = event.mouse_region_x, event.mouse_region_y
            self.crv.click_add_point(context, x,y)
            return 'main'
        
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            self.crv.click_delete_point(mode = 'mouse')
            return 'main'
        
        if event.type == 'X' and event.value == 'PRESS':
            self.crv.delete_selected(mode = 'selected')
            return 'main'
            
        if event.type == 'RET' and event.value == 'PRESS':
            return 'finish'
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            return 'cancel' 

        return 'main'
    
    def modal_grab(self,context,event):
        # no navigation in grab mode
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            #confirm location
            self.crv.grab_confirm()
            return 'main'
        
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            #put it back!
            self.crv.grab_cancel()
            return 'main'
        
        elif event.type == 'MOUSEMOVE':
            #update the b_pt location
            self.crv.grab_mouse_move(context,event.mouse_region_x, event.mouse_region_y)
            return 'grab'
        
    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['grab']    = self.modal_grab
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #clean up callbacks
            context.space_data.show_manipulator = False
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def invoke(self,context, event):
        
        self.splint = odcutils.splint_selction(context)[0]    
        self.crv = None
        margin = self.splint.name + '_buccal'
           
        if self.splint.model != '' and self.splint.model in bpy.data.objects:
            Model = bpy.data.objects[self.splint.model]
            for ob in bpy.data.objects:
                ob.select = False
                ob.hide = True
            Model.select = True
            Model.hide = False
            context.scene.objects.active = Model
            bpy.ops.view3d.viewnumpad(type = 'FRONT')
            bpy.ops.view3d.view_selected()
            context.space_data.show_manipulator = False
            self.crv = CurveDataManager(context,snap_type ='OBJECT', snap_object = Model, shrink_mod = False, name = margin)
            self.crv.crv_obj.parent = Model
            
        else:
            self.report({'ERROR'}, "Need to mark the UpperJaw model first!")
            return {'CANCELLED'}
            
        self.splint.margin = self.crv.crv_obj.name
        
        #TODO, tweak the modifier as needed
        help_txt = "DRAW BUCCAL POINTS\n\nLeft Click on buccal surfaces to define splint boundary \nPoints will snap to objects under mouse \n Right click to delete a point n\ G to grab  \n ENTER to confirm \n ESC to cancel"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(arch_crv_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        
        tracking.trackUsage("D3Splint:MarkOutline", None)
        return {'RUNNING_MODAL'}


class OPENDENTAL_OT_splint_occlusal_arch(bpy.types.Operator):
    """Draw a line along the lingual cusps of the opposign model"""
    bl_idname = "opendental.draw_occlusal_curve"
    bl_label = "Mark Occlusal Curve"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        return True

    def  convert_curve_to_plane(self, context):
        
        me = self.crv.crv_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        mx = self.crv.crv_obj.matrix_world
        arch_vs = [mx*v.co for v in me.vertices]
        arc_vs_even, eds = space_evenly_on_path(arch_vs, [(0,1),(1,2)], 101, 0)
        
        v_ant = arc_vs_even[50] #we established 100 verts so 50 is the anterior midpoint
        v_0 = arc_vs_even[0]
        v_n = arc_vs_even[-1]
        
        center = .5 *(.5*(v_0 + v_n) + v_ant)
        
        vec_n = v_n - v_0
        vec_n.normalize()
        
        vec_ant = v_ant - v_0
        vec_ant.normalize()
        
        Z = vec_n.cross(vec_ant)
        Z.normalize()
        X = v_ant - center
        X.normalize()
        
        if Z.dot(Vector((0,0,1))) < 0:
            Z = -1 * Z
                
        Y = Z.cross(X)
        
        R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
        R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
        R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2]
        
        R = R.to_4x4()
        T = Matrix.Translation(center - 4 * Z)
        T2 = Matrix.Translation(center + 10 * Z)
        
        bme = bmesh.new()
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        bmesh.ops.create_grid(bme, x_segments = 200, y_segments = 200, size = 39.9)
        
        bme.to_mesh(me)
        plane_obj = bpy.data.objects.new('Occlusal Plane', me)
        plane_obj.matrix_world = T * R
        context.scene.objects.link(plane_obj)
        bme.free()
        
        #bme = bmesh.new()
        #bme.verts.ensure_lookup_table()
        #bme.edges.ensure_lookup_table()
        #bme.faces.ensure_lookup_table()
        #bmesh.ops.create_grid(bme, x_segments = 2, y_segments = 2, size = 40)
        
        #new_me = bpy.data.meshes.new('Lower Plane')
        #bme.to_mesh(new_me)
        #plane_obj2 = bpy.data.objects.new('Lower Plane', new_me)
        #plane_obj2.matrix_world = T * R
        #context.scene.objects.link(plane_obj2)
        #bme.free()
        
        #mod = plane_obj.modifiers.new('Shrink', type = 'SHRINKWRAP')
        #mod.wrap_method = 'PROJECT'
        #mod.use_project_z = True
        #mod.use_negative_direction = True
        #mod.use_positive_direction = True
        #mod.target = bpy.data.objects[context.scene.odc_splints[0].opposing]
        #mod.auxiliary_target = plane_obj2
        
        
        #plane_obj2.hide = True
        #plane_obj.hide = True
        
        #Lets Calculate the matrix transform for an
        #8 degree Fox plane cant.
        #Z_w = Vector((0,0,1))
        #X_w = Vector((1,0,0))
        #Y_w = Vector((0,1,0))
        #Fox_R = Matrix.Rotation(8 * math.pi /180, 3, 'Y')
        #Z_fox = Fox_R * Z_w
        #X_fox = Fox_R * X_w
        
        #R_fox = Matrix.Identity(3)  #make the columns of matrix U, V, W
        #R_fox[0][0], R_fox[0][1], R_fox[0][2]  = X_fox[0] ,Y_w[0],  Z_fox[0]
        #R_fox[1][0], R_fox[1][1], R_fox[1][2]  = X_fox[1], Y_w[1],  Z_fox[1]
        #R_fox[2][0] ,R_fox[2][1], R_fox[2][2]  = X_fox[2], Y_w[2],  Z_fox[2]
        
     
        #mx_final = T * R
        #mx_inv = mx_final.inverted()
        
        #incisal = mx_inv * v_ant
        
        #average distance from campers plane to occlusal
        #plane is 30 mm
        #file:///C:/Users/Patrick/Downloads/CGBCC4_2014_v6n6_483.pdf
        #incisal_final = Vector((90, 0, -30))
        
        
        #T2 = Matrix.Translation(incisal_final - incisal)
        
        #mx_mount = T2 * R_fox.to_4x4()
        
        #self.crv.crv_obj.data.transform(mx_inv)
        #self.crv.crv_obj.matrix_world = mx_mount
        
            
    def modal_nav(self, event):
        events_nav = {'MIDDLEMOUSE', 'WHEELINMOUSE','WHEELOUTMOUSE', 'WHEELUPMOUSE','WHEELDOWNMOUSE'} #TODO, better navigation, another tutorial
        handle_nav = False
        handle_nav |= event.type in events_nav

        if handle_nav: 
            return 'nav'
        return ''
    
    def modal_main(self,context,event):
        # general navigation
        nmode = self.modal_nav(event)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'

        #after navigation filter, these are relevant events in this state
        if event.type == 'G' and event.value == 'PRESS':
            if self.crv.grab_initiate():
                return 'grab'
            else:
                #error, need to select a point
                return 'main'
        
        if event.type == 'MOUSEMOVE':
            self.crv.hover(context, event.mouse_region_x, event.mouse_region_y)    
            return 'main'
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            x, y = event.mouse_region_x, event.mouse_region_y
            self.crv.click_add_point(context, x,y)
            return 'main'
        
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            self.crv.click_delete_point(mode = 'mouse')
            return 'main'
        
        if event.type == 'X' and event.value == 'PRESS':
            self.crv.delete_selected(mode = 'selected')
            return 'main'
            
        if event.type == 'RET' and event.value == 'PRESS':
            self.convert_curve_to_plane(context)
            tracking.trackUsage("D3Splint:SplintMandibularCurve",None)
            return 'finish'
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            return 'cancel' 

        return 'main'
    
    def modal_grab(self,context,event):
        # no navigation in grab mode
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            #confirm location
            self.crv.grab_confirm()
            return 'main'
        
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            #put it back!
            self.crv.grab_cancel()
            return 'main'
        
        elif event.type == 'MOUSEMOVE':
            #update the b_pt location
            self.crv.grab_mouse_move(context,event.mouse_region_x, event.mouse_region_y)
            return 'grab'
        
    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['grab']    = self.modal_grab
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            context.space_data.show_manipulator = True
            #clean up callbacks
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def invoke(self,context, event):
        
        self.splint = odcutils.splint_selction(context)[0]    
        self.crv = None
        margin = 'Occlusal Curve Mand'
           
        if self.splint.opposing != '' and self.splint.opposing in bpy.data.objects:
            Model = bpy.data.objects[self.splint.opposing]
            for ob in bpy.data.objects:
                ob.select = False
                ob.hide = True
            Model.select = True
            Model.hide = False
            context.scene.objects.active = Model
            bpy.ops.view3d.viewnumpad(type = 'TOP')
            bpy.ops.view3d.view_selected()
            context.space_data.show_manipulator = False
            self.crv = CurveDataManager(context,snap_type ='OBJECT', snap_object = Model, shrink_mod = False, name = margin)
            self.crv.crv_obj.parent = Model
            
        else:
            self.report({'ERROR'}, "Need to mark the Opposing model first!")
            return {'CANCELLED'}
            
        
        #self.splint.occl = self.crv.crv_obj.name
        
        #TODO, tweak the modifier as needed
        help_txt = "DRAW LINGUAL OCCLUSAL POINTS\n\n-Left Click on lingual cusps and incisal edges to define occlusal plane\n-Points will snap to objects under mouse \n-Right click to delete a point n\ G to grab  \n ENTER to confirm \n ESC to cancel"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(arch_crv_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        return {'RUNNING_MODAL'}
     
def ispltmgn_draw_callback(self, context):  
    self.crv.draw(context)
    self.help_box.draw()      
    

class OPENDENTAL_OT_splint_margin(bpy.types.Operator):
    """Draw a line with the mouse to extrude bezier curves"""
    bl_idname = "opendental.initiate_splint_outline"
    bl_label = "Splint Outine"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        condition_1 = context.object != None
        return condition_1
    
    def modal_nav(self, event):
        events_nav = {'MIDDLEMOUSE', 'WHEELINMOUSE','WHEELOUTMOUSE', 'WHEELUPMOUSE','WHEELDOWNMOUSE'} #TODO, better navigation, another tutorial
        handle_nav = False
        handle_nav |= event.type in events_nav

        if handle_nav: 
            return 'nav'
        return ''
    
    def modal_main(self,context,event):
        # general navigation
        nmode = self.modal_nav(event)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'

        #after navigation filter, these are relevant events in this state
        if event.type == 'G' and event.value == 'PRESS':
            if self.crv.grab_initiate():
                return 'grab'
            else:
                #error, need to select a point
                return 'main'
        
        if event.type == 'MOUSEMOVE':
            self.crv.hover(context, event.mouse_region_x, event.mouse_region_y)    
            return 'main'
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            x, y = event.mouse_region_x, event.mouse_region_y
            self.crv.click_add_point(context, x,y)
            return 'main'
        
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            self.crv.click_delete_point(mode = 'mouse')
            return 'main'
        
        if event.type == 'X' and event.value == 'PRESS':
            self.crv.delete_selected(mode = 'selected')
            return 'main'
            
        if event.type == 'RET' and event.value == 'PRESS':
            return 'finish'
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            return 'cancel' 

        return 'main'
    
    def modal_grab(self,context,event):
        # no navigation in grab mode
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            #confirm location
            self.crv.grab_confirm()
            return 'main'
        
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            #put it back!
            self.crv.grab_cancel()
            return 'main'
        
        elif event.type == 'MOUSEMOVE':
            #update the b_pt location
            self.crv.grab_mouse_move(context,event.mouse_region_x, event.mouse_region_y)
            return 'grab'
        
    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['grab']    = self.modal_grab
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #clean up callbacks
            context.space_data.show_manipulator = True
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}


    def invoke(self,context, event):
        
        if len(context.scene.odc_splints) == 0 and context.object:
            #This is a hidden cheat, allowing quick starting of a splint
            my_item = context.scene.odc_splints.add()        
            my_item.name = context.object.name + '_Splint'
            my_item.model = context.object.name
            self.report({'WARNING'}, "Assumed you wanted to start a new splint on the active object!  If not, then UNDO")
            
            for ob in bpy.data.objects:
                ob.select = False
                
            context.object.select = True
            bpy.ops.view3d.view_selected()
            self.splint = my_item
            
        else:
            self.splint = odcutils.splint_selction(context)[0]
            
        self.crv = None
        margin = self.splint.name + '_outline'
        
        if (self.splint.model == '' or self.splint.model not in bpy.data.objects) and not context.object:
            self.report({'WARNING'}, "There is no model, the curve will snap to anything in the scene!")
            self.crv = CurveDataManager(context,snap_type ='SCENE', snap_object = None, shrink_mod = False, name = margin)
            
        elif self.splint.model != '' and self.splint.model in bpy.data.objects:
            Model = bpy.data.objects[self.splint.model]
            for ob in bpy.data.objects:
                ob.select = False
            Model.select = True
            Model.hide = False
            context.scene.objects.active = Model
            bpy.ops.view3d.view_selected()
            self.crv = CurveDataManager(context,snap_type ='OBJECT', snap_object = Model, shrink_mod = True, name = margin)
            self.crv.crv_obj.parent = Model
            
        if self.crv == None:
            self.report({'ERROR'}, "Not sure what you want, you may need to select an object or plan a splint")
            return {'CANCELLED'}
        
        self.splint.margin = self.crv.crv_obj.name
        
        if 'Wrap' in self.crv.crv_obj.modifiers:
            mod = self.crv.crv_obj.modifiers['Wrap']
            mod.offset = .75
            mod.use_keep_above_surface = True
        
            mod = self.crv.crv_obj.modifiers.new('Smooth','SMOOTH')
            mod.iterations = 10
            
        #TODO, tweak the modifier as needed
        help_txt = "DRAW MARGIN OUTLINE\n\nLeft Click on model to draw outline \nRight click to delete a point \nLeft Click last point to make loop \n G to grab  \n ENTER to confirm \n ESC to cancel"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(ispltmgn_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        context.space_data.show_manipulator = False
        return {'RUNNING_MODAL'}
    
    
def plyknife_draw_callback(self, context):
    self.knife.draw(context)
    self.help_box.draw()
    if len(self.sketch):
        common_drawing.draw_polyline_from_points(context, self.sketch, (.3,.3,.3,.8), 2, "GL_LINE_SMOOTH")
        

class OPENDENTAL_OT_initiate_splint_margin(bpy.types.Operator):
    '''Places a bezier curve to be extruded around the boundaries of a splint'''
    bl_idname = 'opendental.initiate_splint_margin'
    bl_label = "Initiate Splint Margin"
    bl_options = {'REGISTER','UNDO'}
        
    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        return len(context.scene.odc_splints) > 0             

    def execute(self, context):
        
        sce=bpy.context.scene
        n = sce.odc_splint_index
        splint = sce.odc_splints[n]
        
        layers_copy = [layer for layer in context.scene.layers]
        context.scene.layers[0] = True
        
        model = splint.model
        Model = bpy.data.objects[model]

        L = odcutils.get_bbox_center(Model, world=True)
        #L = bpy.context.scene.cursor_location

        #bpy.ops.view3d.viewnumpad(type='TOP')
        bpy.ops.object.select_all(action='DESELECT')
        
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        #bpy.context.scene.cursor_location = L
        bpy.ops.curve.primitive_bezier_curve_add(view_align=True, enter_editmode=True, location=L)
        
        context.tool_settings.use_snap = True
        context.tool_settings.snap_target= 'ACTIVE'
        context.tool_settings.snap_element = 'FACE'
        context.tool_settings.proportional_edit = 'DISABLED'
        
        Margin =context.object
        Margin.name=splint.name + "_margin"
        Margin.parent = Model
        
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.curve.handle_type_set(type='AUTOMATIC')
        bpy.ops.curve.select_all(action='DESELECT')
        context.object.data.splines[0].bezier_points[1].select_control_point=True
        bpy.ops.curve.delete()
        bpy.ops.curve.select_all(action='SELECT')
        
        mod = Margin.modifiers.new('Wrap','SHRINKWRAP')
        mod.target = Model
        mod.offset = .75
        mod.use_keep_above_surface = True
        
        mod = Margin.modifiers.new('Smooth','SMOOTH')
        mod.iterations = 10
        
        splint.margin = Margin.name
        odcutils.layer_management(sce.odc_splints)
        
        for i, layer in enumerate(layers_copy):
            context.scene.layers[i] = layer
        context.scene.layers[4] = True
        return {'FINISHED'}
    
class OPENDENTAL_OT_survey_model(bpy.types.Operator):
    '''Calculates silhouette of object which surveys convexities AND concavities from the current view axis'''
    bl_idname = 'opendental.view_silhouette_survey'
    bl_label = "Survey Model From View"
    bl_options = {'REGISTER','UNDO'}
    
    world = bpy.props.BoolProperty(default = True, name = "Use world coordinate for calculation...almost always should be true.")
    smooth = bpy.props.BoolProperty(default = True, name = "Smooth the outline.  Slightly less acuurate in some situations but more accurate in others.  Default True for best results")

    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        C0 = context.space_data.type == 'VIEW_3D'
        C1 = context.object != None
        if C1:
            C2 = context.object.type == 'MESH'
        else:
            C2 = False
        return  C0 and C1 and C2

    def execute(self, context):
        tracking.trackUsage("D3Splint:SurveyModelView",None)
        settings = get_settings()
        dbg = settings.debug
        splint = context.scene.odc_splints[0]
        
        Model = bpy.data.objects.get(splint.model)
        if Model == None:
            self.report('ERROR','Need to set the model first')
            return {'CANCELLED'}
        
        loc = Model.location
        
        view = context.space_data.region_3d.view_rotation * Vector((0,0,1))
        odcutils.silouette_brute_force(context, Model, view, self.world, self.smooth, debug = dbg)
        
        mxT = Matrix.Translation(loc)
        mxR = context.space_data.region_3d.view_rotation.to_matrix().to_4x4()
        
        if "Insertion Axis" in bpy.data.objects:
            ob = bpy.data.objects.get('Insertion Axis')
        else:
            ob = bpy.data.objects.new('Insertion Axis', None)
            ob.empty_draw_type = 'SINGLE_ARROW'
            ob.empty_draw_size = 20
            context.scene.objects.link(ob)
        
        bpy.ops.object.select_all(action = 'DESELECT')
        ob.parent = Model
        ob.matrix_world = mxT * mxR
        context.scene.objects.active = ob
        ob.select = True
        
        context.scene.cursor_location = ob.location
        bpy.ops.view3d.view_center_cursor()
        bpy.ops.view3d.viewnumpad(type = 'FRONT')
        
        
        return {'FINISHED'}


class OPENDENTAL_OT_survey_model_axis(bpy.types.Operator):
    '''Calculates silhouette of of model from the defined insertion axis arrow object'''
    bl_idname = 'opendental.arrow_silhouette_survey'
    bl_label = "Survey Model From Axis"
    bl_options = {'REGISTER','UNDO'}
    
    world = bpy.props.BoolProperty(default = True, name = "Use world coordinate for calculation...almost always should be true.")
    smooth = bpy.props.BoolProperty(default = True, name = "Smooth the outline.  Slightly less acuurate in some situations but more accurate in others.  Default True for best results")

    @classmethod
    def poll(cls, context):
        
        return  True

    def execute(self, context):
        tracking.trackUsage("D3Splint:SurveyModelArrow",None)
        settings = get_settings()
        dbg = settings.debug
        splint = context.scene.odc_splints[0]
        
        Model = bpy.data.objects.get(splint.model)
        if Model == None:
            self.report('ERROR','Need to set the model first')
            return {'CANCELLED'}
        
        Axis = bpy.data.objects.get('Insertion Axis')
        if Axis == None:
            self.report('ERROR','Need to set survey from view first, then adjust axis arrow')
            return {'CANCELLED'}
        
        
        view = Axis.matrix_world.to_quaternion() * Vector((0,0,1))
        
        odcutils.silouette_brute_force(context, Model, view, self.world, self.smooth, debug = dbg)
        Axis.update_tag()
        context.scene.update()
        return {'FINISHED'}
    
    
class OPENDENTAL_OT_blockout_model(bpy.types.Operator):
    '''Calculates silhouette of object which surveys convexities AND concavities from the current view axis'''
    bl_idname = 'opendental.view_blockout_undercuts'
    bl_label = "Blockout Model From View"
    bl_options = {'REGISTER','UNDO'}
    
    world = bpy.props.BoolProperty(default = True, name = "Use world coordinate for calculation...almost always should be true.")
    smooth = bpy.props.BoolProperty(default = True, name = "Smooth the outline.  Slightly less acuurate in some situations but more accurate in others.  Default True for best results")

    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        C0 = context.space_data.type == 'VIEW_3D'
        C1 = context.object != None
        if C1:
            C2 = context.object.type == 'MESH'
        else:
            C2 = False
        return  C0 and C1 and C2

    def execute(self, context):
        settings = get_settings()
        dbg = settings.debug
        ob = context.object
        view = context.space_data.region_3d.view_rotation * Vector((0,0,1))
        bmesh_fns.remove_undercuts(context, ob, view, self.world, self.smooth)
        return {'FINISHED'}
          
class OPENDENTAL_OT_splint_bezier_model(bpy.types.Operator):
    '''Calc a Splint/Tray from a model and a curve'''
    bl_idname = "opendental.splint_from_curve"
    bl_label = "Calculate Bezier Splint"
    bl_options = {'REGISTER','UNDO'}

    #splint thickness
    thickness = bpy.props.FloatProperty(name="Thickness", description="Splint Thickness", default=2, min=.3, max=5, options={'ANIMATABLE'})
    
    #cleanup models afterward
    cleanup = bpy.props.BoolProperty(name="Cleanup", description="Apply Modifiers and cleanup models \n Do not use if planning bone support", default=True)
    
    @classmethod
    def poll(cls, context):
        if len(context.scene.odc_splints):
            settings = get_settings()
            dbg = settings.debug
            b = settings.behavior
            behave_mode = settings.behavior_modes[int(b)]
            if  behave_mode in {'ACTIVE','ACTIVE_SELECTED'} and dbg > 2:
                obs =  context.selected_objects
                cond_1 = len(obs) == 2
                ob_types = set([obs[0].type, obs[1].type])
                cond_2 = ('MESH' in ob_types) and ('CURVE' in ob_types)
                return cond_1 and cond_2
                
            else: #we know there are splints..we will determine active one later
                return context.mode == 'OBJECT'
        else:
            return False
            
        
    
    def execute(self, context):
        
            
        settings = get_settings()
        dbg = settings.debug
        
        #first, ensure all models are present and not deleted etc
        odcutils.scene_verification(context.scene, debug = dbg)      
        b = settings.behavior
        behave_mode = settings.behavior_modes[int(b)]
        
        settings = get_settings()
        dbg = settings.debug    
        [ob_sets, tool_sets, space_sets] = odcutils.scene_preserv(context, debug=dbg)
        
        #this is sneaky way of letting me test different things
        if behave_mode in {'ACTIVE','ACTIVE_SELECTED'} and dbg > 2:
            obs = context.selected_objects
            if obs[0].type == 'CURVE':
                model = obs[1]
                margin = obs[0]
            else:
                model = obs[0]
                margin = obs[1]
        
                exclude = ['name','teeth','implants','tooth_string','implant_string']
                splint = odcutils.active_odc_item_candidate(context.scene.odc_splints, obs[0], exclude)
        
        else:
            j = context.scene.odc_splint_index
            splint =context.scene.odc_splints[j]
            if splint.model in bpy.data.objects and splint.margin in bpy.data.objects:
                model = bpy.data.objects[splint.model]
                margin = bpy.data.objects[splint.margin]
            else:
                print('whoopsie...margin and model not defined or something is wrong')
                return {'CANCELLED'}
        
        
        layers_copy = [layer for layer in context.scene.layers]
        context.scene.layers[0] = True
        
        z = Vector((0,0,1))
        vrot= context.space_data.region_3d.view_rotation
        Z = vrot*z
        
        [Splint, Falloff, Refractory] = full_arch_methods.splint_bezier_step_1(context, model, margin, Z, self.thickness, debug=dbg)

        splint.splint = Splint.name #that's a pretty funny statement.
        
        if splint.bone and splint.bone in bpy.data.objects:
            mod = Splint.modifiers['Bone']
            mod.target = bpy.data.objects[splint.bone]
        
        if self.cleanup:
            context.scene.objects.active = Splint
            Splint.select = True
            
            for mod in Splint.modifiers:
                
                if mod.name != 'Bone':
                    if mod.type in {'BOOLEAN', 'SHRINKWRAP'}:
                        if mod.type == 'BOOLEAN' and mod.object:
                            bpy.ops.object.modifier_apply(modifier=mod.name)
                        elif mod.type == 'SHRINKWRAP' and mod.target:
                            bpy.ops.object.modifier_apply(modifier=mod.name)
                    else:
                        bpy.ops.object.modifier_apply(modifier=mod.name)

            context.scene.objects.unlink(Falloff)    
            Falloff.user_clear()
            bpy.data.objects.remove(Falloff)
            
            context.scene.objects.unlink(Refractory)
            Refractory.user_clear()
            bpy.data.objects.remove(Refractory)
            odcutils.scene_reconstruct(context, ob_sets, tool_sets, space_sets, debug=dbg)  
            
        else:
            odcutils.scene_reconstruct(context, ob_sets, tool_sets, space_sets, debug=dbg)  
            Falloff.hide = True
            Refractory.hide = True
                
        for i, layer in enumerate(layers_copy):
            context.scene.layers[i] = layer
        context.scene.layers[10] = True
          
        odcutils.material_management(context, context.scene.odc_splints, debug = dbg)
        odcutils.layer_management(context.scene.odc_splints, debug = dbg)   
        return {'FINISHED'}

class OPENDENTAL_OT_splint_margin_trim(bpy.types.Operator):
    '''Cut a model with the margin line'''
    bl_idname = "opendental.splint_model_trim"
    bl_label = "Splint Trim Margin"
    bl_options = {'REGISTER','UNDO'}

    smooth_iterations= bpy.props.IntProperty(name = 'Smooth', default = 5)
    @classmethod
    def poll(cls, context):
        return True
            
        
    
    def execute(self, context):
            
        settings = get_settings()
        dbg = settings.debug
        
        #first, ensure all models are present and not deleted etc
        odcutils.scene_verification(context.scene, debug = dbg)      
        b = settings.behavior
        behave_mode = settings.behavior_modes[int(b)]
        
        settings = get_settings()
        dbg = settings.debug    
        [ob_sets, tool_sets, space_sets] = odcutils.scene_preserv(context, debug=dbg)
        
        
        j = context.scene.odc_splint_index
        splint =context.scene.odc_splints[j]
        if splint.model in bpy.data.objects and splint.margin in bpy.data.objects:
            model = bpy.data.objects[splint.model]
            margin = bpy.data.objects[splint.margin]
        else:
            print('whoopsie...margin and model not defined or something is wrong')
            return {'CANCELLED'}
        
        new_me = margin.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme = bmesh.new()
        bme.from_mesh(new_me)
        new_ob = bpy.data.objects.new('Margin Cut', new_me)
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        orig_verts = [v for v in bme.verts]
        orig_edges = [ed for ed in  bme.edges]
        gdict = bmesh.ops.extrude_edge_only(bme, edges = bme.edges[:])
        bme.edges.ensure_lookup_table()
        new_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
        
        
        gdict = bmesh.ops.extrude_edge_only(bme, edges = new_edges)
        bme.edges.ensure_lookup_table()
        newer_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
        
        
        offset_bmesh_edge_loop(bme, [ed.index for ed in orig_edges], Vector((0,0,1)), -1)
        offset_bmesh_edge_loop(bme, [ed.index for ed in newer_edges], Vector((0,0,1)), 1)
        
        
        smooth_verts = [v for v in bme.verts if v not in orig_verts]
        for i in range(0,self.smooth_iterations):
            bmesh.ops.smooth_vert(bme, verts = smooth_verts, factor = .5)
        
        new_ob.matrix_world = margin.matrix_world
        bme.to_mesh(new_me)
        bme.free()
        context.scene.objects.link(new_ob)
        return {'FINISHED'}
    
          
class OPENDENTAL_OT_splint_margin_detail(bpy.types.Operator):
    '''Use dyntopo sculpt to add/remove detail at margin'''
    bl_idname = "opendental.splint_margin_detail"
    bl_label = "Splint Margin Detail Bezier Splint"
    bl_options = {'REGISTER','UNDO'}

    #splint thickness
    detail = bpy.props.FloatProperty(name="Detail", description="Edge length detail", default=.8, min=.025, max=1, options={'ANIMATABLE'})
    
    
    @classmethod
    def poll(cls, context):
        return True
            
    def execute(self, context):
        
            
        settings = get_settings()
        dbg = settings.debug
        
        
        #first, ensure all models are present and not deleted etc
        odcutils.scene_verification(context.scene, debug = dbg)      
        b = settings.behavior
        behave_mode = settings.behavior_modes[int(b)]
        
        settings = get_settings()
        dbg = settings.debug    
        
        j = context.scene.odc_splint_index
        splint =context.scene.odc_splints[j]
        if splint.model in bpy.data.objects and splint.margin in bpy.data.objects:
            model = bpy.data.objects[splint.model]
            margin = bpy.data.objects[splint.margin]
        else:
            print('whoopsie...margin and model not defined or something is wrong')
            return {'CANCELLED'}
        
        for ob in context.scene.objects:
            ob.select = False
        
        
        bme = bmesh.new()
        bme.from_mesh(model.data)
        bme.normal_update()
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        bvh = BVHTree.FromBMesh(bme)
        
        model.hide = False
        model.select = True
        context.scene.objects.active = model
        
        margin_mesh = margin.to_mesh(context.scene, True, 'PREVIEW')
        mx = margin.matrix_world
        mx2 = model.matrix_world
        
        imx = mx2.inverted()
        
        #try to do it in object space?  But what about 
        margin_path = [imx * mx * v.co for v in margin_mesh.vertices]
        

        
        margin_stroke, stroke_eds = space_evenly_on_path(margin_path, [(0,1),(1,2)], 200)
        
        margin_snaps = [bvh.find_nearest(v) for v in margin_stroke]
        #find_nearest returns (location, normal, index, distance)
        
        
        #new_bme = bmesh.new()
        #new_bme.verts.ensure_lookup_table()
        #new_verts = []
        #for co in margin_stroke:
        #    new_bme.verts.new(co)  
        #new_me = bpy.data.meshes.new('Sculpt Stroke')
        #new_ob = bpy.data.objects.new('Sculpt Stroke', new_me)
        #new_bme.to_mesh(new_me)
        #context.scene.objects.link(new_ob)
        #new_bme.free()
        
            
        bpy.ops.object.mode_set(mode = 'SCULPT')
        if not model.use_dynamic_topology_sculpting:
            bpy.ops.sculpt.dynamic_topology_toggle()
        
        scene = context.scene
        paint_settings = scene.tool_settings.unified_paint_settings
        paint_settings.use_locked_size = True
        paint_settings.unprojected_radius = 1
        brush = bpy.data.brushes['Clay']
        scene.tool_settings.sculpt.brush = brush
        scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
        scene.tool_settings.sculpt.constant_detail = self.detail * 100  #play with this value
        
        brush.strength = 0.0  #we only want to retopologize, not actually sculpt anything
        
        #brush.stroke_method = 'SPACE' 

        
        screen = bpy.context.window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for reg in area.regions:
                    if reg.type == 'WINDOW':
                        break
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        break    
                break
        
        override = bpy.context.copy()
        override['area'] = area
        override['region'] = reg
        override['space_data'] = space
        override['region_data'] = space.region_3d
        override['active_object'] = model
        override['object'] = model
        override['sculpt_object'] = model
        
        no_mx = model.matrix_world.inverted().transposed().to_3x3()
        for i, co in enumerate(margin_stroke):
            
            snap = margin_snaps[i]
            
            f = bme.faces[snap[2]]
    
            Z = no_mx * f.normal
            Y = no_mx * (f.verts[0].co - co)
            Y.normalize()
            X = Y.cross(Z)
            
            #rotation matrix from principal axes
            T = Matrix.Identity(3)  #make the columns of matrix U, V, W
            T[0][0], T[0][1], T[0][2]  = X[0] ,Y[0],  Z[0]
            T[1][0], T[1][1], T[1][2]  = X[1], Y[1],  Z[1]
            T[2][0] ,T[2][1], T[2][2]  = X[2], Y[2],  Z[2]

            Rotation_Matrix = T.to_4x4()
            
            space.region_3d.view_rotation = Rotation_Matrix.to_quaternion()
            space.region_3d.view_location = mx2 * co
            mouse = view3d_utils.location_3d_to_region_2d(reg, space.region_3d, mx2 * co)
            stroke = [{"name": "my_stroke",
                        "mouse" : (mouse[0], mouse[1]),
                        "pen_flip" : False,
                        "is_start": True,
                        "location": (co[0], co[1], co[2]),
                        "pressure": 1,
                        "size" : 20,
                        "time": 1},
                      
                       {"name": "my_stroke",
                        "mouse" : (mouse[0], mouse[1]),
                        "pen_flip" : False,
                        "is_start": False,
                        "location": (co[0], co[1], co[2]),
                        "pressure": 1,
                        "size" : 20,
                        "time": 1}]

            bpy.ops.sculpt.brush_stroke(override, stroke=stroke, mode='NORMAL', ignore_background_click=False)
        
        
        #for view in ['LEFT','RIGHT','TOP','FRONT', 'BACK']:
        #    bpy.ops.view3d.viewnumpad(type = view)
        #    
            
        #    bpy_stroke = []
        #    for i, co in enumerate(margin_stroke):
        
        #       mouse = view3d_utils.location_3d_to_region_2d(reg, space.region_3d, mx2 * co)
        #     
        #       if mouse[0] < 0 or mouse[1] < 0:  #TODO, what about outside the area?  
        #           space.region_3d.view_location = mx2 * co
        #           space.region_3d.update()
        #           mouse = view3d_utils.location_3d_to_region_2d(reg, space.region_3d, mx2 * co)
                
        #        if i == 0:
        #            start = True
        #        else:
        #            start = False
        #        ele = {"name": "my_stroke",
        #                "mouse" : (mouse[0], mouse[1]),
        #                "pen_flip" : False,
        #                "is_start": start,
        #                "location": (co[0], co[1], co[2]),
        #                "pressure": 1,
        #                "size" : 20,
        #                "time": 1}
        #        
        #        bpy_stroke.append(ele)
        #    
                
        #    bpy.ops.sculpt.brush_stroke(override, stroke=bpy_stroke, mode='NORMAL', ignore_background_click=False)
        
        bme.free()
        del bvh
        bpy.ops.object.mode_set(mode = 'OBJECT')
        return {'FINISHED'}

class OPENDENTAL_OT_splint_add_rim(bpy.types.Operator):
    """Create Meta Wax Rim previously defined maxillary and mandibular curves"""
    bl_idname = "opendental.splint_rim_from_dual_curves"
    bl_label = "Create Splint Rim "
    bl_options = {'REGISTER', 'UNDO'}
    
    
    meta_type = EnumProperty(name = 'Meta Type', items = [('CUBE','CUBE','CUBE'), ('ELLIPSOID', 'ELLIPSOID','ELLIPSOID')], default = 'CUBE')
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        MaxCurve = bpy.data.objects.get('Occlusal Curve Max')
        if MaxCurve == None:
            self.report({'ERROR'}, "Need to mark maxillary buccal cusps")
            return {'CANCELLED'}
        
        MandCurve = bpy.data.objects.get('Occlusal Curve Mand')
        if MandCurve == None:
            self.report({'ERROR'}, "Need to mark mandibular lingual cusps")
            return {'CANCELLED'}
        
        shell = bpy.data.objects.get('Splint Shell')
        if not shell:
            self.report({'ERROR'}, "Need to calculate splint shell first")
            return {'CANCELLED'}
        
        tracking.trackUsage("D3Splint:MetaWaxRim",None)
        
        mx_shell = shell.matrix_world
        imx_shell = mx_shell.inverted()
        
        max_crv_data = MaxCurve.data
        mx_max = MaxCurve.matrix_world
        imx_max = mx_max.inverted()
        
        
        mand_crv_data = MandCurve.data
        mx_mand = MandCurve.matrix_world
        imx_mand = mx_mand.inverted()
        
        
        print('got curve object')
        
        meta_data = bpy.data.metaballs.new('Splint Wax Rim')
        meta_obj = bpy.data.objects.new('Meta Surface', meta_data)
        meta_data.resolution = .8
        meta_data.render_resolution = .8
        context.scene.objects.link(meta_obj)
        
        #get world path of the maxillary curve
        me_max = MaxCurve.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme_max = bmesh.new()
        bme_max.from_mesh(me_max)
        bme_max.verts.ensure_lookup_table()
        bme_max.edges.ensure_lookup_table()
        loops = edge_loops_from_bmedges(bme_max, [ed.index for ed in bme_max.edges])
        vs0 = [mx_max * bme_max.verts[i].co for i in loops[0]]
        vs_even_max, eds0 = space_evenly_on_path(vs0, [(0,1),(1,2)], 60)
        
        #get world path of the mandibular curve
        me_mand = MandCurve.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme_mand = bmesh.new()
        bme_mand.from_mesh(me_mand)
        bme_mand.verts.ensure_lookup_table()
        bme_mand.edges.ensure_lookup_table()
        loops = edge_loops_from_bmedges(bme_mand, [ed.index for ed in bme_mand.edges])
        vs0 = [mx_mand * bme_mand.verts[i].co for i in loops[0]]
        vs_even_mand, eds0 = space_evenly_on_path(vs0, [(0,1),(1,2)], 60)
        
        
        #check for tip to tail
        if (vs_even_mand[0] - vs_even_max[0]).length > (vs_even_mand[0] - vs_even_max[-1]).length:
            print('reversing the mandibular curve')
            vs_even_mand.reverse()
        
        Z = Vector((0,0,1))
        
            
        for i in range(1,len(vs_even_max)-1):
            
            #use maxilary curve for estimattino
            
            v0_0 = vs_even_max[i]
            v0_p1 = vs_even_max[i+1]
            v0_m1 = vs_even_max[i-1]

            v0_mand = vs_even_mand[i]
            center = .5 *  v0_0 + 0.5 * v0_mand
            
            size_z = max(1, abs(v0_0[2] - v0_mand[2]))
            size_y = ((v0_0[0] - v0_mand[0])**2 + (v0_0[1] - v0_mand[1])**2)**.5
            size_y = max(3, size_y)
            
            
            X = v0_p1 - v0_m1
            X.normalize()
            
            Y = Z.cross(X)
            X_c = Y.cross(Z) #X corrected
            
            T = Matrix.Identity(3)
            T.col[0] = X_c
            T.col[1] = Y
            T.col[2] = Z
            quat = T.to_quaternion()
            
                        
            mb = meta_data.elements.new(type = self.meta_type)
            mb.size_y = .5 * size_y
            mb.size_z = .5 * size_z
            mb.size_x = 1.5
            mb.rotation = quat
            mb.stiffness = 2
            mb.co = center
            
        context.scene.update()
        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        new_ob = bpy.data.objects.new('Flat Plane', me)
        context.scene.objects.link(new_ob)

        context.scene.objects.unlink(meta_obj)
        bpy.data.objects.remove(meta_obj)
        bpy.data.metaballs.remove(meta_data)
        
        mat = bpy.data.materials.get("Splint Material")
        if mat is None:
            # create material
            mat = bpy.data.materials.new(name="Splint Material")
            mat.diffuse_color = Color((0.5, .1, .6))
        
        new_ob.data.materials.append(mat)
        
        bme_max.free()
        bme_mand.free()
        #todo remove/delete to_mesh mesh
  
        return {'FINISHED'}

    
    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)
    
    
class OPENDENTAL_OT_splint_add_rim_curve(bpy.types.Operator):
    """Create Meta Wax Rim from selected bezier curve"""
    bl_idname = "opendental.splint_rim_from_curve"
    bl_label = "Create Rim from Curve"
    bl_options = {'REGISTER', 'UNDO'}
    
    posterior_width = FloatProperty(default = 12, description = 'Width of posterior rim')
    anterior_width = FloatProperty(default = 8, description = 'Width of anterior rim')
    
    meta_type = EnumProperty(name = 'Meta Type', items = [('CUBE','CUBE','CUBE'), ('ELLIPSOID', 'ELLIPSOID','ELLIPSOID')], default = 'CUBE')
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        splint = context.scene.odc_splints[0]
        occlusal = splint.name + "_occlusal"
        
        if occlusal not in context.scene.objects:
            self.report({'ERROR'}, "Need to mark occlusal cusps first")
            return {'CANCELLED'}
        
        shell = bpy.data.objects.get('Splint Shell')
        if not shell:
            self.report({'ERROR'}, "Need to calculate splint shell first")
            return {'CANCELLED'}
        
        tracking.trackUsage("D3Splint:RimFromCurve",None)
        
        mx_shell = shell.matrix_world
        imx_shell = mx_shell.inverted()
        
        crv_obj = bpy.data.objects.get(occlusal)
        crv_data = crv_obj.data
        mx = crv_obj.matrix_world
        imx = mx.inverted()
        
        meta_data = bpy.data.metaballs.new('Splint Wax Rim')
        meta_obj = bpy.data.objects.new('Meta Surface', meta_data)
        meta_data.resolution = .8
        meta_data.render_resolution = .8
        context.scene.objects.link(meta_obj)
        
        me = crv_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme = bmesh.new()
        bme.from_mesh(me)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in bme.edges])
            
        
        vs0 = [bme.verts[i].co for i in loops[0]]
        
        
        vs_even_0, eds0 = space_evenly_on_path(vs0, [(0,1),(1,2)], 60)
        
        
        Z = mx.inverted().to_3x3() * Vector((0,0,1))
        Z.normalize()
            
        for i in range(1,len(vs_even_0)-1):
            
            
            blend = -abs((i-30)/30)+1
            
            v0_0 = vs_even_0[i]
            v0_p1 = vs_even_0[i+1]
            v0_m1 = vs_even_0[i-1]

            
           
            
            X = v0_p1 - v0_m1
            X.normalize()
            
            Y = Z.cross(X)
            X_c = Y.cross(Z) #X corrected
            
            T = Matrix.Identity(3)
            T.col[0] = X_c
            T.col[1] = Y
            T.col[2] = Z
            quat = T.to_quaternion()
            
            ray_orig = mx * v0_0
            ray_target = mx * v0_0 + 5 * Z
            ok, loc, no, face_ind = shell.ray_cast(imx_shell * ray_orig, imx_shell * ray_target - imx_shell*ray_orig)
            
            if ok:
                zvec = imx * mx_shell * loc - v0_0
                size_z = .4 * zvec.length
                
            else:
                size_z = .4 * 2
            
            mb = meta_data.elements.new(type = self.meta_type)
            mb.size_y = .5 *  (blend*self.anterior_width + (1-blend)*self.posterior_width)
            mb.size_z = size_z
            mb.size_x = 1.5
            mb.rotation = quat
            mb.stiffness = 2
            mb.co = v0_0 + .5 * size_z * Z
            
        meta_obj.matrix_world = mx
        
        

        context.scene.update()
        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        new_ob = bpy.data.objects.new('Flat Plane', me)
        context.scene.objects.link(new_ob)
        new_ob.matrix_world = mx

        context.scene.objects.unlink(meta_obj)
        bpy.data.objects.remove(meta_obj)
        bpy.data.metaballs.remove(meta_data)
        
        mat = bpy.data.materials.get("Splint Material")
        if mat is None:
            # create material
            mat = bpy.data.materials.new(name="Splint Material")
            mat.diffuse_color = Color((0.5, .1, .6))
        
        new_ob.data.materials.append(mat)
        
        bme.free()
        #todo remove/delete to_mesh mesh
  
        return {'FINISHED'}

    
    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)

class OPENDENTAL_OT_splint_trim_model(bpy.types.Operator):
    """Trim model from buccal curve"""
    bl_idname = "opendental.splint_trim_from_curve"
    bl_label = "Trim Splint Model"
    bl_options = {'REGISTER', 'UNDO'}
    

    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        splint = context.scene.odc_splints[0]
        buccal = splint.name + "_buccal"
        model = context.scene.odc_splints[0].model
        Model = bpy.data.objects.get(model)
        if buccal not in context.scene.objects:
            self.report({'ERROR'}, "Need to mark buccal splint limits first")
        
        tracking.trackUsage("D3Splint:TrimModel",None)
        
        crv_obj = bpy.data.objects.get(buccal)
        crv_data = crv_obj.data
        crv_data.splines[0].use_cyclic_u = True
        context.scene.update()
        
        mx = crv_obj.matrix_world
        
        me = crv_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme = bmesh.new()
        bme.from_mesh(me)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in bme.edges])
            
        vs0 = [bme.verts[i].co for i in loops[0]]
        vs_even_0, eds0 = space_evenly_on_path(vs0, [(0,1),(1,0)], 60)
        
        cut_bme = bmesh.new()
        verts = [cut_bme.verts.new(co) for co in vs_even_0]
        eds = [cut_bme.edges.new((verts[i],verts[j])) for (i,j) in eds0]    
        
        cut_bme.verts.ensure_lookup_table()
        cut_bme.edges.ensure_lookup_table()
        
        gdict = bmesh.ops.extrude_edge_only(cut_bme, edges = eds)
        cut_bme.edges.ensure_lookup_table()
        new_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
        
        
        Z = mx.inverted().to_3x3() * Vector((0,0,1))
        offset_bmesh_edge_loop(cut_bme, [ed.index for ed in new_edges],Z, -4)
        
        loops = edge_loops_from_bmedges(cut_bme, [ed.index for ed in eds])
        new_f = loops[0]
        new_f.pop()              
        f = cut_bme.faces.new([cut_bme.verts[i] for i in new_f])
        
        bmesh.ops.recalc_face_normals(cut_bme, faces = cut_bme.faces[:])
        
        bmesh.ops.triangulate(cut_bme, faces = [f])
        
        cut_bme.faces.ensure_lookup_table()
        
        f_test = cut_bme.faces[0]
        z =  mx.to_3x3() * f_test.normal
        
        if z.dot(Vector((0,0,1))) < 0:
            print('reversing faces')
            bmesh.ops.reverse_faces(bme, faces = bme.faces[:])
        
        trim_ob = bpy.data.objects.new('Trim Surface', me)    
        trim_ob.matrix_world = mx
        context.scene.objects.link(trim_ob)
        cut_bme.to_mesh(me)
        
        
        bvh = BVHTree.FromBMesh(cut_bme)
        
        
        trimmed_bme = bmesh.new()
        trimmed_bme.from_mesh(Model.data)
        trimmed_bme.verts.ensure_lookup_table()
        
        
        to_delete = []
        mx2 = Model.matrix_world
        imx = mx.inverted()
        Z = mx.inverted().to_3x3() * Vector((0,0,1))
        for v in trimmed_bme.verts:
            a = imx * mx2 * v.co
            
            res = bvh.ray_cast(a, Z, 20)
            if res[0] == None:
                v.co = Vector((0,0,0))
                to_delete.append(v)
        
        #faces_to_delete = []
        #for f in trimmed_bme.faces:
        #    if all([v in to_delete for v in f.verts]):
        #        faces_to_delete.append(f)
        
        #edges_to_delete = []
        #for ed in trimmed_bme.edges:
        #    if all([v in to_delete for v in ed.verts]):
        #        edges_to_delete.append(ed)
            
        print('deleting %i verts' % len(to_delete))
        
        
        bmesh.ops.delete(trimmed_bme, geom = to_delete, context = 1)
  
        trimmed_bme.verts.ensure_lookup_table()
        trimmed_bme.faces.ensure_lookup_table()
        trimmed_bme.edges.ensure_lookup_table()
        trimmed_bme.verts.index_update()
        trimmed_bme.edges.index_update()
        trimmed_bme.faces.index_update()
        
        to_delete = []
        for v in trimmed_bme.verts:
            if len(v.link_edges) < 2:
                to_delete.append(v)
                
        print('deleting %i loose verts' % len(to_delete))
        bmesh.ops.delete(trimmed_bme, geom = to_delete, context = 1)
        trimmed_bme.verts.ensure_lookup_table()
        trimmed_bme.faces.ensure_lookup_table()
        trimmed_bme.edges.ensure_lookup_table()
        trimmed_bme.verts.index_update()
        trimmed_bme.edges.index_update()
        trimmed_bme.faces.index_update()
        
                
        eds = [ed for ed in trimmed_bme.edges if len(ed.link_faces) == 1]
        
        gdict = bmesh.ops.extrude_edge_only(trimmed_bme, edges = eds)
        bme.edges.ensure_lookup_table()
        new_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
        trimmed_bme.verts.ensure_lookup_table()
        trimmed_bme.edges.ensure_lookup_table()
        trimmed_bme.verts.index_update()
        trimmed_bme.edges.index_update()
        trimmed_bme.faces.index_update()
        
        loops = edge_loops_from_bmedges(trimmed_bme, [ed.index for ed in new_edges])
        print('there are %i loops' % len(loops))
        for loop in loops:
            if len(loop) < 50: continue
            for vi in loop:
                v = trimmed_bme.verts[vi]
                if not v.is_valid:
                    print('invalid vert')
                    continue
                a = imx * mx2 * trimmed_bme.verts[vi].co
                res = bvh.ray_cast(a, Z, 5)
                if res[0] != None:
                    v.co = res[0]
        
        trimmed_model = bpy.data.meshes.new('Trimmed_Model')
        trimmed_obj = bpy.data.objects.new('Trimmed_Model', trimmed_model)
        trimmed_bme.to_mesh(trimmed_model)
        trimmed_obj.matrix_world = mx2
        context.scene.objects.link(trimmed_obj)
                    
        trimmed_bme.verts.ensure_lookup_table()
        for i in range(10):        
            gdict = bmesh.ops.extrude_edge_only(trimmed_bme, edges = new_edges)
            trimmed_bme.edges.ensure_lookup_table()
            trimmed_bme.verts.ensure_lookup_table()
            new_verts = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
            new_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
            for v in new_verts:
                v.co += .4 * Vector((0,0,1))
        
        loops = edge_loops_from_bmedges(trimmed_bme, [ed.index for ed in new_edges])
        print('there are %i loops' % len(loops))
        for loop in loops:
            if loop[0] != loop[-1]:continue
            loop.pop()
            f = [trimmed_bme.verts[i] for i in loop]
            trimmed_bme.faces.new(f)
            
        bmesh.ops.recalc_face_normals(trimmed_bme,faces = trimmed_bme.faces[:])
            
            
                    
        based_model = bpy.data.meshes.new('Based_Model')
        based_obj = bpy.data.objects.new('Based_Model', based_model)
        trimmed_bme.to_mesh(based_model)
        based_obj.matrix_world = mx2
        context.scene.objects.link(based_obj)
        Model.hide = True
        trim_ob.hide = True
        
        bme.free()
        cut_bme.free()
        trimmed_bme.free()
        #todo remove/delete to_mesh mesh
  
        return {'FINISHED'}
    
class OPENDENTAL_OT_splint_mount_on_articulator(bpy.types.Operator):
    """Mount models on articulator"""
    bl_idname = "opendental.splint_mount_articulator"
    bl_label = "Mount in Articulator"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        opposing = context.scene.odc_splints[0].opposing
        Model = bpy.data.objects.get(opposing)
        
        if not Model:
            self.report({'ERROR'},"Please use Add Arcon Articulator function")
            return {'CANCELLED'}
        
        Articulator = bpy.data.objects.get('Articulator')
        if Articulator == None:
            self.report({'ERROR'},"Please use Add Arcon Articulator function")
            return {'CANCELLED'}
        
        tracking.trackUsage("D3Splint:MountOnArticulator",None)
            
        cons = Model.constraints.new(type = 'CHILD_OF')
        cons.target = Articulator
        cons.subtarget = 'Mandibular Bow'
        
        mx = Articulator.matrix_world * Articulator.pose.bones['Mandibular Bow'].matrix
        cons.inverse_matrix = mx.inverted()
        
        #write the lower jaw BVH to cache for fast ray_casting
        bme = bmesh.new()
        bme.from_mesh(Model.data)    
        bvh = BVHTree.FromBMesh(bme)
        splint_cache.write_mesh_cache(Model, bme, bvh)
        
        return {'FINISHED'}


def occlusal_surface_frame_change(scene):

    if not len(scene.odc_splints): return
    splint = scene.odc_splints[0]
    #TODO...get the models better?
    plane = bpy.data.objects.get('Occlusal Plane')
    jaw = bpy.data.objects.get(splint.opposing)
    
    if plane == None: return
    if jaw == None: return
    
    mx_jaw = jaw.matrix_world
    mx_pln = plane.matrix_world
    imx_j = mx_jaw.inverted()
    imx_p = mx_pln.inverted()
    
    bvh = splint_cache.mesh_cache['bvh']
    
    for v in plane.data.vertices:
        
        a = mx_pln * v.co
        b = mx_pln * (v.co + Vector((0,0,10)))
        
        hit = bvh.ray_cast(imx_j * a, imx_j * b - imx_j * a)
        
        if hit[0]:
            v.co = imx_p * mx_jaw * hit[0]
        
class OPENDENTAL_OT_splint_join_rim(bpy.types.Operator):
    """Join Rim to Shell"""
    bl_idname = "opendental.splint_join_rim"
    bl_label = "Join Shell to Rim"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        
        Shell = bpy.data.objects.get('Splint Shell')
        Rim = bpy.data.objects.get('Flat Plane')
        
        if Shell == None:
            self.report({'ERROR'}, 'Need to calculate splint shell first')
        
        if Rim == None:
            self.report({'ERROR'}, 'Need to calculate rim first')
            
        tracking.trackUsage("D3Splint:JoinRim",None)
        bool_mod = Shell.modifiers.new('Join Rim', type = 'BOOLEAN')
        bool_mod.operation = 'UNION'
        bool_mod.object = Rim
        Rim.hide = True
         
        return {'FINISHED'}


class OPENDENTAL_OT_splint_subtract_surface(bpy.types.Operator):
    """Subtract functions surface from Shell"""
    bl_idname = "opendental.splint_subtract_surface"
    bl_label = "Subtract Surface from Shell"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        
        Shell = bpy.data.objects.get('Splint Shell')
        Plane = bpy.data.objects.get('Occlusal Plane')
        
        if Shell == None:
            self.report({'ERROR'}, 'Need to calculate splint shell first')
        
        if Plane == None:
            self.report({'ERROR'}, 'Need to generate functional surface first')
            
        tracking.trackUsage("D3Splint:SubtractSurface",None)
        bool_mod = Shell.modifiers.new('Join Rim', type = 'BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = Plane
        Plane.hide = True 
        return {'FINISHED'}
    
class OPENDENTAL_OT_splint_finish_booleans(bpy.types.Operator):
    """Finish the Booleans"""
    bl_idname = "opendental.splint_finish_booleans"
    bl_label = "Finalize the Splint"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        
        Shell = bpy.data.objects.get('Splint Shell')
        Plane = bpy.data.objects.get('Trim Surface')
        Base = bpy.data.objects.get('Based_Model')
        Passive = bpy.data.objects.get('Passive Spacer')
        
        if Shell == None:
            self.report({'ERROR'}, 'Need to calculate splint shell first')
            return {'CANCELLED'}
        if Plane == None:
            self.report({'ERROR'}, 'Need to generate functional surface first')
            return {'CANCELLED'}
        if Base == None:
            self.report({'ERROR'}, 'Need to trim model first')
            return {'CANCELLED'}
        if Passive == None:
            self.report({'ERROR'}, 'Need to make passive spacer first')    
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode = 'OBJECT')
        
        tracking.trackUsage("D3Splint:FinishBoolean",None)    
        Shell.hide = False
        bpy.ops.object.select_all(action = 'DESELECT')
        Shell.select = True
        context.scene.objects.active = Shell
        for mod in Shell.modifiers:
            bpy.ops.object.modifier_apply(modifier = mod.name)
            
        Plane.location += Vector((0,0,.05))
        thick = Plane.modifiers.new('Thicken', 'SOLIDIFY')
        thick.offset = 1
        thick.thickness = 4
        
        bool_mod = Shell.modifiers.new('Trim Edge ', type = 'BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        #bool_mod.solver = 'CARVE'
        bool_mod.object = Plane
        Plane.hide = True
        
        bool_mod = Shell.modifiers.new('Remove Teeth', type = 'BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = Base
        Base.hide = True 
        
        bool_mod = Shell.modifiers.new('Trim Edge ', type = 'BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = Passive
        Passive.hide = True 
        
        
        return {'FINISHED'}
    
        
class OPENDENTAL_OT_splint_create_functional_surface(bpy.types.Operator):
    """Create functional surface using envelope of motion on articulator"""
    bl_idname = "opendental.splint_animate_articulator"
    bl_label = "Animate on Articulator"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    resolution = IntProperty(name = 'Resolution', descriptinon = "Number of setps along the condyle to create surface.  10-40 is reasonable.  Larger = Slower", default = 20)
    range_of_motion = FloatProperty(name = 'Range of Motion', min = 0.2, max = 1.0, description = 'Percent of condylar path to animate, typically .2 to 1.0', default = 0.8)
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        splint = context.scene.odc_splints[0]
        Model = bpy.data.objects.get(splint.opposing)
        
        if Model == None:
            self.resport({'ERROR'}, 'No Opposing Model')
            return {'CANCELLED'}
        
        if not splint_cache.is_object_valid(Model):
            splint_cache.clear_mesh_cache()
            bme = bmesh.new()
            
            bme.from_mesh(Model.data)    
            bme.faces.ensure_lookup_table()
            bme.verts.ensure_lookup_table()
            
            bvh = BVHTree.FromBMesh(bme)
            splint_cache.write_mesh_cache(Model, bme, bvh)
        
        tracking.trackUsage("D3Splint:CreateSurface",None)
        context.scene.frame_current = -1
        context.scene.frame_current = 0
        
        print('adding the handler!')
        bpy.app.handlers.frame_change_pre.append(occlusal_surface_frame_change)
        bpy.ops.screen.animation_play()
        
        return {'FINISHED'}
    

class OPENDENTAL_OT_splint_stop_functional_surface(bpy.types.Operator):
    """Create functional surface using envelope of motion on articulator"""
    bl_idname = "opendental.splint_stop_articulator"
    bl_label = "Stop Occlusal Surface"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        tracking.trackUsage("D3Splint:StopFunctionalSurface",None)
        print('removing the handler')
        bpy.app.handlers.frame_change_pre.remove(occlusal_surface_frame_change)
        
        
        return {'FINISHED'}

class OPENDENTAL_OT_meta_splint_surface(bpy.types.Operator):
    """Create Offset Surface from mesh"""
    bl_idname = "opendental.splint_offset_shell"
    bl_label = "Create Splint Outer Surface"
    bl_options = {'REGISTER', 'UNDO'}
    
    radius = FloatProperty(default = 2.5, description = 'Thickness of splint')
    finalize = BoolProperty(default = False, description = 'Will convert meta to mesh and remove meta object')
    resolution = FloatProperty(default = .8, description = '0.5 to 1.5 seems to be good')
    n_verts = IntProperty(default = 1000)
    @classmethod
    def poll(cls, context):
        if "Trimmed_Model" in bpy.data.objects:
            return True
        else:
            return False
        
    def execute(self, context):
        self.bme = bmesh.new()
        ob = bpy.data.objects.get('Trimmed_Model')
        self.bme.from_object(ob, context.scene)
        self.bme.verts.ensure_lookup_table()
        
        mx = ob.matrix_world
        
        meta_data = bpy.data.metaballs.new('Splint Shell')
        meta_obj = bpy.data.objects.new('Meta Splint Shell', meta_data)
        meta_data.resolution = self.resolution
        meta_data.render_resolution = self.resolution
        context.scene.objects.link(meta_obj)
        
        for v in self.bme.verts:
            mb = meta_data.elements.new(type = 'BALL')
            mb.radius = self.radius
            mb.co = v.co
            
        meta_obj.matrix_world = mx
        
        context.scene.update()
        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        new_ob = bpy.data.objects.new('Splint Shell', me)
        context.scene.objects.link(new_ob)
        new_ob.matrix_world = mx
        
        mat = bpy.data.materials.get("Splint Material")
        if mat is None:
            # create material
            mat = bpy.data.materials.new(name="Splint Material")
            mat.diffuse_color = Color((0.5, .1, .6))
        
        new_ob.data.materials.append(mat)
        
        mod = new_ob.modifiers.new('Smooth', type = 'SMOOTH')
        mod.iterations = 2
        mod.factor = .8
            
        context.scene.objects.unlink(meta_obj)
        bpy.data.objects.remove(meta_obj)
        bpy.data.metaballs.remove(meta_data)
        
        self.bme.free() 
        tracking.trackUsage("D3Splint:OffsetShell",self.radius)   
        return {'FINISHED'}
    
    def invoke(self, context, event):
        
        self.n_verts = len(bpy.data.objects['Trimmed_Model'].data.vertices)
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self,context):
        
        layout = self.layout
        
        row = layout.row()
        row.label(text = "%i metaballs will be added" % self.n_verts)
        
        if self.n_verts > 10000:
            row = layout.row()
            row.label(text = "WARNING, THIS SEEMS LIKE A LOT")
            row = layout.row()
            row.label(text = "Consider CANCEL/decimating more or possible long processing time")
        
        row = layout.row()
        row.prop(self, "radius")
        row.prop(self,"resolution")
        
class OPENDENTAL_OT_meta_splint_passive_spacer(bpy.types.Operator):
    """Create Meta Offset Surface discs on verts, good for thin offsets .075 to 1mm"""
    bl_idname = "opendental.splint_passive_spacer"
    bl_label = "Create Splint Spacer"
    bl_options = {'REGISTER', 'UNDO'}
    
    radius = FloatProperty(default = .2 , min = .075, max = 1, description = 'Thickness of Offset')
    resolution = FloatProperty(default = 1.2, description = 'Mesh resolution. 1.5 seems ok?')
    n_verts = IntProperty(default = 1000)
    
    @classmethod
    def poll(cls, context):
        if "Trimmed_Model" in bpy.data.objects:
            return True
        else:
            return False
        
    def execute(self, context):
        self.bme = bmesh.new()
        ob = bpy.data.objects.get('Trimmed_Model')
        
        if not ob:
            self.report({'ERROR'}, 'Must trim the upper model first')
            return {'CANCELLED'}
        
        self.bme.from_object(ob, context.scene)
        self.bme.verts.ensure_lookup_table()
        
        mx = ob.matrix_world
        
        meta_data = bpy.data.metaballs.new('Passive Spacer')
        meta_obj = bpy.data.objects.new('Meta Surface Spacer', meta_data)
        meta_data.resolution = self.resolution
        meta_data.render_resolution = self.resolution
        context.scene.objects.link(meta_obj)
               
        #conversion factors
        #for ed in []:
        for v in self.bme.verts:
            co = v.co
            R = .5 * max([ed.calc_length() for ed in v.link_edges])
            
            
            Z = v.normal 
            Z.normalize()
            
            mb = meta_data.elements.new(type = 'ELLIPSOID')
            mb.co = 10 * co
            mb.size_x = 10 * R
            mb.size_y = 10 * R
            mb.size_z = 10 * (self.radius - .025)
            
            v_other = v.link_edges[0].other_vert(v)
            x_prime = v_other.co - v.co
            x_prime.normalize()
            Y = Z.cross(x_prime)
            X = Y.cross(Z)
            
            #rotation matrix from principal axes
            T = Matrix.Identity(3)  #make the columns of matrix U, V, W
            T[0][0], T[0][1], T[0][2]  = X[0] ,Y[0],  Z[0]
            T[1][0], T[1][1], T[1][2]  = X[1], Y[1],  Z[1]
            T[2][0] ,T[2][1], T[2][2]  = X[2], Y[2],  Z[2]

            Rotation_Matrix = T.to_4x4()
            
            mb.rotation = Rotation_Matrix.to_quaternion()
        
        #thickness data
        #.2 to .32
        #.1 to .21
           
        for f in []:        
        #for f in self.bme.faces:
            
            #co = f.calc_center_bounds()
            #vmax = min(f.verts, key = lambda x: (co - x.co).length)
            #R = (co - vmax.co).length
            
            co = f.calc_center_median()
            #R = 2 * f.calc_area() / f.calc_perimeter()
            R = .5 * f.calc_area()**.5
            
            mb = meta_data.elements.new(type = 'CUBE')
            mb.co = 10 * co
            mb.size_x = 10 * .9 * R
            mb.size_y = 10 * .9 * R
            mb.size_z = 10 * self.radius
            
            Z = f.normal
            Y = f.verts[0].co - f.verts[1].co
            #Y = f.verts[0].co - co
            
            Y.normalize()
            X = Y.cross(Z)
            
            #rotation matrix from principal axes
            T = Matrix.Identity(3)  #make the columns of matrix U, V, W
            T[0][0], T[0][1], T[0][2]  = X[0] ,Y[0],  Z[0]
            T[1][0], T[1][1], T[1][2]  = X[1], Y[1],  Z[1]
            T[2][0] ,T[2][1], T[2][2]  = X[2], Y[2],  Z[2]

            Rotation_Matrix = T.to_4x4()
            
            mb.rotation = Rotation_Matrix.to_quaternion()
            
        R = mx.to_quaternion().to_matrix().to_4x4()
        L = Matrix.Translation(mx.to_translation())
        S = Matrix.Scale(.1, 4)
           
        meta_obj.matrix_world =  L * R * S
        
        
        context.scene.update()
        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        new_ob = bpy.data.objects.new('Passive Spacer', me)
        context.scene.objects.link(new_ob)
        new_ob.matrix_world = L * R * S
        
        
        mat = bpy.data.materials.get("Spacer Material")
        if mat is None:
            # create material
            mat = bpy.data.materials.new(name="Spacer Material")
            mat.diffuse_color = Color((0.8, .5, .1))
        new_ob.data.materials.append(mat)
        
        mod = new_ob.modifiers.new('Smooth', type = 'SMOOTH')
        mod.factor = 1
        mod.iterations = 8
            
        context.scene.objects.unlink(meta_obj)
        bpy.data.objects.remove(meta_obj)
        bpy.data.metaballs.remove(meta_data)
        
        self.bme.free()
        #deselect, hide etc to show result
        bpy.ops.object.select_all(action = 'DESELECT')
        for ob in context.scene.objects:
            ob.hide = True
        
        new_ob.hide = False    
        context.scene.objects.active = new_ob
        new_ob.select = True
        ob = bpy.data.objects.get('Based_Model')
        ob.hide = False
        
        bpy.ops.view3d.viewnumpad(type = 'RIGHT')
        tracking.trackUsage("D3Splint:PassiveOffset",self.radius)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        
        
        self.n_verts = len(bpy.data.objects['Trimmed_Model'].data.vertices)
        
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self,context):
        
        layout = self.layout
        
        row = layout.row()
        row.label(text = "%i metaballs will be added" % self.n_verts)
        
        if self.n_verts > 90000:
            row = layout.row()
            row.label(text = "WARNING, THIS SEEMS LIKE A LOT")
            row = layout.row()
            row.label(text = "Consider CANCEL/decimating more or possible long processing time")
        
        row = layout.row()
        row.prop(self, "radius")
        row.prop(self,"resolution")
 
 
class OPENDENTAL_OT_splint_go_sculpt(bpy.types.Operator):
    '''Enter sculpt mode with good settings to start sculpting'''
    bl_idname = "opendental.splint_start_sculpt"
    bl_label = "Splint Sculpt Shell"
    bl_options = {'REGISTER','UNDO'}

    #splint thickness
    detail = bpy.props.FloatProperty(name="Detail", description="Edge length detail", default=.8, min=.025, max=1, options={'ANIMATABLE'})
    
    
    @classmethod
    def poll(cls, context):
        return True
            
    def execute(self, context):
        
            
        Shell = bpy.data.objects.get('Splint Shell')
        if Shell == None:
            self.report({'ERROR'},"Need a splint shell first")
            return {'CANCELLED'}
        
        tracking.trackUsage("D3Splint:GoSculpt",None)
        
        Shell.hide = False
        Shell.select = True
        context.scene.objects.active = Shell
        
        for mod in Shell.modifiers:
            bpy.ops.object.modifier_apply(modifier = mod.name)

                    
        bpy.ops.object.mode_set(mode = 'SCULPT')
        if not Shell.use_dynamic_topology_sculpting:
            bpy.ops.sculpt.dynamic_topology_toggle()
        
        scene = context.scene
        paint_settings = scene.tool_settings.unified_paint_settings
        paint_settings.use_locked_size = True
        paint_settings.unprojected_radius = 3
        brush = bpy.data.brushes['Scrape/Peaks']
        scene.tool_settings.sculpt.brush = brush
        scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
        scene.tool_settings.sculpt.constant_detail = 50
        scene.tool_settings.sculpt.use_symmetry_x = False
        scene.tool_settings.sculpt.use_symmetry_y = False
        scene.tool_settings.sculpt.use_symmetry_z = False
        brush.strength = .6
        
        #brush.stroke_method = 'SPACE' 

        
        return {'FINISHED'}                             
def register():
    bpy.utils.register_class(OPENDENTAL_OT_link_selection_splint)
    bpy.utils.register_class(OPENDENTAL_OT_splint_bezier_model)
    bpy.utils.register_class(OPENDENTAL_OT_splint_add_guides)
    bpy.utils.register_class(OPENDENTAL_OT_splint_subtract_holes)
    bpy.utils.register_class(OPENDENTAL_OT_survey_model)
    bpy.utils.register_class(OPENDENTAL_OT_survey_model_axis)
    bpy.utils.register_class(OPENDENTAL_OT_blockout_model)
    #bpy.utils.register_class(OPENDENTAL_OT_splint_margin_trim)
    bpy.utils.register_class(OPENDENTAL_OT_splint_buccal_marks)
    bpy.utils.register_class(OPENDENTAL_OT_splint_occlusal_arch)
    bpy.utils.register_class(OPENDENTAL_OT_splint_opposing)
    bpy.utils.register_class(OPENDENTAL_OT_splint_add_rim)
    bpy.utils.register_class(OPENDENTAL_OT_splint_trim_model)
    bpy.utils.register_class(OPENDENTAL_OT_splint_mount_on_articulator)
    bpy.utils.register_class(OPENDENTAL_OT_meta_splint_passive_spacer)
    bpy.utils.register_class(OPENDENTAL_OT_meta_splint_surface)
    bpy.utils.register_class(OPENDENTAL_OT_splint_create_functional_surface)
    bpy.utils.register_class(OPENDENTAL_OT_splint_stop_functional_surface)
    
    #bpy.utils.register_class(OPENDENTAL_OT_initiate_arch_curve)
    bpy.utils.register_class(OPENDENTAL_OT_arch_curve)
    bpy.utils.register_class(OPENDENTAL_OT_splint_subtract_sleeves)
    bpy.utils.register_class(OPENDENTAL_OT_splint_bone)
    bpy.utils.register_class(OPENDENTAL_OT_splint_model)
    bpy.utils.register_class(OPENDENTAL_OT_splint_report)
    bpy.utils.register_class(OPENDENTAL_OT_splint_margin)
    bpy.utils.register_class(OPENDENTAL_OT_splint_margin_detail)
    bpy.utils.register_class(OPENDENTAL_OT_splint_join_rim)
    bpy.utils.register_class(OPENDENTAL_OT_splint_subtract_surface)
    bpy.utils.register_class(OPENDENTAL_OT_splint_go_sculpt)
    bpy.utils.register_class(OPENDENTAL_OT_splint_finish_booleans)

    #bpy.utils.register_class(OPENDENTAL_OT_mesh_trim_polyline)
    #bpy.utils.register_module(__name__)
    
def unregister():
    bpy.utils.unregister_class(OPENDENTAL_OT_link_selection_splint)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_bezier_model)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_add_guides)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_subtract_holes)
    bpy.utils.unregister_class(OPENDENTAL_OT_survey_model)
    bpy.utils.unregister_class(OPENDENTAL_OT_survey_model_axis)
    bpy.utils.unregister_class(OPENDENTAL_OT_blockout_model)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_margin_trim)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_buccal_marks)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_occlusal_arch)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_opposing)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_add_rim)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_trim_model)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_mount_on_articulator)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_create_functional_surface)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_stop_functional_surface)
    bpy.utils.unregister_class(OPENDENTAL_OT_meta_splint_surface)
    bpy.utils.unregister_class(OPENDENTAL_OT_meta_splint_passive_spacer)
    #bpy.utils.unregister_class(OPENDENTAL_OT_initiate_arch_curve)
    bpy.utils.unregister_class(OPENDENTAL_OT_arch_curve)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_subtract_sleeves)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_bone)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_model)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_report)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_margin)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_margin_detail)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_join_rim)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_subtract_surface)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_go_sculpt)
    bpy.utils.unregister_class(OPENDENTAL_OT_splint_finish_booleans)
    #bpy.utils.unregister_class(OPENDENTAL_OT_mesh_trim_polyline)
    
if __name__ == "__main__":
    register()
