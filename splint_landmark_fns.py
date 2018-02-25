'''
Created on Aug 15, 2017
@author: Patrick

This module contains functions that are used to mark and set
landmarks on the casts.  For example marking splint boundaries
midine etc.
'''
import bpy
import bmesh
import odcutils
from points_picker import PointPicker
from textbox import TextBox
from mathutils import Vector, Matrix, Color
from bpy_extras.view3d_utils import region_2d_to_location_3d, region_2d_to_origin_3d, region_2d_to_vector_3d
import math
from mesh_cut import flood_selection_faces, edge_loops_from_bmedges, flood_selection_faces_limit, space_evenly_on_path
from curve import CurveDataManager, PolyLineKnife
from common_utilities import bversion, get_settings
import tracking
from odcutils import get_bbox_center
from multiprocessing import get_start_method

def arch_crv_draw_callback(self, context):  
    self.crv.draw(context)
    self.help_box.draw()   
    
class D3SPLINT_OT_splint_occlusal_arch_max(bpy.types.Operator):
    """Draw a line along the cusps of the maxillary model"""
    bl_idname = "d3splint.draw_occlusal_curve_max"
    bl_label = "Mark Occlusal Curve"
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
        T = Matrix.Translation(center + 4 * Z)
        T2 = Matrix.Translation(center + 10 * Z)
        
        bme = bmesh.new()
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        bmesh.ops.create_grid(bme, x_segments = 200, y_segments = 200, size = 39.9)
        
        if 'Dynamic Occlusal Surface' not in bpy.data.objects:
            bme.to_mesh(me)
            plane_obj = bpy.data.objects.new('Dynamic Occlusal Surface', me)
            plane_obj.matrix_world = T * R
        
            mat = bpy.data.materials.get("Plane Material")
            if mat is None:
                # create material
                mat = bpy.data.materials.new(name="Plane Material")
                mat.diffuse_color = Color((0.8, 1, .9))
            
            plane_obj.data.materials.append(mat)
            context.scene.objects.link(plane_obj)
            plane_obj.hide = True
        else:
            plane_obj = bpy.data.objects.get('Dynamic Occlusal Surface')
            plane_obj.matrix_world = T * R
            
        bme.free()   
        Opposing = bpy.data.objects.get(self.splint.get_mandible())
        if Opposing != None:
            for cons in plane_obj.constraints:
                    if cons.type == 'CHILD_OF':
                        plane_obj.constraints.remove(cons)
            
            cons = plane_obj.constraints.new('CHILD_OF')
            cons.target = Opposing
            cons.inverse_matrix = Opposing.matrix_world.inverted()
        
            
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
            if self.splint.jaw_type == 'MANDIBLE':
                self.convert_curve_to_plane(context)
            self.splint.curve_max = True
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
            context.space_data.transform_manipulators = {'TRANSLATE'}
            #clean up callbacks
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def invoke(self,context, event):
        if len(context.scene.odc_splints) == 0:
            self.report({'ERROR'},'need to start splint')
            return {'CANCELLED'}
        prefs = get_settings()
        n = context.scene.odc_splint_index
        self.splint = context.scene.odc_splints[n]
        self.crv = None
        margin = "Occlusal Curve Max"
        
        model = self.splint.get_maxilla()   
        if model != '' and model in bpy.data.objects:
            Model = bpy.data.objects[model]
            for ob in bpy.data.objects:
                ob.select = False
                ob.hide = True
            Model.select = True
            Model.hide = False
            context.scene.objects.active = Model
            bpy.ops.view3d.viewnumpad(type = 'BOTTOM')
            bpy.ops.view3d.view_selected()
            self.crv = CurveDataManager(context,snap_type ='OBJECT', 
                                        snap_object = Model, 
                                        shrink_mod = False, 
                                        name = margin,
                                        cyclic = 'FALSE')
            self.crv.crv_obj.parent = Model
            self.crv.point_size, self.crv.point_color, self.crv.active_color = prefs.point_size, prefs.def_point_color, prefs.active_point_color
            
            context.space_data.show_manipulator = False
            context.space_data.transform_manipulators = {'TRANSLATE'}
        else:
            self.report({'ERROR'}, "Need to set the Master Model first!")
            return {'CANCELLED'}
            
        
        #self.splint.occl = self.crv.crv_obj.name
        
        #TODO, tweak the modifier as needed
        help_txt = "DRAW MAXILLARY OCCLUSAL POINTS\n\n-  Start on one side of arch and sequentially work around to the other \n-  This curve will establish the facial boundary of the Wax Rim\n-  It is not necessary to click every cusp tip\n-  Points will snap to maxilla under mouse \n\n-Right click to delete a point \n-G to grab the point and then LeftClick to place it \n-ENTER to confirm \n-ESC to cancel \n\n\n One strategy for a smooth rim on a reasonably normal dentition is MB cusp 2nd Molar, B cusp 2nd Premolar, Canine Cusp, Mid-Incisal of Central Incisor.  A smooth curve is more important than identifying every cusp tip. Understanding that this defines one edge of the wax rim will also help you decide when to include an extra cusp to ensure the rim extends to it.  Mid-fossa or Marginal ridges can be marked for cases like posterior cross bite"
        
        
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(arch_crv_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        
        tracking.trackUsage("D3Splint:MaxBuccalCusps",None)

        return {'RUNNING_MODAL'}


class D3SPLINT_OT_splint_occlusal_curve_mand(bpy.types.Operator):
    """Draw a line along the lingual cusps of the mandibular model"""
    bl_idname = "d3splint.draw_occlusal_curve_mand"
    bl_label = "Mark Mandible Occlusal Curve"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        return True

    def  convert_curve_to_plane(self, context):
        
        me = self.crv.crv_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        mx = self.crv.crv_obj.matrix_world
        arch_vs = [mx*v.co for v in me.vertices]
        arc_vs_even, eds = space_evenly_on_path(arch_vs, [(0,1),(1,2)], 101, 0)
        
        
        Z = odcutils.calculate_plane(arc_vs_even, itermax = 500, debug = False)
        
        v_ant = arc_vs_even[50] #we established 100 verts so 50 is the anterior midpoint
        v_0 = arc_vs_even[0]
        v_n = arc_vs_even[-1]
        
        center = .5 *(.5*(v_0 + v_n) + v_ant)
        
        vec_n = v_n - v_0
        vec_n.normalize()
        
        vec_ant = v_ant - v_0
        vec_ant.normalize()
        
        #Z = vec_n.cross(vec_ant)
        #Z.normalize()
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
        
        
        if 'Dynamic Occlusal Surface' not in bpy.data.objects:
            bme.to_mesh(me)
            plane_obj = bpy.data.objects.new('Dynamic Occlusal Surface', me)
            plane_obj.matrix_world = T * R
        
            mat = bpy.data.materials.get("Plane Material")
            if mat is None:
                # create material
                mat = bpy.data.materials.new(name="Plane Material")
                mat.diffuse_color = Color((0.8, 1, .9))
            
            plane_obj.data.materials.append(mat)
            context.scene.objects.link(plane_obj)
            plane_obj.hide = True
        else:
            plane_obj = bpy.data.objects.get('Dynamic Occlusal Surface')
            plane_obj.matrix_world = T * R
            
        bme.free()   
        Opposing = bpy.data.objects.get(self.splint.get_maxilla())
        if Opposing != None:
            for cons in plane_obj.constraints:
                    if cons.type == 'CHILD_OF':
                        plane_obj.constraints.remove(cons)
            
            cons = plane_obj.constraints.new('CHILD_OF')
            cons.target = Opposing
            cons.inverse_matrix = Opposing.matrix_world.inverted()
            

        bme.free()
        
        
        
    def finish_up(self,context):     
        for ob in bpy.data.objects:
            ob.hide = True
        self.crv.crv_obj.hide = True
        self.splint.curve_mand = True
        
        Model = bpy.data.objects.get(self.splint.model)
        if Model:
            Model.select = True
            Model.hide = False
            context.scene.objects.active = Model
            if self.splint.jaw_type == 'MAXILLA':
                bpy.ops.view3d.viewnumpad(type = 'BOTTOM')
            else:
                bpy.ops.view3d.viewnumpad(type = 'TOP')
            bpy.ops.view3d.view_selected()
            
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
            
            if self.splint.jaw_type == 'MAXILLA':
                self.convert_curve_to_plane(context)
            
            self.finish_up(context)
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
            context.space_data.transform_manipulators = {'TRANSLATE'}
            #clean up callbacks
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def invoke(self,context, event):
        prefs = get_settings()
        self.splint = context.scene.odc_splints[0]    
        self.crv = None
        margin = 'Occlusal Curve Mand'
        
        model = self.splint.get_mandible()   
        if model != '' and model in bpy.data.objects:
            Model = bpy.data.objects[model]
            for ob in bpy.data.objects:
                ob.select = False
                ob.hide = True
            Model.select = True
            Model.hide = False
            context.scene.objects.active = Model
            bpy.ops.view3d.viewnumpad(type = 'TOP')
            bpy.ops.view3d.view_selected()
            context.space_data.show_manipulator = False
            context.space_data.transform_manipulators = {'TRANSLATE'}
            self.crv = CurveDataManager(context,snap_type ='OBJECT', snap_object = Model, shrink_mod = False, name = margin, cyclic = 'FALSE')
            self.crv.crv_obj.parent = Model
            self.crv.point_size, self.crv.point_color, self.crv.active_color = prefs.point_size, prefs.def_point_color, prefs.active_point_color
            
        else:
            self.report({'ERROR'}, "Need to mark the Opposing model first!")
            return {'CANCELLED'}
            
        
        #self.splint.occl = self.crv.crv_obj.name
        
        #TODO, tweak the modifier as needed
        help_txt = "DRAW MANDIBULAR OCCLUSAL POINTS\n\n-  Start on one side of arch and sequentially work around to the other \n-  This curve will establish the lingual boundary of the Wax Rim \n-  It will also estimate the lower occlusal pane \n-  It is not necessary to click every cusp tip  \n-  Points will snap to mandible under mouse \n\n-  Right click to delete a point \n-  G to grab the point and then LeftClick to place it back on model \n-  ENTER to confirm \n-  ESC to cancel \n\n\n  One strategy for a smooth rim in a reasonably normal dentition is to pace a point on the ML cusp of 2nd Molar, L cusp 2nd Premolar, Canine Cusp Tip, Mid-Incisal of Central Incisor. A smooth curve is more important than identifying every cusp tip. Understanding that this defines one edge of the wax rim will also help you decide when to include an extra cusp to ensure the rim extends sufficiently to it.  Mid-fossa or even Buccal Cusps can be marked for cases like posterior cross bite" 
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(arch_crv_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        return {'RUNNING_MODAL'}

def landmarks_draw_callback(self, context):  
    self.crv.draw(context)
    self.help_box.draw()    
    
class D3SPLINT_OT_splint_land_marks(bpy.types.Operator):
    """Define Right Molar, Left Molar, Midline"""
    bl_idname = "d3splint.splint_mark_landmarks"
    bl_label = "Define Model Landmarks"
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

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if len(self.crv.b_pts) >= 4: return 'main' #can't add more
            
            x, y = event.mouse_region_x, event.mouse_region_y
            
            if len(self.crv.b_pts) == 0:
                txt = "Right Molar"
                help_txt = "DRAW LANDMARK POINTS\n Left Click on Symmetric Patient Left Side Molar"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                
            elif len(self.crv.b_pts) == 1:
                txt = "Left Molar"
                help_txt = "DRAW LANDMARK POINTS\n Left Click Incisal Edge In Anterior"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                    
            elif len(self.crv.b_pts) == 2:
                txt = "Incisal Edge"
                help_txt = "DRAW LANDMARK POINTS\n Left Click Midline (Embrasure or Papilla)l"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                
            else:
                txt = "Midline"
                help_txt = "DRAW LANDMARK POINTS\n Press Enter to Finish"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
            
            self.crv.click_add_point(context, x,y, label = txt)
            
            return 'main'
        
        if event.type == 'DEL' and event.value == 'PRESS':
            self.crv.click_delete_point()
            return 'main'
            
        if event.type == 'RET' and event.value == 'PRESS':
            if len(self.crv.b_pts) != 4:
                return 'main'
            self.finish(context)
            return 'finish'
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            return 'cancel' 

        return 'main'
    
        
    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            context.space_data.show_manipulator = True
            
            if nmode == 'finish':
                context.space_data.transform_manipulators = {'TRANSLATE', 'ROTATE'}
            else:
                context.space_data.transform_manipulators = {'TRANSLATE'}
            #clean up callbacks
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def invoke(self,context, event):
        
        if len(context.scene.odc_splints) == 0:
            self.report({'ERROR'}, "Need to mark splint and opposing models first")
            return {'CANCELLED'}
        n = context.scene.odc_splint_index
        self.splint = context.scene.odc_splints[n]    
        
        model = self.splint.get_maxilla()
        mand_model = self.splint.get_mandible()
        
        
        if model == '' or model not in bpy.data.objects:
            self.report({'ERROR'}, "Need to mark the UpperJaw model first!")
            return {'CANCELLED'}
        
        if mand_model == '' or mand_model not in bpy.data.objects:
            self.report({'WARNING'}, "Consider marking Mandibular model first!")  
            
        
        Model = bpy.data.objects[model]
        Mand_Model = bpy.data.objects.get(mand_model)
        
        #if Model and Mand_Model:
            #Make both models have same origin if they don't
        #    loc = Model.location
        #    loc1 = Mand_Model.location
            
        #    r = loc - loc1
        #    if r.length > .0001:
        #        T = Matrix.Translation(r)
        #        iT = T.inverted()
        #        Mand_Model.data.transform(iT)
        #        mmx = Mand_Model.matrix_world
        #        Mand_Model.matrix_world = T * mmx
            
               
        for ob in bpy.data.objects:
            ob.select = False
            ob.hide = True
        Model.select = True
        Model.hide = False
        context.scene.objects.active = Model
        
        bpy.ops.view3d.viewnumpad(type = 'FRONT')
        
        bpy.ops.view3d.view_selected()
        self.crv = PointPicker(context,snap_type ='OBJECT', snap_object = Model)
        context.space_data.show_manipulator = False
        context.space_data.transform_manipulators = {'TRANSLATE'}
        v3d = bpy.context.space_data
        v3d.pivot_point = 'MEDIAN_POINT'
        
        
        #TODO, tweak the modifier as needed
        help_txt = "DRAW LANDMARK POINTS\n Click on the Patient's Right Molar Occlusal Surface"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(landmarks_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        return {'RUNNING_MODAL'}

    def finish(self, context):
        settings = get_settings()
        Model =  bpy.data.objects[self.splint.get_maxilla()]
        mx = Model.matrix_world
        imx = mx.inverted()
        
        
        Mand_Model = bpy.data.objects.get(self.splint.get_mandible())
        if Mand_Model:
            mx_mand = Mand_Model.matrix_world
            imx_mand = mx_mand.inverted()
        
        #get the local points
        
        v_R = imx * self.crv.b_pts[0] #R molar
        v_L = imx * self.crv.b_pts[1] #L molar 
        v_I = imx * self.crv.b_pts[2] #Incisal Edge
        v_M = imx * self.crv.b_pts[3] #midline
        
        
        center = 1/3 * (v_R + v_L + v_I)
        mx_center = Matrix.Translation(center)
        imx_center = mx_center.inverted()
        
        #vector pointing from left to right
        vec_R =  v_R - v_L
        vec_R.normalize()
        vec_L = v_L - v_R
        vec_L.normalize()
        vec_I = v_I - v_R
        vec_I.normalize()
        vec_M = v_M -v_R
        vec_M.normalize()
        
        Z = vec_I.cross(vec_L)
        Z.normalize()
                
        ##Option 2
        X = v_M - center
        X = X - X.dot(Z) * Z
       
        
        X.normalize()    
        Y = Z.cross(X)
        Y.normalize()
        
        
        v_M_corrected = v_I - (v_I - center).dot(Y) * Y
         
         
        R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
        R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
        R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2] 
        R = R.to_4x4()
        iR = R.inverted()
        #Now we have the rotation matrix that got us where we wanted
        Model.data.transform(iR)
        #Model.matrix_world = Identity is implied, we will reset the matrix later
        if Mand_Model:
            Mand_Model.data.transform(mx_mand)
            Mand_Model.matrix_world = Model.matrix_world
            Mand_Model.data.transform(Model.matrix_world.inverted())
            
            Mand_Model.data.transform(iR)
              
        #Lets Calculate the matrix transform for an
        #8 degree Fox plane cant.
        Z_w = Vector((0,0,1))
        X_w = Vector((1,0,0))
        Y_w = Vector((0,1,0))
        
        op_angle = settings.def_occlusal_plane_angle
        Fox_R = Matrix.Rotation(op_angle * math.pi /180, 3, 'Y')
        Z_fox = Fox_R * Z_w
        X_fox = Fox_R * X_w
        
        R_fox = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R_fox[0][0], R_fox[0][1], R_fox[0][2]  = X_fox[0] ,Y_w[0],  Z_fox[0]
        R_fox[1][0], R_fox[1][1], R_fox[1][2]  = X_fox[1], Y_w[1],  Z_fox[1]
        R_fox[2][0] ,R_fox[2][1], R_fox[2][2]  = X_fox[2], Y_w[2],  Z_fox[2]
        R_fox = R_fox.to_4x4()
        
        #average distance from campers plane to occlusal
        #plane is 30 mm
        #file:///C:/Users/Patrick/Downloads/CGBCC4_2014_v6n6_483.pdf
        
        center = R_fox * iR * center
        v_ant = R_fox * iR * v_M_corrected
        
        if 'Articulator' not in bpy.data.objects:
            x_radius = (settings.def_arm_radius **2 -  (.5 * settings.def_intra_condyle_width)**2)**.5
            
            balk_radians = settings.def_balkwill_angle * math.pi/180
            
            balk_mx = Matrix.Rotation(balk_radians, 3, 'Y')
            incisal_final = Vector((x_radius, 0, 0))
            incisal_final.rotate(balk_mx)
            
            print(balk_radians)
            print(incisal_final)
            
        else:
            art = bpy.data.objects.get('Articulator')
            x_radius = (settings.def_arm_radius **2 -  (.5 * art.get('intra_condyle_width'))**2)**.5
            
            balk_radians = settings.def_balkwill_angle * math.pi/180
            
            balk_mx = Matrix.Rotation(balk_radians, 3, 'Y')
            incisal_final = Vector((x_radius, 0, 0))
            incisal_final.rotate(balk_mx)    
        
        
        T_incisal = Matrix.Translation(iR * v_M_corrected)
        
        
        T = Matrix.Translation(incisal_final-v_ant)
        Model.matrix_world =  T * R_fox
        
        mx_mount = T * R_fox
        
        if 'Incisal' not in bpy.data.objects:
            empty = bpy.data.objects.new('Incisal', None)
            context.scene.objects.link(empty)
            #now it stays with Model forever
            empty.parent = Model
            empty.matrix_world = Matrix.Translation(incisal_final)
        else:
            empty = bpy.data.objects.get('Incisal')
            empty.matrix_world = Matrix.Translation(incisal_final)    
            
        if Mand_Model:
            #todo..check to move lower jaw after landmarks?    
            if len(Mand_Model.constraints):
                for cons in Mand_Model.constraints:
                    Mand_Model.constraints.remove(cons)

            Mand_Model.matrix_world = T * R_fox
            Mand_Model.hide = False
                
            cons = Mand_Model.constraints.new('CHILD_OF')
            cons.target = Model
            cons.inverse_matrix = Model.matrix_world.inverted()
        
            if "Mandibular Orientation" in bpy.data.objects:
                Transform = bpy.data.objects.get('Mandibular Orientation')
            else:
                Transform = bpy.data.objects.new('Mandibular Orientation', None)
                Transform.parent = Model
                context.scene.objects.link(Transform)
            Transform.matrix_world = T * R_fox
                
        if "Trim Surface" in bpy.data.objects:
            trim_ob = bpy.data.objects['Trim Surface']
            trim_ob.data.transform(iR)
            trim_ob.matrix_world = mx_mount
            trim_ob.hide = True
        
        margin = self.splint.name + '_margin'
        if margin in bpy.data.objects:
            bobj = bpy.data.objects[margin]
            bobj.data.transform(iR)
            bobj.matrix_world = mx_mount
            bobj.hide = True
            
        if "Trimmed_Model" in bpy.data.objects:
            trim_ob = bpy.data.objects["Trimmed_Model"]
            trim_ob.data.transform(iR)
            trim_ob.matrix_world = mx_mount
            trim_ob.hide = True
        
        context.scene.cursor_location = Model.location
        bpy.ops.view3d.view_center_cursor()
        
        if self.splint.workflow_type != 'SIMPLE_SHELL':
            bpy.ops.view3d.viewnumpad(type = 'FRONT')
            
        else:
            if self.splint.jaw_type == 'MAXILLA':
                if Mand_Model:
                    Mand_Model.hide = True
                bpy.ops.view3d.viewnumpad(type = 'BOTTOM')
            else: # self.splint.jaw_type == 'MANDIBLE':
                Model.hide = True
                bpy.ops.view3d.viewnumpad(type = 'TOP')
            
        self.splint.landmarks_set = True
        
        if 'Articulator' not in context.scene.objects and self.splint.workflow_type != 'SIMPLE_SHELL':
            
            
        
            bpy.ops.d3splint.generate_articulator(
                intra_condyle_width = settings.def_intra_condyle_width,
                condyle_angle = settings.def_condyle_angle,
                bennet_angle = settings.def_bennet_angle,
                incisal_guidance = settings.def_incisal_guidance,
                canine_guidance = settings.def_canine_guidance,
                guidance_delay_ant = settings.def_guidance_delay_ant,
                guidance_delay_lat = settings.def_guidance_delay_lat)
            
            
            bpy.ops.d3splint.generate_articulator('EXEC_DEFAULT')
        tracking.trackUsage("D3Splint:SplintLandmarks",None)

class D3SPLINT_OT_splint_paint_margin(bpy.types.Operator):
    '''Use dyntopo sculpt to add/remove detail at margin'''
    bl_idname = "d3splint.splint_paint_margin"
    bl_label = "Paint Splint Margin"
    bl_options = {'REGISTER','UNDO'}

    #splint thickness
    detail = bpy.props.FloatProperty(name="Detail", description="Edge length detail", default=.8, min=.025, max=1, options={'ANIMATABLE'})
    
    
    @classmethod
    def poll(cls, context):
        return True
            
    def execute(self, context):
        
            
        settings = get_settings()
   
        
        j = context.scene.odc_splint_index
        splint =context.scene.odc_splints[j]
        if splint.model in bpy.data.objects:
            model = bpy.data.objects[splint.model]
        else:
            print('whoopsie...margin and model not defined or something is wrong')
            return {'CANCELLED'}
        
        for ob in context.scene.objects:
            ob.select = False
        
                
        model.hide = False
        model.select = True
        context.scene.objects.active = model
        
            
        bpy.ops.object.mode_set(mode = 'SCULPT')
        bpy.ops.view3d.viewnumpad(type = 'RIGHT')
        #if not model.use_dynamic_topology_sculpting:
        #    bpy.ops.sculpt.dynamic_topology_toggle()
        
        scene = context.scene
        paint_settings = scene.tool_settings.unified_paint_settings
        paint_settings.use_locked_size = True
        paint_settings.unprojected_radius = .5
        brush = bpy.data.brushes['Mask']
        brush.strength = 1
        brush.stroke_method = 'LINE'
        scene.tool_settings.sculpt.brush = brush
        
        bpy.ops.brush.curve_preset(shape = 'MAX')
        
        return {'FINISHED'}
    
class D3SPLINT_OT_splint_trim_model_paint(bpy.types.Operator):
    """Trim model from painted boundary"""
    bl_idname = "d3splint.splint_trim_from_paint"
    bl_label = "Trim Model From Paint"
    bl_options = {'REGISTER','UNDO'}

    invert = bpy.props.BoolProperty(default = False, name = 'Invert')
    @classmethod
    def poll(cls, context):
        
        c1 = context.object.type == 'MESH'
        c2 = context.mode == 'SCULPT'
        return c1 & c2
    
    def execute(self, context):
        
        n = context.scene.odc_splint_index
        model = context.scene.odc_splints[n].model
        Model = bpy.data.objects.get(model)
        if not Model:
            self.report({'ERROR'}, "Need to set Model first")
        
        
        mx = Model.matrix_world
        bme = bmesh.new()
        bme.from_mesh(Model.data)

        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        
        mask = bme.verts.layers.paint_mask.verify()
        
        #clean loose verts
        mask_verts = []
        for v in bme.verts:
            if v[mask] > 0.1:
                mask_verts.append(v)
        
        
        mask_set_verts = set(mask_verts)
        
        
        ### TODO GOOD ERROR CONDITIONS###
        total_faces = set(bme.faces[:])
        mask_faces = set([f for f in bme.faces if all([v in mask_set_verts for v in f.verts])])
        total_faces.difference_update(mask_faces)
        
        
        print('there are %i faces in the mesh' % len(bme.faces))
        print('there are %i faces in the mask' % len(mask_faces))
        print('there are %i other faces' % len(total_faces))
        
        
        
        ###TODO, make the flood selection work with sets not just BME###
        mask_islands = []
        iters = 0
        while len(mask_faces) and iters < 100:
            iters += 1
            seed = mask_faces.pop()
            island = flood_selection_faces_limit(bme, {}, seed, mask_faces, max_iters = 10000)
            
            print('iteration %i with %i mask island faces' % (iters, len(island)))
            mask_islands.append(island)
            mask_faces.difference_update(island)
            
        
        print('there are %i mask islands' % len(mask_islands))    
        
        mask_islands.sort(key = len)
        mask_islands.reverse()
        mask_faces = mask_islands[0]
        
        print('there are %i faces in the largest mask' % len(mask_faces))
        
        if len(mask_islands) > 1 and len(mask_islands[1]) != 0:
            seed_faces = mask_islands[1]
            seed_face = seed_faces.pop()
            best = flood_selection_faces(bme, mask_faces, seed_face, max_iters = 10000)
        
        else:
            islands = []
            iters = 0
            while len(total_faces) and iters < 100:
                iters += 1
                seed = total_faces.pop()
                island = flood_selection_faces(bme, mask_faces, seed, max_iters = 10000)
                
                print('iteration %i with %i island faces' % (iters, len(island)))
                islands.append(island)
                total_faces.difference_update(island)
                
            print('there are %i islands' % len(islands))
            best = max(islands, key = len)
        
        total_faces = set(bme.faces[:])
        del_faces = total_faces - best
        
        
        if len(del_faces) == 0:
            print('ERROR because we are not deleting any faces')
            #reset the mask for the small mask islands
            if len(mask_islands) > 1:
                for isl in mask_islands[1:]:
                    print('fixing %i faces in mask island' % len(isl))
                    for f in isl:
                        for v in f.verts:
                            v[mask] = 0
            
            
            bme.to_mesh(Model.data)
            Model.data.update()
        
            bme.free()
            self.report({'WARNING'}, 'Unable to trim, undo, then ensure your paint loop is closed and try again')
            return {'FINISHED'}
        
        
        print('deleting %i faces' % len(del_faces))
        bmesh.ops.delete(bme, geom = list(del_faces), context = 3)
        del_verts = []
        for v in bme.verts:
            if all([f in del_faces for f in v.link_faces]):
                del_verts += [v]        
        bmesh.ops.delete(bme, geom = del_verts, context = 1)
        print('deleteing %i verts' % len(del_verts))
        
        del_edges = []
        for ed in bme.edges:
            if len(ed.link_faces) == 0:
                del_edges += [ed]
        
        bmesh.ops.delete(bme, geom = del_edges, context = 4) 
        
        trimmed_model = bpy.data.meshes.new('Trimmed_Model')
        trimmed_obj = bpy.data.objects.new('Trimmed_Model', trimmed_model)
        bme.to_mesh(trimmed_model)
        trimmed_obj.matrix_world = mx
        context.scene.objects.link(trimmed_obj)
        
        
        new_edges = [ed for ed in bme.edges if len(ed.link_faces) == 1]
        
    
        for i in range(10):        
            gdict = bmesh.ops.extrude_edge_only(bme, edges = new_edges)
            bme.edges.ensure_lookup_table()
            bme.verts.ensure_lookup_table()
            new_verts = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
            new_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
            for v in new_verts:
                v.co += .4 * Vector((0,0,1))
        v_max = max(new_verts, key = lambda x: x.co[2])
        z_max = v_max.co[2]
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in new_edges])
        print('there are %i loops' % len(loops))
        for loop in loops:
            for i in loop:
                bme.verts[i].co[2] = z_max
            if loop[0] != loop[-1]:continue
            loop.pop()
            f = [bme.verts[i] for i in loop]
            if len(set(f)) == len(f):
                bme.faces.new(f)
            
        bmesh.ops.recalc_face_normals(bme,faces = bme.faces[:])
            
        based_model = bpy.data.meshes.new('Based_Model')
        based_obj = bpy.data.objects.new('Based_Model', based_model)
        bme.to_mesh(based_model)
        based_obj.matrix_world = mx
        context.scene.objects.link(based_obj)
        
        Model.hide = True    
                    
        bme.free()
        
        
        return {'FINISHED'}

