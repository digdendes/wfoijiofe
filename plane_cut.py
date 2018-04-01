import bpy
import bmesh
import bgl
import time
from curve import LineDrawer
from textbox import TextBox
import tracking

from mathutils import Vector, Matrix, Quaternion
from test.test_binop import isint
from odcutils import get_com_bme
import common_drawing
from common_drawing import outline_region
from common_utilities import get_settings
from bpy_extras import view3d_utils
import odcutils

def plane_cut_draw_callback(self, context):  
    self.crv.draw(context)
    self.help_box.draw() 
    
    prefs = get_settings()
    r,g,b = prefs.active_region_color
    outline_region(context.region,(r,g,b,1))  
    
    if len(self.new_geom_draw_points):
        
        common_drawing.draw_3d_points(context, self.new_geom_draw_points, self.new_geom_color, 4)
        common_drawing.draw_3d_points(context, [self.new_geom_point], self.new_geom_point_color, 10)

class D3SPLINT_OT_finalize_all_cuts(bpy.types.Operator):
    """Apply all cut modifiers for closed plane cuts"""
    bl_idname = "d3splint.splint_finalize_plane_cuts"
    bl_label = "Finalize Plane Cuts"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        if context.object == None: return False
        if context.object.type != 'MESH': return False
        
        return True
    
    def execute(self, context):
    
        if "Plane Cut" in context.object.name:
            self.report({'ERROR'}, 'You need to select the object to be cut, not ')
            return {'CANCELLED'}
        
        if len(context.object.modifiers) == 0:
            self.report({'ERROR'}, 'This object does not have any boolean modifiers which means it is finalized already')

        
        for mod in context.object.modifiers:
            if not mod.show_viewport:
                mod.show_viewport = True
        
        old_mesh = context.object.data
                
        # settings for to_mesh
        apply_modifiers = True
        settings = 'PREVIEW'
        new_mesh = context.object.to_mesh(context.scene, apply_modifiers, settings)

        # object will still have modifiers, remove them
        context.object.modifiers.clear()
        
        # assign the new mesh to obj.data 
        context.object.data = new_mesh
        
        # remove the old mesh from the .blend
        bpy.data.meshes.remove(old_mesh)
        
        
        return {'FINISHED'}


class D3SPLINT_OT_batch_process_plane_cuts(bpy.types.Operator):
    """Apply all cut modifiers for closed plane cuts"""
    bl_idname = "d3splint.batch_process_plane_cuts"
    bl_label = "Batch Process Plane Cuts"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        if context.object == None: return False
        if context.object.type != 'MESH': return False
        
        return True
    
    
    simple_base = bpy.props.BoolProperty(default = False, description = 'Extude open edge downward before cutting')
    simple_base_height = bpy.props.FloatProperty(default = 8.0, description = 'Amount to add to extrude the border edges')
    
    
    hollow = bpy.props.BoolProperty(default = False, description = 'Hollow the model after cutting')
    wall_thickness = bpy.props.FloatProperty(default = 3.5, description = 'Wall thickness')
    
    def invoke(self, context, event):
        
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
    
        start = time.time()
        interval_time = time.time()
        plane_cuts = [ob for ob in context.scene.objects if "Plane Cut" in ob.name]
        
        obs_to_cut = []
        for ob in context.scene.objects:
            if "Plane Cut" not in ob.name and ob.type == 'MESH' and ob.hide == False:
                obs_to_cut += [ob]
                
        
        for ob in obs_to_cut:
            for ob in context.scene.objects:
                ob.select = False
            for ob in obs_to_cut:
                ob.select = True
                
        if self.simple_base:
            print('starting the simple base batch processing')
            bpy.ops.d3splint.simple_base(mode = 'WORLD_Z', batch_mode = True, base_height = self.simple_base_height)
        
            print('Finished adding all bases in %s seconds' % str(time.time() - interval_time)[:4])
            print('Total time elapsed so far: %s seconds' % str(time.time() - start)[:4])
            interval_time = time.time()
            
        for ob in obs_to_cut:
            print('\n\n')
            print('processing model %s' % ob.name)
            
            for cut_ob in plane_cuts:
                mod = ob.modifiers.new('Plane Cut', type = 'BOOLEAN')
                mod.operation = 'DIFFERENCE'  
                mod.object = cut_ob
                mod.solver = 'CARVE'
                
            old_mesh = ob.data
                
            # settings for to_mesh
            apply_modifiers = True
            settings = 'PREVIEW'
            new_mesh = ob.to_mesh(context.scene, apply_modifiers, settings)

            # object will still have modifiers, remove them
            ob.modifiers.clear()
        
            # assign the new mesh to obj.data 
            ob.data = new_mesh
        
            # remove the old mesh from the .blend
            bpy.data.meshes.remove(old_mesh)
        
            
            print('Object cuts processed in %s seconds' % str(time.time() - interval_time)[:4])
            print('Total time elapsed so far: %s seconds' % str(time.time() - start)[:4])
            interval_time = time.time()
            
        return {'FINISHED'}

