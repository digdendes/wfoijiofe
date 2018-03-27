'''
Created on Oct 11, 2015

@author: Patrick
'''
from ..common_utilities import showErrorMessage

class HoleFiller_UI_ModalWait():
    
    def modal_wait(self,context,eventd):
        # general navigation
        nmode = self.modal_nav(context, eventd)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'

        #after navigation filter, these are relevant events in this state
        if  eventd['type'] == 'MOUSEMOVE':
            x,y = eventd['mouse']
            self.hole_manager.hover(context, x, y)    
            return 'main'
        
        if  eventd['press'] == 'LEFTMOUSE':
            x,y = eventd['mouse']
            
            if self.hole_manager.hovered != None:
                self.hole_manager.process_hovered_element()
            return 'main'
                
        if eventd['press'] == 'F':
            
            self.hole_manager.fill_smallest_hole()
            
            return 'main'
        
        if eventd['press'] == 'S':
            self.hole_manager.snap_smallest_hole(context)
            return 'main'
            
        if eventd['press'] == 'K':     
            if self.knife.split and self.knife.face_seed and len(self.knife.ed_map):
                self.knife.split_geometry(eventd['context'], mode = 'KNIFE')
                return 'finish' 
        
        if eventd['press'] == 'P':
            #self.knife.preview_mesh(eventd['context'])
            self.knife.split_geometry(eventd['context'], mode = 'SEPARATE')
            return 'finish'
        
        if eventd['press'] == 'X':
            self.knife.split_geometry(eventd['context'], mode = 'DELETE')
            return 'finish'
        
        if eventd['press'] == 'Y':
            self.knife.split_geometry(eventd['context'], mode = 'SPLIT')
            return 'finish'
        
        if eventd['press'] == 'SHIFT+D':
            self.knife.split_geometry(eventd['context'], mode = 'DUPLICATE')
            return 'finish'
            
        
            
          
        if eventd['press'] == 'RET' :
            self.knife.confirm_cut_to_mesh()
            return 'finish'
            
        elif eventd['press'] == 'ESC':
            return 'cancel' 

        return 'main'
    
    def modal_grab(self,context,eventd):
        # no navigation in grab mode
        
        if eventd['press'] == 'LEFTMOUSE':
            #confirm location
            self.knife.grab_confirm()
            
            if len(self.knife.bad_segments):
                self.knife.make_cut()
            elif len(self.knife.new_cos) and (self.knife.cyclic or (self.knife.start_edge != None and self.knife.end_edge != None)):
                self.knife.make_cut()
            
            if len(self.knife.new_cos) and len(self.knife.bad_segments) == 0:
                context.area.header_text_set("Poly Trim.  When cut is satisfactory, press 'S' then 'LeftMouse' in region to cut")
            elif len(self.knife.new_cos) and len(self.knife.bad_segments) != 0:
                context.area.header_text_set("Poly Trim.  Fix Bad segments so that no segments are red!")
            
            else: 
                context.area.header_text_set("Poly Trim.  Left click to place cut points on the mesh, then press 'C' to preview the cut")
            
            return 'main'
        
        elif eventd['press'] in {'RIGHTMOUSE', 'ESC'}:
            #put it back!
            self.knife.grab_cancel()
            
            if len(self.knife.new_cos):
                context.area.header_text_set("Poly Trim.  When cut is satisfactory, press 'S' then 'LeftMouse' in region to cut")
            elif len(self.knife.new_cos) and len(self.bad_segments) != 0:
                context.area.header_text_set("Poly Trim.  Fix Bad segments so that no segments are red!")
            else: 
                context.area.header_text_set("Poly Trim.  Left click to place cut points on the mesh, then press 'C' to preview the cut")
            return 'main'
        
        elif eventd['type'] == 'MOUSEMOVE':
            #update the b_pt location
            x,y = eventd['mouse']
            self.knife.grab_mouse_move(context,x, y)
            return 'grab'
    
    def modal_sketch(self,context,eventd):
        if eventd['type'] == 'MOUSEMOVE':
            x,y = eventd['mouse']
            if not len(self.sketch):
                return 'main'
            (lx, ly) = self.sketch[-1]
            ss0,ss1 = self.stroke_smoothing ,1-self.stroke_smoothing
            self.sketch += [(lx*ss0+x*ss1, ly*ss0+y*ss1)]
            return 'sketch'
        
        elif eventd['release'] == 'LEFTMOUSE':
            self.sketch_confirm(context, eventd)
            self.sketch = []
            return 'main'
        
    def modal_inner(self,context,eventd):
        
        if eventd['press'] == 'LEFTMOUSE':
            
            x,y = eventd['mouse']
            result = self.knife.click_seed_select(context, x,y) 
            if result == 1:
                context.window.cursor_modal_set('CROSSHAIR')
                
                if len(self.knife.new_cos) and len(self.knife.bad_segments) == 0 and not self.knife.split:
                    self.knife.confirm_cut_to_mesh_no_ops()
                    context.area.header_text_set("X:delete, P:separate, SHIFT+D:duplicate, K:knife, Y:split")
                return 'main'
            
            elif result == -1:
                showErrorMessage('Seed is too close to cut boundary, try again more interior to the cut')
                return 'inner'
            else:
                showErrorMessage('Seed not found, try again')
                return 'inner'
        
        if eventd['press'] in {'RET', 'ESC'}:
            return 'main'