def pick_model_callback(self, context):
    self.help_box.draw()
    
class D3SPLINT_OT_pick_model(bpy.types.Operator):
    """Left Click on Model to Build Splint"""
    bl_idname = "d3splint.pick_model"
    bl_label = "Pick Model"
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

        
        if event.type == 'MOUSEMOVE':
            self.hover_scene(context, event.mouse_region_x, event.mouse_region_y)    
            return 'main'
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            
            return self.pick_model(context)
        
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            return 'cancel' 

        return 'main'
    


    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #clean up callbacks
            context.window.cursor_modal_restore()
            context.area.header_text_set()
            context.user_preferences.themes[0].view_3d.outline_width = self.outline_width
        
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def hover_scene(self,context,x, y):
        scene = context.scene
        region = context.region
        rv3d = context.region_data
        coord = x, y
        ray_max = 10000
        view_vector = region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = region_2d_to_origin_3d(region, rv3d, coord)
        ray_target = ray_origin + (view_vector * ray_max)

        if bversion() <= '002.076.000':
            result, ob, mx, loc, normal = scene.ray_cast(ray_origin, ray_target)
        else:
            result, loc, normal, idx, ob, mx = scene.ray_cast(ray_origin, ray_target)

        if result:
            self.ob = ob
            self.ob_preview = ob.name
            context.area.header_text_set(ob.name)
            
            for obj in context.scene.objects:
                if obj != ob:
                    obj.select = False
                else:
                    obj.select = True
        
        else:
            self.ob = None
            self.ob_preview = 'None'
            context.area.header_text_set('None')
            for ob in context.scene.objects:
                ob.select = False
            if context.object:
                context.scene.objects.active = None
    
    def pick_model(self, context):
        
        prefs = get_settings()
        if self.ob == None:
            return 'main'
        
        n = context.scene.odc_splint_index
        if len(context.scene.odc_splints) != 0:
            
            odc_splint = context.scene.odc_splints[n]
            odc_splint.model = self.ob.name
            odc_splint.model_set = True
            
        else:
            my_item = context.scene.odc_splints.add()        
            my_item.name = 'Splint'
            my_item.model = self.ob.name
            my_item.model_set = True
            
            my_item.jaw_type = prefs.default_jaw_type
            my_item.workflow_type = prefs.default_workflow_type
            
        if "Model Mat" not in bpy.data.materials:
            mat = bpy.data.materials.new('Model Mat')
            mat.diffuse_color = prefs.def_model_color
            mat.diffuse_intensity = 1
            mat.emit = .8
        else:
            mat = bpy.data.materials.get('Model Mat')
        
        # Assign it to object
        if self.ob.data.materials:
            # assign to 1st material slot
            self.ob.data.materials[0] = mat
        else:
            # no slots
            self.ob.data.materials.append(mat)
        
        
        bb_center = get_bbox_center(self.ob)
        T = Matrix.Translation(bb_center)
        iT = T.inverted()
        
        self.ob.data.transform(iT)
        self.ob.matrix_world *= T
        
        tracking.trackUsage("D3Splint:PickModel")
        return 'finish'
            
    def invoke(self,context, event):
        
        self.report({'WARNING'}, 'By Continuuing, you certify this is for non-clinial, educational or training purposes')
        
        self.outline_width = context.user_preferences.themes[0].view_3d.outline_width
        context.user_preferences.themes[0].view_3d.outline_width = 4
        
        self.ob_preview = 'None'
        context.window.cursor_modal_set('EYEDROPPER')
        
        #hide the stupid grid floor
        context.space_data.show_floor = False
        context.space_data.show_axis_x = False
        context.space_data.show_axis_y = False
        
        #TODO, tweak the modifier as needed
        help_txt = "Pick Model\n\n Hover over objects in the scene \n left click on model that splint will build on \n ESC to cancel"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(pick_model_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        
        tracking.trackUsage("D3Splint:MarkOutline", None)
        return {'RUNNING_MODAL'}
   
class D3SPLINT_OT_pick_opposing(bpy.types.Operator):
    """Left Click on Model to mark the opposing"""
    bl_idname = "d3splint.pick_opposing"
    bl_label = "Pick Opposing"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        if len(context.scene.odc_splints) == 0:
            return False
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

        
        if event.type == 'MOUSEMOVE':
            self.hover_scene(context, event.mouse_region_x, event.mouse_region_y)    
            return 'main'
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            
            return self.pick_model(context)
        
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            return 'cancel' 

        return 'main'
    


    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #clean up callbacks
            context.window.cursor_modal_restore()
            context.area.header_text_set()
            context.user_preferences.themes[0].view_3d.outline_width = self.outline_width
        
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def hover_scene(self,context,x, y):
        scene = context.scene
        region = context.region
        rv3d = context.region_data
        coord = x, y
        ray_max = 10000
        view_vector = region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = region_2d_to_origin_3d(region, rv3d, coord)
        ray_target = ray_origin + (view_vector * ray_max)

        if bversion() <= '002.076.000':
            result, ob, mx, loc, normal = scene.ray_cast(ray_origin, ray_target)
        else:
            result, loc, normal, idx, ob, mx = scene.ray_cast(ray_origin, ray_target)

        if result:
            self.ob = ob
            self.ob_preview = ob.name
            context.area.header_text_set(ob.name)
            
            for obj in context.scene.objects:
                if obj != ob:
                    obj.select = False
                else:
                    obj.select = True
        
        else:
            self.ob = None
            self.ob_preview = 'None'
            context.area.header_text_set('None')
            for ob in context.scene.objects:
                ob.select = False
            if context.object:
                context.scene.objects.active = None
    
    def pick_model(self, context):
        prefs = get_settings()
        if self.ob == None:
            return 'main'
            
        n = context.scene.odc_splint_index
        odc_splint = context.scene.odc_splints[n]
        odc_splint.opposing = self.ob.name
        odc_splint.opposing_set = True
         
        if "Opposing Mat" not in bpy.data.materials:
            mat = bpy.data.materials.new('Opposing Mat')
            mat.diffuse_color = prefs.def_opposing_color
            mat.diffuse_intensity = 1
            mat.emit = 0.0
            mat.specular_intensity = 0.0
        else:
            mat = bpy.data.materials.get('Opposing Mat')
        
        # Assign it to object
        if self.ob.data.materials:
            # assign to 1st material slot
            self.ob.data.materials[0] = mat
        else:
            # no slots
            self.ob.data.materials.append(mat) 
        
        bb_center = get_bbox_center(self.ob)
        T = Matrix.Translation(bb_center)
        iT = T.inverted()
        
        self.ob.data.transform(iT)
        self.ob.matrix_world *= T
            
        tracking.trackUsage("D3Splint:SetOpposing")
        return 'finish'
            
    def invoke(self,context, event):
        
        if not len(context.scene.odc_splints):
            self.report({'ERROR'}, 'Need to set master model first')
            return('CANCELLED')
        
        
        n = context.scene.odc_splint_index
        odc_splint = context.scene.odc_splints[n]
        
        Model = bpy.data.objects.get(odc_splint.model)
        if not Model:
            self.report({'ERROR'}, 'Need to set master model first')
            return('CANCELLED')
        
        self.outline_width = context.user_preferences.themes[0].view_3d.outline_width
        context.user_preferences.themes[0].view_3d.outline_width = 4
        
        self.ob_preview = 'None'
        context.window.cursor_modal_set('EYEDROPPER')
        
        #TODO, tweak the modifier as needed
        help_txt = "Pick Model\n\n Hover over objects and left click on opposing model\n ESC to cancel"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(pick_model_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        
        tracking.trackUsage("D3Splint:PickOpposing", None)
        return {'RUNNING_MODAL'}
    
    
    
class D3SPLINT_OT_pick_external_shell(bpy.types.Operator):
    """Left Click on shell to mark shell from outside software"""
    bl_idname = "d3splint.pick_shell"
    bl_label = "Pick 3rd Party Shell"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        if len(context.scene.odc_splints) == 0:
            return False
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

        
        if event.type == 'MOUSEMOVE':
            self.hover_scene(context, event.mouse_region_x, event.mouse_region_y)    
            return 'main'
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            
            return self.pick_model(context)
        
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            return 'cancel' 

        return 'main'
    
    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #clean up callbacks
            context.window.cursor_modal_restore()
            context.area.header_text_set()
            context.user_preferences.themes[0].view_3d.outline_width = self.outline_width
        
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def hover_scene(self,context,x, y):
        scene = context.scene
        region = context.region
        rv3d = context.region_data
        coord = x, y
        ray_max = 10000
        view_vector = region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = region_2d_to_origin_3d(region, rv3d, coord)
        ray_target = ray_origin + (view_vector * ray_max)

        if bversion() <= '002.076.000':
            result, ob, mx, loc, normal = scene.ray_cast(ray_origin, ray_target)
        else:
            result, loc, normal, idx, ob, mx = scene.ray_cast(ray_origin, ray_target)

        if result:
            self.ob = ob
            self.ob_preview = ob.name
            context.area.header_text_set(ob.name)
            
            for obj in context.scene.objects:
                if obj != ob:
                    obj.select = False
                else:
                    obj.select = True
        
        else:
            self.ob = None
            self.ob_preview = 'None'
            context.area.header_text_set('None')
            for ob in context.scene.objects:
                ob.select = False
            if context.object:
                context.scene.objects.active = None
    
    def pick_model(self, context):
        
        if self.ob == None:
            return 'main'
            
        n = context.scene.odc_splint_index
        odc_splint = context.scene.odc_splints[n]
        
        
        self.ob.name = 'Splint Shell'
        odc_splint.splint_shell = True
        
        
        cons = self.ob.constraints.new('COPY_TRANSFORMS')
        cons.target = bpy.data.objects.get(odc_splint.model)
        
        if "Splint Material" not in bpy.data.materials:
            mat = bpy.data.materials.new(name = 'Splint Material')
            mat.diffuse_color = get_settings().def_splint_color
        else:
            mat = bpy.data.materials.get('Splint Material')
        
        # Assign it to object
        if self.ob.data.materials:
            # assign to 1st material slot
            self.ob.data.materials[0] = mat
        else:
            # no slots
            self.ob.data.materials.append(mat) 
            
        tracking.trackUsage("D3Splint:SetOpposing")
        return 'finish'
            
    def invoke(self,context, event):
        
        if not len(context.scene.odc_splints):
            self.report({'ERROR'}, 'Need to set splint model first')
            return('CANCELLED')
        
        
        n = context.scene.odc_splint_index
        odc_splint = context.scene.odc_splints[n]
        
        Model = bpy.data.objects.get(odc_splint.model)
        if not Model:
            self.report({'ERROR'}, 'Need to set splint model first')
            return('CANCELLED')
        
        self.outline_width = context.user_preferences.themes[0].view_3d.outline_width
        context.user_preferences.themes[0].view_3d.outline_width = 4
        
        self.ob_preview = 'None'
        context.window.cursor_modal_set('EYEDROPPER')
        
        #TODO, tweak the modifier as needed
        help_txt = "Pick Model\n\n Hover over objects and left click on shell model\n ESC to cancel"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(pick_model_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        
        tracking.trackUsage("D3Splint:Pick3rdPartyShell", None)
        return {'RUNNING_MODAL'}
    
class D3SPLINT_OT_pick_external_trim(bpy.types.Operator):
    """Left Click on shell to mark shell from outside software"""
    bl_idname = "d3splint.pick_trimmed_model"
    bl_label = "Pick 3rd Party Trimmed Model"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        if len(context.scene.odc_splints) == 0:
            return False
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

        
        if event.type == 'MOUSEMOVE':
            self.hover_scene(context, event.mouse_region_x, event.mouse_region_y)    
            return 'main'
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            
            return self.pick_model(context)
        
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            return 'cancel' 

        return 'main'
    
    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #clean up callbacks
            context.window.cursor_modal_restore()
            context.area.header_text_set()
            context.user_preferences.themes[0].view_3d.outline_width = self.outline_width
        
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def hover_scene(self,context,x, y):
        scene = context.scene
        region = context.region
        rv3d = context.region_data
        coord = x, y
        ray_max = 10000
        view_vector = region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = region_2d_to_origin_3d(region, rv3d, coord)
        ray_target = ray_origin + (view_vector * ray_max)

        if bversion() <= '002.076.000':
            result, ob, mx, loc, normal = scene.ray_cast(ray_origin, ray_target)
        else:
            result, loc, normal, idx, ob, mx = scene.ray_cast(ray_origin, ray_target)

        if result:
            self.ob = ob
            self.ob_preview = ob.name
            context.area.header_text_set(ob.name)
            
            for obj in context.scene.objects:
                if obj != ob:
                    obj.select = False
                else:
                    obj.select = True
        
        else:
            self.ob = None
            self.ob_preview = 'None'
            context.area.header_text_set('None')
            for ob in context.scene.objects:
                ob.select = False
            if context.object:
                context.scene.objects.active = None
    
    def pick_model(self, context):
        
        if self.ob == None:
            return 'main'
            
        n = context.scene.odc_splint_index
        odc_splint = context.scene.odc_splints[n]
        
        
        self.ob.name = 'Trimmed_Model'
        
        cons = self.ob.constraints.new('COPY_TRANSFORMS')
        cons.target = bpy.data.objects.get(odc_splint.model)
        
        tracking.trackUsage("D3Splint:SetOpposing")
        return 'finish'
            
    def invoke(self,context, event):
        
        if not len(context.scene.odc_splints):
            self.report({'ERROR'}, 'Need to set splint model first')
            return('CANCELLED')
        
        
        n = context.scene.odc_splint_index
        odc_splint = context.scene.odc_splints[n]
        
        Model = bpy.data.objects.get(odc_splint.model)
        if not Model:
            self.report({'ERROR'}, 'Need to set splint model first')
            return('CANCELLED')
        
        self.outline_width = context.user_preferences.themes[0].view_3d.outline_width
        context.user_preferences.themes[0].view_3d.outline_width = 4
        
        self.ob_preview = 'None'
        context.window.cursor_modal_set('EYEDROPPER')
        
        #TODO, tweak the modifier as needed
        help_txt = "Pick Model\n\n Hover over objects and left click on trimmed model\n ESC to cancel"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(pick_model_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        
        tracking.trackUsage("D3Splint:Pick3rdPartyTrim", None)
        return {'RUNNING_MODAL'}
    
    
class D3SPLINT_OT_start_splint_on_opposing(bpy.types.Operator):
    """Start a splint on the opposite model, prepare scene for that workflow"""
    bl_idname = "d3splint.plan_splint_on_opposing"
    bl_label = "Plan Splint on Opposingr"
    bl_options = {'REGISTER', 'UNDO'}
    

    keep_func_surface = bpy.props.BoolProperty(default = False, description = "If True, keep the old functional surface for comparison")
    @classmethod
    def poll(cls, context):
        
        return True
    
    def invoke(self, context, event):
        
        
        return context.window_manager.invoke_props_dialog(self)
         
    def execute(self, context):
        
        #save a copy
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        
        if splint.opposing == '':
            self.report({'ERROR'}, "You can not plan a splint on opposing if you have not marked opposing")
        splint.name = splint.name + "_opposing"
        
        #Items Which Don't Need to be re-done
        #-Pick Model and Pick Opposing, we can deduce this
        #-Set landmarks
        #-Maxillary Curve and Mandibular Curve
        #-Articulator Settings shoudl remain unchanged
        old_model = splint.model
        new_model = splint.opposing
        
        OldModel = bpy.data.objects.get(old_model)
        OldOpposing = bpy.data.objects.get(new_model)
        
        
        model_mat = bpy.data.materials.get('Model Mat')
        opp_mat = bpy.data.materials.get('Opposing Mat')
        
        OldModel.data.materials[0] = opp_mat
        OldOpposing.data.materials[0] = model_mat
        
        if 'Final Splint' in context.scene.objects:
            new_opposing = 'Opposing Splint'
            FinalSplint = bpy.data.objects.get('Final Splint')
            FinalSplint.name = 'Opposing Splint'
            
            context.scene.objects.active = FinalSplint
            FinalSplint.select = True
            for mod in FinalSplint.modifiers:
                try:
                    bpy.ops.object.modifier_apply(modifier = mod.name)
                except:
                    continue
            
            mx = FinalSplint.matrix_world
            FinalSplint.parent = OldModel
            FinalSplint.matrix_world = mx
            FinalSplint.data.materials.append(opp_mat)
            splint.opposing = 'Opposing Splint'
            
            
        else:
            splint.opposing = old_model
        
        splint.model = new_model
        
        #Switch the jaw type   
        if splint.jaw_type == 'MAXILLA':
            splint.jaw_type = 'MANDIBLE'
            PlaneCurve = bpy.data.objects.get('Occlusal Curve Max')
        else:
            splint.jaw_type = 'MAXILLA'
            PlaneCurve = bpy.data.objects.get('Occlusal Curve Mand')
        
        splint.ops_string = ''
        #handle the margin
        Margin = bpy.data.objects.get(splint.margin)
        if Margin:
            context.scene.objects.unlink(Margin)
            crv = Margin.data
            bpy.data.objects.remove(Margin)
            bpy.data.curves.remove(crv)
            
            
        TrimModel = bpy.data.objects.get('Trimmed_Model')
        if TrimModel:
            context.scene.objects.unlink(TrimModel)
            me = TrimModel.data
            bpy.data.objects.remove(TrimModel)
            bpy.data.meshes.remove(me)
        
        BlockoutModel = bpy.data.objects.get('Blockout Wax')
        if BlockoutModel:
            context.scene.objects.unlink(BlockoutModel)
            me = BlockoutModel.data
            bpy.data.objects.remove(BlockoutModel)
            bpy.data.meshes.remove(me)
            
        BaseModel = bpy.data.objects.get('Based_Model')
        if BaseModel:
            context.scene.objects.unlink(BaseModel)
            me = BaseModel.data
            bpy.data.objects.remove(BaseModel)
            bpy.data.meshes.remove(me)
            
        splint.splint = ''
        Splint = bpy.data.objects.get('Splint Shell')
        if Splint:
            context.scene.objects.unlink(Splint)
            me = Splint.data
            bpy.data.objects.remove(Splint)
            bpy.data.meshes.remove(me)
               
        Spacer = bpy.data.objects.get('Passive Spacer')
        if Spacer:
            context.scene.objects.unlink(Spacer)
            me = Spacer.data
            bpy.data.objects.remove(Spacer)
            bpy.data.meshes.remove(me)
        
        splint.splint_outline = False
        splint.trim_upper = False 
        splint.splint_shell = False
        splint.passive_offset = False
        splint.finalize_splint = False
        
        if PlaneCurve:
            me = PlaneCurve.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            mx = PlaneCurve.matrix_world
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
            T = Matrix.Translation(center + 4 * Z)
            T2 = Matrix.Translation(center + 10 * Z)
            
            bme = bmesh.new()
            bme.verts.ensure_lookup_table()
            bme.edges.ensure_lookup_table()
            bme.faces.ensure_lookup_table()
            bmesh.ops.create_grid(bme, x_segments = 200, y_segments = 200, size = 39.9)
            
            
            
            if 'Dynamic Occlusal Surface' not in bpy.data.objects:
                bme.to_mesh(me)
                plane_obj = bpy.data.objects.new('Dynamic Occlusal Surface', me)
            else:
                plane_obj = bpy.data.objects.get('Dynamic Occlusal Surface')
                if self.keep_func_surface:
                    
                    plane_obj.name = 'Functional Surface' + splint.jaw_type[0:3]
                    plane_obj.data.name = 'Functional Surface' + splint.jaw_type[0:3]
                    me = bpy.data.meshes.new('Dynamic Occlusal Surface')
                    plane_obj =bpy.data.objects.new('Dynamic Occlusal Surface', me)
                    context.scene.objects.link(plane_obj)
                   
                bme.to_mesh(plane_obj.data)
            
            plane_obj.matrix_world = T * R
            bme.free()
            
            if splint.jaw_type == 'MAXILLA':
                Target = bpy.data.objects.get(splint.get_maxilla())
            else:
                Target = bpy.data.objects.get(splint.get_mandible())
                
            if 'Child Of' in plane_obj.constraints:
                cons = plane_obj.constraints['Child Of']
            else:
                cons = plane_obj.constraints.new('CHILD_OF')
        
            cons.target = Target
            cons.inverse_matrix = Target.matrix_world.inverted()
        #The opposing functional surfaces can be re-generated if available
        
        #Items Which Must Be Redone
        # - Survey if needed
        # -Splint Perimeter
        # -Splint Shell
        # -Passive Offset
        
        # -Finalize
         
        return {'FINISHED'}
        
    def draw(self, context):
        
        layout = self.layout
        
        row = layout.row()
        row.label('This operator will permanently change this project!')
        row = layout.row()
        row.label('Please save a copy of this .blend file BEFORE changing it')
        row = layout.row()
        row.label('Click outside of this box to cancel and save first')
        row = layout.row()
        row.prop(self, "keep_func_surface")
        
        
        
def register():
    bpy.utils.register_class(D3SPLINT_OT_splint_land_marks)
    bpy.utils.register_class(D3SPLINT_OT_splint_paint_margin)  
    bpy.utils.register_class(D3SPLINT_OT_splint_trim_model_paint)
    bpy.utils.register_class(D3SPLINT_OT_splint_occlusal_arch_max)
    bpy.utils.register_class(D3SPLINT_OT_splint_occlusal_curve_mand)
    bpy.utils.register_class(D3SPLINT_OT_pick_model)
    bpy.utils.register_class(D3SPLINT_OT_pick_opposing)
    bpy.utils.register_class(D3SPLINT_OT_pick_external_shell)
    bpy.utils.register_class(D3SPLINT_OT_start_splint_on_opposing)
     
def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_splint_land_marks)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_paint_margin)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_trim_model_paint)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_occlusal_arch_max)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_occlusal_curve_mand)
    bpy.utils.unregister_class(D3SPLINT_OT_pick_model)
    bpy.utils.unregister_class(D3SPLINT_OT_pick_opposing)
    bpy.utils.unregister_class(D3SPLINT_OT_pick_external_shell)
    bpy.utils.unregister_class(D3SPLINT_OT_start_splint_on_opposing)
    
if __name__ == "__main__":
    register()