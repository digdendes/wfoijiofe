'''
Created on Sep 17, 2016

@author: Patrick
'''
'''
Created on Aug 18, 2016

@author: Patrick
'''
import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Color
from mathutils.bvhtree import BVHTree
from bpy_extras import view3d_utils
from common_utilities import bversion
import common_drawing
import bgl_utils
from mesh_cut import edge_loops_from_bmedges, space_evenly_on_path
from textbox import TextBox
from odcutils import get_settings, obj_list_from_lib, obj_from_lib
from bpy.props import IntProperty, FloatProperty, BoolProperty, EnumProperty


class OPENDENTAL_OT_prepare_meta_scaffold(bpy.types.Operator):
    """Decimate Mesh to Target edge length, usualy a cutout from polytrim"""
    bl_idname = "opendental.meta_scaffold_create"
    bl_label = "Create Meta Scaffold"
    bl_options = {'REGISTER', 'UNDO'}
    
    radius = FloatProperty(default = 1.25, description = 'Radius of scafold should be 1/2 radius of planned metaballs')
    finalize = BoolProperty(default = False, description = 'Will apply the decimate modifier')
    
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None:
            return True
        else:
            return False
        
    def execute(self, context):
        
        ob = context.object
        
        bme = bmesh.new()
        bme.from_object(ob, context.scene)
        
        bme.edges.ensure_lookup_table()
        total_l = 0
        for ed in bme.edges:
            total_l += ed.calc_length()
            
        total_l *= 1/len(bme.edges)
        
        factor = total_l / self.radius
         
        mod = ob.modifiers.new('Reduce','DECIMATE')    
        mod.ratio = min(1,.5 * factor)
        
        if self.finalize:
            context.scene.update()
            me = ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            new_ob = bpy.data.objects.new('Meta Scaffold', me)
            context.scene.objects.link(new_ob)
            new_ob.matrix_world = ob.matrix_world
            
            if ob.data.materials:
                new_ob.data.materials.append(ob.data.materials[0])
                
            
        bme.free()
            
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.n_verts = len(context.object.data.vertices)
        
        return context.window_manager.invoke_props_dialog(self)
             
class OPENDENTAL_OT_meta_offset_surface(bpy.types.Operator):
    """Create Meta Offset Surface from mesh"""
    bl_idname = "opendental.meta_offset_surface"
    bl_label = "Create Meta Surface"
    bl_options = {'REGISTER', 'UNDO'}
    
    radius = FloatProperty(default = 2.5, description = 'Radius metaballs to be added')
    finalize = BoolProperty(default = False, description = 'Will convert meta to mesh and remove meta object')
    resolution = FloatProperty(default = .8, description = 'Mesh resolution. 0.8 for dentures, .3 for cast reduction')
    n_verts = IntProperty(default = 1000)
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None:
            return True
        else:
            return False
        
    def execute(self, context):
        
        ob = context.object
        mx = ob.matrix_world
        
        meta_data = bpy.data.metaballs.new('Meta Mesh')
        meta_obj = bpy.data.objects.new('Meta Surface', meta_data)
        meta_data.resolution = self.resolution
        meta_data.render_resolution = self.resolution
        context.scene.objects.link(meta_obj)
        
        # Copy Material if any
        if ob.data.materials:
            mat = ob.data.materials[0]
            meta_obj.data.materials.append(mat)
            
            
        for v in self.bme.verts:
            mb = meta_data.elements.new(type = 'BALL')
            mb.radius = self.radius
            mb.co = v.co
            
        meta_obj.matrix_world = mx
        
        if self.finalize:
            context.scene.update()
            me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            new_ob = bpy.data.objects.new('MetaSurfaceMesh', me)
            context.scene.objects.link(new_ob)
            new_ob.matrix_world = mx
            if meta_obj.data.materials:
                new_ob.data.materials.append(mat)
                
            context.scene.objects.unlink(meta_obj)
            bpy.data.objects.remove(meta_obj)
            bpy.data.metaballs.remove(meta_data)
        
        self.bme.free()    
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.bme = bmesh.new()
        self.bme.from_object(context.object, context.scene)
        self.bme.verts.ensure_lookup_table()
        
        self.n_verts = len(self.bme.verts)
        
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self,context):
        
        layout = self.layout
        
        row = layout.row()
        row.label(text = "%i metaballs will be added" % self.n_verts)
        
        if self.n_verts > 10000:
            row = layout.row()
            row.label(text = "WARNING, THIS SEEMS LIKE A LOT")
            row = layout.row()
            row.label(text = "Consider CANCEL/decimating more or possible long processing time")
        
        row = layout.row()
        row.prop(self, "radius")
        row.prop(self,"resolution")
        row.prop(self, "finalize")
        
