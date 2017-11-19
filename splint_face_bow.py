'''
Created on Oct 29, 2017

@author: Patrick
'''

import bpy
import bgl
import blf
import math

import numpy as np
from mathutils import Vector, Matrix
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_location_3d, region_2d_to_origin_3d, region_2d_to_vector_3d
import bpy_extras

#BGL wrappers/utils
def draw_line_3d(color, start, end, width=1):
    bgl.glLineWidth(width)
    bgl.glColor4f(*color)
    bgl.glBegin(bgl.GL_LINES)
    bgl.glVertex3f(*start)
    bgl.glVertex3f(*end)

def draw_points_3d(points, color, size, far=0.997):
    bgl.glColor4f(*color)
    bgl.glPointSize(size)
    bgl.glDepthRange(0.0, far)
    bgl.glBegin(bgl.GL_POINTS)
    for coord in points: bgl.glVertex3f(*coord)
    bgl.glEnd()
    bgl.glPointSize(1.0)
    
def img_editor_draw_callback_px(self, context):

    # draw text
    if len(self.pixel_coords) == 0:
        draw_typo_2d((1.0, 1.0, 1.0, 1), "Click on Ala/Condyle")
    elif len(self.pixel_coords) == 1:
        draw_typo_2d((1.0, 1.0, 1.0, 1), "Click on Frankfurt/OrbitalRidge")
    elif len(self.pixel_coords) == 2:
        draw_typo_2d((1.0, 1.0, 1.0, 1), "Click Ref Point 1 (LEFT)")
    elif len(self.pixel_coords) == 3:
        draw_typo_2d((1.0, 1.0, 1.0, 1), "Click Ref Point 1 (RIGHT)")
    elif len(self.pixel_coords) == 4:
        draw_typo_2d((1.0, 1.0, 1.0, 1), "Click Ref Point 1 (TOP)")
    elif len(self.pixel_coords) == 5:
        draw_typo_2d((1.0, 1.0, 1.0, 1), "Click Ref Point 1 (BOTTOM)")
                
    #draw the user clicked points on the image
    bgl.glPointSize(5)
    bgl.glBegin(bgl.GL_POINTS)
    bgl.glColor4f(0.8, 0.2, 0.5, 1.0)
    for pix in self.pixel_coords:
        img_x, img_y = pix[0], pix[1]
        img_size = self.imgeditor_area.spaces.active.image.size
        rx,ry = context.region.view2d.view_to_region(img_x/img_size[0], (img_size[1] - img_y)/img_size[1], clip=True)
        
        if rx and ry:
            bgl.glVertex2f(rx, ry)
        
    bgl.glEnd()
    
    # restore opengl defaults
    bgl.glPointSize(1)
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)

    font_id = 0
    for pix in self.pixel_coords:
        img_x, img_y = pix[0], pix[1]
        img_size = self.imgeditor_area.spaces.active.image.size
        
        rx,ry = context.region.view2d.view_to_region(img_x/img_size[0], (img_size[1] - img_y)/img_size[1], clip=True)
        
        blf.position(font_id, rx+5, ry+5, 0)
        text = str((round(pix[0]),round(pix[1])))
        
        blf.draw(font_id, text)
        
        blf.position(font_id, rx+5, ry+20, 0)
        text = str((round(pix[0]),round(pix[1])))
        
def tag_redraw_view3d_imgeditor(context):
    # Py cant access notifers
    #iterate through and tag all 'VIEW_3D' regions
    #for drawing
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D' or area.type == 'IMAGE_EDITOR':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        region.tag_redraw()
                            
def draw_typo_2d(color, text):
    font_id = 0  # XXX, need to find out how best to get this.
    # draw some text
    bgl.glColor4f(*color)
    blf.position(font_id, 20, 70, 0)
    blf.size(font_id, 20, 72)
    blf.draw(font_id, text)


