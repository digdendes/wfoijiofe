import bpy

import  bpy
from bpy.types import OperatorStrokeElement, PropertyGroup
from bpy_extras import view3d_utils

print('attempt')

sculpt_ob = bpy.context.object

stroke_ob = bpy.data.objects['BezierCurve']
mx = stroke_ob.matrix_world
stroke_data = [mx * v.co for v in stroke_ob.data.vertices]

bpy.context.scene.cursor_location = stroke_data[0]
bpy_stroke = []

screen = bpy.context.window.screen
for area in screen.areas:
    if area.type == 'VIEW_3D':
        for reg in area.regions:
            if reg.type == 'WINDOW':
                break
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                break  
        break

override = bpy.context.copy()
override['area'] = area
override['region'] = reg
override['space_data'] = space
override['region_data'] = space.region_3d
override['active_object'] = bpy.data.objects['Plane']
override['object'] = bpy.data.objects['Plane']
override['sculpt_object'] = bpy.data.objects['Plane']


#scene = bpy.context.scene
#paint_settings = scene.tool_settings.unified_paint_settings
#paint_settings.use_locked_size = True
#paint_settings.unprojected_radius = 3
#brush = bpy.data.brushes['Smooth']
#scene.tool_settings.sculpt.brush = brush
#brush.strength = .5
#brush.stroke_method = 'SPACE' 

for i, co in enumerate(stroke_data):
    

    mouse = view3d_utils.location_3d_to_region_2d(reg, space.region_3d, co)
    
    if mouse[0] < 0 or mouse[1] < 1:
        space.region_3d.view_location = co
        space.region_3d.update()
        mouse = view3d_utils.location_3d_to_region_2d(reg, space.region_3d, co)
    
    ele = {"name": "my_stroke",
            "mouse" : (mouse[0], mouse[1]),
            "pen_flip" : False,
            "is_start": True,
            "location": (co[0], co[1], co[2]),
            "pressure": 1,
            "size" : 50,
            "time": 1}
    
    bpy_stroke.append(ele)
          
bpy.ops.sculpt.brush_stroke(override, stroke=bpy_stroke, mode='NORMAL', ignore_background_click=False)


#Area
   #spaces
       #