class OPENDENTAL_OT_meta_offset_surface_cubes(bpy.types.Operator):
    """Create Meta Offset Surface from mesh"""
    bl_idname = "opendental.meta_offset_surface_cube"
    bl_label = "Create Meta Cube Surface"
    bl_options = {'REGISTER', 'UNDO'}
    
    radius = FloatProperty(default = .2 , description = 'Thickness of Offset')
    finalize = BoolProperty(default = False, description = 'Will convert meta to mesh and remove meta object')
    resolution = FloatProperty(default = .8, description = 'Mesh resolution. 0.8 for dentures, .3 for cast reduction')
    n_verts = IntProperty(default = 1000)
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None:
            return True
        else:
            return False
        
    def execute(self, context):
        
        ob = context.object
        mx = ob.matrix_world
        
        meta_data = bpy.data.metaballs.new('Meta Mesh')
        meta_obj = bpy.data.objects.new('Meta Surface', meta_data)
        meta_data.resolution = self.resolution
        meta_data.render_resolution = self.resolution
        context.scene.objects.link(meta_obj)
        
        # Copy Material if any
        if ob.data.materials:
            mat = ob.data.materials[0]
            meta_obj.data.materials.append(mat)
            
        #conversion factors
        for ed in []:
        #for ed in self.bme.edges:
            co = .5 * ed.verts[0].co + .5 * ed.verts[1].co
            R = .5 * ed.calc_length()
            Z = ed.verts[1].co - ed.verts[0].co 
            
            Z.normalize()
            
            mb = meta_data.elements.new(type = 'ELLIPSOID')
            mb.co = 10 * co
            mb.size_x = 10 * self.radius
            mb.size_y = 10 * self.radius
            mb.size_z = 10 * R
            
            x_prime = ed.verts[0].normal
            
            Y = Z.cross(x_prime)
            X = Y.cross(Z)
            
            #rotation matrix from principal axes
            T = Matrix.Identity(3)  #make the columns of matrix U, V, W
            T[0][0], T[0][1], T[0][2]  = X[0] ,Y[0],  Z[0]
            T[1][0], T[1][1], T[1][2]  = X[1], Y[1],  Z[1]
            T[2][0] ,T[2][1], T[2][2]  = X[2], Y[2],  Z[2]

            Rotation_Matrix = T.to_4x4()
            
            mb.rotation = Rotation_Matrix.to_quaternion()
        
        #thickness data
        #.2 to .32
        #.1 to .21
           
        #for f in []:        
        for f in self.bme.faces:
            
            #co = f.calc_center_bounds()
            #vmax = min(f.verts, key = lambda x: (co - x.co).length)
            #R = (co - vmax.co).length
            
            co = f.calc_center_median()
            #R = 2 * f.calc_area() / f.calc_perimeter()
            R = .5 * f.calc_area()**.5
            
            mb = meta_data.elements.new(type = 'CUBE')
            mb.co = 10 * co
            mb.size_x = 10 * .9 * R
            mb.size_y = 10 * .9 * R
            mb.size_z = 10 * self.radius
            
            Z = f.normal
            Y = f.verts[0].co - f.verts[1].co
            #Y = f.verts[0].co - co
            
            Y.normalize()
            X = Y.cross(Z)
            
            #rotation matrix from principal axes
            T = Matrix.Identity(3)  #make the columns of matrix U, V, W
            T[0][0], T[0][1], T[0][2]  = X[0] ,Y[0],  Z[0]
            T[1][0], T[1][1], T[1][2]  = X[1], Y[1],  Z[1]
            T[2][0] ,T[2][1], T[2][2]  = X[2], Y[2],  Z[2]

            Rotation_Matrix = T.to_4x4()
            
            mb.rotation = Rotation_Matrix.to_quaternion()
            
        R = mx.to_quaternion().to_matrix().to_4x4()
        L = Matrix.Translation(mx.to_translation())
        S = Matrix.Scale(.1, 4)
           
        meta_obj.matrix_world =  L * R * S
        
        if self.finalize:
            context.scene.update()
            me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            new_ob = bpy.data.objects.new('MetaSurfaceMesh', me)
            context.scene.objects.link(new_ob)
            new_ob.matrix_world = mx
            if meta_obj.data.materials:
                new_ob.data.materials.append(mat)
                
            context.scene.objects.unlink(meta_obj)
            bpy.data.objects.remove(meta_obj)
            bpy.data.metaballs.remove(meta_data)
        
        self.bme.free()    
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.bme = bmesh.new()
        self.bme.from_object(context.object, context.scene)
        self.bme.verts.ensure_lookup_table()
        
        self.n_verts = len(self.bme.verts)
        
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self,context):
        
        layout = self.layout
        
        row = layout.row()
        row.label(text = "%i metaballs will be added" % self.n_verts)
        
        if self.n_verts > 10000:
            row = layout.row()
            row.label(text = "WARNING, THIS SEEMS LIKE A LOT")
            row = layout.row()
            row.label(text = "Consider CANCEL/decimating more or possible long processing time")
        
        row = layout.row()
        row.prop(self, "radius")
        row.prop(self,"resolution")
        row.prop(self, "finalize")

