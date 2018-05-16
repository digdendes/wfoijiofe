'''
Created on Nov 25, 2017

@author: Patrick
'''
import bpy
from mathutils import Vector, Matrix, Quaternion
from bmesh_fns import join_objects, bmesh_loose_parts
import bmesh
import tracking
from curve import LineDrawer, TextLineDrawer
from textbox import TextBox
from common_utilities import get_settings
from common_drawing import outline_region
from bpy_extras.view3d_utils import location_3d_to_region_2d
        

t_topo = {}
t_topo['FACES'] = 56
t_topo['EDGES'] = 113
t_topo['VERTS'] = 58
        
def stencil_text_callback(self, context):  
    self.help_box.draw()
    self.crv.draw(context)
    prefs = get_settings()
    r,g,b = prefs.active_region_color
    outline_region(context.region,(r,g,b,1))     
    
class D3SPLINT_OT_stencil_text(bpy.types.Operator):
    """Click and draw a line to place text on the model"""
    bl_idname = "d3splint.stencil_text"
    bl_label = "Stencil Text"
    bl_options = {'REGISTER', 'UNDO'}
    
    
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
    
    def modal_main(self,context,event):
        # general navigation
        nmode = self.modal_nav(event)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'

        if event.type == 'MOUSEMOVE':
            
            x, y = event.mouse_region_x, event.mouse_region_y
            self.crv.hover(context, x, y)
            if len(self.crv.screen_pts) != 2:
                self.crv.calc_text_values()
            return 'main'
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            #if len(self.crv.screen_pts) >= 2: return 'main' #can't add more
            
            if len(self.crv.screen_pts) == 0:
                context.window.cursor_modal_set('CROSSHAIR')
            
                #help_txt = "Left Click again to place end of line"
                #self.help_box.raw_text = help_txt
                #self.help_box.format_and_wrap_text()
                
            #if len(self.crv.screen_pts) == 1:
                #help_txt = "Left Click to end the text"
                #self.help_box.raw_text = help_txt
                #self.help_box.format_and_wrap_text()
                
                
            x, y = event.mouse_region_x, event.mouse_region_y
            
            res = self.crv.click_add_point(context, x,y)
            
            
            return 'main'
        
        if event.type == 'DEL' and event.value == 'PRESS':
            self.crv.click_delete_point()
            return 'main'
        
        if event.type == 'P'  and event.value == 'PRESS':
            self.create_and_project_text(context)
            return 'main'            
        
        if event.type == 'RIGHTMOUSE'  and event.value == 'PRESS':
            
            x, y = event.mouse_region_x, event.mouse_region_y
            
            v3d = context.space_data
            rv3d = v3d.region_3d
            rot = rv3d.view_rotation
            
            X = rot * Vector((1,0,0))
            Y = rot * Vector((0,1,0))
            Z = rot * Vector((0,0,1))
            
            loc, no = self.crv.ray_cast_pt(context, (x,y))
            no_mx = self.crv.snap_ob.matrix_world.inverted().transposed().to_3x3()
            world_no = no_mx * no
            
            
            
            world_no_aligned = world_no - world_no.dot(X) * X
            world_no_aligned.normalize()
            
            angle = world_no_aligned.angle(Z)
            
            if world_no.dot(Y) > 0:
                angle = -1 * angle
            R_mx = Matrix.Rotation(angle, 3, X)
            R_quat = R_mx.to_quaternion()
            rv3d.view_rotation = R_quat * rot
            
            return 'main'
               
        if event.type == 'LEFT_ARROW' and event.value == 'PRESS':
            print('reset old matrix')
            v3d = context.space_data
            rv3d = v3d.region_3d
            rv3d.view_rotation = self.last_view_rot
            rv3d.view_location = self.last_view_loc
            rv3d.view_matrix = self.last_view_matrix
            rv3d.view_distance = self.last_view_distance
            
            rv3d.update()
            return 'main'
        
        if event.type == 'RET' and event.value == 'PRESS':
            if len(self.crv.screen_pts) != 2:
                return 'main'
            
            if not len(self.crv.projected_points):
                self.create_and_project_text(context)
            
            self.finalize_text(context)    
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
         
        
        label_message = get_settings().d3_model_label
        Model = context.object
        
               
        for ob in bpy.data.objects:
            if "D3T Label" in ob.name: continue
            ob.select = False
            ob.hide = True
        Model.select = True
        Model.hide = False
        
        #bpy.ops.view3d.view_selected()
        self.crv = TextLineDrawer(context,snap_type ='OBJECT', snap_object = Model, msg = label_message)
        
        context.space_data.use_ssao = True
        
        
        #TODO, tweak the modifier as needed
        help_txt = "INTERACTIVE LABEL STENCIL\n\n-  LeftClick and move mouse to define a line across your model \n-  The line will stick to your mouse until you Left Click again\n-  A preview of the text label will follow your line\n  -press 'ENTER' to project the text onto your model and finish the operator.\n\nADVANCED USAGE\n\n-RightMouse in the middle of the label to snap your view perpendicular to the model surface, you may need to adjust the position slightly\n-  You can press 'P' to project the  text onto the object without leaving the operator.  You can then alter your view to inspect the text projection.\n-  LEFT_ARROW key to snap back to the original view, you can then modify your viewing angle and press 'P' again.  When satisfied, press 'ENTER' to finish."
        
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        
        
        
        self.bme= bmesh.new()
        self.bme.from_mesh(Model.data)
        self.ob = Model
        self.cursor_updated = True
        
        #get new text data and object in the scene
        self.txt_crv = bpy.data.curves.new("D3T Label", type = 'FONT')
        self.txt_crv_ob = bpy.data.objects.new("D3T Label", self.txt_crv)
        context.scene.objects.link(self.txt_crv_ob)
        context.scene.update()
        
        self.txt_crv_ob.hide = True
            
        self.txt_me_data = self.txt_crv_ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')    
        self.txt_me_ob = bpy.data.objects.new("D3T Label Mesh", self.txt_me_data)
        context.scene.objects.link(self.txt_me_ob)
          
        self.txt_crv.align_x = 'LEFT'
        self.txt_crv.align_y = 'BOTTOM'    
        self.txt_crv.body = label_message  #TODO hook up to property
        
        
        context.space_data.show_manipulator = False
        
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(stencil_text_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        
        v3d = context.space_data
        rv3d = v3d.region_3d
        
        self.last_view_rot = rv3d.view_rotation
        self.last_view_loc = rv3d.view_location
        self.last_view_matrix = rv3d.view_matrix.copy()
        self.last_view_distance = rv3d.view_distance
        
        return {'RUNNING_MODAL'}

    def create_and_project_text(self, context):
        
        self.crv.project_line(context, res = 20)
        
        if len(self.crv.projected_points) == 0:
            return
        
        v3d = context.space_data
        rv3d = v3d.region_3d
        self.last_view_rot = rv3d.view_rotation
        self.last_view_loc = rv3d.view_location
        self.last_view_matrix = rv3d.view_matrix.copy()
        self.last_view_distance = rv3d.view_distance
            
        txt_ob = self.txt_crv_ob
        txt_ob.matrix_world = Matrix.Identity(4)
        
        bbox = txt_ob.bound_box[:]
        bbox_vs = []
        for v in bbox:
            bbox_vs += [Vector(v)]
        
        v_max_x= max(bbox_vs, key = lambda x: x[0])
        v_min_x = min(bbox_vs, key = lambda x: x[0])
        
        X_dim = v_max_x[0] - v_min_x[0]
        print("The text object has %f length" % X_dim)
        
        #really need a path and bezier class for this kind of stuff
        proj_path_len = 0
        s_v_map = {}
        s_v_map[0.0] = 0
        for i in range(0,19):
            seg = self.crv.projected_points[i + 1] - self.crv.projected_points[i]
            proj_path_len += seg.length
            s_v_map[proj_path_len] = i+1
        
        
        def find_path_len_v(s_len):
            '''
            Get the interpolated position along a polypath
            at a given length along the path.
            '''
            p_len = 0
            
            for i in range(0, 19):
                seg = self.crv.projected_points[i + 1] - self.crv.projected_points[i]
                p_len += seg.length
                
                if p_len > s_len:
                    delta = p_len - s_len
                    vec = seg.normalized()
                    
                    v = self.crv.projected_points[i] + delta * vec
        
                    return v, vec
            return self.crv.projected_points[i+1], seg.normalized()
        
        #place the text object on the path
        s_factor = proj_path_len/X_dim
        S = Matrix.Scale(s_factor, 4)
        loc = self.crv.projected_points[0]
        T = Matrix.Translation(loc)
        R = self.crv.calc_matrix(context)
        
        
        txt_ob.matrix_world = T * R * S
            
        me = txt_ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        
        bme = bmesh.new()
        bme.from_mesh(me)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        #bullshit it doesn't work
        #print('dissolving degeneration')
        #ret = bmesh.ops.dissolve_degenerate(bme, dist = .001, edges = bme.edges[:])
        #print(ret)
        
        print('beauty faces')
        bmesh.ops.beautify_fill(bme, faces = bme.faces[:], edges = bme.edges[:])
        
        
        characters = bmesh_loose_parts(bme, selected_faces = None, max_iters = 200)
        
        #parameterize each character based on it's center of mass in the x direction
        #eg, it's length down the curve path
        
        ts = []
        path_pts = []
        for fs in characters:
            vs = set()
            com = Vector((0,0,0))
            for f in fs:
                vs.update(f.verts[:])
            for v in vs:
                com += v.co
            com *= 1/len(vs)
            
            world_com = T * R * S * com
            point_2d = location_3d_to_region_2d(context.region, context.space_data.region_3d, world_com)
            loc, no = self.crv.ray_cast_pt(context, point_2d)
            
            world_projected_com = self.crv.snap_ob.matrix_world * loc
            
            #self.crv.projected_points += [world_projected_com]
            
            world_delta = world_projected_com - world_com
            
            local_delta = (R * S).inverted().to_3x3() * world_delta
            
            
            ts += [com[0]/X_dim]
            
            path_pt, path_tan = find_path_len_v(com[0]/X_dim * proj_path_len)
            
            local_tan = (R * S).inverted().to_3x3() * path_tan
            
            angle_dif = Vector((1,0,0)).angle(local_tan)
            
            if local_tan.cross(Vector((1,0,0))).dot(Vector((0,1,0))) < 0:
                angle_dif *= -1
                
                
                
            r_prime = Matrix.Rotation(-angle_dif, 4, 'Y')
            print('The angle difference is %f' % angle_dif)
            #translate to center
            for v in vs:
                v.co -= com
                
                v.co = r_prime * v.co
                
                v.co += com + local_delta    
            
            
            

        #text mesh
        
        bme.to_mesh(me)
        self.txt_me_ob.data = me
        
        if self.txt_me_data != None:
            self.txt_me_data.user_clear()
            bpy.data.meshes.remove(self.txt_me_data)
            
        self.txt_me_data = me
        
        
        self.txt_me_ob.matrix_world = T * R * S
        bme.free()
        
        if 'Solidify' not in self.txt_me_ob.modifiers:
            mod = self.txt_me_ob.modifiers.new('Solidify',type = 'SOLIDIFY')
            mod.offset = 0
        
        else:
            mod = self.txt_me_ob.modifiers.get('Solidify')
            
        mod.thickness = .5 * 1/s_factor #TODO put as setting
        
        return True
    
    
    def finalize_text(self,context):
        
        context.scene.objects.unlink(self.txt_crv_ob)
        bpy.data.objects.remove(self.txt_crv_ob)
        bpy.data.curves.remove(self.txt_crv)
        
        
        return
        
        
            
    def finish(self, context):
        #settings = get_settings()
        context.window.cursor_modal_restore()
        tracking.trackUsage("D3Splint:StencilText",None)
        

class D3Splint_place_text_on_model(bpy.types.Operator):
    """Place Custom Text at 3D Cursor on template Box"""
    bl_idname = "d3splint.place_text_on_model"
    bl_label = "Custom Label"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    message = bpy.props.StringProperty(default = '')
    font_size = bpy.props.FloatProperty(default = 3.0, description = "Text Size", min = 1, max = 7)
    depth = bpy.props.FloatProperty(default = 1.0, description = "Text Depth", min = .2, max = 7)
    
    align_y = ['BOTTOM', 'CENTER', 'TOP']
    items_align_y = []
    for index, item in enumerate(align_y):
        items_align_y.append((item, item, item))
       
    y_align = bpy.props.EnumProperty(items = items_align_y, name = "Vertical Alignment", default = 'BOTTOM')
    align_x = ['LEFT', 'CENTER', 'RIGHT']
    items_align_x = []
    for index, item in enumerate(align_x):
        items_align_x.append((item, item, item))
    x_align = bpy.props.EnumProperty(items = items_align_x, name = "Horizontal Alignment", default = 'LEFT')
    
    invert = bpy.props.BoolProperty(default = False, description = "Mirror text")
    spin = bpy.props.BoolProperty(default = False, description = "Spin text 180")
    @classmethod
    def poll(cls, context):
        
        if not context.object:
            return False
        
        if "D3T Label" in context.object.name:
            return False
        
        return True
            
    
    def invoke(self, context, event):
        
        
        return context.window_manager.invoke_props_dialog(self)

        
    def execute(self, context):
        context.scene.update()
        
        t_base = context.object
        #t_base = context.object
        
        mx = t_base.matrix_world
        imx = t_base.matrix_world.inverted()
        mx_norm = imx.transposed().to_3x3()
        
        cursor_loc = context.scene.cursor_location
        
        ok, new_loc, no, ind = t_base.closest_point_on_mesh(imx * cursor_loc)
        
        
        if (mx * new_loc - cursor_loc).length > 1:
            self.report({'ERROR'}, "Cursor not close to active object.  Right click model to select, Left click to place cursor, then Re-Do")
            return {'CANCELLED'}
        
        v3d = context.space_data
        rv3d = v3d.region_3d
        vrot = rv3d.view_rotation  
        
        
        X = vrot * Vector((1,0,0))
        Y = vrot * Vector((0,1,0))
        Z = vrot * Vector((0,0,1))
        
        #currently, the base should not be scaled or rotated...but perhaps it may be later
        #x = mx_norm * x
        #y = mx_norm * y
        #z = mx_norm * z    
        
        #if self.spin:
        #    x *= -1
        #    y *= -1
        
        if 'Emboss Boss' in bpy.data.curves and 'Emboss Boss' in bpy.data.objects:    
            txt_crv = bpy.data.curves.get('Emboss Boss')
            txt_ob = bpy.data.objects.get('Emboss Boss')
            txt_crv.body = self.message
            new_mods = False
            
        else:
            txt_crv = bpy.data.curves.new('Emboss Boss', type = 'FONT')
            txt_crv.body = self.message
        
        
            txt_crv.align_x = 'LEFT'
            txt_crv.align_y = 'BOTTOM'
            txt_ob = bpy.data.objects.new('Emboss Boss', txt_crv)
            context.scene.objects.link(txt_ob)
            new_mods = True
            
        #txt_crv.extrude = 1
        txt_crv.size = self.font_size
        txt_crv.resolution_u = 5
        #txt_crv.offset = .02  #thicken up the letters a little
        
        txt_ob.update_tag()
        
        context.scene.update()
        
        #handle the alignment
        translation = mx * new_loc
        
        bb = txt_ob.bound_box
        max_b = max(bb, key = lambda x: Vector(x)[1])
        max_y = max_b[1]
        
        if self.x_align == 'CENTER':
            delta_x = 0.5 * txt_ob.dimensions[0]
            if (self.spin and self.invert) or (self.invert and not self.spin):
                translation = translation + delta_x * X
            else:
                translation = translation - delta_x * X           
        elif self.x_align == 'RIGHT':
            delta_x = txt_ob.dimensions[0]
            
            if self.invert:
                translation = translation + delta_x * X 
            else:
                translation = translation - delta_x * X 
            
        if self.y_align == 'CENTER':
            delta_y = 0.5 * max_y
            translation = translation - delta_y * Y
        elif self.y_align == 'TOP':
            delta_y = max_y
            translation = translation - delta_y * Y
        #build the rotation matrix which corresponds
        R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
        R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
        R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2]
        R = R.to_4x4()

        S = Matrix.Identity(4)
        
        if self.invert:
            S[0][0] = -1
              
        T = Matrix.Translation(translation)
        
        
        txt_ob.matrix_world = T * R * S
        text_mx = T * R * S
        
        me = txt_ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme = bmesh.new()
        bme.from_mesh(me)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        characters = bmesh_loose_parts(bme, selected_faces = None, max_iters = 200)
        
        #snap each letter individually
        for fs in characters:
            vs = set()
            com = Vector((0,0,0))
            for f in fs:
                vs.update(f.verts[:])
            for v in vs:
                com += v.co
            com *= 1/len(vs)
            
            #TODO Ray Cast wit view direction
            world_com = text_mx * com
            ok, local_com, no, ind = t_base.closest_point_on_mesh(imx * world_com) 
            world_snap = mx * local_com
            delta = text_mx.inverted() * world_snap - com
            
            for v in vs:
                v.co += delta
        
        #text mesh
        bme.to_mesh(me)
        text_me_ob = bpy.data.objects.new('Emboss Mesh', me)
        context.scene.objects.link(text_me_ob)
        text_me_ob.matrix_world = text_mx
            
        if new_mods:
            mod = txt_ob.modifiers.new('Shrinkwrap', type = 'SHRINKWRAP')
            mod.wrap_method = 'PROJECT'
            mod.use_project_z = True
            mod.use_negative_direction = True
            mod.use_positive_direction = True
        
        
            tmod = txt_ob.modifiers.new('Triangulate', type = 'TRIANGULATE')
        
            smod = txt_ob.modifiers.new('Smooth', type = 'SMOOTH')
            smod.use_x = False
            smod.use_y = False
            smod.use_z = True
            smod.factor = 1
            smod.iterations = 2000
        
        
            solid = txt_ob.modifiers.new('Solidify', type = 'SOLIDIFY')
            solid.thickness = self.depth
            solid.offset = 0
        
        else:
            mod = txt_ob.modifiers.get('Shrinkwrap')
        mod.target = context.object           
        txt_ob.hide = False
        return {"FINISHED"}


