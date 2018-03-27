'''
Created on Oct 8, 2015

@author: Patrick
'''
import copy

import bpy
import bmesh
from mathutils import Matrix, Vector

from .splint_outline_datastructure import PolyLineKnife


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
        Model.hide = False
        
        if Model.name + '_silhouette' in bpy.data.objects:
            Survey = bpy.data.objects.get(Model.name + '_silhouette')
            Survey.hide = False
            
        context.scene.objects.active = Model
        bpy.ops.view3d.viewnumpad(type = 'FRONT')
        bpy.ops.view3d.view_selected()
        context.space_data.show_manipulator = False
        
        self.knife = PolyLineKnife(context, Model)
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