'''
Created on Nov 23, 2017

@author: Patrick
'''
import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Color, Quaternion, kdtree
from mathutils.geometry import intersect_point_line

from mesh_cut import edge_loops_from_bmedges, space_evenly_on_path, flood_selection_faces
from bpy_extras import view3d_utils
from bpy.props import FloatProperty, BoolProperty, IntProperty, EnumProperty
from textbox import TextBox
from curve import CurveDataManager, PolyLineKnife
import tracking

def arch_crv_draw_callback(self, context):  
    self.crv.draw(context)
    self.help_box.draw()
    
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
        
         
        self.crv = None
        
        if 'Meta Curve' in context.scene.objects:
            crv_ob = bpy.data.objects.get('Meta Curve')
            context.scene.objects.unlink(crv_ob)
            crv_data = crv_ob.data
            bpy.data.objects.remove(crv_ob)
            bpy.data.curves.remove(crv_data)
            
            
        self.crv = CurveDataManager(context,snap_type ='SCENE', snap_object = None, shrink_mod = False, name = 'Meta Curve')
            
        
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
    """Create Virtual Wax Objecyt from selected bezier curve"""
    bl_idname = "d3splint.virtual_wax_on_curve"
    bl_label = "Virtual Wax on Curve"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    segments = IntProperty(default = 60, description = 'Resolution of the wax elements')
    posterior_width = FloatProperty(default = 4, description = 'Width of posterior rim')
    anterior_width = FloatProperty(default = 4, description = 'Width of anterior rim')
    thickness = FloatProperty(default = 2, description = 'Height of  rim')
    
    
    flare = IntProperty(default = 0, min = -90, max = 90, description = 'Angle off of world Z')
    meta_type = EnumProperty(name = 'Meta Type', items = [('CUBE','CUBE','CUBE'), 
                                                          ('ELLIPSOID', 'ELLIPSOID','ELLIPSOID'),
                                                          ('BALL','BALL','BALL')], default = 'CUBE')
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
            mat.diffuse_color = Color((0.5, .1, .6))
        
        
        if mat.name not in meta_obj.data.materials:
            meta_obj.data.materials.append(mat)
        
        bme.free()
        #todo remove/delete to_mesh mesh
  
        return {'FINISHED'}

    
    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)




class D3SPLINT_OT_anterior_deprogrammer_element(bpy.types.Operator):
    """Create an anterior deprogrammer ramp"""
    bl_idname = "d3splint.anterior_deprogrammer_element"
    bl_label = "Anterior Deprogrammer ELement"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    guidance_angle = IntProperty(default = 15, min = -90, max = 90, description = 'Angle off of world Z')
    anterior_length = FloatProperty(default = 4, description = 'Length of anterior ramp')
    posterior_length = FloatProperty(default = 6, description = 'Length of posterior ramp')
    posterior_width = FloatProperty(default = 8, description = 'Posterior Width of ramp')
    anterior_width = FloatProperty(default = 8, description = 'Anterior Width of ramp')
    thickness = FloatProperty(default = 3, description = 'Thickness of ramp')
    support_height = FloatProperty(default = 6, description = 'Height of support strut')
    support_width =  FloatProperty(default = 6, description = 'Width of support strut')
    
    
    @classmethod
    def poll(cls, context):
        
        return True
    
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

    
    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)


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
            Rim.data.elements.reomve(ele)
            
        rim_ob.hide = True
        Shell.hide = False
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        splint.ops_string += 'JoinRim:VirtualWax' 
        return {'FINISHED'}
    
        
def register():
    bpy.utils.register_class(D3SPLINT_OT_draw_meta_curve)
    bpy.utils.register_class(D3SPLINT_OT_splint_virtual_wax_on_curve)
    bpy.utils.register_class(D3SPLINT_OT_splint_join_meta_to_shell)
    bpy.utils.register_class(D3SPLINT_OT_anterior_deprogrammer_element)
    bpy.utils.register_class(D3SPLINT_OT_splint_join_depro_to_shell)
    
def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_draw_meta_curve)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_virtual_wax_on_curve)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_join_meta_to_shell)
    bpy.utils.unregister_class(D3SPLINT_OT_anterior_deprogrammer_element)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_join_depro_to_shell)
    