class D3SPLINT_OT_pause_all_cuts(bpy.types.Operator):
    """Pause all cut modifiers to imrpove performance while editing cuts"""
    bl_idname = "d3splint.splint_pause_plane_cuts"
    bl_label = "Pause Plane Cuts"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        if context.object == None: return False
        if context.object.type != 'MESH': return False
        
        return True
    
    def execute(self, context):
    
        if "Plane Cut" in context.object.name:
            self.report({'ERROR'}, 'You need to select the object to be cut, not ')
            return {'CANCELLED'}
        
        if len(context.object.modifiers) == 0:
            self.report({'ERROR'}, 'This object does not have any boolean modifiers')

        
        old_mesh = context.object.data
        
        context.object.data = None  #make it an empty for a second
        
        for mod in context.object.modifiers:
            mod.show_viewport = False
        
        context.object.data = old_mesh  #turn it back on
                
        return {'FINISHED'} 
 
 
class D3SPLINT_OT_activate_all_cuts(bpy.types.Operator):
    """Re-activate and calculate all cut modifiers after editing cuts"""
    bl_idname = "d3splint.splint_activate_plane_cuts"
    bl_label = "Activate Plane Cuts"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        if context.object == None: return False
        if context.object.type != 'MESH': return False
        
        return True
    
    def execute(self, context):
    
        if "Plane Cut" in context.object.name:
            self.report({'ERROR'}, 'You need to select the object to be cut, not one of the cut objects')
            return {'CANCELLED'}
        
        if len(context.object.modifiers) == 0:
            self.report({'ERROR'}, 'This object does not have any boolean modifiers')

        
        old_mesh = context.object.data
        
        context.object.data = None  #make it an empty for a second
        
        for mod in context.object.modifiers:
            mod.show_viewport = True
        
        context.object.data = old_mesh  #turn it back on
                
        return {'FINISHED'} 
                
