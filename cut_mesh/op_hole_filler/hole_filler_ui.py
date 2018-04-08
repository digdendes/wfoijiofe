'''
Created on Oct 8, 2015

@author: Patrick
'''
import copy

import bpy
import bmesh
from mathutils import Matrix, Vector

from .hole_filler_datastructure import HoleManager
from .cache import holefiller_undo_cache
from ...textbox import TextBox
from ...common_utilities import get_settings
class HoleFiller_UI:
    
    def start_ui(self, context):
        
        self.stroke_smoothing = 0.75          # 0: no smoothing. 1: no change
        self.mode_pos        = (0, 0)
        self.cur_pos         = (0, 0)
        self.mode_radius     = 0
        self.action_center   = (0, 0)
        self.is_navigating   = False
        self.sketch_curpos   = (0, 0)
        self.sketch          = []
        
        self.hole_manager = HoleManager(context,context.object)
        
        prefs = get_settings()
        
        #d3_model_hole_fill_edge_length
        #d3_model_max_hole_size
        #d3_model_auto_fill_small
        
        if prefs.d3_model_auto_fill_small:
            n_filled = self.hole_manager.fill_holes_by_size(prefs. d3_model_max_hole_size)
        
        
        context.window.cursor_modal_set('CROSSHAIR')

        help_txt = "HOLE FILLER and INSPECTOR\n\n-   Holes are outlined in green\n-   Islands are outlined in red\n\
        -  Left Click to close hole or delete island\n\
        -  Right Click to blot a hole which will delete the immediately surrounding faces\n\
        -  'R' to recalculate and find new holes after blotting\n\n\nENTER to confirm and leave the Hole Filler session"
        
        
        if prefs.d3_model_auto_fill_small:
            help_txt += '\n\n Auto filled ' + str(n_filled) + ' holes on first pass'
            
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        
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
    def create_undo_snapshot(self, action):
        '''
        unsure about all the _timers get deep copied
        and if sel_gedges and verts get copied as references
        or also duplicated, making them no longer valid.
        '''

        p_data = copy.deepcopy(self.polytrim)
        holefiller_undo_cache.append((p_data, action))

        if len(holefiller_undo_cache) > 10:
            holefiller_undo_cache.pop(0)

    def undo_action(self):
        '''
        '''
        if len(holefiller_undo_cache) > 0:
            data, action = holefiller_undo_cache.pop()

            self.polytrim = data[0]

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