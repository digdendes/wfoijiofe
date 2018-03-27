'''
Created on Oct 8, 2015

@author: Patrick
'''
import bpy

from ..modaloperator import ModalOperator
from .hole_filler_ui            import HoleFiller_UI
from .hole_filler_ui_modalwait  import HoleFiller_UI_ModalWait
from .hole_filler_ui_tools      import HoleFiller_UI_Tools
from .hole_filler_ui_draw       import HoleFiller_UI_Draw


class D3Model_OT_hole_filler(ModalOperator, HoleFiller_UI, HoleFiller_UI_ModalWait, HoleFiller_UI_Tools, HoleFiller_UI_Draw):
    ''' Identify and repair holes '''
    ''' Note: the functionality of this operator is split up over multiple base classes '''
    
    bl_idname      = "d3model.mesh_repair"
    bl_label       = "Hole Filler"
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
            #showErrorMessage('Object Mode please')
            return False
        
        if not context.object:
            return False
        
        if context.object.type != 'MESH':
            #showErrorMessage('Must select a mesh object')
            return False
        
        
        return True
    
    def start(self, context):
        ''' Called when tool is invoked '''
        self.start_ui(context)
    
    def end(self, context):
        ''' Called when tool is ending modal '''
        self.end_ui(context)
    
    def end_commit(self, context):
        ''' Called when tool is committing '''
        
        
        self.cleanup(context, 'commit')
    
    def end_cancel(self, context):
        ''' Called when tool is canceled '''
        self.cleanup(context, 'cancel')
        pass
    
    def update(self, context):
        pass
    
def register():
    bpy.utils.register_class(D3Model_OT_hole_filler)
    
     
def unregister():
    bpy.utils.unregister_class(D3Model_OT_hole_filler)