class OPENDENTAL_OT_meta_offset_surface_discs(bpy.types.Operator):
    """Create Meta Offset Surface discs on verts, good for thin offsets .075 to 1mm"""
    bl_idname = "opendental.meta_offset_surface_disk"
    bl_label = "Create Meta Disk Surface"
    bl_options = {'REGISTER', 'UNDO'}
    
    radius = FloatProperty(default = .2 , min = .075, max = 1, description = 'Thickness of Offset')
    finalize = BoolProperty(default = False, description = 'Will convert meta to mesh and remove meta object')
    resolution = FloatProperty(default = 1.5, description = 'Mesh resolution. 1.5 seems ok?')
    n_verts = IntProperty(default = 1000)
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None:
            return True
        else:
            return False
        
    def execute(self, context):
        
        ob = context.object
        mx = ob.matrix_world
        
        meta_data = bpy.data.metaballs.new('Meta Mesh')
        meta_obj = bpy.data.objects.new('Meta Surface', meta_data)
        meta_data.resolution = self.resolution
        meta_data.render_resolution = self.resolution
        context.scene.objects.link(meta_obj)
        
        # Copy Material if any
        if ob.data.materials:
            mat = ob.data.materials[0]
            meta_obj.data.materials.append(mat)
            
        #conversion factors
        #for ed in []:
        for v in self.bme.verts:
            co = v.co
            R = .5 * max([ed.calc_length() for ed in v.link_edges])
            
            
            Z = v.normal 
            Z.normalize()
            
            mb = meta_data.elements.new(type = 'ELLIPSOID')
            mb.co = 10 * co
            mb.size_x = 10 * R
            mb.size_y = 10 * R
            mb.size_z = 10 * (self.radius - .025)
            
            v_other = v.link_edges[0].other_vert(v)
            x_prime = v_other.co - v.co
            x_prime.normalize()
            Y = Z.cross(x_prime)
            X = Y.cross(Z)
            
            #rotation matrix from principal axes
            T = Matrix.Identity(3)  #make the columns of matrix U, V, W
            T[0][0], T[0][1], T[0][2]  = X[0] ,Y[0],  Z[0]
            T[1][0], T[1][1], T[1][2]  = X[1], Y[1],  Z[1]
            T[2][0] ,T[2][1], T[2][2]  = X[2], Y[2],  Z[2]

            Rotation_Matrix = T.to_4x4()
            
            mb.rotation = Rotation_Matrix.to_quaternion()
        
        #thickness data
        #.2 to .32
        #.1 to .21
           
        for f in []:        
        #for f in self.bme.faces:
            
            #co = f.calc_center_bounds()
            #vmax = min(f.verts, key = lambda x: (co - x.co).length)
            #R = (co - vmax.co).length
            
            co = f.calc_center_median()
            #R = 2 * f.calc_area() / f.calc_perimeter()
            R = .5 * f.calc_area()**.5
            
            mb = meta_data.elements.new(type = 'CUBE')
            mb.co = 10 * co
            mb.size_x = 10 * .9 * R
            mb.size_y = 10 * .9 * R
            mb.size_z = 10 * self.radius
            
            Z = f.normal
            Y = f.verts[0].co - f.verts[1].co
            #Y = f.verts[0].co - co
            
            Y.normalize()
            X = Y.cross(Z)
            
            #rotation matrix from principal axes
            T = Matrix.Identity(3)  #make the columns of matrix U, V, W
            T[0][0], T[0][1], T[0][2]  = X[0] ,Y[0],  Z[0]
            T[1][0], T[1][1], T[1][2]  = X[1], Y[1],  Z[1]
            T[2][0] ,T[2][1], T[2][2]  = X[2], Y[2],  Z[2]

            Rotation_Matrix = T.to_4x4()
            
            mb.rotation = Rotation_Matrix.to_quaternion()
            
        R = mx.to_quaternion().to_matrix().to_4x4()
        L = Matrix.Translation(mx.to_translation())
        S = Matrix.Scale(.1, 4)
           
        meta_obj.matrix_world =  L * R * S
        
        if self.finalize:
            context.scene.update()
            me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            new_ob = bpy.data.objects.new('MetaSurfaceMesh', me)
            context.scene.objects.link(new_ob)
            new_ob.matrix_world = mx
            if meta_obj.data.materials:
                new_ob.data.materials.append(mat)
                
            context.scene.objects.unlink(meta_obj)
            bpy.data.objects.remove(meta_obj)
            bpy.data.metaballs.remove(meta_data)
        
        self.bme.free()    
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.bme = bmesh.new()
        self.bme.from_object(context.object, context.scene)
        self.bme.verts.ensure_lookup_table()
        
        self.n_verts = len(self.bme.verts)
        
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self,context):
        
        layout = self.layout
        
        row = layout.row()
        row.label(text = "%i metaballs will be added" % self.n_verts)
        
        if self.n_verts > 10000:
            row = layout.row()
            row.label(text = "WARNING, THIS SEEMS LIKE A LOT")
            row = layout.row()
            row.label(text = "Consider CANCEL/decimating more or possible long processing time")
        
        row = layout.row()
        row.prop(self, "radius")
        row.prop(self,"resolution")
        row.prop(self, "finalize")
                
