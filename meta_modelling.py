'''
Created on Nov 23, 2017

@author: Patrick
'''
import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Color, Quaternion, kdtree
from mathutils.geometry import intersect_point_line, intersect_line_plane
from mathutils.bvhtree import BVHTree

from mesh_cut import edge_loops_from_bmedges, space_evenly_on_path, flood_selection_faces,\
    bound_box
from bpy_extras import view3d_utils
from bpy.props import FloatProperty, BoolProperty, IntProperty, EnumProperty
from textbox import TextBox
from curve import CurveDataManager, PolyLineKnife
from loops_tools import relax_loops_util
from common_utilities import get_settings
from common_drawing import outline_region
import survey_utils
import tracking
import time
import random
import odcutils
from odcutils import get_bbox_center

def arch_crv_draw_callback(self, context):  
    self.crv.draw(context)
    self.help_box.draw()
    prefs = get_settings()
    r,g,b = prefs.active_region_color
    outline_region(context.region,(r,g,b,1))  
    
class D3SPLINT_OT_draw_meta_curve(bpy.types.Operator):
    """Draw a curve on the scene to be used with Meta modelling"""
    bl_idname = "d3splint.draw_meta_scaffold_curve"
    bl_label = "Draw Curve for Wax"
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
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def invoke(self,context, event):
        
        prefs = get_settings()
        self.crv = None
        
        if 'Meta Curve' in context.scene.objects:
            crv_ob = bpy.data.objects.get('Meta Curve')
            context.scene.objects.unlink(crv_ob)
            crv_data = crv_ob.data
            bpy.data.objects.remove(crv_ob)
            bpy.data.curves.remove(crv_data)
            
            
        self.crv = CurveDataManager(context,snap_type ='SCENE', snap_object = None, shrink_mod = False, name = 'Meta Curve')
        self.crv.point_size, self.crv.point_color, self.crv.active_color = prefs.point_size, prefs.def_point_color, prefs.active_point_color
        
        #TODO, tweak the modifier as needed
        help_txt = "DRAW POINTS\n\nLeft Click on scene to define curve \nPoints will snap to objects under mouse \n Right click to delete a point n\ Click the first point to close the loop \n  Left click a point to select, then G to grab  \n ENTER to confirm \n ESC to cancel"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(arch_crv_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        
        tracking.trackUsage("D3Splint:MetaCurveDraw", None)
        return {'RUNNING_MODAL'}

class D3SPLINT_OT_splint_virtual_wax_on_curve(bpy.types.Operator):
    """Create Virtual Wax Object on the user drawn wax curve"""
    bl_idname = "d3splint.virtual_wax_on_curve"
    bl_label = "Virtual Wax on Curve"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    segments = IntProperty(default = 60, description = 'Resolution of the wax elements')
    posterior_width = FloatProperty(default = 4, description = 'Width of wax object at endpoints', name = "Width at End")
    anterior_width = FloatProperty(default = 4, description = 'Width of wax object in the middle', name = "width in Middle")
    thickness = FloatProperty(default = 2, description = 'Height/Thickness of  rim')
    
    
    flare = IntProperty(default = 0, min = -90, max = 90, description = 'Angle off of world Z')
    meta_type = EnumProperty(name = 'Meta Type', items = [('CUBE','CUBE','CUBE'), 
                                                          ('ELLIPSOID', 'ELLIPSOID','ELLIPSOID'),
                                                          ('BALL','BALL','BALL')], default = 'CUBE', description = "Shape of extruded wax object")
    @classmethod
    def poll(cls, context):
        
        if 'Meta Curve' not in context.scene.objects:
            return False
        
        return True
    
    def execute(self, context):
            
        crv_obj = bpy.data.objects.get('Meta Curve')
        crv_data = crv_obj.data
        mx = crv_obj.matrix_world
        imx = mx.inverted()
        
        
        if 'Virtual Wax' in bpy.data.objects:
            meta_obj = bpy.data.objects.get('Virtual Wax')
            meta_data = meta_obj.data
            meta_mx = meta_obj.matrix_world
            meta_obj.hide = False
            
        else:
            meta_data = bpy.data.metaballs.new('Virtual Wax')
            meta_obj = bpy.data.objects.new('Virtual Wax', meta_data)
            meta_data.resolution = .8
            meta_data.render_resolution = .8
            context.scene.objects.link(meta_obj)
            meta_mx = meta_obj.matrix_world
        
        meta_imx = meta_mx.inverted()
            
        me = crv_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme = bmesh.new()
        bme.from_mesh(me)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in bme.edges])
            
        
        vs0 = [bme.verts[i].co for i in loops[0]]
        
        
        vs_even_0, eds0 = space_evenly_on_path(vs0, [(0,1),(1,2)], self.segments)
        
        
        Z = mx.inverted().to_3x3() * Vector((0,0,1))
        Z.normalize()
            
        for i in range(1,len(vs_even_0)-1):
            
            #factor that tapers end to middle to end
            blend = -abs((i-self.segments/2)/(self.segments/2))+1
            
            v0_0 = vs_even_0[i]
            v0_p1 = vs_even_0[i+1]
            v0_m1 = vs_even_0[i-1]

            

            mb = meta_data.elements.new(type = self.meta_type)
            loc = mx * v0_0           
            if self.meta_type in {'CUBE', 'ELLIPSOID'}:
                X = v0_p1 - v0_m1
                X.normalize()
                
                Qrot = Quaternion(X, math.pi/180 * self.flare)
                Zprime = Qrot * Z
                
                Y = Zprime.cross(X)
                X_c = Y.cross(Zprime) #X corrected
                
                T = Matrix.Identity(3)
                T.col[0] = X_c
                T.col[1] = Y
                T.col[2] = Zprime
                quat = T.to_quaternion()
                
            
            
            
            
                mb.size_y = .4 *  (blend*self.anterior_width + (1-blend)*self.posterior_width)
                mb.size_z = self.thickness/2
                mb.size_x = 1.5
                mb.rotation = quat
            
            else:
                mb.radius = self.thickness/2
                
            mb.stiffness = 2
            mb.co = meta_imx * loc
            
        
        
        context.scene.update()
        #me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        #new_ob = bpy.data.objects.new('Flat Plane', me)
        #context.scene.objects.link(new_ob)
        #new_ob.matrix_world = mx

        #context.scene.objects.unlink(meta_obj)
        #bpy.data.objects.remove(meta_obj)
        #bpy.data.metaballs.remove(meta_data)
        
        mat = bpy.data.materials.get("Splint Material")
        if mat is None:
            # create material
            mat = bpy.data.materials.new(name="Splint Material")
            mat.diffuse_color = get_settings().def_splint_color
            mat.use_transparency = True
            mat.transparency_method = 'Z_TRANSPARENCY'
            mat.alpha = .4
        
        if mat.name not in meta_obj.data.materials:
            meta_obj.data.materials.append(mat)
        
        bme.free()
        #todo remove/delete to_mesh mesh
  
        return {'FINISHED'}

    
    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)