class D3SPLINT_OT_emboss_text_on_model(bpy.types.Operator):
    """Joins all emboss text label objects and boolean add/subtraction from the object"""
    bl_idname = "d3tool.remesh_and_emboss_text"
    bl_label = "Emboss Text Into Object"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    positive = bpy.props.BoolProperty(default = True, description = 'Add text vs subtract text')
    remesh = bpy.props.BoolProperty(default = True, description = 'Remesh text vs subtract text')
    solver = bpy.props.EnumProperty(description="Boolean Method", items=(("BMESH", "Bmesh", "Faster/More Errors"),("CARVE", "Carve", "Slower/Less Errors")), default = "CARVE")
    @classmethod
    def poll(cls, context):
        if not context.object: return False
        c1 = "D3T Label" not in context.object.name
        c2 = context.object.type == 'MESH'
        
        return c1 and c2
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    
    def draw(self,contxt):
        layout = self.layout
        row = layout.row()
        row.prop(self, "positive")
        row = layout.row()
        row.prop(self, "remesh")
        row = layout.row()
        row.prop(self, "solver")
        
    def execute(self, context):
        

        labels = [ob for ob in bpy.data.objects if 'D3T Label Mesh' in ob.name]
        
        if len(labels) == 0:
            self.report({'ERROR'}, 'Need to add Stencil Text Labels')
            return {'CACELLED'}
        
        model = context.object
            
        all_obs = [ob.name for ob in bpy.data.objects]
        
        if self.remesh:
            bpy.ops.object.select_all(action = 'DESELECT')
            for ob in labels:
                ob.select = True
                ob.hide = False
                context.scene.objects.active = ob
                bpy.ops.object.mode_set(mode = 'EDIT')
                bpy.ops.mesh.select_all(action = 'SELECT')
                #bpy.ops.mesh.dissolve_degenerate()
                bpy.ops.mesh.separate(type = 'LOOSE')
                bpy.ops.object.mode_set(mode = 'OBJECT')
                bpy.ops.object.origin_set(type = 'ORIGIN_GEOMETRY', center = 'BOUNDS')
                
            labels_new = [ob for ob in bpy.data.objects if ob.name not in all_obs]    
            
            for ob in labels_new + labels:
                context.scene.objects.active = ob
                ob.select = True
                bpy.ops.object.mode_set(mode = 'EDIT')
                bpy.ops.mesh.select_all(action = 'SELECT')
                bpy.ops.mesh.dissolve_degenerate()
                bpy.ops.object.mode_set(mode = 'OBJECT')
                                        
                                        
                mod = ob.modifiers.new('Remesh', type = 'REMESH')
                mod.octree_depth = 5
                ob.update_tag()
            
            context.scene.update()
            label_final = join_objects(labels_new + labels, name = 'Text Labels')
            
            for ob in labels_new + labels:
                bpy.ops.object.select_all(action = 'DESELECT')
                context.scene.objects.unlink(ob)
                me = ob.data
                bpy.data.objects.remove(ob)
                bpy.data.meshes.remove(me)
            context.scene.objects.link(label_final)
        else:
            if len(labels) > 1:
                label_final = join_objects(labels_new, name = 'Text Labels')
                for ob in labels_new:
                    bpy.ops.object.select_all(action = 'DESELECT')
                    context.scene.objects.unlink(ob)
                    me = ob.data
                    bpy.data.objects.remove(ob)
                    bpy.data.meshes.remove(me)
                
                context.scene.objects.link(label_final)
                
            else:
                label_final = labels[0]
            
        label_final.select = True
        context.scene.objects.active = label_final
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.mesh.select_all(action = 'SELECT')
        bpy.ops.mesh.normals_make_consistent()
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
        #subtract the whole thing from the template block
        mod = model.modifiers.new(type = 'BOOLEAN', name = 'Boolean')
        mod.solver = 'CARVE'
        mod.object = label_final
        if self.positive:
            mod.operation = 'UNION'
        else:
            mod.operation = 'DIFFERENCE'
        
        label_final.hide = True
        return {"FINISHED"}
    
