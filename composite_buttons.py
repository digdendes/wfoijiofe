'''
Created on May 18, 2018

@author: Patrick
'''
import math

import bpy
import bmesh
from mathutils import Vector, Matrix

def generate_trap_prizm_bme(wi, wg, hg, hi, dig, theta_i, theta_g, theta_m, theta_d, p_warp):
    '''
    wi = incisal width of trapezoid
    wg = ginigval width of trapezoid
    hg = thickness in facial direction at the gingival or button
    hi = thickness in facial direciton at the incisal of button
    dig = the incisal/gingival height of the button
    
    theta_i = angle of the incisal face of the button in radians
    theat_g = angle of the gingival face of the button in radians
    theta_m = angle of the mesial face of the button in radians
    theat_d = angle of the distal face of the button in radians
    
    pb = parabolic curvature factor along the facial
    '''
    bme = bmesh.new()
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    v0 = Vector((-wg/2, -dig/2, 0))
    v1 = Vector((wg/2, -dig/2, 0))
    v2 = Vector((wi/2, dig/2, 0))
    v3 = Vector((-wi/2, dig/2, 0))
    v4 = Vector((-wg/2 + math.sin(theta_m)*hg, -dig/2 + math.sin(theta_g)*hg, hg)) #
    v5 = Vector((wg/2 - math.sin(theta_d)*hg, -dig/2 + math.sin(theta_g)*hg, hg))#
    v6 = Vector((wi/2 - math.sin(theta_d)*hi, dig/2 - math.sin(theta_i)*hi, hi))
    v7 = Vector((-wi/2 + math.sin(theta_m)*hi, dig/2 - math.sin(theta_i)*hi, hi))
    
    V0 = bme.verts.new(v0)
    V1 = bme.verts.new(v1)
    V2 = bme.verts.new(v2)
    V3 = bme.verts.new(v3)
    V4 = bme.verts.new(v4)
    V5 = bme.verts.new(v5)
    V6 = bme.verts.new(v6)
    V7 = bme.verts.new(v7)
    
    f0 = bme.faces.new((V0,V3,V2,V1))
    f1 = bme.faces.new((V0,V4,V7,V3))
    f2 = bme.faces.new((V1,V5,V4,V0))
    f3 = bme.faces.new((V2,V6,V5,V1))
    f4 = bme.faces.new((V3,V7,V6,V2))
    f5 = bme.faces.new((V4,V5,V6,V7))
    
    bme.faces.ensure_lookup_table()

    bmesh.ops.subdivide_edges(bme, edges = bme.edges[:], cuts = 8, use_grid_fill = True)
    
    
    for v in bme.verts:
        r = abs(v.co[1] + dig/2)
        factor = (r/dig)**(3/2)
        
        print(math.sin(p_warp))
        v.co[0] += factor * math.sin(p_warp) * r
        v.co[1] -= factor * (1 - math.cos(p_warp))* r
        
    return bme

class D3Tool_OT_composite_attachment_element(bpy.types.Operator):
    """Create a composite attachment located at the 3D cursor"""
    bl_idname = "d3tool.composite_attachment"
    bl_label = "Composite attachment"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    wi = bpy.props.FloatProperty(default = 2.0, min = 1.0, max = 6.0, description = 'Incisal width')
    wg = bpy.props.FloatProperty(default = 3.0, min = 1.0, max = 6.0, description = 'Gingival widht')
    hg = bpy.props.FloatProperty(default = 2.0, description = 'height at the gingival aspect of the button')
    hi = bpy.props.FloatProperty(default = 2.0, description = 'height at the incisal aspect of the button')
    dig = bpy.props.FloatProperty(default = 4.0, description = 'incisal gingival length of ramp')
    theta_i = bpy.props.IntProperty(default = 7, min = -30, max = 30, description = 'incisal angle of the surface')
    theta_g = bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'gingival angle of the surface')
    theta_m =  bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'mesial angle of the surface')
    theta_d =  bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'distal angle of the surface')
    theta_warp =  bpy.props.IntProperty(default = 0,  min = -30, max = 30, description = 'cruvature of the attachment')
    
    @classmethod
    def poll(cls, context):
        
        return True
    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)
        
    def execute(self, context):
        
        
        if len(context.scene.odc_splints):
            n = context.scene.odc_splint_index
            splint = context.scene.odc_splints[n]
            if splint.jaw_type == 'MANDIBLE':
                R = Matrix.Rotation(math.pi, 4, 'X')
            else:
                R = Matrix.Identity(4)
        else:
            R = Matrix.Identity(4)
            
        loc = context.scene.cursor_location
        
        
        bme = generate_trap_prizm_bme(self.wi, 
                                      self.wg, 
                                      self.hg, 
                                      self.hi, 
                                      self.dig, 
                                      math.pi * self.theta_i/180, 
                                      math.pi * self.theta_g/180,  
                                      math.pi * self.theta_m/180,  
                                      math.pi * self.theta_d/180,
                                      math.pi * self.theta_warp/180)
        
        
    
        me = bpy.data.meshes.new('Composite Button')
        ob = bpy.data.objects.new('Composite Button', me)
        context.scene.objects.link(ob)
        
        T = Matrix.Translation(loc)
        ob.matrix_world = T * R
        
        b1 = ob.modifiers.new('Subdivision Surface', type = 'SUBSURF')
        b1.levels = 2

        #rm = ob.modifiers.new('Remesh', type = 'REMESH')
        #rm.octree_depth = 6
        #rm.mode = 'SMOOTH'
        
        #mat = bpy.data.materials.get("Attahcment Material")
        #if mat is None:
        #    # create material
        #    mat = bpy.data.materials.new(name="Attachment Material")
        #    mat.diffuse_color = get_settings().def_splint_color
        #    mat.use_transparency = True
        #    mat.transparency_method = 'Z_TRANSPARENCY'
        #    mat.alpha = .4
        
        #if mat.name not in ob.data.materials:
        #    ob.data.materials.append(mat)
            
            
        ob['wi'] =  self.wi
        ob['wg'] = self.wg
        ob['hg'] = self.hg
        ob['hi'] = self.hi
        ob['dig'] = self.dig
        ob['theta_i'] = self.theta_i
        ob['theta_g'] =  self.theta_g
        ob['theta_m'] = self.theta_m
        ob['theta_d'] = self.theta_d
        ob['theta_warp'] = self.theta_warp   
                               
        bme.to_mesh(me)
        bme.free()
       
        for ob in bpy.data.objects:
            ob.select = False
            
        ob.select = True
        context.scene.objects.active = ob
        context.space_data.show_manipulator = True
        context.space_data.transform_manipulators = {'TRANSLATE','ROTATE'}
        context.space_data.transform_orientation = 'LOCAL'
                 
        return {'FINISHED'}
    
    
def register():
    bpy.utils.register_class(D3Tool_OT_composite_attachment_element)
   
    
def unregister():
    bpy.utils.unregister_class(D3Tool_OT_composite_attachment_element)
        