class D3SPLINT_OT_surgical_bite_positioner(bpy.types.Operator):
    """Create Meta Wax Rim previously defined maxillary and mandibular curves"""
    bl_idname = "d3splint.surgical_bite_appliance"
    bl_label = "Create Bite Wafer"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    meta_type = EnumProperty(name = 'Meta Type', items = [('CUBE','CUBE','CUBE'), ('ELLIPSOID', 'ELLIPSOID','ELLIPSOID')], default = 'CUBE')
    
    width_offset = FloatProperty(name = 'Extra Wdith', default = 0.01, min = -3, max = 3)
    
    thickenss_offset = FloatProperty(name = 'Extra Thickness', default = 0.01, min = -3, max = 3)
    
    anterior_projection = FloatProperty(name = 'Extra Anterior Width', default = 0.01, min = -2, max = 3)
    
    
    flare = IntProperty(default = 0, min = -60, max = 60, description = 'Angle off of world Z')
    anterior_segement = FloatProperty(name = 'AP Spread', default = 0.3, min = .15, max = .5)
    ap_segment = EnumProperty(name = 'Rim Area', items = [('ANTERIOR_ONLY','Anterior Ramp','Only builds rim anterior to AP spread'),
                                                          ('POSTERIOR_ONLY', 'Posterior Pad','ONly builds rim posterior to AP spread'),
                                                          ('FULL_RIM', 'Full Rim', 'Buillds a posterior pad and anteiror ramp')], default = 'FULL_RIM')
    
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
        

        tracking.trackUsage("D3Splint:SurgicalBitePositioner",None)
        

        max_crv_data = MaxCurve.data
        mx_max = MaxCurve.matrix_world
        imx_max = mx_max.inverted()
        
        
        mand_crv_data = MandCurve.data
        mx_mand = MandCurve.matrix_world
        imx_mand = mx_mand.inverted()
        
        
        print('got curve object')
        
        meta_data = bpy.data.metaballs.new('Splint Wax Rim')
        meta_obj = bpy.data.objects.new('Meta Surface', meta_data)
        meta_data.resolution = .4
        meta_data.render_resolution = .4
        context.scene.objects.link(meta_obj)
        
        #get world path of the maxillary curve
        me_max = MaxCurve.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme_max = bmesh.new()
        bme_max.from_mesh(me_max)
        bme_max.verts.ensure_lookup_table()
        bme_max.edges.ensure_lookup_table()
        loops = edge_loops_from_bmedges(bme_max, [ed.index for ed in bme_max.edges])
        vs0 = [mx_max * bme_max.verts[i].co for i in loops[0]]
        vs_even_max, eds0 = space_evenly_on_path(vs0, [(0,1),(1,2)], 100)
        
        #get world path of the mandibular curve
        me_mand = MandCurve.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme_mand = bmesh.new()
        bme_mand.from_mesh(me_mand)
        bme_mand.verts.ensure_lookup_table()
        bme_mand.edges.ensure_lookup_table()
        loops = edge_loops_from_bmedges(bme_mand, [ed.index for ed in bme_mand.edges])
        vs0 = [mx_mand * bme_mand.verts[i].co for i in loops[0]]
        vs_even_mand, eds0 = space_evenly_on_path(vs0, [(0,1),(1,2)], 100)
        
        
        #check for tip to tail
        if (vs_even_mand[0] - vs_even_max[0]).length > (vs_even_mand[0] - vs_even_max[-1]).length:
            print('reversing the mandibular curve')
            vs_even_mand.reverse()
        
        Z = Vector((0,0,1))
        
        
        max_x = max(vs_even_max, key = lambda x: x[0])
        min_x = min(vs_even_max, key = lambda x: x[0])
        A_ap = max_x[0]
        P_ap = min_x[0]
        ap_spread = max_x[0] - min_x[0]
        
        
        for i in range(1,len(vs_even_max)-1):
            
            #use maxilary curve for estimattino
            
            v0_0 = vs_even_max[i]
            v0_p1 = vs_even_max[i+1]
            v0_m1 = vs_even_max[i-1]

            v0_mand = vs_even_mand[i]
            center = .5 *  v0_0 + 0.5 * v0_mand
            
            size_z = max(1, abs(v0_0[2] - v0_mand[2] - 1))
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
            
            if v0_0[0] > P_ap + (1-self.anterior_segement) * ap_spread:
                if self.ap_segment == 'POSTERIOR_ONLY': continue
                mb = meta_data.elements.new(type = self.meta_type)
                mb.size_x = 1.5
                Qrot = Quaternion(X_c, math.pi/180 * self.flare)
                Zprime = Qrot * Z
            
                Y_c = Zprime.cross(X_c)
            
            
                T = Matrix.Identity(3)
                T.col[0] = X_c
                T.col[1] = Y_c
                T.col[2] = Zprime
                quat = T.to_quaternion()
                
                if v0_0[0] > A_ap - self.anterior_segement * ap_spread + .25 * self.anterior_segement * ap_spread:
                    mb.size_y =  max(.5 * (size_y - 1.5 + self.width_offset) + self.anterior_projection, 1)
                    mb.size_z = max(.35 * size_z + .5 * self.thickenss_offset, .75)
                    mb.co = center + (.5 * self.width_offset + self.anterior_projection) * Y_c
                    mb.rotation = quat
                else:
                    blend =  (v0_0[0] - (A_ap - self.anterior_segement * ap_spread))/(.25 * self.anterior_segement * ap_spread)
                    mb.size_y =  max(.5 * (size_y - 1.5 + self.width_offset) + blend * self.anterior_projection, 1)
                    mb.size_z = max(.35 * size_z + .5 * self.thickenss_offset, .75)
                    mb.co = center + (.5 * self.width_offset + blend * self.anterior_projection) * Y_c
                    mb.rotation = quat
            else:          
                if self.ap_segment == 'ANTERIOR_ONLY': continue
                mb = meta_data.elements.new(type = self.meta_type)
                mb.size_x = 1.5
                mb.size_y = max(.5 * (size_y - 1.5) + self.width_offset, 1)
                mb.size_z = max(.35 * size_z + .5 * self.thickenss_offset, .75)
                mb.co = center
                
                mb.rotation = quat
            mb.stiffness = 2
            
            
        context.scene.update()
        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        
        if 'Splint Shell' not in bpy.data.objects:
            new_ob = bpy.data.objects.new('Splint Shell', me)
            context.scene.objects.link(new_ob)
            
            mat = bpy.data.materials.get("Splint Material")
            if mat is None:
            # create material
                mat = bpy.data.materials.new(name="Splint Material")
                mat.diffuse_color = get_settings().def_splint_color
                mat.use_transparency = True
                mat.transparency_method = 'Z_TRANSPARENCY'
                mat.alpha = .4
            new_ob.data.materials.append(mat)
            
        else:
            new_ob = bpy.data.objects.get('Splint Shell')
            new_ob.data = me
            new_ob.hide = False

        center = get_bbox_center(new_ob, world=True)
        Tmx = Matrix.Translation(center)
        iTmx = Tmx.inverted()
        
        new_ob.matrix_world *= iTmx
        new_ob.data.transform(Tmx) 
        
        context.scene.objects.unlink(meta_obj)
        bpy.data.objects.remove(meta_obj)
        bpy.data.metaballs.remove(meta_data)
        
        bme_max.free()
        bme_mand.free()
        #todo remove/delete to_mesh mesh
  
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        splint.ops_string += 'SplintShellSurgicalWafer:'
        return {'FINISHED'}

    
    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)
    
class D3SPLINT_OT_anterior_deprogrammer_element(bpy.types.Operator):
    """Create an anterior deprogrammer ramp"""
    bl_idname = "d3splint.anterior_deprogrammer_element"
    bl_label = "Anterior Deprogrammer ELement"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    guidance_angle = IntProperty(default = 15, min = -90, max = 90, description = 'Angle off of world Z')
    anterior_length = FloatProperty(default = 5, description = 'Length of anterior ramp')
    posterior_length = FloatProperty(default = 10, description = 'Length of posterior ramp')
    posterior_width = FloatProperty(default = 10, description = 'Posterior Width of ramp')
    anterior_width = FloatProperty(default = 8, description = 'Anterior Width of ramp')
    thickness = FloatProperty(default = 2.75, description = 'Thickness of ramp')
    support_height = FloatProperty(default = 3, description = 'Height of support strut')
    support_width =  FloatProperty(default = 6, description = 'Width of support strut')
    
    
    @classmethod
    def poll(cls, context):
        
        return True
    def invoke(self, context, event):
        settings = get_settings()
        
        self.guidance_angle = settings.def_guidance_angle
        self.anterior_length = settings.def_anterior_length 
        self.posterior_length = settings.def_posterior_length 
        self.posterior_width = settings.def_posterior_width
        self.anterior_width = settings.def_anterior_width 
        self.thickness = settings.def_thickness
        self.support_height = settings.def_support_height
        self.support_width = settings.def_support_width
        
        return context.window_manager.invoke_props_dialog(self)
        
    def execute(self, context):
            
        loc = context.scene.cursor_location
        
        
        bme = bmesh.new()
        
        RMx = Matrix.Rotation(self.guidance_angle * math.pi/180, 3, 'Y')
        
        
        v0 =  bme.verts.new(RMx * Vector((self.anterior_length, .5 * (self.anterior_width - 2), -self.thickness)))
        v1 =  bme.verts.new(RMx * Vector((self.anterior_length, -.5 * (self.anterior_width - 2), -self.thickness)))
        v2 =  bme.verts.new(RMx * Vector((-self.posterior_length, -.5 * (self.posterior_width - 2), -self.thickness)))
        v3 =  bme.verts.new(RMx * Vector((-self.posterior_length, .5 * (self.posterior_width - 2), -self.thickness)))
        
        bme.faces.new([v0, v1, v2, v3])
        
        v4 =  bme.verts.new(RMx * Vector((self.anterior_length, .5 * self.anterior_width, -self.thickness + 1)))
        v5 =  bme.verts.new(RMx * Vector((self.anterior_length, -.5 * self.anterior_width, -self.thickness + 1)))
        v6 =  bme.verts.new(RMx * Vector((-self.posterior_length, -.5 * self.posterior_width, -self.thickness + 1)))
        v7 =  bme.verts.new(RMx * Vector((-self.posterior_length, .5 * self.posterior_width, -self.thickness + 1)))
        
        
        bme.faces.new([v4, v5, v1, v0])
        bme.faces.new([v5, v6, v2, v1])
        bme.faces.new([v6, v7, v3, v2])
        bme.faces.new([v7, v4, v0, v3])

        v8 = bme.verts.new(RMx * Vector((self.anterior_length, .5 * self.anterior_width, 0)))
        v9 = bme.verts.new(RMx * Vector((self.anterior_length, -.5 * self.anterior_width, 0)))
        v10 = bme.verts.new(RMx * Vector((-self.posterior_length, -.5 * self.posterior_width, 0)))
        v11 = bme.verts.new(RMx * Vector((-self.posterior_length, .5 * self.posterior_width, 0)))

        bme.faces.new([v8, v9, v5, v4])
        bme.faces.new([v9, v10, v6, v5])
        bme.faces.new([v10, v11, v7, v6])
        bme.faces.new([v11, v8, v4, v7])
        
        
        v12  =  bme.verts.new(Vector((.5 * self.support_width, .5 * self.anterior_width, self.support_height)))
        v13  =  bme.verts.new(Vector((.5 * self.support_width, -.5 * self.anterior_width, self.support_height)))
        v14 =  bme.verts.new(Vector((-.5 * self.support_width, -.5 * self.posterior_width, self.support_height)))
        v15 =  bme.verts.new(Vector((-.5 * self.support_width, .5 * self.posterior_width, self.support_height)))    
        
        bme.faces.new([v12, v13, v9, v8])
        bme.faces.new([v13, v14, v10, v9])
        bme.faces.new([v14, v15, v11, v10])
        bme.faces.new([v15, v12, v8, v11])
        
        
        bme.faces.new([v15, v14, v13, v12])
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        e0 = bme.edges[0]
        e2 = bme.edges[2]
        bevel_verts = [e0.verts[0].index, e0.verts[1].index, e2.verts[0].index, e2.verts[1].index]
        
        bme.normal_update()
        #gdict = bmesh.ops.bevel(bme, geom = [e0.verts[0], e0.verts[1], e0], offset = 1) #, offset = .5, offset_type = 1, segments = 2, profile = .3, vertex_only = False, clamp_overlap = True)
        #gdict = bmesh.ops.bevel(bme, geom = [e2.verts[0], e2.verts[1], e2], offset = 1)
        
        
        if "Anterior Deprogrammer" in bpy.data.objects:
            ob = bpy.data.objects.get('Anterior Deprogrammer')
            me = ob.data
            ob.hide = False
            
        else:
            me = bpy.data.meshes.new('Anterior Deprogrammer')
            ob = bpy.data.objects.new('Anterior Deprogrammer', me)
            context.scene.objects.link(ob)
            ob.location = loc
            
            b1 = ob.modifiers.new('Bevel', type = 'BEVEL')
            b1.width = .5
            b1.segments = 3

            rm = ob.modifiers.new('Remesh', type = 'REMESH')
            rm.octree_depth = 6
            rm.mode = 'SMOOTH'
        
        bme.to_mesh(me)
        bme.free()
                
        
        
        
        return {'FINISHED'}

    