class D3Splint_OT_image_face_bow(bpy.types.Operator):
    """Click on Image Reference Points"""
    bl_idname = "d3guard.img_face_bow"
    bl_label = "Mount Model from Image"

    @classmethod
    def poll(cls, context):
        #TODO, some nice poling
        return True

    def modal(self, context, event):
        
        tag_redraw_view3d_imgeditor(context)
        FSM = {}
        FSM['nav']  = self.modal_nav
        FSM['wait'] = self.modal_wait
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #clean up callbacks
            #bpy.types.SpaceView3D.draw_handler_remove(self._handle2d, 'WINDOW')
            #bpy.types.SpaceView3D.draw_handler_remove(self._handle3d, 'WINDOW')
            bpy.types.SpaceImageEditor.draw_handler_remove(self._handle_image, 'WINDOW')
            
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}   
        
    def modal_nav(self, context, event):
        '''
        Determine/handle navigation events.
        FSM passes control through to underlying panel if we're in 'nav' state
        '''
 
        handle_nav = False
        handle_nav |= event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE','MIDDLEMOUSE'}
        
        if handle_nav:
            self.post_update   = True
            self.is_navigating = True
            return 'wait' if event.value =='RELEASE' else 'nav'

        self.is_navigating = False
        return ''
       
    def modal_wait(self, context, event):
        
        # general navigation
        nmode = self.modal_nav(context, event)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'
        
        #TODO, tag redraw current if only needing to redraw that single window
        #depends on what information you are changing
        
        if event.type == 'MOUSEMOVE':
            
            #get the appropriate region and region_3d for ray_casting
            #also, important because this is what your blf and bgl
            #wrappers are going to draw in at that moment
            
            if (event.mouse_x > self.imgeditor_area.x and event.mouse_x < self.imgeditor_area.x + self.imgeditor_area.width) and \
                (event.mouse_y > self.imgeditor_area.y and event.mouse_y < self.imgeditor_area.y + self.imgeditor_area.height):
            
                for reg in self.imgeditor_area.regions:
                    if reg.type == 'WINDOW':
                        region = reg
                #for spc in self.imgeditor_area.spaces:
                
                #just transform the mouse window coords into the region coords        
                coord_region = (event.mouse_x - region.x, event.mouse_y - region.y)
                self.mouse_region_coord = coord_region
                self.mouse_raw = (event.mouse_x, event.mouse_y)
                        
            return 'wait'
        
        if event.type == 'M' and event.value == 'PRESS':
            self.build_matrix()
            
            return 'wait'
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            
            
                    
            if (event.mouse_x > self.imgeditor_area.x and event.mouse_x < self.imgeditor_area.x + self.imgeditor_area.width) and \
                (event.mouse_y > self.imgeditor_area.y and event.mouse_y < self.imgeditor_area.y + self.imgeditor_area.height):
            
                coord_region = (event.mouse_x - self.imgeditor_region.x, event.mouse_y - self.imgeditor_region.y)
                reg_x, reg_y = event.mouse_region_x, event.mouse_region_y
                img_size = self.imgeditor_area.spaces.active.image.size

                uv_x, uv_y = self.imgeditor_region.view2d.region_to_view(coord_region[0], coord_region[1])
                #print('The Region Coordinates')
                #print((coord_region[0], coord_region[1]))
                
                #print('The Image Size')
                #print((img_size[0],img_size[1]))
                
                if uv_x < 0 or uv_x > 1:
                    print('off image')
                    return 'wait'
                if uv_y < 0 or uv_y > 1:
                    print('off image')
                    return 'wait'
                

                #pixel coords origin at TOP left corner
                img_x, img_y = uv_x * img_size[0], img_size[1] - uv_y * img_size[1]
                
                #print('The Pixel Coordinates') #perhaps we need to make these reference top left corner! yes
                #print(img_x, img_y)
                
                self.pixel_coords += [Vector((img_x, img_y))]
                print(round(img_x), round(img_y))
                #back the coords out to region space, compare to reg_x, reg_y
                rx,ry = self.imgeditor_region.view2d.view_to_region(uv_x, uv_y, clip=False)

                #just transform the mouse window coords into the region coords        
                self.mouse_region_coord = coord_region
                self.mouse_raw = (event.mouse_x, event.mouse_y)
                
                               
            return 'wait'
        
        elif event.type == 'ESC':
            return 'cancel'
        
        return 'wait'
    
    def build_matrix(self):
        
        #the largest dimeions of image is scaled to 1 blender unit
        #in the empty image
        #unsure how things work with non square pixels
        img_scl = 1/max([self.image.size[0], self.image.size[1]])
        
        print('the world unit to pixel scale is')
        print(img_scl)
        
        #Condyle Position
        center = Vector((self.pixel_coords[0][0], self.image.size[1]-self.pixel_coords[0][1]))
        
        tV = -img_scl * center.to_3d()
        T = Matrix.Translation(tV)
        
        
        #Frankfurt Horizontal is desired to align with X axis
        X = self.pixel_coords[1] - self.pixel_coords[0]
        X[1] = -X[1]  #the Y coodinates go from the top down
        print(X)
        X.normalize()
        X = X.to_3d()
        
        #The Image Z should ultimately be the world -Y
        Y = Vector((0,0,-1))
        
        Z = X.cross(Y)
        
        
        #build a rotation matrix from x,y,z
        R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
        R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
        R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2]

        Q = R.to_quaternion()
        Qi = Q.inverted()
        
        Rqi = Qi.to_matrix().to_4x4()
        Rr = R.to_4x4()
        Ri = R.to_4x4().inverted()
        
        
        
        
        #scale factor and occlusal plane
        vy = self.pixel_coords[3] - self.pixel_coords[2]
        #remember dumb y axis is top down
        vy[1] = -vy[1]
        
        
        scl_x = 100/vy.length/img_scl
        
        vz = self.pixel_coords[4] - self.pixel_coords[5]
        scl_y = 40/vz.length/img_scl
        
        print('Are scl_x and scl_y close?')
        print((scl_x, scl_y))
        
        scl_final = .5 * (scl_x + scl_y)
        
        
        
        S = Matrix.Identity(4)
        S[0][0], S[1][1] = scl_final, scl_final
        
        
        
        self.empty.matrix_world = Ri * S * T
        
        
        
        return
        
        
        
    def invoke(self, context, event):
       
        #collect all the 3d_view regions
        #this can be done with other types
        
        self.mode = 'wait'
        
        #self.view3d_area = None
        #self.view3d_region = None
        #self.points_3d = []
        
        self.imgeditor_area = None
        self.imgeditor_region = None
        self.pixel_coords = []
        
        
        #TODO, check that only one of each area is open
        #TODO, manufacture one or 2 areas?
        for window in context.window_manager.windows:
            for area in window.screen.areas:        
                if area.type == 'IMAGE_EDITOR':
                    self.imgeditor_area = area
                    for region in area.regions:
                        if region.type == 'WINDOW': #ignore the tool-bar, header etc
                            self.imgeditor_region = region
    
        if self.imgeditor_area == None:
            
            return {'CANCELLED'}
        
        
        #add image empty
        empty = bpy.data.objects.new('FaceBow',None)
        empty.empty_draw_type = 'IMAGE'
        img = self.imgeditor_area.spaces.active.image
        context.scene.objects.link(empty)
        empty.data = img
        empty.color[3] = .75
        
        self.image = img
        self.empty = empty
        
        self.mouse_screen_coord = (0,0)
        context.window_manager.modal_handler_add(self)
        
        #the different drawing handles
        self._handle_image = bpy.types.SpaceImageEditor.draw_handler_add(img_editor_draw_callback_px, (self, context), 'WINDOW', 'POST_PIXEL')

        return {'RUNNING_MODAL'}
    
def register():
    bpy.utils.register_class(D3Splint_OT_image_face_bow)
    
     
def unregister():
    bpy.utils.unregister_class(D3Splint_OT_image_face_bow)
    
