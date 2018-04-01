'''
Created on Oct 8, 2015

@author: Patrick
'''
import bpy
import bmesh

from ..modaloperator import ModalOperator
from .splint_outline_ui            import SplintOutline_UI
from .splint_outline_ui_modalwait  import SplintOutline_UI_ModalWait
from .splint_outline_ui_tools      import SplintOutline_UI_Tools
from .splint_outline_ui_draw       import SplintOutline_UI_Draw

from ..common_utilities import showErrorMessage

class D3Splint_CutSplintMargin(ModalOperator, SplintOutline_UI, SplintOutline_UI_ModalWait, SplintOutline_UI_Tools, SplintOutline_UI_Draw):
    ''' Mark Splint Outline Cut Mesh version '''
    
    
    bl_idname      = "d3splint.polytrim_splint_outline"
    bl_label       = "Splint Outline Polytrim"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_options = {'REGISTER','UNDO'}
    
    def __init__(self):
        FSM = {}
        FSM['sketch']  = self.modal_sketch
        FSM['grab']    = self.modal_grab
        FSM['inner']   = self.modal_inner

        ModalOperator.initialize(self, FSM)
    
    def start_poll(self, context):
        ''' Called when tool is invoked to determine if tool can start '''
                
        if context.mode != 'OBJECT':
            showErrorMessage('Object Mode please')
            return False
        
        splint = context.scene.odc_splints[0]
        
        if splint.model == '':
            showErrorMessage('Need to Set Splint Model')
            return False
        if splint.model not in bpy.data.objects:
            showErrorMessage('Splint Model has been removed')
            return False

        return True
    
    def start(self, context):
        ''' Called when tool is invoked '''
        self.start_ui(context)
    
    def end(self, context):
        ''' Called when tool is ending modal '''
        self.end_ui(context)
    
    def end_commit(self, context):
        
        
        
        self.cleanup(context, 'commit')
        
        pmodel = bpy.data.objects.get('Perim Model')
        pmodel.select = True
        context.scene.objects.active = pmodel
        
        bpy.ops.object.mode_set(mode = 'SCULPT')
        if not pmodel.use_dynamic_topology_sculpting:
            bpy.ops.sculpt.dynamic_topology_toggle()
        bpy.ops.paint.mask_flood_fill(mode = 'VALUE', value = 0)
        context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
        context.scene.tool_settings.sculpt.constant_detail_resolution = 5.5
        bpy.ops.sculpt.detail_flood_fill()
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
        tmodel = bpy.data.objects.get('Trimmed_Model')
        
        bme = bmesh.new()
        bme.from_mesh(pmodel.data)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        
        to_keep = set()
        to_delete = set()
        for v in bme.verts:
            hit, point, normal, face = tmodel.closest_point_on_mesh(v.co)
            R = v.co - point
            if not hit: continue
            if R.length > .01:
                to_keep.add(v)
            else:
                to_delete.add(v)
        expand = set()
        for v in to_keep:
            for ed in v.link_edges:
                expand.add(ed.other_vert(v))
        
        to_keep |= expand
        
        to_delete = set(bme.verts[:])
        to_delete -= to_keep        
        bmesh.ops.delete(bme, geom = list(to_delete), context = 1)
        bme.to_mesh(pmodel.data)
        bme.free()
        tmodel.select = True
        context.scene.objects.active = tmodel
        
        bpy.ops.object.mode_set(mode = 'SCULPT')
        if not pmodel.use_dynamic_topology_sculpting:
            bpy.ops.sculpt.dynamic_topology_toggle()
        bpy.ops.paint.mask_flood_fill(mode = 'VALUE', value = 0)
        context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
        context.scene.tool_settings.sculpt.constant_detail_resolution = 5.5
        bpy.ops.sculpt.detail_flood_fill()
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
    def end_cancel(self, context):
        ''' Called when tool is canceled '''
        self.cleanup(context, 'cancel')
        pass
    
    def update(self, context):
        pass
    
def register():
    bpy.utils.register_class(D3Splint_CutSplintMargin)
    
     
def unregister():
    bpy.utils.unregister_class(D3Splint_CutSplintMargin)