class D3SPLINT_OT_splint_join_depro_to_shell(bpy.types.Operator):
    """Join Deprogrammer Element to Shell"""
    bl_idname = "d3splint.splint_join_deprogrammer"
    bl_label = "Join Deprogrammer to Shell"
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
        Rim = bpy.data.objects.get('Anterior Deprogrammer')
        
        if Shell == None:
            self.report({'ERROR'}, 'Need to calculate splint shell first')
        
        if Rim == None:
            self.report({'ERROR'}, 'Need to add a deprogrammer')
            
        tracking.trackUsage("D3Splint:JoinDeprogrammer",None)
        
        bool_mod = Shell.modifiers.new('Join Rim', type = 'BOOLEAN')
        bool_mod.operation = 'UNION'
        bool_mod.object = Rim
        bool_mod.solver = 'CARVE'
        Rim.hide = True
        Shell.hide = False
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        splint.ops_string += 'JoinDeprogrammer: ' 
        return {'FINISHED'}
    
    
class D3SPLINT_OT_splint_join_meta_to_shell(bpy.types.Operator):
    """Join Meta Element to Shell"""
    bl_idname = "d3splint.splint_join_meta_shell"
    bl_label = "Join Virtual Wax to Shell"
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
        Rim = bpy.data.objects.get('Virtual Wax')
        
        if Shell == None:
            self.report({'ERROR'}, 'Need to calculate splint shell first')
            return {'CANCELLED'}
        
        if Rim == None:
            self.report({'ERROR'}, 'Need to add virtual wax first')
            return {'CANCELLED'}
        if len(Rim.data.elements) == 0:
            self.report({'ERROR'}, 'No new virtual wax to fuse')
            return {'CANCELLED'}
             
        tracking.trackUsage("D3Splint:JoinVirtualWax",None)
        
        rim_me = Rim.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW' )
        rim_ob = bpy.data.objects.new('Virtual Wax Mesh', rim_me)
        rim_ob.matrix_world = Rim.matrix_world
        
        context.scene.objects.link(rim_ob)
        bool_mod = Shell.modifiers.new('Join Rim', type = 'BOOLEAN')
        bool_mod.operation = 'UNION'
        bool_mod.object = rim_ob
        Rim.hide = True
        
        for ele in Rim.data.elements:
            Rim.data.elements.remove(ele)
            
        rim_ob.hide = True
        Shell.hide = False
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        splint.ops_string += 'JoinRim:VirtualWax' 
        return {'FINISHED'}
    
class D3SPLINT_OT_blockout_splint_shell(bpy.types.Operator):
    '''Blockout large undercuts in the splint'''
    bl_idname = "d3splint.meta_blockout_shell"
    bl_label = "Meta Blockout Shell"
    bl_options = {'REGISTER','UNDO'}
    
    world = bpy.props.BoolProperty(default = True, name = "Use world coordinate for calculation...almost always should be true.")
    #smooth = bpy.props.BoolProperty(default = True, name = "Smooth the outline.  Slightly less acuurate in some situations but more accurate in others.  Default True for best results")
    resolution = FloatProperty(default = 1.5, min = 0.5, max =3, description = 'Mesh resolution. Lower numbers are slower, bigger numbers less accurate')
    threshold = FloatProperty(default = .09, min = .001, max = .2, description = 'angle to blockout.  .09 is about 5 degrees, .17 is 10degrees.0001 no undercut allowed.')
    
    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        return  True
    
    def execute(self, context):
        tracking.trackUsage("D3Splint:BlockoutSplintConcavities",None)
        
        Shell = bpy.data.objects.get('Splint Shell')
        if Shell == None:
            self.report({'ERROR'},'Need to have a splint shell created')
            return {'CANCELLED'}
                

        if len(Shell.modifiers):
            old_data = Shell.data
            new_data = Shell.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            
            for mod in Shell.modifiers:
                Shell.modifiers.remove(mod)
            
            Shell.data = new_data
            bpy.data.meshes.remove(old_data)       
            print('Applied modifiers')
        
        #if False:
        #    context.scene.objects.active = Shell
        #    Shell.select = True
        #    bpy.ops.object.mode_set(mode = 'SCULPT')
        #    if not Shell.use_dynamic_topology_sculpting:
        #        bpy.ops.sculpt.dynamic_topology_toggle()
        #    context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
        #    context.scene.tool_settings.sculpt.constant_detail_resolution = 2
        #    bpy.ops.sculpt.detail_flood_fill()
        #    bpy.ops.object.mode_set(mode = 'OBJECT')
        
        #careful, this can get expensive with multires    
        bme = bmesh.new()
        bme.from_mesh(Shell.data)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        bme.normal_update()
        
        bvh = BVHTree.FromBMesh(bme)
        #keep track of the world matrix
        
        Z = Vector((0,0,1))  #the splint is more more less aligned with occlusal plane
        
        mx = Shell.matrix_world
        epsilon = .000009
        undercut_vectors = []
        verts_seen = set()
        
        radius = .5
        S = 6
        
        
        for f in bme.faces:
            if f.normal.dot(Z) > self.threshold:
                for v in f.verts:
                    if v in verts_seen: continue
                    
                    loc, no, ind, d = bvh.ray_cast(v.co + epsilon * Z, Z)
                    if not loc: continue
                    if no.dot(Z) > epsilon: continue 
                    if loc and d > radius/2:
                        undercut_vectors += [(v.co, loc, d)]
                
            elif f.normal.dot(Z) < -self.threshold:
                for v in f.verts:
                    if v in verts_seen: continue
                    
                    loc, no, ind, d = bvh.ray_cast(v.co - epsilon * Z, -Z)
                    if not loc: continue
                    if no.dot(Z) < -epsilon: continue 
                    if loc and d > radius/2:
                        undercut_vectors += [(v.co, loc, d)]
        
        
        
        #bme_new = bmesh.new()
        #for ele in undercut_vectors:
        #    v0 = bme_new.verts.new(ele[0])
        #    v1 = bme_new.verts.new(ele[1])
        #    bme_new.edges.new((v0, v1))
            
            
        #me = bpy.data.meshes.new('Skeleton')
        #ob = bpy.data.objects.new('Skeleton', me)
        #bme_new.to_mesh(me)
        #ob.matrix_world = mx
        #context.scene.objects.link(ob)
        #bme_new.free()
        #bme.free()
        #return {'FINISHED'}
        
        print('found %i undercut vectors' % len(undercut_vectors))
        
        if 'Splint Blockot Meta' in bpy.data.metaballs:
            
            print('cleaning out old metaball data')
            meta_data = bpy.data.metaballs.get('Splint Blockout Meta')
            meta_obj = bpy.data.objects.get('Blockout Mesh')
            for ele in meta_data.elements:
                meta_data.elements.remove(ele)
                
            print('cleaned out old metaball data')
        else:
            meta_data = bpy.data.metaballs.new('Splint Blockout Meta')
            meta_obj = bpy.data.objects.new('Blockout Mesh', meta_data)
            meta_data.resolution = self.resolution
            meta_data.render_resolution = self.resolution
            context.scene.objects.link(meta_obj)
        
        print('adding in new metaball data')
        for ele in undercut_vectors:
            
            
            mb = meta_data.elements.new(type = 'BALL')
            mb.co = S * ele[0]
            mb.radius = S * radius
            
            mb = meta_data.elements.new(type = 'BALL')
            mb.co = S * ele[1]
            mb.radius = S * radius
            
            vec = ele[1] - ele[0]
            steps = math.ceil(2 * vec.length/radius)
            vec.normalize() 
               
            for i in range(0,steps):
                mb = meta_data.elements.new(type = 'BALL')
                mb.co = S * ( ele[0] + i * radius/2 *  vec)
                mb.radius = S * radius
            
            
        print('added in new metaball data')
        q = mx.to_quaternion()
        Rmx = q.to_matrix().to_4x4()
        L = Matrix.Translation(mx.to_translation())
        Smx = Matrix.Scale(1/S, 4)
         
        print('setting world matrix')  
        meta_obj.matrix_world =  L * Rmx * Smx
        print('udating scene')
        context.scene.update()
        print('getting meta mesh')
        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        print('got meta mesh')
        
        bme.free()
        del bvh
        
        print('freed bmesh and made a new one')
        bme = bmesh.new()
        bme.from_mesh(me)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        bme.transform(L * Rmx * Smx)
        
        total_faces = set(bme.faces[:])
        islands = []
        iters = 0
        while len(total_faces) and iters < 100:
            iters += 1
            seed = total_faces.pop()
            island = flood_selection_faces(bme, {}, seed, max_iters = 10000)
            islands += [island]
            total_faces.difference_update(island)
            
        del_faces = set()
        for isl in islands:
            if len(isl) < 3000:
                del_faces.update(isl)
        
        bmesh.ops.delete(bme, geom = list(del_faces), context = 3)
        del_verts = []
        for v in bme.verts:
            if all([f in del_faces for f in v.link_faces]):
                del_verts += [v]        
        bmesh.ops.delete(bme, geom = del_verts, context = 1)
        
        
        del_edges = []
        for ed in bme.edges:
            if len(ed.link_faces) == 0:
                del_edges += [ed]
        bmesh.ops.delete(bme, geom = del_edges, context = 4) 
            
        bme.to_mesh(me)
        bme.free()
        
        b_ob = bpy.data.objects.new('Splint Blockout', me)
        #b_ob.matrix_world = Shell.matrix_world
        context.scene.objects.link(b_ob)
        
        context.scene.objects.unlink(meta_obj)
        bpy.data.objects.remove(meta_obj)
        bpy.data.metaballs.remove(meta_data)
        
        mod = Shell.modifiers.new('Blockout', type = 'BOOLEAN')
        mod.operation = 'UNION'
        mod.solver = 'CARVE'
        mod.object = b_ob
        
        b_ob.hide = True
        return {'FINISHED'}        

