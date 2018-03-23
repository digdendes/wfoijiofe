import bpy
import bmesh

from curve import LineDrawer
from textbox import TextBox
import tracking

from mathutils import Vector, Matrix, Quaternion
from test.test_binop import isint

def landmarks_draw_callback(self, context):  
    self.crv.draw(context)
    self.help_box.draw()    
    
class D3SPLINT_OT_plane_cut_mesh_rough(bpy.types.Operator):
    """Click and draw a line to cut mesh"""
    bl_idname = "d3splint.splint_plane_cut"
    bl_label = "Plane Cut Mesh Raw"
    bl_options = {'REGISTER', 'UNDO'}
    
    cut_method = bpy.props.EnumProperty(name = 'Mode', items = (('SURFACE','SURFACE','SURFACE'), ('SOLID', 'SOLID','SOLID')), default = 'SURFACE')
    @classmethod
    def poll(cls,context):
        c1 = context.object != None
        c2 = context.object.type == 'MESH'
        
        return c1 and c2
    
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
            
            x, y = event.mouse_region_x, event.mouse_region_y
            self.crv.hover(context, x, y)
            return 'main'
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            #if len(self.crv.screen_pts) >= 2: return 'main' #can't add more
            
            if len(self.crv.screen_pts) == 0:
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
                
                
                res2 = self.crv.ray_cast_ob(context, x, y)
                if res2:
                    filter_geom = True
                else:
                    filter_geom = False
            
                if self.cut_method == 'SOLID':
                    self.boolean_bisect_object(context)
                else:
                    self.bmesh_bisect_object(context, mesh_filter= filter_geom)
                    
                    
               
                    
                
                context.window.cursor_modal_set('WAIT')
                
                context.window.cursor_modal_set('KNIFE')
                help_txt = "Left Click to start a cut, then move mouse"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                return 'main'
            
            return 'main'
        
        if event.type == 'DEL' and event.value == 'PRESS':
            self.crv.click_delete_point()
            return 'main'
        
        if event.type == 'P'  and event.value == 'PRESS':
            plane = bpy.data.objects.get('Plane')
            
            if plane == None: return 'main'
            mx = self.crv.calc_matrix(context)
            plane.matrix_world = mx
            return 'main'

        if event.type == 'K' and event.value == 'PRESS':
            self.bmesh_bisect_object(context)
            return 'main'
            
               
        if event.type == 'RET' and event.value == 'PRESS':
            if len(self.crv.screen_pts) != 4:
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
        
        bpy.ops.view3d.view_selected()
        self.crv = LineDrawer(context,snap_type ='OBJECT', snap_object = Model)
        context.space_data.show_manipulator = False
        context.space_data.transform_manipulators = {'TRANSLATE'}
        v3d = bpy.context.space_data
        v3d.pivot_point = 'MEDIAN_POINT'
        
        
        #TODO, tweak the modifier as needed
        help_txt = "Click and Draw a line to slice and dice"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(landmarks_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        
        self.bme= bmesh.new()
        self.bme.from_mesh(Model.data)
        self.ob = Model
        self.cursor_updated = True
        
        self.new_geom = []
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
        
        self.new_geom = new_vs
        self.bme.to_mesh(self.ob.data)
        self.ob.data.update()
        self.crv.screen_pts = [] #reset
        self.crv.selected = -1
        return True
    
    def boolean_bisect_object(self, context):
        
        
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
        context.window.cursor_modal_restore()
        tracking.trackUsage("D3Splint:PlaneCutRaw",None)
        
        
def register():
    bpy.utils.register_class(D3SPLINT_OT_plane_cut_mesh_rough)
    
     
def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_plane_cut_mesh_rough)
    