class D3SPLINT_OT_finalize_all_labels(bpy.types.Operator):
    """Apply all label boolean modifiers for label stencils"""
    bl_idname = "d3splint.splint_finalize_labels"
    bl_label = "Finalize Labels"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        if context.object == None: return False
        if context.object.type != 'MESH': return False
        
        return True
    
    def execute(self, context):
    
        if "D3T Label" in context.object.name:
            self.report({'ERROR'}, 'You need to select the object to be labelled, not a label object')
            return {'CANCELLED'}
        
        if len(context.object.modifiers) == 0:
            self.report({'ERROR'}, 'This object does not have any boolean modifiers which means it is finalized already')

        
        labels = []
        for mod in context.object.modifiers:
            if not mod.show_viewport:
                mod.show_viewport = True
        
            if hasattr(mod, 'object'):
                if "Text Labels" in mod.object.name:
                    labels.append(mod.object)
                        
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
        
        #clean up old labels:
        for ob in labels:
            context.scene.objects.unlink(ob)
            old_data = ob.data
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(old_data)
        
        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(D3Splint_place_text_on_model)
    bpy.utils.register_class(D3SPLINT_OT_emboss_text_on_model)
    bpy.utils.register_class(D3SPLINT_OT_stencil_text)
    bpy.utils.register_class(D3SPLINT_OT_finalize_all_labels)
   
def unregister():
    bpy.utils.unregister_class(D3Splint_place_text_on_model)
    bpy.utils.unregister_class(D3SPLINT_OT_emboss_text_on_model)
    bpy.utils.register_class(D3SPLINT_OT_stencil_text)
    bpy.utils.register_class(D3SPLINT_OT_finalize_all_labels)