class D3SPLINT_OT_blockout_trimmed_model(bpy.types.Operator):
    '''Calculates selective blockout for model'''
    bl_idname = 'd3splint.meta_blockout_trimmed_model'
    bl_label = "Blockout Trimmed Model"
    bl_options = {'REGISTER','UNDO'}
    
    
    radius = FloatProperty(default = .05 , min = .01, max = .12, description = 'Allowable Undercut', name = 'Undercut')
    resolution = FloatProperty(default = 1.5, description = 'Mesh resolution. 1.5 seems ok?')
    scale = FloatProperty(default = 10, description = 'Scale up to make it better')
    
    meta_type = EnumProperty(name = 'Meta Type', items = [ ('CYLINDER', 'CYLINDER','CYLINDER'),('ELLIPSOID', 'ELLIPSOID','ELLIPSOID')], default = 'ELLIPSOID')
    
    
    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        return  True

    def invoke(self,context, evenet):
        Axis = bpy.data.objects.get('Insertion Axis')
        if Axis == None:
            self.report({'ERROR'},'Need to set survey from view first, then adjust axis arrow')
            return {'CANCELLED'}
        
        if len(context.scene.odc_splints) == 0:
            self.report({'ERROR'},'Need to plan a splint first')
            return {'CANCELLED'}
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        axis_z = Axis.matrix_world.to_quaternion() * Vector((0,0,1))
        
        angle = axis_z.angle(Vector((0,0,1)))
        angle_deg = 180/math.pi * angle
        
        if angle_deg > 25:
            self.angle = angle_deg
        
        
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        
        settings = get_settings()
        dbg = settings.debug
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        
        Model = bpy.data.objects.get(splint.model)
        if Model == None:
            self.report({'ERROR'},'Need to set the model first')
            return {'CANCELLED'}
        
        Axis = bpy.data.objects.get('Insertion Axis')
        if Axis == None:
            self.report({'ERROR'},'Need to set survey from view first, then adjust axis arrow')
            return {'CANCELLED'}
        
        
        start = time.time()
        interval_start = start
        
        
        ob = bpy.data.objects.get('Based_Model')
        ob1 = bpy.data.objects.get('Trimmed_Model')
        if not ob:
            self.report({'ERROR'}, 'Must trim the upper model first')
            return {'CANCELLED'}
        
        if not ob1:
            self.report({'ERROR'}, 'Must trim the upper model first')
            return {'CANCELLED'}
        
        if not ob.modifiers.get('Displace'):
            self.report({'ERROR'}, 'New version requires you to Trim the Model again')
            return {'CANCELLED'}
        

        bme = bmesh.new()
        bme.from_object(ob1, context.scene)  #this object should have a displace modifier
        bme.verts.ensure_lookup_table()
        
        
        mx = Model.matrix_world
        
        axis_z = Axis.matrix_world.to_quaternion() * Vector((0,0,1))
        i_mx = mx.inverted()
        local_axis_z = i_mx.to_quaternion() * axis_z
        local_axis_z.normalize()
        
        meta_data = bpy.data.metaballs.new('Blockout Meta')
        meta_obj = bpy.data.objects.new('Blockout Meta', meta_data)
        meta_data.resolution = self.resolution
        meta_data.render_resolution = self.resolution
        context.scene.objects.link(meta_obj)
        
        min_bv = max(self.bme.verts, key = lambda x: x.co[2])
        z_flat = min_bv.co
   
        n_elements = 0
        for v in bme.verts:
            if not len(v.link_edges): continue
            
            co = v.co - .22 * v.normal
            R = .5 * max([ed.calc_length() for ed in v.link_edges])
            
            Z = v.normal 
            Z.normalize()
            
            size_x = self.scale * R
            size_y = self.scale * R
            size_z = self.scale * (.22 - .05 - self.radius )
            
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
            quat = Rotation_Matrix.to_quaternion()
        
            height = z_flat[2] - co[2] + .5
            co_mid = co + .5 * (height - .5) * Vector((0,0,1))  #TODO MAX vs MAND
        
            N = math.ceil(height/.2)
            for i in range(0,N):
                n_elements += 1
                if self.meta_type == 'ELLIPSOID':
                    mb = meta_data.elements.new(type = 'ELLIPSOID')
                    mb.co = self.scale * (co - i * .2 * local_axis_z)
                
                    mb.size_x = size_x
                    mb.size_y = size_y
                    mb.size_z = size_z
                    mb.rotation = quat
                

        print('finished adding metaballs at %f' % (time.time() - start)) 
        print('added %i metaballs' % n_elements)
        R = mx.to_quaternion().to_matrix().to_4x4()
        L = Matrix.Translation(mx.to_translation())
        S = Matrix.Scale(.1, 4)
           
        meta_obj.matrix_world =  L * R * S

        print('transformed the meta ball object %f' % (time.time() - start))
        context.scene.update()
        print('updated the scene %f' % (time.time() - start))
        

        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        
        if 'Blockout Wax' in bpy.data.objects:
            new_ob = bpy.data.objects.get('Blockout Wax')
            old_data = new_ob.data
            new_ob.data = me
            old_data.user_clear()
            bpy.data.meshes.remove(old_data)
        else:
            new_ob = bpy.data.objects.new('Blockout Wax', me)
            context.scene.objects.link(new_ob)
        
        new_ob.matrix_world = L * R * S
        mat = bpy.data.materials.get("Blockout Material")
        if mat is None:
            # create material
            mat = bpy.data.materials.new(name="Blockout Material")
            mat.diffuse_color = Color((0.8, .1, .1))
        
        
        if len(new_ob.material_slots) == 0:
            new_ob.data.materials.append(mat)
        
        interval_start = time.time()
        if 'Smooth' not in new_ob.modifiers:
            mod = new_ob.modifiers.new('Smooth', type = 'SMOOTH')
            mod.factor = 1
            mod.iterations = 4
        
        else:
            mod = new_ob.modifiers.get('Smooth')
            
        context.scene.objects.active = new_ob
        new_ob.select = True
        bpy.ops.object.modifier_apply(modifier = 'Smooth')
        
        
        if 'Child Of' not in new_ob.constraints:
            Master = bpy.data.objects.get(splint.model)
            cons = new_ob.constraints.new('CHILD_OF')
            cons.target = Master
            cons.inverse_matrix = Master.matrix_world.inverted()
         
        context.scene.objects.unlink(meta_obj)
        bpy.data.objects.remove(meta_obj)
        bpy.data.metaballs.remove(meta_data)
        
        bme.free()
        
        for ob in context.scene.objects:
            if "silhouette" in ob.name:
                ob.hide = False 
            else:
                ob.hide = True
            
        Model.hide = False
        new_ob.hide = False
        
        return {'FINISHED'}
    

