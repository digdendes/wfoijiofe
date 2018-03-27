'''
Created on Oct 8, 2015

@author: Patrick
'''
import bpy

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
        ''' Called when tool is committing '''
        
        
        self.cleanup(context, 'commit')
    
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