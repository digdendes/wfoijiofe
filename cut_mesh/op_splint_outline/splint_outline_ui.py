'''
Created on Oct 8, 2015

@author: Patrick
'''
import copy

import bpy
import bmesh
from mathutils import Matrix, Vector
import math

from .splint_outline_datastructure import PolyLineKnife
from ...textbox import TextBox

class SplintOutline_UI:
    
    def start_ui(self, context):
        
        self.stroke_smoothing = 0.75          # 0: no smoothing. 1: no change
        self.mode_pos        = (0, 0)
        self.cur_pos         = (0, 0)
        self.mode_radius     = 0
        self.action_center   = (0, 0)
        self.is_navigating   = False
        self.sketch_curpos   = (0, 0)
        self.sketch          = []
        
        self.splint = context.scene.odc_splints[0]   
        self.crv = None
        
        Model = bpy.data.objects[self.splint.model]
        for ob in bpy.data.objects:
            ob.select = False
            ob.hide = True
        Model.select = True
        Model.hide = True
        
        
        model_data = Model.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        
        #need to cache a detail optimized version of the model
        #copy the original model data
        #detail optimize it first
        #then cut it
        if 'Trimmed_Model' in bpy.data.objects:
            trimmed_obj = bpy.data.objects.get('Trimmed_Model')
            trimmed_obj.data = model_data
        else:
            
            #trimmed_model = bpy.data.meshes.new('Trimmed_Model')
            trimmed_obj = bpy.data.objects.new('Trimmed_Model', model_data)
            context.scene.objects.link(trimmed_obj)
        
            cons = trimmed_obj.constraints.new('COPY_TRANSFORMS')
            cons.target = bpy.data.objects.get(self.splint.model)
            
        context.scene.objects.active = trimmed_obj
        trimmed_obj.select = True
        trimmed_obj.hide = False
        #bpy.ops.object.mode_set(mode = 'SCULPT')
        #if not trimmed_obj.use_dynamic_topology_sculpting:
        #    bpy.ops.sculpt.dynamic_topology_toggle()
        
        print('setting the mode')
        bpy.ops.object.mode_set(mode = 'SCULPT')
        
        #if not trimmed_obj.use_dynamic_topology_sculpting :       
        #    bpy.ops.sculpt.dynamic_topology_toggle()
        
        print('getting the bmesh')    
        bme = bmesh.new()
        bme.from_mesh(trimmed_obj.data)
        
        print('getting the mask')
        mask = bme.verts.layers.paint_mask.verify()
        
        #print(mask)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        print('checking the length')
        long_eds = [ed for ed in bme.edges if ed.calc_length() > .75]
        
        if len(long_eds) < 10:
            print('no long edges')
            bme.free()
            
        else:
            print('there are many long edges')
            long_faces = set()
            for ed in long_eds:
                long_faces.update(ed.link_faces)
            
            long_verts = set()
            for f in long_faces:
                long_verts.update(f.verts[:])
                
            for v in bme.verts:
                if v in long_verts:
                    v.select_set(True)
                    v[mask] = 0.0
                else:
                    v[mask] = 1.0   
            
            bme.to_mesh(trimmed_obj.data)
            trimmed_obj.data.update()
            
            print('changing to dyntopo')
            if not trimmed_obj.use_dynamic_topology_sculpting :       
                bpy.ops.sculpt.dynamic_topology_toggle()
            context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
            context.scene.tool_settings.sculpt.constant_detail_resolution = 1.5
            bpy.ops.sculpt.detail_flood_fill()
            bme.free()
        
        bpy.ops.object.mode_set(mode = 'OBJECT')
          

        bpy.ops.view3d.viewnumpad(type = 'FRONT')
        bpy.ops.view3d.view_selected()
        context.space_data.show_manipulator = False
        
        
        if Model.name + '_silhouette' in bpy.data.objects:
            Survey = bpy.data.objects.get(Model.name + '_silhouette')
            Survey.hide = False
        
        #self.knife = PolyLineKnife(context, Model)
        
        help_txt = "DRAW SPLINT OUTLINE\n\nTHIS FUNCTION IS ALPHA AND YOU SHOULD SAVE FIRST\n\nLeft click one time to create a start point\n-   Single Left Click to add individual points \n-  Hover an existing point, then sketch from it to draw a smooth curve\n-  Right click to delete a point n\ Sketch from curve and back into curve to replace segment  \n Left Click final point to close the loop\n\nThen press C to preview the cut.\n-    Red segments should be re-drawn or points moved until they turn green\n\nPRESS S and click on the part of the model that defines the splint"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        
        self.knife = PolyLineKnife(context, trimmed_obj)
        context.window.cursor_modal_set('CROSSHAIR')
        context.area.header_text_set("Mark The Outline of the Splint\n  Left click to place cut points on the mesh, then press 'C' to preview the cut")
        
    def end_ui(self, context):            
        context.area.header_text_set()
        context.window.cursor_modal_restore()
        
    def cleanup(self, context, cleantype=''):
        '''
        remove temporary object
        '''
        if cleantype == 'commit':
            pass

        elif cleantype == 'cancel':
            pass
    ###############################
    # undo functions
    def create_polytrim_from_bezier(self, ob_bezier):
        #TODO, read al the bezier points or interp the bezier?
        return
        
    def create_polytrim_from_vert_loop(self, ob_bezier):
        #TODO, read all the mesh data in and make a polylineknife
        return
        
    def create_polystrips_from_greasepencil(self):
        Mx = self.obj_orig.matrix_world
        gp = self.obj_orig.grease_pencil
        gp_layers = gp.layers
        # for gpl in gp_layers: gpl.hide = True
        strokes = [[(p.co,p.pressure) for p in stroke.points] for layer in gp_layers for frame in layer.frames for stroke in frame.strokes]
        self.strokes_original = strokes