class D3SPLINT_OT_blockout_trimmed_model2(bpy.types.Operator):
    '''Calculates selective blockout for model'''
    bl_idname = 'd3splint.meta_blockout_trimmed_model2'
    bl_label = "Blockout Trimmed Model2"
    bl_options = {'REGISTER','UNDO'}
    
    
    radius = FloatProperty(default = .05 , min = .01, max = .12, description = 'Allowable Undercut', name = 'Undercut')
    resolution = FloatProperty(default = 1.5, description = 'Mesh resolution. 1.5 seems ok?')
    scale = FloatProperty(default = 10, description = 'Scale up to make it better')
    
    meta_type = EnumProperty(name = 'Meta Type', items = [ ('CYLINDER', 'CYLINDER','CYLINDER'),('ELLIPSOID', 'ELLIPSOID','ELLIPSOID')], default = 'ELLIPSOID')
    
    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        return  True

    def invoke(self,context, evenet):
        
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        
        settings = get_settings()
        dbg = settings.debug
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        
        Model = bpy.data.objects.get(splint.model)
        if Model == None:
            self.report({'ERROR'},'Need to set the model first')
            return {'CANCELLED'}
        
        Axis = bpy.data.objects.get('Insertion Axis')
        if Axis == None:
            self.report({'ERROR'},'Need to set survey from view first, then adjust axis arrow')
            return {'CANCELLED'}
        
        
        start = time.time()
        interval_start = start
        
        ob1 = bpy.data.objects.get('Trimmed_Model')

        if not ob1:
            self.report({'ERROR'}, 'Must trim the upper model first')
            return {'CANCELLED'}
        
        bme = bmesh.new()
        bme_pp = bmesh.new()
        
        bme.from_mesh(ob1.data)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        interval_start = time.time()
        #Pre process an offset and a smoothing
        
        me = bpy.data.meshes.new('Temp Offset')
        ob2 = bpy.data.objects.new('Temp Offset', me)
        context.scene.objects.link(ob2)
        bme.to_mesh(ob2.data)
        ob2.matrix_world = ob1.matrix_world
        
        
        mod1 = ob2.modifiers.new('Displace', type = 'DISPLACE')
        mod1.mid_level = 1 - (.22 + self.radius)
        mod1.strength = -1
        
        mod2 = ob2.modifiers.new('Smooth', type = 'SMOOTH')
        mod2.iterations = 20
        
        
        mod3 = ob2.modifiers.new('Shrinkwrap', type = 'SHRINKWRAP')
        mod3.target = ob1
        mod3.offset = .22 + self.radius
        
        mod4 = ob2.modifiers.new('Smooth', type = 'SMOOTH')
        mod4.iterations = 10
        
        bme_pp.from_object(ob2, context.scene)
        bme_pp.verts.ensure_lookup_table()
        bme_pp.edges.ensure_lookup_table()
        bme_pp.faces.ensure_lookup_table()
        
        print('Finished pre-processing in %f' % (time.time() - interval_start))
        interval_start = time.time()
        
        
        mx = ob1.matrix_world
        axis_z = Axis.matrix_world.to_quaternion() * Vector((0,0,1))
        i_mx = mx.inverted()
        local_axis_z = i_mx.to_quaternion() * axis_z
        local_axis_z.normalize()
        
        undercut_verts = set()
        for f in bme.faces:
            if f.normal.dot(local_axis_z) < -.01:
                undercut_verts.update([v for v in f.verts])
        
        perimeter_verts = set()
        perimeter_faces = set()
        for ed in bme.edges:
            if len(ed.link_faces) == 1:
                perimeter_verts.update([ed.verts[0], ed.verts[1]])
                for v in ed.verts:
                    perimeter_faces.update([f for f in v.link_faces])
        

        #often the verts at the perimeter get mislabeled.  We will handle them
        #for f in perimeter_faces:
        #    undercut_verts.difference_update([v for v in f.verts])
        
        fit_plane_co = Vector((0,0,0))
        for v in perimeter_verts:
            fit_plane_co += v.co
        
        fit_plane_co *= 1/len(perimeter_verts)
        fit_plane_no = odcutils.calculate_plane([v.co for v in list(perimeter_verts)])
        
        if fit_plane_no.dot(local_axis_z) < 0:
            fit_plane_no *= -1
            
        
        base_plane_v = min(list(perimeter_verts), key = lambda x: (x.co - fit_plane_co).dot(fit_plane_no))
        base_plane_co = base_plane_v.co + .2 * fit_plane_no
        
        base_plane_center_max_height = fit_plane_co + (base_plane_v.co - fit_plane_co).dot(fit_plane_no) * fit_plane_no
        #Add the base plane to the scene with BBox larger than the model
        bbox = Model.bound_box[:]
        bbox_vs = []
        for v in bbox:
            a = Vector(v)
            bbox_vs += [ob1.matrix_world.inverted() * Model.matrix_world * a]
        
        v_max_x= max(bbox_vs, key = lambda x: x[0])
        v_min_x = min(bbox_vs, key = lambda x: x[0])
        v_max_y= max(bbox_vs, key = lambda x: x[1])
        v_min_y = min(bbox_vs, key = lambda x: x[1])
        
        diag_xy = (((v_max_x - v_min_x)[0])**2 + ((v_max_y - v_min_y)[1])**2)**.5
        
        T_cut = Matrix.Translation(base_plane_center_max_height)
        Z_cut = fit_plane_no
        X_cut = Vector((1,0,0)) - Vector((1,0,0)).dot(fit_plane_no) * fit_plane_no
        X_cut.normalize()
        Y_cut = Z_cut.cross(X_cut)
        
        R_cut = Matrix.Identity(3)
        R_cut[0][0], R_cut[0][1], R_cut[0][2]  = X_cut[0] ,Y_cut[0],  Z_cut[0]
        R_cut[1][0], R_cut[1][1], R_cut[1][2]  = X_cut[1], Y_cut[1],  Z_cut[1]
        R_cut[2][0] ,R_cut[2][1], R_cut[2][2]  = X_cut[2], Y_cut[2],  Z_cut[2]
        
        R_cut = R_cut.to_4x4()
        
        base_cut = bmesh.new()
        bmesh.ops.create_grid(base_cut, x_segments = 100, y_segments = 100, size = .5 * diag_xy, matrix = T_cut * R_cut)
        if 'Auto Base' not in bpy.data.objects:
            a_base_me = bpy.data.meshes.new('Auto Base')
            a_base = bpy.data.objects.new('Auto Base', a_base_me)
            a_base.matrix_world = ob1.matrix_world
            base_cut.to_mesh(a_base_me)
            context.scene.objects.link(a_base)
        else:
            a_base = bpy.data.objects.get('Auto Base')
            base_cut.to_mesh(a_base.data)
            a_base.matrix_world = ob1.matrix_world
        base_cut.free()
        
        print('Identified undercuts and best fit base in %f' % (time.time() - interval_start))
        interval_start = time.time()
        
        
        meta_data = bpy.data.metaballs.new('Blockout Meta')
        meta_obj = bpy.data.objects.new('Blockout Meta', meta_data)
        meta_data.resolution = self.resolution
        meta_data.render_resolution = self.resolution
        context.scene.objects.link(meta_obj)
        
        
        
        #No Longer Neded we pre-process the mesh
        #relax_loops_util(bme, [ed for ed in bme.edges if len(ed.link_faces) == 1], iterations = 10, influence = .5, override_selection = True, debug = True)
        #undisplaced_locs = dict()
        #pre_discplacement = self.radius + .17
        #for v in bme.verts:
        #    undisplaced_locs[v] = (v.co, v.normal)
        #    v.co -= pre_discplacement * v.normal
            
        #bme.normal_update()
        
        
        n_voids = 0 
        n_elements = 0
        for v in bme.verts:
            #VERY IMPORTANT!  GET THE PREPROCESSED COODINATE
            v_pre_p = bme_pp.verts[v.index]
            co = v_pre_p.co
            
            if not len(v.link_edges)>1: continue
            #This should guarantee good overlap of the disks, going past 1/2 way toward the furthest neighbor
            #by definition the neighbors disk has to go > 1/2 than it's furthest neighbor
            R = .8 * max([ed.calc_length() for ed in v_pre_p.link_edges])
        
            Z = v_pre_p.normal #get a smoothed normal, very important
            Z.normalize()
        
            size_x = self.scale * R
            size_y = self.scale * R
            
            #we pre-calculate a thickness for predictablility
            size_z = self.scale * .17   #.22 + self.radius - .05 - self.radius
        
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
            quat = Rotation_Matrix.to_quaternion()
            
            base_plane_intersection = intersect_line_plane(co, co + 30 * local_axis_z, base_plane_co, fit_plane_no)
            
            height = (base_plane_intersection - co).length
            co_top = base_plane_intersection
        
            
            if v in perimeter_verts:
                N = math.ceil(height/.125)
                if size_x < self.scale * .125 and size_y < self.scale * .125:
                        n_voids += 1
                for i in range(0,N):
                    n_elements += 1
                    
                    mb = meta_data.elements.new(type = 'ELLIPSOID')
                    mb.co = self.scale * (co - i * .125 * local_axis_z)
                    
                    
                        
                        
                    mb.size_x = max(size_x, self.scale*.125)
                    mb.size_y = max(size_y, self.scale*.125)
                    mb.size_z = size_z
                    mb.rotation = quat
                    
    
            if v in undercut_verts:
                N = math.ceil(height/.2)
                for i in range(0,N):
                    
                    n_elements += 1
                    
                    mb = meta_data.elements.new(type = 'ELLIPSOID')
                    mb.co = self.scale * (co - i * .2 * local_axis_z)
                
                    mb.size_x = size_x
                    mb.size_y = size_y
                    mb.size_z = size_z
                    mb.rotation = quat
            
            
            if not (v in perimeter_verts or v in undercut_verts):
                
                n_elements += 2
                mb= meta_data.elements.new(type = 'ELLIPSOID')
                mb.co = self.scale * co 
            
                mb.size_x = size_x
                mb.size_y = size_y
                mb.size_z = self.scale * (.17 - .05)   #.17 - .02
                mb.rotation = quat
                
                #Add a flat base
                mb= meta_data.elements.new(type = 'BALL')
                mb.co = self.scale * co_top
                mb.radius = self.scale * .3
                 
        bme.free()
        bme_pp.free()
        
        print('%i voides were avoided by overthickening' % n_voids)
                       
        print('finished adding metaballs in %f' % (time.time() - interval_start))
        interval_start = time.time()
        print('added %i metaballs' % n_elements)
        R = mx.to_quaternion().to_matrix().to_4x4()
        L = Matrix.Translation(mx.to_translation())
        S = Matrix.Scale(.1, 4)
           
        meta_obj.matrix_world =  L * R * S

        print('transformed the meta ball object %f' % (time.time() - start))
        context.scene.update()
        total_meta_time = (time.time() - start)
        print('updated the scene %f' % total_meta_time )
        

        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        
        bme_final = bmesh.new()
        bme_final.from_mesh(me)
        
    
        
        
        bme_final.verts.ensure_lookup_table()
        bme_final.edges.ensure_lookup_table()
        bme_final.faces.ensure_lookup_table()
        
        
        
        #clean loose verts
        to_delete = []
        for v in bme_final.verts:
            if len(v.link_edges) < 2:
                to_delete.append(v)
                
        print('deleting %i loose verts' % len(to_delete))
        bmesh.ops.delete(bme_final, geom = to_delete, context = 1)
        
        bme_final.verts.ensure_lookup_table()
        bme_final.edges.ensure_lookup_table()
        bme_final.faces.ensure_lookup_table()
        
        #delete edges without faces
        to_delete = []
        for ed in bme_final.edges:
            if len(ed.link_faces) == 0:
                for v in ed.verts:
                    if len(v.link_faces) == 0:
                        to_delete.append(v)

        to_delete = list(set(to_delete))
        bmesh.ops.delete(bme_final, geom = to_delete, context = 1)
                
        bme_final.verts.ensure_lookup_table()
        bme_final.edges.ensure_lookup_table()
        bme_final.faces.ensure_lookup_table()
        
        #we have done basic validity checks
        Lv = len(bme_final.verts)
        Lf = len(bme_final.faces)
        
        #by definition, the vert with a max coordinate in any reference
        #will be a vertex in the outer shell
        #we have also guaranteed that there are no crappy verts/edges which
        #might throw us off
        v_max = max(bme_final.verts[:], key = lambda x: x.co[0])
        
        f_seed = v_max.link_faces[0]
        
        island = flood_selection_faces(bme_final, {}, f_seed, max_iters = 10000)
        
        do_not_clean = False
        if len(island) == Lf:
            self.report({'WARNING'}, 'The Blockout Wax may have internal voids')
            do_not_clean = True
        
        #get smarter    
        #if len(island) < int(Lf/1.5):
        #    self.report({'WARNING'}, 'The Blockout Wax may have disconnected islands')
        
        if not do_not_clean:
            total_faces = set(bme_final.faces[:])
            del_faces = total_faces - set(island)
            
            bmesh.ops.delete(bme_final, geom = list(del_faces), context = 3)
            del_verts = []
            for v in bme_final.verts:
                if all([f in del_faces for f in v.link_faces]):
                    del_verts += [v]        
            bmesh.ops.delete(bme_final, geom = del_verts, context = 1)
            
            del_edges = []
            for ed in bme_final.edges:
                if len(ed.link_faces) == 0:
                    del_edges += [ed]
            bmesh.ops.delete(bme_final, geom = del_edges, context = 4) 
        
        
        bme_final.to_mesh(me)
    
        if 'Blockout Wax' in bpy.data.objects:
            new_ob = bpy.data.objects.get('Blockout Wax')
            old_data = new_ob.data
            new_ob.data = me
            old_data.user_clear()
            bpy.data.meshes.remove(old_data)
        else:
            new_ob = bpy.data.objects.new('Blockout Wax', me)
            context.scene.objects.link(new_ob)
        
        
        
        
        new_ob.matrix_world = L * R * S
        mat = bpy.data.materials.get("Blockout Material")
        if mat is None:
            # create material
            mat = bpy.data.materials.new(name="Blockout Material")
            mat.diffuse_color = Color((0.8, .1, .1))
        
        
        if len(new_ob.material_slots) == 0:
            new_ob.data.materials.append(mat)
        
        interval_start = time.time()
        if 'Smooth' not in new_ob.modifiers:
            mod = new_ob.modifiers.new('Smooth', type = 'SMOOTH')
            mod.factor = 1
            mod.iterations = 4
        
        else:
            mod = new_ob.modifiers.get('Smooth')
            
        context.scene.objects.active = new_ob
        new_ob.select = True
        bpy.ops.object.modifier_apply(modifier = 'Smooth')
        
        if 'Child Of' not in new_ob.constraints:
            Master = bpy.data.objects.get(splint.model)
            cons = new_ob.constraints.new('CHILD_OF')
            cons.target = Master
            cons.inverse_matrix = Master.matrix_world.inverted()
         
        context.scene.objects.unlink(meta_obj)
        bpy.data.objects.remove(meta_obj)
        bpy.data.metaballs.remove(meta_data)
        
        context.scene.objects.unlink(ob2)
        me = ob2.data
        bpy.data.objects.remove(ob2)
        bpy.data.meshes.remove(me)
        
        
        for ob in context.scene.objects:
            if "silhouette" in ob.name:
                ob.hide = False 
            else:
                ob.hide = True
            
        Model.hide = False
        new_ob.hide = False
        splint.remove_undercuts = True
        tracking.trackUsage("D3Splint:RemoveUndercuts", (str(self.radius)[0:4], str(total_meta_time)[0:4]), background = True)
        return {'FINISHED'}
    