class D3SPLINT_OT_plane_cut_mesh_rough(bpy.types.Operator):
    """Click and draw a line to cut mesh"""
    bl_idname = "d3splint.splint_plane_cut"
    bl_label = "Plane Cut Mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
    cut_method = bpy.props.EnumProperty(name = 'Mode', items = (('SURFACE','SURFACE','SURFACE'), ('SOLID', 'SOLID','SOLID')), default = 'SURFACE')
    @classmethod
    def poll(cls,context):
        if context.object == None: return False
        if context.object.type != 'MESH': return False
        
        return True
    
    def modal_nav(self, event):
        events_nav = {'MIDDLEMOUSE', 'WHEELINMOUSE','WHEELOUTMOUSE', 'WHEELUPMOUSE','WHEELDOWNMOUSE'} #TODO, better navigation, another tutorial
        handle_nav = False
        handle_nav |= event.type in events_nav

        if handle_nav: 
            return 'nav'
        return ''
    
    def modal_extend(self, context, event):
        
        if event.type == 'MOUSEMOVE':
            
            x, y = event.mouse_region_x, event.mouse_region_y
            
            #get mouse position at depth of the extrusion midpoint
            mouse_projected = view3d_utils.region_2d_to_location_3d(context.region, context.region_data, (x,y), self.new_geom_point)
            imx = self.ob.matrix_world.inverted()
            #calculate the delta vector
            local_delta = imx * mouse_projected - imx * self.new_geom_point
            
            #update bmverts position
            for v in self.extrude_verts:
                v.co = self.extrude_origins[v] + local_delta
                
            #how costly is this to do live? We will find out
            self.bme.to_mesh(self.ob.data)
            self.ob.data.update()
           
            
            
            return 'extend'
        
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
        
            #confirm vert positions
            self.new_geom = []
            self.new_geom_point = Vector((0,0,0))
            self.new_geom_draw_points = []
        
            self.extrude_verts = []
            self.extrude_origins = dict()
            self.extrude_geom_draw_points = []
            #clear "extrusion candidates"
            
            return 'main'
        
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            
            #delete extruded verts
            bmesh.ops.delete(self.bme, geom = self.extrude_verts, context = 1)
            self.bme.verts.ensure_lookup_table()
            self.bme.edges.ensure_lookup_table()
            self.bme.faces.ensure_lookup_table()
            self.bme.to_mesh(self.obj.data)
            self.ob.data.update()
            
            self.new_geom = []
            self.new_geom_point = Vector((0,0,0))
            self.new_geom_draw_points = []
        
            self.extrude_verts = []
            self.extrude_origns = dict()
            self.extrude_geom_draw_points = []
            return 'main'
        
    def modal_main(self,context,event):
        # general navigation
        nmode = self.modal_nav(event)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'

        if event.type == 'MOUSEMOVE':
            
            x, y = event.mouse_region_x, event.mouse_region_y
            
            
            
            #######Hover Operator Level Elements  ###
            if len(self.crv.screen_pts) == 0:
                if len(self.new_geom):
                    region = context.region
                    rv3d = context.region_data
                    extrude_screen_point = view3d_utils.location_3d_to_region_2d(region, rv3d, self.new_geom_point)
                    if extrude_screen_point != None:
                        R = Vector((x,y)) - extrude_screen_point
                        if R.length < 30:
                            
                            self.new_geom_point_color = (1,.1,.1,1)
                            self.new_geom_color = (1,.1,.1,1)
                        else:
                            self.new_geom_color = (.8, .8, .1, 1)
                            self.new_geom_point_color = (.1, .1, .8, 1)
            
            ######Hover Line Drawer Class Elments###
            self.crv.hover(context, x, y)
            
            if self.cut_method == 'SOLID':
                self.crv.calc_box()

            return 'main'
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            #if len(self.crv.screen_pts) >= 2: return 'main' #can't add more
            
            if len(self.crv.screen_pts) == 0:
                
                x,y = event.mouse_region_x, event.mouse_region_y
                if len(self.new_geom):
                    region = context.region
                    rv3d = context.region_data
                    extrude_screen_point = view3d_utils.location_3d_to_region_2d(region, rv3d, self.new_geom_point)
                    if extrude_screen_point != None:
                        R = Vector((x,y)) - extrude_screen_point
                        if R.length < 30:
                            
                            eds = [ele for ele in self.new_geom if isinstance(ele, bmesh.types.BMEdge)]
                            new_geom = bmesh.ops.extrude_edge_only(self.bme, edges = eds)
                            
                            new_verts  = [v for v in new_geom['geom'] if isinstance(v, bmesh.types.BMVert)]
                            
                            self.extrude_verts = new_verts
                            for v in self.extrude_verts:
                                self.extrude_origins[v] = v.co.copy()
                                
                                
                            return 'extend'
                
                context.window.cursor_modal_set('KNIFE')
            
                help_txt = "Left Click again to place end of cut"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                
            if len(self.crv.screen_pts) == 1:
                help_txt = "Left Click on side of line to delete \n click on model to limit cut to line length \n click in space to to cut infinitely."
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                
                
            x, y = event.mouse_region_x, event.mouse_region_y
            
            res = self.crv.click_add_point(context, x,y)
            
            if res == None and len(self.crv.screen_pts) == 2:
                print('bisecting object on 3rd click ')
                
                context.window.cursor_modal_set('WAIT')
                res2 = self.crv.ray_cast_ob(context, x, y)
                if res2:
                    filter_geom = True
                else:
                    filter_geom = False
            
                if self.cut_method == 'SOLID':
                    self.boolean_bisect_object(context, mesh_filter= True)
                    return 'finish'
                else:
                    self.bmesh_bisect_object(context, mesh_filter= filter_geom)
                    return 'main'

                context.window.cursor_modal_set('KNIFE')
                #help_txt = "Left Click to start a cut, then move mouse"
                #self.help_box.raw_text = help_txt
                #self.help_box.format_and_wrap_text()
                return 'main'
            
            return 'main'
        

        
        if event.type == 'P'  and event.value == 'PRESS':
            plane = bpy.data.objects.get('Plane')
            
            if plane == None: return 'main'
            mx = self.crv.calc_matrix(context)
            plane.matrix_world = mx
            return 'main'

        #if event.type == 'K' and event.value == 'PRESS':
        #    self.bmesh_bisect_object(context)
        #    return 'main'
            
               
        if event.type == 'RET' and event.value == 'PRESS':
            self.finish(context)
            return 'finish'
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            #need to return 'finish' to get the undo, since our 'cancel' function does not "reset" the bmesh data
            return 'finish' 

        return 'main'
    
        
    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['nav']     = self.modal_nav
        FSM['extend'] = self.modal_extend
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #clean up callbacks
            self.bme.free()
            context.window.cursor_modal_restore()
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def invoke(self,context, event):
         
        
        Model = context.object
        
               
        for ob in bpy.data.objects:
            if ob.name == 'Plane': continue
            ob.select = False
            ob.hide = True
        Model.select = True
        Model.hide = False
        
        #bpy.ops.view3d.view_selected()
        self.crv = LineDrawer(context,snap_type ='OBJECT', snap_object = Model)
        context.space_data.show_manipulator = False
        context.space_data.transform_manipulators = {'TRANSLATE'}
        v3d = bpy.context.space_data
        v3d.pivot_point = 'MEDIAN_POINT'
        
        
        #TODO, tweak the modifier as needed
        #help_txt = "Interactive Plane Cutting\n\nLeft click, move the mouse, and left click again.\nThen place your mouse on the side of the line to remove. \n Click on the model to isolate the cut to the line limits.\nClick off the model to cut beyond the end-points of the line."
        help_txt_open = "INTERACTIVE PLANE CUTTING OPEN\n\n-  LeftClick and move mouse to define a line across your model \n-  The line will stick to your mouse until you Left Click again\n-  LeftClick a 3rd time on the side of the line to be cut\n-  If you click on the model, the cut will be limited to the edges of the line \n-  If you click off of the model, the cut will extend into space\n\n\nEXTRUDING\n\n-  A dot will appear next to the most recent cut, you can click and move your mouse to extrude the new cut edge.\n-  LeftClick to confirm the position of the extrusion"
        help_txt_solid = "INTERACTIVE PLANE CUTTING SOLID\n\n-  LeftClick and move mouse to define a line across your model \n-  The line will stick to your mouse until you Left Click again\n-  A blue preview of the region to be deleted will present itself, everything behind the blue preview will be removed from the model\n-  LeftClick a 3rd time to confirm and the operator will end"
        
        if self.cut_method == 'SOLID':
            help_txt = help_txt_solid
        else:
            help_txt = help_txt_open
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(plane_cut_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        
        self.bme= bmesh.new()
        self.bme.from_mesh(Model.data)
        self.ob = Model
        self.cursor_updated = True
        
        
        self.new_geom = []
        self.new_geom_point = Vector((0,0,0))
        self.new_geom_draw_points = []
        
        self.extrude_verts = []
        self.extrude_origins = dict()
        self.extrude_geom_draw_points = []
        
        
        
        self.new_geom_color = (.8, .8, .1, 1)
        self.new_geom_point_color = (.1, .1, .8, 1)
        
        return {'RUNNING_MODAL'}

    def bmesh_bisect_object(self, context, mesh_filter = True):
        
        if len(self.crv.screen_pts) != 2: return
        
        mx_ob = self.ob.matrix_world
        imx_ob = mx_ob.inverted()
        imx_ob_no = imx_ob.to_3x3()  #assumes no  scaling
        
        mx_cut = self.crv.calc_matrix(context)
        imx_cut = mx_cut.inverted()

        #cut location in oject local coords        
        l_cut = imx_ob * mx_cut.to_translation()
        
        
        #need the local direction of the normal
        #first, get the world direction
        mx_no_cut = imx_cut.transposed().to_3x3()
        #then transform it to the local space
        no_cut = imx_ob_no * mx_no_cut.to_3x3() * Vector((0,0,1))
        
        
        if mesh_filter:
            
            print('filtering verts')
            
            local_x = imx_ob_no * mx_no_cut.to_3x3() * Vector((1,0,0))
            local_x.normalize()
            
            w0, w1, world_y = self.crv.calc_line_limits(context)
            
            L = w1 - w0
            print(L.length)
            
            
            filter_verts = []
            for v in self.bme.verts:
                
                v_prime = v.co - l_cut
                vx = v_prime.dot(local_x)
                
                if abs(vx) < .5 * L.length:
                    filter_verts += [v]
            
            filter_edges = set()
            filter_faces = set()
            
            for v in filter_verts:
                filter_edges.update(v.link_edges[:])
                filter_faces.update(v.link_faces[:])    
            
            
            cut_geom = filter_verts + list(filter_edges) + list(filter_faces)
        else:
            cut_geom = self.bme.verts[:] + self.bme.edges[:] +self.bme.faces[:]
            
        gdict = bmesh.ops.bisect_plane(self.bme, geom=cut_geom,
                                     dist=0.000001, 
                                     plane_co = l_cut,
                                     plane_no=no_cut, 
                                     use_snap_center=False, 
                                     clear_outer=True, 
                                     clear_inner=False)
        
        
        new_stuff = gdict['geom_cut']
        new_vs = [ele for ele in new_stuff if isinstance(ele, bmesh.types.BMVert)]
        new_edges = [ele for ele in new_stuff if isinstance(ele, bmesh.types.BMEdge)]
        
        self.bme.verts.ensure_lookup_table()
        self.bme.edges.ensure_lookup_table()
        self.bme.faces.ensure_lookup_table()
        
        self.new_geom = new_vs + new_edges
        self.new_geom_point = get_com_bme(self.bme, [v.index for v in new_vs], self.ob.matrix_world) + 5 * mx_no_cut.to_3x3()*Vector((0,0,1))
        self.new_geom_draw_points = [self.ob.matrix_world * v.co for v in new_vs]
        
        self.bme.to_mesh(self.ob.data)
        self.ob.data.update()
        self.crv.screen_pts = [] #reset
        self.crv.selected = -1
        return True
    
    def boolean_bisect_object(self, context, mesh_filter = True):
        
        mx_ob = self.ob.matrix_world
        imx_ob = mx_ob.inverted()
        imx_ob_no = imx_ob.to_3x3()  #assumes no  scaling
        
        mx_cut = self.crv.calc_matrix(context, depth = 'BOUNDS')
        imx_cut = mx_cut.inverted()
        
        #need the local direction of the normal
        #first, get the world direction
        mx_no_cut = imx_cut.transposed().to_3x3()
        #then transform it to the local space
        no_cut = imx_ob_no * mx_no_cut.to_3x3() * Vector((0,0,1))
        
        
        bbox = self.ob.bound_box[:]
        bbox_vs = []
        for v in bbox:
            a = Vector(v)
            bbox_vs += [self.ob.matrix_world * a]
        
        v_max_x= max(bbox_vs, key = lambda x: x[0])
        v_min_x = min(bbox_vs, key = lambda x: x[0])
        v_max_y= max(bbox_vs, key = lambda x: x[1])
        v_min_y = min(bbox_vs, key = lambda x: x[1])
        v_max_z= max(bbox_vs, key = lambda x: x[2])
        v_min_z = min(bbox_vs, key = lambda x: x[2])
        
        diag_xyz = (((v_max_x - v_min_x)[0])**2 + ((v_max_y - v_min_y)[1])**2+((v_max_z - v_min_z)[1])**2)**.5
        
        cut_plane = bpy.data.meshes.new('Plane Cut')
        cut_ob = bpy.data.objects.new('Plane Cut', cut_plane)
        context.scene.objects.link(cut_ob)
        cut_ob.draw_type = 'WIRE'
        
        if mesh_filter:
            
            print('filtering verts')
            
            local_x = imx_ob_no * mx_no_cut.to_3x3() * Vector((1,0,0))
            local_x.normalize()
            
            w0, w1, world_y = self.crv.calc_line_limits(context)
            
            L = w1 - w0
            print(L.length)
            
            Lz = world_y.length
            
            cube_bme = bmesh.new()
            bmesh.ops.create_cube(cube_bme, size = 1, matrix = Matrix.Identity(4))
            bmesh.ops.subdivide_edges(cube_bme, edges = cube_bme.edges[:], cuts = 50, use_grid_fill = True)
            cube_bme.to_mesh(cut_plane)
            
            T = Matrix.Translation(.5 * world_y)
            cut_ob.matrix_world = T * mx_cut
            cut_ob.scale[1] = diag_xyz
            cut_ob.scale[0] = L.length
            cut_ob.scale[2] = Lz
            cut_ob.hide = True
            
        else:    
            
            
            grid_bme = bmesh.new()
            bmesh.ops.create_grid(grid_bme, x_segments = 150, y_segments = 150, size = diag_xyz)
            for f in grid_bme.faces:
                f.normal_flip()
            
            grid_bme.to_mesh(cut_plane)
            
            mx_cut = self.crv.calc_matrix(context)
            cut_ob.matrix_world = mx_cut
            
            cut_ob.hide = True
        
        mod = self.ob.modifiers.new('Plane Cut', type = 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = cut_ob
        
        self.crv.screen_pts = [] #reset
        self.crv.selected = -1
        return None
    
        
    def finish(self, context):
        #settings = get_settings()
        #apply all modifiers
        context.window.cursor_modal_restore()
        tracking.trackUsage("D3Splint:PlaneCutRaw",None)
        
        
def register():
    bpy.utils.register_class(D3SPLINT_OT_plane_cut_mesh_rough)
    bpy.utils.register_class(D3SPLINT_OT_activate_all_cuts)
    bpy.utils.register_class(D3SPLINT_OT_finalize_all_cuts)
    bpy.utils.register_class(D3SPLINT_OT_pause_all_cuts)
    bpy.utils.register_class(D3SPLINT_OT_batch_process_plane_cuts)
     
def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_plane_cut_mesh_rough)
    bpy.utils.unregister_class(D3SPLINT_OT_activate_all_cuts)
    bpy.utils.unregister_class(D3SPLINT_OT_finalize_all_cuts)
    bpy.utils.unregister_class(D3SPLINT_OT_pause_all_cuts)
    bpy.utils.register_class(D3SPLINT_OT_batch_process_plane_cuts)