'''
Created on Oct 8, 2015

@author: Patrick
'''
from ... import common_drawing
from ... import common_utilities

class HoleFiller_UI_Draw():
    def draw_postview(self, context):
        ''' Place post view drawing code in here '''
        self.draw_3d(context)
        pass
    
    def draw_postpixel(self, context):
        ''' Place post pixel drawing code in here '''
        self.draw_2d(context)
        pass
    
    def draw_3d(self,context):
        self.hole_manager.draw3d(context)
        
    
    def draw_2d(self,context):
        self.hole_manager.draw(context)
        
        if len(self.sketch):
            common_drawing.draw_polyline_from_points(context, self.sketch, (.8,.3,.3,.8), 2, "GL_LINE_SMOOTH")
        
        self.help_box.draw()
        
        prefs = common_utilities.get_settings()
        r,g,b = prefs.active_region_color
        common_drawing.outline_region(context.region,(r,g,b,1)) 