class D3SPLINT_OT_refractory_model(bpy.types.Operator):
    '''Calculates selective blockout and a compensation gap, takes 35 to 55 seconds'''
    bl_idname = 'd3splint.refractory_model'
    bl_label = "Create Refractory Model"
    bl_options = {'REGISTER','UNDO'}
    
    
    b_radius = FloatProperty(default = .05 , min = .01, max = .12, description = 'Allowable Undercut, larger values results in more retention, more snap into place', name = 'Undercut')
    c_radius = FloatProperty(default = .12 , min = .05, max = .25, description = 'Compensation Gap, larger values results in less retention, less friction', name = 'Compensation Gap')
    resolution = FloatProperty(default = 1.5, description = 'Mesh resolution. 1.5 seems ok?')
    scale = FloatProperty(default = 10, description = 'Only chnage if willing to crash blender.  Small chnages can make drastic differences')
    
    max_blockout = FloatProperty(default = 10.0 , min = 2, max = 10.0, description = 'Limit the depth of blockout to save processing itme', name = 'Blockout Limit')
    override_large_angle = BoolProperty(name = 'Angle Override', default = False, description = 'Large deviations between insertion asxis and world Z')
    angle = FloatProperty(default = 0.0 , min = 0.0, max = 180.0, description = 'Angle between insertion axis and world Z', name = 'Insertion angle')
    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        return  True

    
    def draw(self,context):
        
        layout = self.layout
    
        row = layout.row()
        row.prop(self, "b_radius")
        
        row = layout.row()
        row.prop(self, "c_radius")
        
        row = layout.row()
        row.prop(self, "max_blockout")
        
        if self.angle > 25:
            row = layout.row()
            msg  = 'The angle between insertion axis and world z is: ' + str(self.angle)[0:3]
            row.label(msg)
            
            row = layout.row()
            row.label('You will need to confirm this by overriding')
            
            row = layout.row()
            row.label('Consider cancelling (right click) and inspecting your insertion axis')
            
            row = layout.row()
            row.prop(self, "override_large_angle")
            
    def invoke(self,context, evenet):
        #gather some information
        Axis = bpy.data.objects.get('Insertion Axis')
        if Axis == None:
            self.report({'ERROR'},'Need to set survey from view first, then adjust axis arrow')
            return {'CANCELLED'}
        
        if len(context.scene.odc_splints) == 0:
            self.report({'ERROR'},'Need to plan a splint first')
            return {'CANCELLED'}
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        axis_z = Axis.matrix_world.to_quaternion() * Vector((0,0,1))
        
        if splint.jaw_type == 'MAXILLA':
            Z = Vector((0,0,-1))
        else:
            Z = Vector((0,0,1))
            
        angle = axis_z.angle(Z)
        angle_deg = 180/math.pi * angle
        
        if angle_deg > 35:
            self.angle = angle_deg
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        
        settings = get_settings()
        dbg = settings.debug
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        
        Model = bpy.data.objects.get(splint.model)
        if Model == None:
            self.report({'ERROR'},'Need to set the model first')
            return {'CANCELLED'}
        
        Axis = bpy.data.objects.get('Insertion Axis')
        if Axis == None:
            self.report({'ERROR'},'Need to set survey from view first, then adjust axis arrow')
            return {'CANCELLED'}
        
        if splint.jaw_type == 'MAXILLA':
            Z = Vector((0,0,-1))
        else:
            Z = Vector((0,0,1))
            
        axis_z = Axis.matrix_world.to_quaternion() * Vector((0,0,1))    
        angle = axis_z.angle(Z)
        angle_deg = 180/math.pi * angle
        
        if angle_deg > 35 and not self.override_large_angle:
            self.report({'ERROR'},'The insertion axis is very deviated from the world Z,\n confirm this is correct by using the override feature or \nsurvey the model from view again')
            return {'CANCELLED'}
            
            
        
        start = time.time()
        interval_start = start
        
        Trim = bpy.data.objects.get('Trimmed_Model')
        Perim = bpy.data.objects.get('Perim Model')

        if not Trim:
            self.report({'ERROR'}, 'Must trim the upper model first')
            return {'CANCELLED'}
        if not Perim:
            self.report({'ERROR'}, 'Must trim the upper model first')
            return {'CANCELLED'}
           
        
        mx = Trim.matrix_world
        
           
        bme = bmesh.new()
        bme_pp = bmesh.new() #BME Pre Processing (by modifiers)
        
        bme.from_mesh(Trim.data)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        
        bme2 = bmesh.new()
        bme2.from_object(Perim, context.scene)
        bme2.verts.ensure_lookup_table()
        bme2.normal_update()
        
        
        interval_start = time.time()
        #Pre process an offset and a smoothing
        
        me = bpy.data.meshes.new('Temp Offset')
        ob2 = bpy.data.objects.new('Temp Offset', me)
        context.scene.objects.link(ob2)
        bme.to_mesh(ob2.data)
        ob2.matrix_world = Trim.matrix_world
        
        
        mod1 = ob2.modifiers.new('Displace', type = 'DISPLACE')
        mod1.mid_level = 1 - (.22 + self.b_radius)
        mod1.strength = -1
        
        mod2 = ob2.modifiers.new('Smooth', type = 'SMOOTH')
        mod2.iterations = 20
        
        
        mod3 = ob2.modifiers.new('Shrinkwrap', type = 'SHRINKWRAP')
        mod3.target = Trim
        mod3.offset = .22 + self.b_radius
        
        mod4 = ob2.modifiers.new('Smooth', type = 'SMOOTH')
        mod4.iterations = 10
        
        bme_pp.from_object(ob2, context.scene)
        bme_pp.verts.ensure_lookup_table()
        bme_pp.edges.ensure_lookup_table()
        bme_pp.faces.ensure_lookup_table()
        
        print('Finished pre-processing in %f' % (time.time() - interval_start))
        interval_start = time.time()
        
        
        mx = Trim.matrix_world
        axis_z = Axis.matrix_world.to_quaternion() * Vector((0,0,1))
        i_mx = mx.inverted()
        local_axis_z = i_mx.to_quaternion() * axis_z
        local_axis_z.normalize()
        
        undercut_verts = set()
        for f in bme.faces:
            if f.normal.dot(local_axis_z) < -.01:
                undercut_verts.update([v for v in f.verts])
        
        perimeter_verts = set()
        perimeter_faces = set()
        for ed in bme.edges:
            if len(ed.link_faces) == 1:
                perimeter_verts.update([ed.verts[0], ed.verts[1]])
                for v in ed.verts:
                    perimeter_faces.update([f for f in v.link_faces])
        

        #often the verts at the perimeter get mislabeled.  We will handle them
        #for f in perimeter_faces:
        #    undercut_verts.difference_update([v for v in f.verts])
        
        fit_plane_co = Vector((0,0,0))
        for v in perimeter_verts:
            fit_plane_co += v.co
        
        fit_plane_co *= 1/len(perimeter_verts)
        fit_plane_no = odcutils.calculate_plane([v.co for v in list(perimeter_verts)])
        
        if fit_plane_no.dot(local_axis_z) < 0:
            fit_plane_no *= -1
            
        
        base_plane_v = min(list(perimeter_verts), key = lambda x: (x.co - fit_plane_co).dot(fit_plane_no))
        base_plane_co = base_plane_v.co + .2 * fit_plane_no
        
        base_plane_center_max_height = fit_plane_co + (base_plane_v.co - fit_plane_co).dot(fit_plane_no) * fit_plane_no
        #Add the base plane to the scene with BBox larger than the model
        bbox = Model.bound_box[:]
        bbox_vs = []
        for v in bbox:
            a = Vector(v)
            bbox_vs += [Trim.matrix_world.inverted() * Model.matrix_world * a]
        
        v_max_x= max(bbox_vs, key = lambda x: x[0])
        v_min_x = min(bbox_vs, key = lambda x: x[0])
        v_max_y= max(bbox_vs, key = lambda x: x[1])
        v_min_y = min(bbox_vs, key = lambda x: x[1])
        
        diag_xy = (((v_max_x - v_min_x)[0])**2 + ((v_max_y - v_min_y)[1])**2)**.5
        
        T_cut = Matrix.Translation(base_plane_center_max_height)
        Z_cut = fit_plane_no
        X_cut = Vector((1,0,0)) - Vector((1,0,0)).dot(fit_plane_no) * fit_plane_no
        X_cut.normalize()
        Y_cut = Z_cut.cross(X_cut)
        
        R_cut = Matrix.Identity(3)
        R_cut[0][0], R_cut[0][1], R_cut[0][2]  = X_cut[0] ,Y_cut[0],  Z_cut[0]
        R_cut[1][0], R_cut[1][1], R_cut[1][2]  = X_cut[1], Y_cut[1],  Z_cut[1]
        R_cut[2][0] ,R_cut[2][1], R_cut[2][2]  = X_cut[2], Y_cut[2],  Z_cut[2]
        
        R_cut = R_cut.to_4x4()
        
        base_cut = bmesh.new()
        bmesh.ops.create_grid(base_cut, x_segments = 100, y_segments = 100, size = .5 * diag_xy, matrix = T_cut * R_cut)
        if 'Auto Base' not in bpy.data.objects:
            a_base_me = bpy.data.meshes.new('Auto Base')
            a_base = bpy.data.objects.new('Auto Base', a_base_me)
            a_base.matrix_world = Trim.matrix_world
            base_cut.to_mesh(a_base_me)
            context.scene.objects.link(a_base)
        else:
            a_base = bpy.data.objects.get('Auto Base')
            base_cut.to_mesh(a_base.data)
            a_base.matrix_world = Trim.matrix_world
        base_cut.free()
        
        print('Identified undercuts and best fit base in %f' % (time.time() - interval_start))
        interval_start = time.time()
        
        
        meta_data = bpy.data.metaballs.new('Blockout Meta')
        meta_obj = bpy.data.objects.new('Blockout Meta', meta_data)
        meta_data.resolution = self.resolution
        meta_data.render_resolution = self.resolution
        context.scene.objects.link(meta_obj)
        
        
        
        #No Longer Neded we pre-process the mesh
        #relax_loops_util(bme, [ed for ed in bme.edges if len(ed.link_faces) == 1], iterations = 10, influence = .5, override_selection = True, debug = True)
        #undisplaced_locs = dict()
        #pre_discplacement = self.radius + .17
        #for v in bme.verts:
        #    undisplaced_locs[v] = (v.co, v.normal)
        #    v.co -= pre_discplacement * v.normal
            
        #bme.normal_update()
        
        
        n_voids = 0 
        n_elements = 0
        for v in bme.verts:
            #VERY IMPORTANT!  GET THE PREPROCESSED COODINATE
            v_pre_p = bme_pp.verts[v.index]
            co = v_pre_p.co
            
            if not len(v.link_edges)>1: continue
            #This should guarantee good overlap of the disks, going past 1/2 way toward the furthest neighbor
            #by definition the neighbors disk has to go > 1/2 than it's furthest neighbor
            R = .8 * max([ed.calc_length() for ed in v_pre_p.link_edges])
        
            Z = v_pre_p.normal #get a smoothed normal, very important
            Z.normalize()
        
            size_x = self.scale * R
            size_y = self.scale * R
            
            #we pre-calculate a thickness for predictablility
            size_z = self.scale * .17   #.22 + self.radius - .05 - self.radius
        
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
            quat = Rotation_Matrix.to_quaternion()
            
            base_plane_intersection = intersect_line_plane(co, co + 30 * local_axis_z, base_plane_co, fit_plane_no)
            
            height = (base_plane_intersection - co).length
            co_top = base_plane_intersection
        
            
            if v in perimeter_verts:
                N = min(math.ceil(height/.125), math.ceil(self.max_blockout/.125))  #limit the blockout depth
                if size_x < self.scale * .125 and size_y < self.scale * .125:
                        n_voids += 1
                for i in range(0,N):
                    n_elements += 1
                    
                    mb = meta_data.elements.new(type = 'ELLIPSOID')
                    mb.co = self.scale * (co - i * .125 * local_axis_z)  
                        
                    mb.size_x = max(size_x, self.scale*.125)
                    mb.size_y = max(size_y, self.scale*.125)
                    mb.size_z = size_z
                    mb.rotation = quat
                    
    
            if v in undercut_verts:
                N = min(math.ceil(height/.2), math.ceil(self.max_blockout/.2))  #limit the blockout depth
                for i in range(0,N):
                    
                    n_elements += 1
                    
                    mb = meta_data.elements.new(type = 'ELLIPSOID')
                    mb.co = self.scale * (co - i * .2 * local_axis_z)
                
                    mb.size_x = size_x
                    mb.size_y = size_y
                    mb.size_z = size_z
                    mb.rotation = quat
            
            
            if not (v in perimeter_verts or v in undercut_verts):
                
                n_elements += 2
                mb= meta_data.elements.new(type = 'ELLIPSOID')
                mb.co = self.scale * co 
            
                mb.size_x = size_x
                mb.size_y = size_y
                mb.size_z = self.scale * (.17 - .05)   #.17 - .02
                mb.rotation = quat
                
                #Add a flat base
                if self.angle < 25:
                    mb= meta_data.elements.new(type = 'BALL')
                    mb.co = self.scale * co_top
                    mb.radius = self.scale * .3
                 
        #Now do teh passive spacer part
        for v in bme.verts: 
            v.co -= .15 * v.normal
        
        for v in bme2.verts:
            v.co -= .16 * v.normal
        
        bme.normal_update()
        bme2.normal_update()
        
        
        for v in bme.verts[:] + bme2.verts[:]:
            if not len(v.link_edges): continue
            co = v.co
            R = .5 * max([ed.calc_length() for ed in v.link_edges])
            
            n_elements += 1
            Z = v.normal 
            Z.normalize()
            
            mb = meta_data.elements.new(type = 'ELLIPSOID')
            mb.co = self.scale * co
            mb.size_x = self.scale * R
            mb.size_y = self.scale * R
            mb.size_z = self.scale * (self.c_radius - .025 + .15)  #surface is pre negatively offset by .15
            
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
            

        bme.free()
        bme_pp.free()
        
        print('%i voides were avoided by overthickening' % n_voids)
                       
        print('finished adding metaballs in %f' % (time.time() - interval_start))
        interval_start = time.time()
        print('added %i metaballs' % n_elements)
        R = mx.to_quaternion().to_matrix().to_4x4()
        L = Matrix.Translation(mx.to_translation())
        S = Matrix.Scale(.1, 4)
           
        meta_obj.matrix_world =  L * R * S

        print('transformed the meta ball object %f' % (time.time() - start))
        context.scene.update()
        total_meta_time = (time.time() - start)
        print('updated the scene %f' % total_meta_time )
        

        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        
        bme_final = bmesh.new()
        bme_final.from_mesh(me)

        bme_final.verts.ensure_lookup_table()
        bme_final.edges.ensure_lookup_table()
        bme_final.faces.ensure_lookup_table()
        
        
        
        #clean loose verts
        to_delete = []
        for v in bme_final.verts:
            if len(v.link_edges) < 2:
                to_delete.append(v)
                
        print('deleting %i loose verts' % len(to_delete))
        bmesh.ops.delete(bme_final, geom = to_delete, context = 1)
        
        bme_final.verts.ensure_lookup_table()
        bme_final.edges.ensure_lookup_table()
        bme_final.faces.ensure_lookup_table()
        
        #delete edges without faces
        to_delete = []
        for ed in bme_final.edges:
            if len(ed.link_faces) == 0:
                for v in ed.verts:
                    if len(v.link_faces) == 0:
                        to_delete.append(v)

        to_delete = list(set(to_delete))
        bmesh.ops.delete(bme_final, geom = to_delete, context = 1)
                
        bme_final.verts.ensure_lookup_table()
        bme_final.edges.ensure_lookup_table()
        bme_final.faces.ensure_lookup_table()
        
        #we have done basic validity checks
        Lv = len(bme_final.verts)
        Lf = len(bme_final.faces)
        
        #by definition, the vert with a max coordinate in any reference
        #will be a vertex in the outer shell
        #we have also guaranteed that there are no crappy verts/edges which
        #might throw us off
        v_max = max(bme_final.verts[:], key = lambda x: x.co[0])
        
        f_seed = v_max.link_faces[0]
        
        island = flood_selection_faces(bme_final, {}, f_seed, max_iters = 10000)
        
        do_not_clean = False
        if len(island) == Lf:
            self.report({'WARNING'}, 'The Blockout Wax may have internal voids')
            do_not_clean = True
        
        #get smarter    
        #if len(island) < int(Lf/1.5):
        #    self.report({'WARNING'}, 'The Blockout Wax may have disconnected islands')
        
        if not do_not_clean:
            total_faces = set(bme_final.faces[:])
            del_faces = total_faces - set(island)
            
            bmesh.ops.delete(bme_final, geom = list(del_faces), context = 3)
            del_verts = []
            for v in bme_final.verts:
                if all([f in del_faces for f in v.link_faces]):
                    del_verts += [v]        
            bmesh.ops.delete(bme_final, geom = del_verts, context = 1)
            
            del_edges = []
            for ed in bme_final.edges:
                if len(ed.link_faces) == 0:
                    del_edges += [ed]
            bmesh.ops.delete(bme_final, geom = del_edges, context = 4) 
        
        
        bme_final.to_mesh(me)
    
        if 'Refractory Model' in bpy.data.objects:
            new_ob = bpy.data.objects.get('Refractory Model')
            old_data = new_ob.data
            new_ob.data = me
            old_data.user_clear()
            bpy.data.meshes.remove(old_data)
        else:
            new_ob = bpy.data.objects.new('Refractory Model', me)
            context.scene.objects.link(new_ob)
        
        new_ob.matrix_world = L * R * S
        mat = bpy.data.materials.get("Refractory Material")
        if mat is None:
            # create material
            mat = bpy.data.materials.new(name="Refractory Material")
            mat.diffuse_color = Color((0.36, .8,.36))
            mat.use_transparency = True
            mat.transparency_method = 'Z_TRANSPARENCY'
            mat.alpha = .4
            
        if len(new_ob.material_slots) == 0:
            new_ob.data.materials.append(mat)
        
        interval_start = time.time()
        if 'Smooth' not in new_ob.modifiers:
            mod = new_ob.modifiers.new('Smooth', type = 'SMOOTH')
            mod.factor = 1
            mod.iterations = 4
        
        else:
            mod = new_ob.modifiers.get('Smooth')
            
        context.scene.objects.active = new_ob
        new_ob.select = True
        bpy.ops.object.modifier_apply(modifier = 'Smooth')
        
        
        #apply the smoothing
        context.scene.objects.active = new_ob
        new_ob.select = True
        bpy.ops.object.modifier_apply(modifier = 'Smooth')
        
        
        
        print('Took %f seconds to smooth BMesh' % (time.time() - interval_start))
        interval_start = time.time()
        
                
        mx = new_ob.matrix_world
        imx = mx.inverted()
        bme = bmesh.new()
        bme.from_object(new_ob, context.scene)
        bme.verts.ensure_lookup_table()
        
        mx_check = Trim.matrix_world
        imx_check = mx_check.inverted()
        bme_check = bmesh.new()
        bme_check.from_mesh(Trim.data)
        bme_check.verts.ensure_lookup_table()
        bme_check.edges.ensure_lookup_table()
        bme_check.faces.ensure_lookup_table()
        bvh = BVHTree.FromBMesh(bme_check)
        
        
        boundary_inds = set()
        for ed in bme_check.edges:
            if len(ed.link_faces) == 1:
                for v in ed.verts:
                    for f in v.link_faces:
                        boundary_inds.add(f.index)
        
        bme_check.free()
        

        
        print('Took %f seconds to initialize BMesh and build BVH' % (time.time() - interval_start))
        interval_start = time.time()
            
        n_corrected = 0
        n_normal = 0
        n_loc = 0
        n_too_far = 0
        n_boundary = 0
        for v in bme.verts:
            #check the distance in trimmed model space
            co = imx_check * mx * v.co
            loc, no, ind, d = bvh.find_nearest(co)
            
            if not loc: continue
            
            if d < self.c_radius:  #compensation radius
                if ind in boundary_inds:
                    n_boundary += 1
                    continue
                n_corrected += 1
                R = co - loc
                
                R.normalize()
                    
                if R.dot(no) > 0:
                    delta = self.c_radius - d + .002
                    co += delta * R
                    n_loc += 1
                else:
                    co = loc + (self.c_radius + .002) * no
                    n_normal += 1
                    
                v.co = imx * mx_check * co
                v.select_set(True)
            
            elif d > self.c_radius and d < (self.c_radius + self.b_radius):
                co = loc + (self.c_radius + .0001) * no
                n_too_far += 1
                
            else:
                v.select_set(False)        
        print('corrected %i verts too close offset' % n_corrected)
        print('corrected %i verts using normal method' % n_normal)
        print('corrected %i verts using location method' % n_loc)
        print('corrected %i verts using too far away' % n_too_far)
        print('ignored %i verts clsoe to trim boundary' % n_boundary)
        

        if 'Child Of' not in new_ob.constraints:
            Master = bpy.data.objects.get(splint.model)
            cons = new_ob.constraints.new('CHILD_OF')
            cons.target = Master
            cons.inverse_matrix = Master.matrix_world.inverted()
         
        context.scene.objects.unlink(meta_obj)
        bpy.data.objects.remove(meta_obj)
        bpy.data.metaballs.remove(meta_data)
        
        context.scene.objects.unlink(ob2)
        me = ob2.data
        bpy.data.objects.remove(ob2)
        bpy.data.meshes.remove(me)
        
        
        for ob in context.scene.objects:
            if "silhouette" in ob.name:
                ob.hide = False 
            else:
                ob.hide = True
        
        
        bme.to_mesh(new_ob.data)
        bme.free()
            
        Model.hide = False
        new_ob.hide = False
        splint.refractory_model = True
        tracking.trackUsage("D3Splint:RemoveUndercuts", (str(self.b_radius)[0:4], str(self.b_radius)[0:4], str(total_meta_time)[0:4]), background = True)
        return {'FINISHED'}
    
    