class OPENDENTAL_OT_meta_rim_from_curve(bpy.types.Operator):
    """Create Meta Wax Rim from double bezier curve"""
    bl_idname = "opendental.meta_rim_from_curve"
    bl_label = "Create Meta Wax Rim"
    bl_options = {'REGISTER', 'UNDO'}
    
    posterior_width = FloatProperty(default = 9, description = 'Width of posterior rim')
    anterior_width = FloatProperty(default = 4, description = 'Width of anterior rim')
    meta_type = EnumProperty(name = 'Meta Type', items = [('CUBE','CUBE','CUBE'), ('ELLIPSOID', 'ELLIPSOID','ELLIPSOID')], default = 'CUBE')
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
            return True
        else:
            return False
        
    def execute(self, context):
        
        crv_data = context.object.data
        if len(crv_data.splines) != 2:
            #TODO, make real error
            print('ERROR, curve must have 2 splines in one object')
            return {'CANCELLED'}
            
        ob = context.object
        mx = ob.matrix_world
        
        meta_data = bpy.data.metaballs.new('Meta Wax Rim')
        meta_obj = bpy.data.objects.new('Meta Surface', meta_data)
        meta_data.resolution = .8
        meta_data.render_resolution = .8
        context.scene.objects.link(meta_obj)
        
        me = context.object.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme = bmesh.new()
        bme.from_mesh(me)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in bme.edges])
            
        
        vs0 = [bme.verts[i].co for i in loops[0]]
        vs1 = [bme.verts[i].co for i in loops[1]]
        
        vs_even_0, eds0 = space_evenly_on_path(vs0, [(0,1),(1,2)], 60)
        vs_even_1, eds1 = space_evenly_on_path(vs1, [(0,1),(1,2)], 60)
        
        if (vs_even_0[0]-vs_even_1[0]).length > (vs_even_0[0]-vs_even_1[-1]).length:
            vs_even_1.reverse()
            
            
        for i in range(1,len(vs_even_0)-1):
            
            
            blend = -abs((i-30)/30)+1
            
            v0_0 = vs_even_0[i]
            v1_1 = vs_even_1[i]
            
            v0_p1 = vs_even_0[i+1]
            v1_p1 = vs_even_1[i+1]
            
            v0_m1 = vs_even_0[i-1]
            v1_m1 = vs_even_1[i-1]
            
            mid = .5*v0_0 + .5*v1_1
            
            Z = v1_1 - v0_0
            Z.normalize()
            x0, x1 = v0_p1 - v0_m1, v1_p1 - v1_m1
            x0.normalize()
            x1.normalize()
            X = .5*x0 + .5*x1
            X.normalize()
            
            Y = Z.cross(X)
            X_c = Y.cross(Z) #X corrected
            
            T = Matrix.Identity(3)
            T.col[0] = X_c
            T.col[1] = Y
            T.col[2] = Z
            quat = T.to_quaternion()
            
            mb = meta_data.elements.new(type = self.meta_type)
            mb.size_y = .5 *  (blend*self.anterior_width + (1-blend)*self.posterior_width)
            mb.size_z = .5 * (v1_1 - v0_0).length
            mb.size_x = 2
            mb.rotation = quat
            mb.stiffness = 2
            mb.co = mid
            
        meta_obj.matrix_world = mx
        
        #if self.finalize:
        #    context.scene.update()
        #    me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        #    new_ob = bpy.data.objects.new('MetaSurfaceMesh', me)
        #    context.scene.objects.link(new_ob)
        #    new_ob.matrix_world = mx
        #    if meta_obj.data.materials:
        #        new_ob.data.materials.append(meta_obj.data.materials[0])
        #        
        #    context.scene.objects.unlink(meta_obj)
        #    bpy.data.objects.remove(meta_obj)
        #    bpy.data.metaballs.remove(meta_data)
        bme.free()
  
        return {'FINISHED'}
    
    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)
    
