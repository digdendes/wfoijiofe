'''
Created on Nov 23, 2017

@author: Patrick
'''
import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Color, Quaternion, kdtree
from mathutils.geometry import intersect_point_line
from mathutils.bvhtree import BVHTree

from mesh_cut import edge_loops_from_bmedges, space_evenly_on_path, flood_selection_faces
from bpy_extras import view3d_utils
from bpy.props import FloatProperty, BoolProperty, IntProperty, EnumProperty
from textbox import TextBox
from curve import CurveDataManager, PolyLineKnife

import survey_utils
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

    def invoke(self,context, evenet):
        
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        tracking.trackUsage("D3Splint:BlockoutSplintConcavities",None)
        splint = context.scene.odc_splints[0]
        
        Shell = bpy.data.objects.get('Splint Shell')
        if Shell == None:
            self.report('ERROR','Need to have a splint shell created')
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
            self.report('ERROR','Need to have a splint shell created')
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
    
def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_draw_meta_curve)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_virtual_wax_on_curve)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_join_meta_to_shell)
    bpy.utils.unregister_class(D3SPLINT_OT_anterior_deprogrammer_element)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_join_depro_to_shell)
    bpy.utils.unregister_class(D3SPLINT_OT_blockout_splint_shell)
    bpy.utils.unregister_class(D3SPLINT_OT_sculpt_concavities)
    