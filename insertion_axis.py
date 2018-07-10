'''
Created on Jul 7, 2018

@author: Patrick
'''
import time
import math

import bpy
import bmesh
from mathutils import Vector, Matrix, Color
from bpy_extras.view3d_utils import region_2d_to_location_3d, region_2d_to_origin_3d, region_2d_to_vector_3d
import odcutils
from common_utilities import bversion, get_settings
from common_drawing import outline_region
from textbox import TextBox
from survey_utils import bme_undercut_faces
from vertex_color_utils import bmesh_color_bmfaces, add_volcolor_material_to_obj



def pick_axis_draw_callback(self, context):  
    self.help_box.draw()
    prefs = get_settings()
    r,g,b = prefs.active_region_color
    outline_region(context.region,(r,g,b,1))
    
class D3SPLINT_OT_live_insertion_axis(bpy.types.Operator):
    """Pick Insertin Axis by viewing model from occlusal"""
    bl_idname = "d3splint.live_insertion_axis"
    bl_label = "Pick Insertion Axis"
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

        if event.type in {'NUMPAD_1', 'NUMPAD_3', "NUMPAD_7"} and event.value == 'PRESS':
            return 'nav'
              
        if "ARROW" in event.type and event.value == 'PRESS':
            self.rotate_arrow(context, event)
            return 'main'
        if event.type == 'LEFTMOUSE'  and event.value == 'PRESS':
            x, y = event.mouse_region_x, event.mouse_region_y
            res = self.click_model(context, x, y)
            if res:
                self.preview_direction(context)
            return 'main'
        
        if event.type == 'P' and event.value == 'PRESS':
            self.preview_direction(context)
            return 'main'
          
        if event.type == 'RET' and event.value == 'PRESS':
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
            #context.space_data.show_manipulator = True
            
            #if nmode == 'finish':
            #    context.space_data.transform_manipulators = {'TRANSLATE', 'ROTATE'}
            #else:
            #    context.space_data.transform_manipulators = {'TRANSLATE'}
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
        self.previewed = False
        
        max_model = self.splint.get_maxilla()
        mand_model = self.splint.get_mandible()
        
        if self.splint.jaw_type == 'MANDIBLE':
            Model = bpy.data.objects.get(mand_model)
            
        else:
            Model = bpy.data.objects.get(max_model)
     
        for ob in bpy.data.objects:
            ob.select = False
            ob.hide = True
        Model.select = True
        Model.hide = False
        context.scene.objects.active = Model
        
        add_volcolor_material_to_obj(Model, 'Undercut')
        
        #view a presumptive occlusal axis
        if self.splint.jaw_type == 'MAXILLA':
            bpy.ops.view3d.viewnumpad(type = 'BOTTOM')
        else:
            bpy.ops.view3d.viewnumpad(type = 'TOP')
            
        
        #add in a insertin axis direction
        loc = odcutils.get_bbox_center(Model, world = True)
        view = context.space_data.region_3d.view_rotation * Vector((0,0,1))    
        mxT = Matrix.Translation(loc)
        mxR = context.space_data.region_3d.view_rotation.to_matrix().to_4x4()
        
        if "Insertion Axis" in bpy.data.objects:
            ins_ob = bpy.data.objects.get('Insertion Axis')
            
        else:
            ins_ob = bpy.data.objects.new('Insertion Axis', None)
            ins_ob.empty_draw_type = 'SINGLE_ARROW'
            ins_ob.empty_draw_size = 20
            context.scene.objects.link(ins_ob)
        
        ins_ob.hide = False
        ins_ob.parent = Model
        ins_ob.matrix_world = mxT * mxR
        
        self.ins_ob = ins_ob
        
        #get bmesh data to process
        self.bme = bmesh.new()
        self.bme.from_mesh(Model.data)
        self.bme.verts.ensure_lookup_table()
        self.bme.edges.ensure_lookup_table()
        self.bme.faces.ensure_lookup_table()
        
        self.model = Model
        
        bpy.ops.view3d.view_selected()
        context.space_data.viewport_shade = 'SOLID'
        context.space_data.show_textured_solid = True
        
        #TODO, tweak the modifier as needed
        help_txt = "Pick Insertion Axis\n\n-  Position your viewing direction looking onto the model\n-  LEFT CLICK on the model\n-  You can then rotate and pan your view to assess the undercuts.  This process can be repeated until the desired insertion axis is chosen.\n\nADVANCED USE\n\n-  Use LEFT_ARROW, RIGHT_ARROW, UP_ARROW and DOWN_ARROW to accurately alter the axis.  Holding SHIFT while pressing the ARROW keys will alter the axis by 0.5 degrees.\nPress ENTER when finished"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(pick_axis_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        return {'RUNNING_MODAL'}

    def rotate_arrow(self, context, event):
        loc = Matrix.Translation(self.ins_ob.matrix_world.to_translation())
        rot_base = self.ins_ob.matrix_world.to_3x3()
        
        r_model = self.model.matrix_world.to_quaternion()
        
        
        if event.type == "UP_ARROW":
            axis = r_model * Vector((0,1,0))
        if event.type == "DOWN_ARROW":
            axis = r_model * Vector((0,-1,0))
        if event.type == "LEFT_ARROW":
            axis = r_model * Vector((1,0,0))
        if event.type == "RIGHT_ARROW":        
            axis = r_model * Vector((-1,0,0))
            
        
        if event.shift:
            ang = .5 * math.pi/180
        else:
            ang = 2.5*math.pi/180
        
        rot = Matrix.Rotation(ang, 3, axis)
        self.ins_ob.matrix_world = loc * (rot * rot_base).to_4x4()
        
        view = self.ins_ob.matrix_world.to_quaternion() * Vector((0,0,1))
        view_local = self.model.matrix_world.inverted().to_quaternion() * view
        fs_undercut = bme_undercut_faces(self.bme, view_local)
        vcolor_data = self.bme.loops.layers.color['Undercut']
        bmesh_color_bmfaces(self.bme.faces[:], vcolor_data, Color((1,1,1)))
        bmesh_color_bmfaces(fs_undercut, vcolor_data, Color((.8,.2,.5)))
        self.bme.to_mesh(self.model.data)
        return
    
    def click_model(self,context,x, y):
        region = context.region
        rv3d = context.region_data
        coord = x, y
        ray_max = 10000
        view_vector = region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = region_2d_to_origin_3d(region, rv3d, coord)
        ray_target = ray_origin + (view_vector * ray_max)

        imx = self.model.matrix_world.inverted()
        
        result, loc, normal, idx = self.model.ray_cast(imx * ray_origin, imx * ray_target - imx*ray_origin)

        return result
    
    def preview_direction(self, context):
        
        start = time.time()
        view = context.space_data.region_3d.view_rotation * Vector((0,0,1))
        mx = self.model.matrix_world
        i_mx = mx.inverted()
        view_local = i_mx.to_quaternion() * view
        fs_undercut = bme_undercut_faces(self.bme, view_local)
        print('there are %i undercts' % len(fs_undercut))
        vcolor_data = self.bme.loops.layers.color['Undercut']
        bmesh_color_bmfaces(self.bme.faces[:], vcolor_data, Color((1,1,1)))
        bmesh_color_bmfaces(fs_undercut, vcolor_data, Color((.8,.2,.5)))
        self.bme.to_mesh(self.model.data)
        finish = time.time()
        print('took %s to detect undercuts' % str(finish - start)[0:4])
        
        loc = odcutils.get_bbox_center(self.model, world = True)
        mxT = Matrix.Translation(loc)
        mxR = context.space_data.region_3d.view_rotation.to_matrix().to_4x4()
        self.ins_ob.matrix_world = mxT * mxR
        
        self.previewed = True
        return
        
    def finish(self, context):
        
        loc = odcutils.get_bbox_center(self.model, world = True)
        ins_ob = bpy.data.objects.get('Insertion Axis')
        view = ins_ob.matrix_world.to_quaternion() * Vector((0,0,1))
        
        #view = context.space_data.region_3d.view_rotation * Vector((0,0,1))
        odcutils.silouette_brute_force(context, self.model, view, True)
            
        #mxT = Matrix.Translation(loc)
        #mxR = context.space_data.region_3d.view_rotation.to_matrix().to_4x4()
        
        #if "Insertion Axis" in bpy.data.objects:
        #    ob = bpy.data.objects.get('Insertion Axis')
        #    ob.hide = False
        #else:
        #    ob = bpy.data.objects.new('Insertion Axis', None)
        #    ob.empty_draw_type = 'SINGLE_ARROW'
        #    ob.empty_draw_size = 20
        #    context.scene.objects.link(ob)
        
        bpy.ops.object.select_all(action = 'DESELECT')
        #ob.parent = self.model
        #ob.matrix_world = mxT * mxR
        context.scene.objects.active = self.model
        self.model.select = True
        
        #context.scene.cursor_location = loc
        #bpy.ops.view3d.view_center_cursor()
        #bpy.ops.view3d.viewnumpad(type = 'FRONT')
        #bpy.ops.view3d.view_selected()
        
        #context.space_data.transform_manipulators = {'ROTATE'}
        
        for i, mat in enumerate(self.model.data.materials):
            if mat.name == 'Undercut':
                break
        self.model.data.materials.pop(i, update_data = True)
        context.space_data.show_textured_solid = False
        self.splint.insertion_path = True
        self.model.lock_location[0], self.model.lock_location[1], self.model.lock_location[2] = True, True, True
        
        
def register():
    bpy.utils.register_class(D3SPLINT_OT_live_insertion_axis)

def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_live_insertion_axis)