class OPENDENTAL_OT_meta_custom_tray(bpy.types.Operator):
    """Create Meta Offset Solid from mesh"""
    bl_idname = "opendental.meta_custom_tray"
    bl_label = "Create Meta Custom Tray"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    tray_thickness = FloatProperty(default = 2, description = 'Thickness of tray')
    tray_offset = FloatProperty(default = 2.5, description = 'Spacer for impression material')
    finalize = BoolProperty(default = False, description = 'Will convert meta to mesh and remove meta object')
    
    n_verts = IntProperty(default = 5000)
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None:
            return True
        else:
            return False
        
    def execute(self, context):
        
        ob = context.object
        mx = ob.matrix_world
        
        meta_data = bpy.data.metaballs.new('Meta Mesh')
        meta_obj = bpy.data.objects.new('Meta Surface', meta_data)
        meta_data.resolution = .8
        meta_data.render_resolution = .8
        context.scene.objects.link(meta_obj)
        
        
        # Copy Material if any
        if ob.data.materials:
            mat = ob.data.materials[0]
            meta_obj.data.materials.append(mat)
            
            
        for v in self.bme.verts:
            
            #outer shell
            mb = meta_data.elements.new(type = 'BALL')
            mb.radius = self.tray_thickness + self.tray_offset
            mb.co = v.co
            
            
            #inner spacer
            #mb2 = meta_data2.elements.new(type = 'BALL')
            #mb2.radius = self.tray_offset
            #mb2.co = v.co
            
            #bridge them?
            
            
        meta_obj.matrix_world = mx
        
        if self.finalize:
            context.scene.update()
            me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            new_ob = bpy.data.objects.new('MetaSurfaceMesh', me)
            context.scene.objects.link(new_ob)
            new_ob.matrix_world = mx
            if meta_obj.data.materials:
                new_ob.data.materials.append(mat)
                
            context.scene.objects.unlink(meta_obj)
            bpy.data.objects.remove(meta_obj)
            bpy.data.metaballs.remove(meta_data)
        
        self.bme.free()    
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.bme = bmesh.new()
        self.bme.from_object(context.object, context.scene)
        self.bme.verts.ensure_lookup_table()
        
        self.n_verts = len(self.bme.verts)
        
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self,context):
        
        layout = self.layout
        
        row = layout.row()
        row.label(text = "%i metaballs will be added" % self.n_verts)
        
        if self.n_verts > 10000:
            row = layout.row()
            row.label(text = "WARNING, THIS SEEMS LIKE A LOT")
            row = layout.row()
            row.label(text = "Consider CANCEL and decimating more")
        
        row = layout.row()
        row.prop(self, "tray_thickness")
        row = layout.row()
        row.prop(self, "tray_offset")
        row = layout.row()
        row.prop(self, "finalize")