class D3SPLINT_OT_sculpt_concavities(bpy.types.Operator):
    '''Blend sharp concavties by adding mateiral or by smoothing, good for small crevices'''
    bl_idname = 'd3splint.auto_sculpt_concavities'
    bl_label = "Auto Sculpt Concavities"
    bl_options = {'REGISTER','UNDO'}
    
    
    #smooth = bpy.props.BoolProperty(default = True, name = "Smooth the outline.  Slightly less acuurate in some situations but more accurate in others.  Default True for best results")
    radius = FloatProperty(default = 1.5, min = 0.5, max =3, description = 'Radius of area to fill in')
    strength = FloatProperty(default = .6 , min = .1, max = 1, description = 'how strong to apply the brush')
    angle = bpy.props.IntProperty(default = 30, name = "Crease Angle", min = 25, max = 50, description = 'How sharp a crevice needs to be to fill, bigger number means only really sharp creases')
    
    modes = ['FRONT', 'LEFT', 'RIGHT', 'BACK', 'TOP','BOTTOM', 'CURRENT_VIEW']
    mode_items = []
    for m in modes:
        mode_items += [(m, m, m)]
        
    view = EnumProperty(name = 'View Direction', items = mode_items, default = 'TOP')
    
    #views = ['FRONT', 'BACK', 'LEFT','RIGHT']
    @classmethod
    def poll(cls, context):
        #restoration exists and is in scene
        return  True

    def invoke(self,context, evenet):
        
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        tracking.trackUsage("D3Splint:SculptSplintConcavities",None)
        
        Shell = bpy.data.objects.get('Splint Shell')
        if Shell == None:
            self.report({'ERROR'},'Need to have a splint shell created')
            return {'CANCELLED'}
                
        context.scene.objects.active = Shell
        Shell.select = True
        Shell.hide = False
        
        if len(Shell.modifiers):
            for mod in Shell.modifiers:            
                bpy.ops.object.modifier_apply(modifier = mod.name)      
            print('Applied modifiers')
        
        #if False:
        #    context.scene.objects.active = Shell
        #    Shell.select = True
        #    bpy.ops.object.mode_set(mode = 'SCULPT')
        #    if not Shell.use_dynamic_topology_sculpting:
        #        bpy.ops.sculpt.dynamic_topology_toggle()
        #    context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
        #    context.scene.tool_settings.sculpt.constant_detail_resolution = 2
        #    bpy.ops.sculpt.detail_flood_fill()
        #    bpy.ops.object.mode_set(mode = 'OBJECT')
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        mx = Shell.matrix_world
        imx = mx.inverted()
        
        #careful, this can get expensive with multires    
        bme = bmesh.new()
        bme.from_mesh(Shell.data)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        bme.normal_update()
        
        sculpt_edges = []
        sculpt_verts = set()
        angle = self.angle * math.pi/180
        for ed in bme.edges:
            if ed.calc_face_angle_signed() <= -angle:
                ed.select_set(True)
                sculpt_edges += [ed]
                sculpt_verts.update([ed.verts[0], ed.verts[1]])
            else:
                ed.select_set(False)
                    
        
        sculpt_verts = list(sculpt_verts)
        world_sculpt_verts = [mx * v.co for v in sculpt_verts]
        
        print('there are %i sculpt verts' % len(world_sculpt_verts))
        bme.free()
        
        context.scene.objects.active = Shell
        Shell.select = True
        Shell.hide = False
        bpy.ops.object.mode_set(mode = 'SCULPT')
        bpy.ops.view3d.view_selected()
        #if splint.jaw_type == 'MANDIBLE':
        #    bpy.ops.view3d.viewnumpad(type = 'FRONT')
        #else:
        #    bpy.ops.view3d.viewnumpad(type = 'FRONT')
        
        if self.view != 'CURRENT_VIEW':
            bpy.ops.view3d.viewnumpad(type = self.view)
            
        if not Shell.use_dynamic_topology_sculpting:
            bpy.ops.sculpt.dynamic_topology_toggle()
        
        scene = context.scene
        paint_settings = scene.tool_settings.unified_paint_settings
        paint_settings.use_locked_size = True
        paint_settings.unprojected_radius = self.radius
        brush = bpy.data.brushes['Fill/Deepen']
        scene.tool_settings.sculpt.brush = brush
        scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
        
        
        #if bversion() < '002.079.000':
            #scene.tool_settings.sculpt.constant_detail = 50
        #else:
        #enforce 2.79
        scene.tool_settings.sculpt.constant_detail_resolution = 2
        
        scene.tool_settings.sculpt.use_symmetry_x = False
        scene.tool_settings.sculpt.use_symmetry_y = False
        scene.tool_settings.sculpt.use_symmetry_z = False
        brush.strength = self.strength
        
        brush.use_frontface = False
        brush.stroke_method = 'DOTS'
        
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
        override['active_object'] = Shell
        override['object'] = Shell
        override['sculpt_object'] = Shell
        
        
        stroke = []
        i = 0
        for co in world_sculpt_verts:
            #if i > 100: break
            i += 1
            mouse = view3d_utils.location_3d_to_region_2d(reg, space.region_3d, co)
            l_co = imx * co
            stroke = [{"name": "my_stroke",
                        "mouse" : (mouse[0], mouse[1]),
                        "pen_flip" : False,
                        "is_start": True,
                        "location": (l_co[0], l_co[1], l_co[2]),
                        "pressure": 1,
                        "size" : 30,
                        "time": 1}]
                      
            bpy.ops.sculpt.brush_stroke(override, stroke=stroke, mode='NORMAL', ignore_background_click=False)
        
        bpy.ops.object.mode_set(mode = 'OBJECT')
        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(D3SPLINT_OT_draw_meta_curve)
    bpy.utils.register_class(D3SPLINT_OT_splint_virtual_wax_on_curve)
    bpy.utils.register_class(D3SPLINT_OT_splint_join_meta_to_shell)
    bpy.utils.register_class(D3SPLINT_OT_anterior_deprogrammer_element)
    bpy.utils.register_class(D3SPLINT_OT_splint_join_depro_to_shell)
    bpy.utils.register_class(D3SPLINT_OT_blockout_splint_shell)
    bpy.utils.register_class(D3SPLINT_OT_sculpt_concavities)
    bpy.utils.register_class(D3SPLINT_OT_blockout_trimmed_model)
    bpy.utils.register_class(D3SPLINT_OT_blockout_trimmed_model2)
    bpy.utils.register_class(D3SPLINT_OT_refractory_model)
    bpy.utils.register_class(D3SPLINT_OT_surgical_bite_positioner)
    
def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_draw_meta_curve)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_virtual_wax_on_curve)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_join_meta_to_shell)
    bpy.utils.unregister_class(D3SPLINT_OT_anterior_deprogrammer_element)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_join_depro_to_shell)
    bpy.utils.unregister_class(D3SPLINT_OT_blockout_splint_shell)
    bpy.utils.unregister_class(D3SPLINT_OT_sculpt_concavities)
    bpy.utils.unregister_class(D3SPLINT_OT_blockout_trimmed_model)
    bpy.utils.unregister_class(D3SPLINT_OT_blockout_trimmed_model2)
    bpy.utils.unregister_class(D3SPLINT_OT_refractory_model)
    bpy.utils.unregister_class(D3SPLINT_OT_surgical_bite_positioner)
    