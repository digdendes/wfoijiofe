'''
Created on Jul 8, 2018

@author: Patrick
'''
import bpy

def add_volcolor_material_to_obj(ob, color_name):
    '''
    adds or get's vertex color data
    and adds or gets material of same name
    
    return vcolor, material
    '''
    if color_name not in ob.data.vertex_colors:
        vcol = ob.data.vertex_colors.new(name = color_name)
    else:
        vcol = ob.data.vertex_colors.get(color_name)
        
    if color_name not in bpy.data.materials:
        mat = bpy.data.materials.new(color_name)
        mat.use_shadeless = True
        mat.use_vertex_color_paint = True
    else:
        mat = bpy.data.materials.get(color_name)
        mat.use_shadeless = True
        mat.use_vertex_color_paint = True
         
    if color_name not in ob.data.materials:
        ob.data.materials.append(mat)
        if len(ob.data.materials) > 1:
            if ob.material_slots[0] != mat:
                mat1 = ob.material_slots[0].material
                ob.material_slots[0].material = mat
                ob.material_slots[1].material = mat1
        
    return vcol, mat

def bmesh_color_bmverts(verts, vcolor_data, color):
    '''
    adds vertex colro to verts
    
    args:
        verts: list or set of BMVert
        vcolor: vertex colro data  eg bme.loops.layers.color["my_color"]
        color: mathutils.Color  eg Color((1,0,0)) is RED
    '''
    
    for v in verts:
        for f in v.link_faces:
            for loop in f.loops:
                if loop.vert == v:
                    loop[vcolor_data] = color
                

def bmesh_color_bmfaces(faces, vcolor_data, color):
    '''
    adds vertex colro to verts
    
    args:
        verts: list or set of BMVert
        vcolor: vertex colro data  eg bme.loops.layers.color["my_color"]
        color: mathutils.Color  eg Color((1,0,0)) is RED
    '''
    
    for f in faces:
        for loop in f.loops:
            loop[vcolor_data] = color       