class OPENDENTAL_OT_simple_offset_surface(bpy.types.Operator):
    """Simple normal offset 0 - 2mm """
    bl_idname = "opendental.simple_offset_surface"
    bl_label = "Simple Meta Surface"
    bl_options = {'REGISTER', 'UNDO'}
    
    offset = FloatProperty(default = 0.3, min = -3, max = 3,  description = 'Distance to offset')
    duplicate = BoolProperty(default = False , description = 'Will create new object, leaving original in tact')
    smooth = BoolProperty(default = True, description = 'Will add smooth modifier to attempt to remove self intersections')
    shrink = smooth = BoolProperty(default = False, description = 'Will add shrinkwrap modifier to attempt to reoffset after smoothing')
    
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None and context.object.type == 'MESH':
            return True
        else:
            return False
        
    def execute(self, context):
        
        ob = context.object
        mx = ob.matrix_world
        
        if not self.duplicate:
            for v in ob.data.vertices:
                v.co += self.offset*v.normal
            
            return {'FINISHED'}
        
        
        # Copy Material if any
        if ob.data.materials:
            mat = ob.data.materials[0]
            
        me = context.object.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        
        nos = [v.normal for v in me.vertices]
        for i, v in enumerate(me.vertices):
            v.co += self.offset * nos[i]
            
            
        new_ob = bpy.data.objects.new(ob.name + '_offset', me)
        context.scene.objects.link(new_ob)
        new_ob.matrix_world = mx
        if ob.data.materials:
            new_ob.data.materials.append(mat)
        if self.smooth:
            smod = new_ob.modifiers.new('Smooth', type = 'SMOOTH')
            smod.iterations = 10
            
        if self.duplicate and self.shrink:
            swmod = new_ob.modifiers.new('Shrinkwrap', type = 'SHRINKWRAP')
            swmod.wrap_method = 'NEAREST_SURFACEPOINT'
            swmod.offset = self.offset
            swmod.use_keep_above_surface = True
            swmod.target = ob
            
            smod = new_ob.modifiers.new('Smooth', type = 'SMOOTH')
            smod.iterations = 10
                  
        return {'FINISHED'}
               
class OPENDENTAL_OT_boolean_intaglio(bpy.types.Operator):
    """Add boolean modifier to remove intaglio surfaec"""
    bl_idname = "opendental.denture_boolean_intaglio"
    bl_label = "Create Meta Surface"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    def item_cb(self, context):
        return [(obj.name, obj.name, '') for obj in self.objs]
 
    objs = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    
    ob = bpy.props.EnumProperty(name="Master Cast", 
                                 description="Select obj in scene which is master cast", 
                                 items=item_cb)
    
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None:
            return True
        else:
            return False
        
    def execute(self, context):
        
        ob = context.object
        mod = ob.modifiers.new('Intaglio', type = 'BOOLEAN')
        
        mod.operation = 'DIFFERENCE'
        if self.ob != None:
            mod.object = bpy.data.objects[self.ob]  
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.objs.clear()
        assets = [ob.name for ob in context.scene.objects if ob != context.object]
       
        for asset_object_name in assets:
            self.objs.add().name = asset_object_name
        
        return context.window_manager.invoke_props_dialog(self)
    
    
def register():
    bpy.utils.register_class(OPENDENTAL_OT_meta_offset_surface)
    bpy.utils.register_class(OPENDENTAL_OT_meta_custom_tray)
    bpy.utils.register_class(OPENDENTAL_OT_prepare_meta_scaffold)
    bpy.utils.register_class(OPENDENTAL_OT_meta_rim_from_curve)
    bpy.utils.register_class(OPENDENTAL_OT_boolean_intaglio)
    bpy.utils.register_class(OPENDENTAL_OT_simple_offset_surface)
    bpy.utils.register_class(OPENDENTAL_OT_meta_offset_surface_cubes)
    bpy.utils.register_class(OPENDENTAL_OT_meta_offset_surface_discs)
    
def unregister():
    bpy.utils.unregister_class(OPENDENTAL_OT_meta_offset_surface)
    bpy.utils.unregister_class(OPENDENTAL_OT_meta_custom_tray)
    bpy.utils.unregister_class(OPENDENTAL_OT_prepare_meta_scaffold)
    bpy.utils.unregister_class(OPENDENTAL_OT_meta_rim_from_curve)
    bpy.utils.unregister_class(OPENDENTAL_OT_boolean_intaglio)
    bpy.utils.unregister_class(OPENDENTAL_OT_simple_offset_surface)
    bpy.utils.unregister_class(OPENDENTAL_OT_meta_offset_surface_cubes)
    bpy.utils.unregister_class(OPENDENTAL_OT_meta_offset_surface_discs)
    
if __name__ == "__main__":
    register()