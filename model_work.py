'''
Created on Aug 20, 2017

@author: Patrick

Need to re-read this later, similar to my old button code in 3D
http://blog.michelanders.nl/2016/03/performance-of-ray-casting-in-blender_81.html

'''

import math

import bpy
import bmesh
from mathutils.bvhtree import BVHTree

from mesh_cut import flood_selection_faces, edge_loops_from_bmedges,\
    space_evenly_on_path, bound_box, contract_selection_faces, \
    face_neighbors_by_vert, flood_selection_faces_limit

from bmesh_fns import join_bmesh, bme_linked_flat_faces    
from mathutils import Vector, Matrix
import odcutils
from common_utilities import bversion, get_settings
from common_drawing import outline_region
from loops_tools import relax_loops_util
import time
import bmesh_fns
import bgl_utils
from points_picker import PointPicker
from textbox import TextBox
from bpy_extras import view3d_utils
from mathutils.geometry import intersect_point_line, intersect_line_plane
import random
import blf

#TODO, put this somewhere logical and useful
def vector_angle_between(v0, v1, vcross):
    a = v0.angle(v1)
    d = v0.cross(v1).dot(vcross)
    return a if d>0 else 2*math.pi - a

def sort_objects_by_angles(vec_about, l_objs, l_vecs):
    '''
    sort a list of objects, around a normal vector,
    with a corresponding list of vectors.
    the first object, vector pair will remain the 0th item in the list
    and others will be sorted relative to it
    '''
    if len(l_objs) <= 1:  return l_objs
    o0,v0 = l_objs[0],l_vecs[0]
    l_angles = [0] + [vector_angle_between(v0,v1,vec_about) for v1 in l_vecs[1:]]
    l_inds = sorted(range(len(l_objs)), key=lambda i: l_angles[i])
    return [l_objs[i] for i in l_inds]

def delta_angles(vec_about, l_vecs):
    '''
    will find the difference betwen each element and the next element in the list
    this is a foward difference.  Eg delta[n] = item[n+1] - item[n]
    
    deltas should add up to 2*pi
    '''
    
    v0 = l_vecs[0]
    l_angles = [0] + [vector_angle_between(v0,v1,vec_about) for v1 in l_vecs[1:]]
    
    L = len(l_angles)
    
    deltas = [l_angles[n + 1] - l_angles[n] for n in range(0, L-1)] + [2*math.pi - l_angles[-1]]
    return deltas
def calc_angle(v):
                
    #use link edges and non_man eds
    eds_non_man = [ed for ed in v.link_edges if len(ed.link_faces) == 1]
    if len(eds_non_man) == 0:
        print('this is not a hole perimeter vertex')
        return 2 * math.pi, None, None
    
        
    eds_all = [ed for ed in v.link_edges]
    
    #shift list to start with a non manifold edge if needed
    base_ind = eds_all.index(eds_non_man[0])
    eds_all = eds_all[base_ind:] + eds_all[:base_ind]
    
    #vector representation of edges
    eds_vecs = [ed.other_vert(v).co - v.co for ed in eds_all]
    
    if len(eds_non_man) != 2:
        print("more than 2 non manifold edges, loop self intersects or there is a dangling edge")
        return 2 * math.pi, None, None
    
    
    va = eds_non_man[0].other_vert(v)
    vb = eds_non_man[1].other_vert(v)
    
    Va = va.co - v.co
    Vb = vb.co - v.co
    
    if Va.length < .00001 or Vb.length < .00001:
        print("zero length edge")
        return 2 * math.pi, None, None
    
    angle = Va.angle(Vb)
    
    #check for connectivity
    if len(eds_all) == 2:
        if any([ed.other_vert(va) == vb for ed in vb.link_edges]):
            #already a tri over here
            #print('va and vb connect')
            return 2 * math.pi, None, None
    
        elif any([f in eds_non_man[0].link_faces for f in eds_non_man[1].link_faces]):
            #print('va and vb share face')
            return 2 * math.pi, None, None
        
        else: #completely regular situation
            
            if Va.cross(Vb).dot(v.normal) < 0:
                print('keep normals consistent reverse')
                return angle, vb, va
            else:
                return angle, va, vb
    
    elif len(eds_all) > 2:
        #sort edges ccw by normal, starting at eds_nm[0]
        eds_sorted = sort_objects_by_angles(v.normal, eds_all, eds_vecs)
        vecs_sorted = [ed.other_vert(v).co - v.co for ed in eds_sorted]
        deltas = delta_angles(v.normal, vecs_sorted)
        ed1_ind = eds_sorted.index(eds_non_man[1])
        
        #delta_forward = sum(deltas[:ed1_ind])
        #delta_reverse = sum(deltas[ed1_ind:])
        
        if Va.cross(Vb).dot(v.normal) > 0:
        
            if ed1_ind == 1:
            

                return angle, va, vb
            
            elif ed1_ind == (len(eds_sorted) - 1):
                
                return 2*math.pi - angle, vb, va
            
            else:
                #PROBLEMS!
                #print("Sorted angle is %i in the list" % ed1_ind)
                return angle, va, vb
        
        else:
                
            if ed1_ind == 1:
                return 2*math.pi - angle, va, vb
            
            elif ed1_ind == (len(eds_sorted) - 1):
                return angle, vb, va
            
            else:
                #PROBLEMS!
                #print("BIG BIG PROBLEMS")
                return angle, vb, va

def clockwise_loop(vert_loop, z):
    
    
    vcoords = [v.co for v in vert_loop]
    vcoords += [vcoords[0], vcoords[1]]
    l = len(vcoords)
    curl = 0
    
    for n in range(0,l-2):
        #Vec representation of the two edges
        V0 = (vcoords[n+1] - vcoords[n])
        V1 = (vcoords[n+2] - vcoords[n+1])
        
        ##XY projection
        T0 = V0 - V0.project(z)
        T1 = V1 - V1.project(z)
        
        cross = T0.cross(T1)        
        sign = 1
        if cross.dot(z) < 0:
            sign = -1
        
        rot = T0.rotation_difference(T1)  
        ang = rot.angle
        curl = curl + ang*sign
        

    if curl < 0:
        return False
    else:
        return True
             
class D3SPLINT_OT_paint_model(bpy.types.Operator):
    '''Use sculpt mask to mark parts of model'''
    bl_idname = "d3splint.enter_sculpt_paint_mask"
    bl_label = "Paint Model"
    bl_options = {'REGISTER','UNDO'}

    
    
    @classmethod
    def poll(cls, context):
        if not context.object:
            return False
        if context.object.type != 'MESH':
            return False
        
        return True
            
    def execute(self, context):
             
            
        bpy.ops.object.mode_set(mode = 'SCULPT')
        #if not model.use_dynamic_topology_sculpting:
        #    bpy.ops.sculpt.dynamic_topology_toggle()
        
        scene = context.scene
        paint_settings = scene.tool_settings.unified_paint_settings
        paint_settings.use_locked_size = True
        paint_settings.unprojected_radius = .5
        brush = bpy.data.brushes['Mask']
        brush.strength = 1
        brush.stroke_method = 'SPACE'
        scene.tool_settings.sculpt.brush = brush
        scene.tool_settings.sculpt.use_symmetry_x = False
        scene.tool_settings.sculpt.use_symmetry_y = False
        scene.tool_settings.sculpt.use_symmetry_z = False
        bpy.ops.brush.curve_preset(shape = 'MAX')
        
        return {'FINISHED'}

class D3SPLINT_OT_finish_paint(bpy.types.Operator):
    '''Finish painting by re-entering object mode'''
    bl_idname = "d3splint.finish_pain"
    bl_label = "Paint Model"
    bl_options = {'REGISTER','UNDO'}

    
    
    @classmethod
    def poll(cls, context):
        if not context.object:
            return False
        if context.object.type != 'MESH':
            return False
        if context.mode != 'SCULTP':
            return False
        
        return True
            
    def execute(self, context):
             
            
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
        
        return {'FINISHED'}
      
class D3SPLINT_OT_delete_sculpt_mask(bpy.types.Operator):
    '''Delete painted parts of mesh'''
    bl_idname = "d3splint.delete_sculpt_mask"
    bl_label = "Delete Sculpt Mask"
    bl_options = {'REGISTER','UNDO'}

    @classmethod
    def poll(cls, context):
        
        if not context.object:
            return False
        
        c1 = context.object.type == 'MESH'
        c2 = context.mode != 'EDIT'
        return c1 & c2
    
    def execute(self, context):
        
        bme = bmesh.new()
            
        bme.from_mesh(context.object.data)
        
        print('got a bmesh.')
        bme.verts.ensure_lookup_table()
        mask = bme.verts.layers.paint_mask.verify()
            
        
        bme.verts.ensure_lookup_table()
        
        print('There are %i verts in the bmesh' % len(bme.verts))
        delete = []
        for v in bme.verts:
            if v[mask] > 0:
                delete.append(v)

        print('Deleting %i verts' % len(delete))
        bmesh.ops.delete(bme, geom = delete, context = 1)
        
        print('Doing the deleting')
        bme.to_mesh(context.object.data)
        bme.free()
        context.object.data.update()
        
        return {'FINISHED'}


class D3SPLINT_OT_sculpt_model_undo(bpy.types.Operator):
    '''Special undo because of sculpt mode'''
    bl_idname = "d3splint.sculpt_maodel_undo"
    bl_label = "Undo Model Modification"
    bl_options = {'REGISTER','UNDO'}

    @classmethod
    def poll(cls, context):
        
        if not context.object:
            return False
        
        c1 = context.object.type == 'MESH'
        c2 = context.mode == 'SCULPT'
        return c1 & c2
    
    def execute(self, context):
        #remember where we are..because the undo can change it
        ob = context.object
        bpy.ops.object.mode_set(mode = 'OBJECT')
        bpy.ops.ed.undo()
        bpy.ops.object.select_all(action = 'DESELECT')
        ob.select = True
        context.scene.objects.active = ob
        ob.select = True
        bpy.ops.d3splint.enter_sculpt_paint_mask()
        return {'FINISHED'}
    
    
class D3SPLINT_OT_close_painted_hole(bpy.types.Operator):
    '''Paint a hole to close it'''
    bl_idname = "d3splint.close_paint_hole"
    bl_label = "Close Paint Hole"
    bl_options = {'REGISTER','UNDO'}

    iterations = bpy.props.IntProperty(default = 5, min = 1, max = 30, description ="Number of times to relax hole border")
    
    @classmethod
    def poll(cls, context):
        
        if not context.object:
            return False
        
        c1 = context.object.type == 'MESH'
        c2 = context.mode != 'EDIT'
        return c1 & c2
    
    def execute(self, context):
        
        if context.mode == 'SCULPT':
            #this is to snag an undo snapshot
            bpy.ops.object.mode_set(mode = 'OBJECT')
            bpy.ops.object.mode_set(mode = 'SCULPT')
        bme = bmesh.new()
            
        bme.from_mesh(context.object.data)
        mask = bme.verts.layers.paint_mask.verify()
        bme.verts.ensure_lookup_table()
        
        verts = set()
        for v in bme.verts:
            if v[mask] > 0:
                verts.add(v)

        eds = set()
        for v in verts:
            eds.update(v.link_edges)
            
        eds = list(eds)
        
        eds_non_man = [ed for ed in eds if len(ed.link_faces) == 1]
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in eds_non_man])    
        
        if len(loops) > 1:
            self.report({'ERROR'}, 'This tool only closes one hole at a time! Clear Paint or make sure boundary is completley selected')
            bme.free()
            return {'CANCELLED'}
        
        for loop in loops:
            if loop[0] == loop[-1]:
                loop.pop()
            
            if len(loop) < 3: continue
            
            loop_eds = [ed for ed in eds_non_man if all([v.index in loop for v in ed.verts])]
            relax_loops_util(bme, loop_eds, self.iterations, influence = .5)
            bme.faces.new([bme.verts[i] for i in loop])
        
        bme.to_mesh(context.object.data)
        bme.free()
        context.object.data.update()
        
        bpy.ops.paint.mask_flood_fill(mode = 'VALUE', value = 0)
          
        return {'FINISHED'}

class D3SPLINT_OT_keep_sculpt_mask(bpy.types.Operator):
    '''Delete everything not painted'''
    bl_idname = "d3splint.delete_sculpt_mask_inverse"
    bl_label = "Delete Sculpt Mask Inverse"
    bl_options = {'REGISTER','UNDO'}

    @classmethod
    def poll(cls, context):
        if not context.object:
            return False
        c1 = context.object.type == 'MESH'
        c2 = context.mode != 'EDIT'
        return c1 & c2
    
    def execute(self, context):
        
        bme = bmesh.new()
            
        bme.from_mesh(context.object.data)
        mask = bme.verts.layers.paint_mask.verify()
        bme.verts.ensure_lookup_table()
        delete = []
        for v in bme.verts:
            if v[mask] < 0.1:
                delete.append(v)

        bmesh.ops.delete(bme, geom = delete, context = 1)
        
        bme.to_mesh(context.object.data)
        bme.free()
        context.object.data.update()
        bpy.ops.paint.mask_flood_fill(mode = 'VALUE', value = 0)

        return {'FINISHED'}

class D3SPLINT_OT_mask_to_convex_hull(bpy.types.Operator):
    '''Turn painted area into convex hull'''
    bl_idname = "d3splint.sculpt_mask_qhull"
    bl_label = "Sculpt Mask to convex hull"
    bl_options = {'REGISTER','UNDO'}

    @classmethod
    def poll(cls, context):
        
        c1 = context.object.type == 'MESH'
        c2 = context.mode != 'EDIT'
        return c1 & c2
    
    def execute(self, context):
        
        start_ob = context.object
        
        bme = bmesh.new()
            
        bme.from_mesh(context.object.data)
        mask = bme.verts.layers.paint_mask.verify()
        bme.verts.ensure_lookup_table()
        delete = []
        for v in bme.verts:
            if v[mask] < 0.1:
                delete.append(v)

        bmesh.ops.delete(bme, geom = delete, context = 1)
        
        out_geom = bmesh.ops.convex_hull(bme, input = bme.verts[:], use_existing_faces = True)
        
        print('out geom')
        
        unused_geom = out_geom['geom_interior']
        
        del_v = [ele for ele in unused_geom if isinstance(ele, bmesh.types.BMVert)]
        del_e = [ele for ele in unused_geom if isinstance(ele, bmesh.types.BMEdge)]
        del_f = [ele for ele in unused_geom if isinstance(ele, bmesh.types.BMFace)]
        
        #these must go
        bmesh.ops.delete(bme, geom = del_v, context = 1)
        #bmesh.ops.delete(bme, geom = del_e, context = )
        bmesh.ops.delete(bme, geom = del_f, context = 5)
        #then we need to remove internal faces that got enclosed in
        holes_geom = out_geom['geom_holes']
        
        
        for v in bme.verts:
            v.select_set(False)
        for ed in bme.edges:
            ed.select_set(False)
        for f in bme.faces:
            f.select_set(False)
            
        bme.select_mode = {'FACE'}    
        
        del_f = [ele for ele in holes_geom if isinstance(ele, bmesh.types.BMFace)]
        #bmesh.ops.delete(bme, geom = del_f, context = 5)
        
        
        
        #find bad edges
        
        bad_eds = [ed for ed in bme.edges if len(ed.link_faces) != 2]
        print("there are %i bad eds" % len(bad_eds))
        
        eds_zero_face = [ed for ed in bad_eds if len(ed.link_faces) == 0]
        eds_one_face = [ed for ed in bad_eds if len(ed.link_faces) == 1]
        eds_three_face = [ed for ed in bad_eds if len(ed.link_faces) == 3]
        eds_other = [ed for ed in bad_eds if len(ed.link_faces) > 3]
        
        print('there are %i bad edges with 0 facew' % len(eds_zero_face))
        print('there are %i bad edges with 1 faces' % len(eds_one_face))
        print('there are %i bad edges with 3 faces' % len(eds_three_face))
        print('there are %i bad edges with more faces' % len(eds_other))
        
        
        #First Delete loose edge
        
        bad_faces = [f for f in bme.faces if not all(len(ed.link_faces) == 2 for ed in f.edges)]
        print("there are %i bad faces" % len(bad_faces))
        
        new_me = bpy.data.meshes.new("CHull")
        new_ob = bpy.data.objects.new("CHull", new_me)
        new_ob.matrix_world = context.object.matrix_world
        context.scene.objects.link(new_ob)
        new_ob.parent = context.object
        bme.to_mesh(new_me)
        bme.free()
        context.object.data.update()
        
        bpy.ops.paint.mask_flood_fill(mode = 'VALUE', value = 0)
        
        mod = new_ob.modifiers.new('Remesh', type = 'REMESH')
        mod.mode = 'SMOOTH'
        mod.octree_depth = 5
        
        final_bme = bmesh.new()
        final_bme.from_object(new_ob, context.scene, deform = True)
        
        new_ob.modifiers.remove(mod)
        final_bme.to_mesh(new_ob.data)
        
        final_bme.free()
        
        return {'FINISHED'}

class D3SPLINT_OT_remesh_decimate(bpy.types.Operator):
    '''Remesh to close holes and decimate to target resolution'''
    bl_idname = "d3model.remesh_and_decimate"
    bl_label = "Remesh and Decimate"
    bl_options = {'REGISTER','UNDO'}

    remesh_depth = bpy.props.IntProperty(default = 9, min = 5, max = 10, description = 'Remesh Modifier depth 9 is usually good, 10 is slow, 8 for quick prints')
    detail_level = bpy.props.IntProperty(default = 3, min = 1, max = 8, description = 'Sculpt remesh triangulation detail, 3 to 4 is fine for splints')
    #target_resolution = bpy.props.IntProperty(default = 150, min = 30, max = 300, step = 10,description = 'Target number of verts in thousands')
    method = bpy.props.EnumProperty(items = (('BMESH','BMESH','BMESH'),('MESH','MESH','MESH')),default = 'BMESH')
    @classmethod
    def poll(cls, context):
        
        c1 = context.object.type == 'MESH'
        c2 = context.mode != 'EDIT'
        return c1 & c2
    
    def invoke(self,context,event):
        return context.window_manager.invoke_props_dialog(self)
        
    def execute(self, context):
        
        ob = context.object
        
        mod = ob.modifiers.new('Remesh', type = 'REMESH')
        mod.mode = 'SMOOTH'
        mod.octree_depth = self.remesh_depth
        
        if self.method == 'BMESH':
            start = time.time()
            bme = bmesh.new()
            bme.from_object(ob, context.scene)
            bme.verts.ensure_lookup_table()
            n = len(bme.verts)
            finish = time.time()
            print('took %f seconds to extract BMesh' % (finish-start))
        else:
            start = time.time()
            me = ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            n = len(me.vertices)
            finish = time.time()
            print('took %f seconds to extract regular Mesh' % (finish-start))
        
        
        
        #factor = self.target_resolution * 1000 / n
        
        ob.modifiers.clear()
        
        
        if self.method == 'BMESH':
            bme.to_mesh(ob.data)
            bme.free()
            print('took %f seconds to entire operation BMesh' % (finish-start))
        else:
            old_me = ob.data
            ob.data = me
            bpy.data.meshes.remove(old_me)
            finish = time.time()
            print('took %f seconds to do entire operation Mesh' % (finish-start))
            
            
        
        
        bpy.ops.object.mode_set(mode = 'SCULPT')
        if not ob.use_dynamic_topology_sculpting:
            bpy.ops.sculpt.dynamic_topology_toggle()
        context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
        context.scene.tool_settings.sculpt.constant_detail_resolution = self.detail_level
        bpy.ops.sculpt.detail_flood_fill()
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
        
        #if factor < 1:
        #    mod = ob.modifiers.new('Decimate', type = 'DECIMATE')
        #    mod.use_collapse_triangulate = True
        #    mod.ratio = factor
            
        #    if self.method == 'BMESH':
        #        start = time.time()
        #        bme = bmesh.new()
        #        bme.from_object(ob, context.scene)
        #        bme.verts.ensure_lookup_table()
        #        n = len(bme.verts)
        #        finish = time.time()
        #        print('took %f seconds to extract 2nd BMesh' % (finish-start))
        #    else:
        #        start = time.time()
        #        me = ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        #        n = len(me.vertices)
        #        finish = time.time()
        #        print('took %f seconds to extract 2nd regular Mesh' % (finish-start))
        
        #    ob.modifiers.clear()
        
        
        #    if self.method == 'BMESH':
        #        bme.to_mesh(ob.data)
        #        bme.free()
        #        print('took %f seconds to entire operation BMesh' % (finish-start))
        #    else:
        #        old_me = ob.data
        #        ob.data = me
        #        bpy.data.meshes.remove(old_me)
        #        finish = time.time()
        #        print('took %f seconds to do entire operation Mesh' % (finish-start))
                        
        return {'FINISHED'}
    
    
class D3SPLINT_OT_delete_islands(bpy.types.Operator):
    '''Delete small disconnected pieces of mesh'''
    bl_idname = "d3splint.delete_islands"
    bl_label = "Delete Mesh Islands"
    bl_options = {'REGISTER','UNDO'}

    invert = bpy.props.BoolProperty(default = False, name = 'Invert')
    @classmethod
    def poll(cls, context):
        
        if not context.object:
            return False
        c1 = context.object.type == 'MESH'
        c2 = context.mode != 'EDIT'
        return c1 & c2
    
    def execute(self, context):
        
        bme = bmesh.new()
            
        bme.from_mesh(context.object.data)
        
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        #clean loose verts
        to_delete = []
        for v in bme.verts:
            if len(v.link_edges) < 2:
                to_delete.append(v)
                
        print('deleting %i loose verts' % len(to_delete))
        bmesh.ops.delete(bme, geom = to_delete, context = 1)
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        #delete edges without faces
        to_delete = []
        for ed in bme.edges:
            if len(ed.link_faces) == 0:
                for v in ed.verts:
                    if len(v.link_faces) == 0:
                        to_delete.append(v)

        to_delete = list(set(to_delete))
        bmesh.ops.delete(bme, geom = to_delete, context = 1)
                
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        total_faces = set(bme.faces[:])
        islands = []
        iters = 0
        while len(total_faces) and iters < 100:
            iters += 1
            seed = total_faces.pop()
            island = flood_selection_faces(bme, {}, seed, max_iters = 10000)
            islands += [island]
            total_faces.difference_update(island)
            
        
        best = max(islands, key = len)
        
        total_faces = set(bme.faces[:])
        del_faces = total_faces - best
        
        bmesh.ops.delete(bme, geom = list(del_faces), context = 3)
        del_verts = []
        for v in bme.verts:
            if all([f in del_faces for f in v.link_faces]):
                del_verts += [v]        
        bmesh.ops.delete(bme, geom = del_verts, context = 1)
        
        
        del_edges = []
        for ed in bme.edges:
            if len(ed.link_faces) == 0:
                del_edges += [ed]
        bmesh.ops.delete(bme, geom = del_edges, context = 4) 
        
        
        bme.to_mesh(context.object.data)
        bme.free()
        context.object.data.update()
        
        return {'FINISHED'}


class D3SPLINT_OT_remove_ragged_edges(bpy.types.Operator):
    '''Remove small peninsulas by an expansion and contraction selection'''
    bl_idname = "d3splint.ragged_edges"
    bl_label = "Improve Ragged Border"
    bl_options = {'REGISTER','UNDO'}

    
    
    iterations = bpy.props.IntProperty(name = 'Expansion/Dilation Iterations', default = 20, min = 3, max = 100)
    
    preview_selection = bpy.props.IntProperty(name = 'Previoew Selection', default = 0, min = 0, max = 10)
    
    @classmethod
    def poll(cls, context):
        
        if not context.object:
            return False
        c1 = context.object.type == 'MESH'
        c2 = context.mode != 'EDIT'
        return c1 & c2
    
    def execute(self, context):
        
        start_global = time.time()
        start = start_global
        
        
        bme = bmesh.new()
        bme.from_mesh(context.object.data)
        
        bme.edges.ensure_lookup_table()
        bme.verts.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        
        print('Took %f seconds to initiate bmesh' % (time.time() - start))
        start = time.time()
        
        non_man_eds = [ed for ed in bme.edges if len(ed.link_faces) == 1]
        
        print('Took %f seconds to find non manifold edges' % (time.time() - start))
        start = time.time()
        
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in non_man_eds])

        if len(loops)>1:
            biggest_loop = max(loops, key = len)
            self.report({'WARNING'}, 'There are multiple holes in mesh')
            
        else:
            biggest_loop = loops[0]
            
        print('Took %f seconds to find mesh perimeter' % (time.time() - start))
        start = time.time()
        
        perim_faces =  set()
        for i in biggest_loop:
            perim_faces.update(bme.verts[i].link_faces)
        
        perim_faces = list(perim_faces)    
        print('Took %f seconds to initiate perimeter faces' % (time.time() - start))
        start = time.time()
        
        expansion = flood_selection_faces(bme, perim_faces, perim_faces, max_iters = self.iterations)
        
        print('Took %f seconds to dilate selection' % (time.time() - start))
        start = time.time() 
        
        
        expansion_perimeter = [f for f in expansion if not all([bmf in expansion for bmf in face_neighbors_by_vert(f)])]
        
        #contraction = contract_selection_faces(bme, expansion, expansion_mode = 'EDGE', max_iters = self.iterations -1)    
        
        print('Took %f seconds to identify epxansion border' % (time.time() - start))
        start = time.time() 
        
        
        reverse_expansion = flood_selection_faces(bme, expansion_perimeter, expansion_perimeter, max_iters = self.iterations)
        
        
        final_faces = expansion- reverse_expansion
        
        print('Took %f seconds to epxand in reverse' % (time.time() - start))
        start = time.time() 
        
        
        #all_verts = set()
        #delete_edges = set()
        #for f in final_faces:
        #    all_verts.update(f.verts)
        
        #    for ed in f.edges:
        #        if ed in delete_edges: continue
        #        if all([bmf in final_faces for bmf in ed.link_faces]):
        #            delete_edges.add(ed)
        #delete_verts = []
        #for v in all_verts:      
        #    if all(bmf in final_faces for bmf in v.link_faces):
        #        delete_verts += [v]
        
        bmesh.ops.delete(bme, geom = list(final_faces), context = 5)
        #bmesh.ops.delete(bme, geom = list(delete_edges), context = 2)
        #bmesh.ops.delete(bme, geom = delete_verts, context = 1)
        
        
        
        for f in bme.faces:
            f.select_set(False)
            
        
        print('Took %f seconds to delete' % (time.time() - start))
        start = time.time() 
        
        #if self.preview_selection == 0:
        #    preview = perim_faces
        #elif self.preview_selection == 1:
        #    preview = expansion
        #elif self.preview_selection == 2:
        #    preview = expansion_perimeter
        #elif self.preview_selection == 3:
        #    preview = reverse_expansion
        #else:
        #    preview = final_faces
            
        #for f in preview:
        #    f.select_set(True)
        
        bme.to_mesh(context.object.data)
        bme.free()
        context.object.data.update()
        
        print('Took %f seconds to finish entire operator' % (time.time() - start_global))
        start = time.time() 
        
        return {'FINISHED'}
    
    
class D3PLINT_OT_simple_model_base(bpy.types.Operator):
    """Simple ortho base with height 5 - 50mm """
    bl_idname = "d3splint.simple_base"
    bl_label = "Simple model base"
    bl_options = {'REGISTER', 'UNDO'}
    
    base_height = bpy.props.FloatProperty(name = 'Base Height', default = 3, min = 0, max = 50,  description = 'Base height added in mm')
    #smooth_zone = bpy.props.FloatProperty(name = 'Smooth Zone', default = .5, min = .2, max = 2.0,  description = 'Width of border smoothing zone in mm')
    smooth_iterations = bpy.props.IntProperty(name = 'Smooth Iterations', default = 10, min = 0, max = 50,  description = 'Iterations to smooth the smoothing zone')
    #reverse = bpy.props.BoolProperty(name = 'Reverse Z direction', default = False, description = 'Use if auto detection detects base direction wrong')
    
    mode_items = {('BEST_FIT','BEST_FIT','BEST_FIT'), ('LOCAL_Z','LOCAL_Z','LOCAL_Z'),('WORLD_Z','WORLD_Z','WORLD_Z')}
    mode = bpy.props.EnumProperty(name = 'Base Mode', items = mode_items)
    
    batch_mode = bpy.props.BoolProperty(name = 'Batch Mode', default = False, description = 'Will do all selected models, may take 1 minute per model, ')
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None and context.object.type == 'MESH':
            return True
        else:
            return False
        
    
        
    def invoke(self,context,event):
        
        return context.window_manager.invoke_props_dialog(self)
        
    
    def execute(self,context):
        
        if self.batch_mode:
            for ob in context.selected_objects:
                if ob.type != 'MESH': continue
                
                self.exe_tool(context, ob)
   
        else:
            self.exe_tool(context, context.object)
            
        return {'FINISHED'}
        
    def exe_tool(self, context, ob):
        
        def clean_geom(bme):
            #make sure there are no node_verts
            #make sure no loose triangles
            
            #first pass, collect all funky edges
            funky_edges = [ed for ed in bme.edges if (len(ed.link_faces) != 2 or ed.calc_length() < .00001)]
            
            
            degenerate_eds = [ed for ed in funky_edges if len(ed.link_faces) > 2]
            zero_len_eds = [ed for ed in funky_edges if ed.calc_length() < .00001]
            loose_eds = [ed for ed in funky_edges if len(ed.link_faces) == 0]
            non_man_eds = [ed for ed in funky_edges if len(ed.link_faces) == 1]
            
            
            if len(degenerate_eds):
                print('found %i degenerate edges' % len(degenerate_eds))
                bmesh.ops.split_edges(bme, edges = degenerate_eds, verts = [])
                
                #now need to run again, and hopefully delete loose triangles
                return -1
            if len(zero_len_eds):
                print('dissolving zero length edges %i' % len(zero_len_eds))
                bmesh.ops.dissolve_degenerate(bme, dist = .0001, edges = zero_len_eds)  
                return -1  
            if len(loose_eds):
                loose_vs = set()
                for ed in loose_eds:
                    vs = [v for v in ed.verts if len(v.link_faces) == 0]
                    loose_vs.update(vs)
                print('Deleting %i loose edges' % len(loose_eds))    
                bmesh.ops.delete(bme, geom = loose_eds, context = 4)
                bmesh.ops.delete(bme, geom = list(loose_vs), context = 1)
                
                #deleteing loose eds has no effect on existing perimeter edges
                #no need to return
                
            perim_verts = set()
            perim_faces = set()
            for ed in non_man_eds:
                perim_verts.update([ed.verts[0], ed.verts[1]])
                if len(ed.link_faces) == 1:
                    perim_faces.add(ed.link_faces[0])
            
            #first check for loose triangles
            bad_triangles = []
            for f in perim_faces:
                check = [ed for ed in f.edges if ed in non_man_eds]
                if len(check) == 3:
                    bad_triangles.append(f)
                elif len(check) ==2:
                    for v in f.verts:
                        if v in check[0].verts and v in check[1].verts:
                            veca = check[0].other_vert(v).co - v.co
                            vecb = check[1].other_vert(v).co - v.co
                            
                            
                            if veca.angle(vecb) < 50 * math.pi/180:
                                print(veca.angle(vecb))
                                bad_triangles.append(f)
                        
                               
            if len(bad_triangles):
                bad_verts = set()
                bad_edges = set()
                for f in bad_triangles:
                    del_verts = [v for v in f.verts if len(v.link_faces) == 1]
                    del_edges = [ed for ed in f.edges if len(ed.link_faces) == 1]
                    bad_verts.update(del_verts)
                    bad_edges.update(del_edges)
                bmesh.ops.delete(bme, geom = bad_triangles, context = 3)
                bmesh.ops.delete(bme, geom = list(bad_edges), context = 4)
                bmesh.ops.delete(bme, geom = list(bad_verts), context = 1)
                print('Deleting %i loose and flag/dangling triangles' % len(bad_triangles))
                
                #this affects the perimeter, will need to do another pass
                #could also remove bad_fs from perimeter fs...
                #for now laziness do another pass
                return -1
            
            
            #fill small angle coves
            #initiate the front and calc angles
            angles = {}
            neighbors = {}
            for v in perim_verts:
                ang, va, vb = calc_angle(v)
                angles[v] = ang
                neighbors[v] = (va, vb)    
                 
            
            iters = 0 
            start = time.time()
            N = len(perim_verts)
            new_fs = []
            coved = False
            while len(perim_verts) > 3 and iters < 2 * N:
                iters += 1
                
                v_small = min(perim_verts, key = angles.get)
                smallest_angle = angles[v_small]
                
                va, vb = neighbors[v_small]
                
                vec_a = va.co - v_small.co
                vec_b = vb.co - v_small.co
                vec_ab = va.co - vb.co
                
                
                Ra, Rb = vec_a.length, vec_b.length
                
                R_13 = .67*Ra + .33*Rb
                R_12 = .5*Ra + .5*Rb
                R_23 = .33*Ra + .67*Rb

                vec_a.normalize()
                vec_b.normalize()
                v_13 = vec_a.lerp(vec_b, .33) #todo, verify lerp
                v_12 = vec_a.lerp(vec_b, .5)
                v_23 = vec_a.lerp(vec_b, .67)
                
                v_13.normalize()
                v_12.normalize()
                v_23.normalize()
                
                if smallest_angle < math.pi/180 * 120:
                    try:
                        #f = bme.faces.new((va, v_small, vb))
                        f = bme.faces.new((vb, v_small, va))
                        new_fs += [f]
                        f.normal_update()
                        coved = True
                        
                        #update angles and neighbors
                        ang_a, vaa, vba = calc_angle(va)
                        ang_b, vab, vbb = calc_angle(vb)
                        
                        angles[va] = ang_a
                        angles[vb] = ang_b
                        neighbors[va] = (vaa, vba)
                        neighbors[vb] = (vab, vbb)
                        perim_verts.remove(v_small)
                        
                    except ValueError:
                        print('concavity with face on back side')
                        angles[v_small] = 2*math.pi
            
            
                else:
                    
                    print('finished coving all small angle concavities')
                    print('Coved %i verts' % len(new_fs))
                    for f in new_fs:
                        f.select_set(True)
                    break
            if coved:
                print('Coved returning early')
                return -1
            
                     
            node_verts = []
            end_verts = []
            for v in perim_verts:
                check = [ed for ed in v.link_edges if ed in non_man_eds]
                if len(check) != 2:
                    if len(check) > 2:
                        node_verts.append(v)
                    elif len(check) == 1:
                        print("found an endpoint of an unclosed loop")
                        end_verts.append(v)
            
            
            if len(node_verts):
                for v in node_verts:
                    bmesh_fns.bme_rip_vertex(bme, v)
                
                #ripping changes the perimeter and topology, try again
                print('ripping %i node vertices' % len(node_verts))
                return -1
    
    
        
        start_global = time.time()
        
        
        mx = ob.matrix_world
        imx = mx.inverted()
        
        bme = bmesh.new()
        bme.from_mesh(ob.data)
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        

        start = time.time()
        clean_iterations = 0
        test = -1
        while clean_iterations < 10 and test == -1:
            print('Cleaning iteration %i' % clean_iterations)
            clean_iterations += 1
            test = clean_geom(bme) 
        
        
        print('took %f seconds to clean geometry and edges' % (time.time() - start))
        start = time.time()
        
        #update everything
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        bme.verts.index_update()
        bme.edges.index_update()
        bme.faces.index_update()
        #bme.to_mesh(context.object.data)
        #context.object.data.update()
        #bme.free()
        #return {'FINISHED'}
        
        non_man_eds = [ed for ed in bme.edges if len(ed.link_faces) == 1]        
        
        for f in bme.faces:
            f.select_set(False)
        for ed in non_man_eds:
            ed.select_set(True)
        
        #bme.to_mesh(context.object.data)
        #context.object.data.update()
        #bme.free()
        #return {'FINISHED'}
        
        
        non_man_inds = [ed.index for ed in non_man_eds]
        
        if len(non_man_inds) == 0:
            print('no perimeter loop')
            bme.free()
            return
        loops = edge_loops_from_bmedges(bme, non_man_inds)
        
        
        #if loops[0][0] != loops[0][-1]:
        #    print('Not a closed loop!')
        #    print(loops[0][0:20])
        #    print(loops[0][len(loops[0])-20:])
        
        #if len(loops[0]) != len(set(loops[0])):
        #    print('doubles in the loop')
        #    seen = set()
        #    uniq = []
        #    for x in loops[0]:
        #        if x not in seen:
        #            uniq.append(x)
        #            seen.add(x)

        if len(loops)>1:
            biggest_loop = max(loops, key = len)
            self.report({'WARNING'}, 'There are multiple holes in mesh')
            
            for l in loops:
                if l != biggest_loop:
                    print(l)
        else:
            biggest_loop = loops[0]
            
        if biggest_loop[0] != biggest_loop[-1]:
            print('Biggest loop not a hole!')
            bme.free() 
            return {'FINISHED'}
        
        biggest_loop.pop()
        final_eds = [ed for ed in non_man_eds if all([v.index in biggest_loop for v in ed.verts])]
        
        
        print('took %f seconds to identify single perimeter loop' % (time.time() - start))
        start = time.time()
        
        relax_loops_util(bme, final_eds, iterations = 3, influence = .5, override_selection = True, debug = True)
        
        #get the total median point of model
        total_com = Vector((0,0,0))
        for v in bme.verts:
            total_com += v.co
        total_com *= 1/len(bme.verts)
        
        loop_verts = [bme.verts[i] for i in biggest_loop]
        
        locs = [v.co for v in loop_verts]
        com = Vector((0,0,0))
        for v in locs:
            com += v
        com *= 1/len(locs)
            
        if self.mode == 'BEST_FIT':
            
            plane_vector = com - total_com
            no = odcutils.calculate_plane(locs, itermax = 500, debug = False)
            if plane_vector.dot(no) < 0:
                no *= -1
            
            Z = no
            
            print('took %f seconds to calculate best fit plane' % (time.time() - start))
            start = time.time()
        
        elif self.mode == 'WORLD_Z':
            Z = imx.to_3x3() * Vector((0,0,1))
        else:
            Z = Vector((0,0,1))
        
        #Z should point toward the occlusal always
        direction = 0
        for f in bme.faces:
            direction += f.calc_area() * f.normal.dot(Z)
        
        if direction < 0:
            #flip Z            
            Z *= -1
                
    
        print('took %f seconds to identify average face normal' % (time.time() - start))
        start = time.time()
        
        Z.normalize()
        minv = min(loop_verts, key = lambda x: (x.co - com).dot(Z))
        
        print('took %f seconds to identify average smallest vert' % (time.time() - start))
        start = time.time()
          
        #select one extra boundary of verts to smooth
        smooth_verts = set(loop_verts)
        for v in loop_verts:
            neighbors = [ed.other_vert(v) for ed in v.link_edges]
            smooth_verts.update(neighbors)
            
        
        gdict = bmesh.ops.extrude_edge_only(bme, edges = final_eds)
        bme.edges.ensure_lookup_table()
        newer_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
        newer_verts = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
    
        for v in newer_verts:
            v.co += -.1 * Z
            
    
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        relax_loops_util(bme, newer_edges, iterations = 10, influence = .5, override_selection = True, debug = True)
            
            
        gdict = bmesh.ops.extrude_edge_only(bme, edges = newer_edges)
        bme.edges.ensure_lookup_table()
        bme.verts.ensure_lookup_table()
        new_verts = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
        new_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
        
        
        for v in new_verts:
            
            co_flat = v.co +  (minv.co - v.co).dot(Z) * Z
            
            v.co = co_flat - self.base_height * Z
            
        
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in new_edges])  
            
        loops[0].pop()
        f = bme.faces.new([bme.verts[i] for i in loops[0]])
        
        
        #base face should point away from occlusal
        f.normal_update()
        if f.normal.dot(Z) > 0:
            f.normal_flip()
        
        
        bme.to_mesh(ob.data)
        ob.data.update()
        
        if 'Smooth Base' not in ob.vertex_groups:
            sgroup = ob.vertex_groups.new('Smooth Base')
        else:
            sgroup = ob.vertex_groups.get('Smooth Base')
        sgroup.add([v.index for v in smooth_verts], 1, type = 'REPLACE')
        
        if 'Smoooth Base' not in ob.modifiers:
            smod = ob.modifiers.new('Smooth Base', type = 'SMOOTH')
        else:
            smod = ob.modifiers['Smooth Base']
        smod.vertex_group = 'Smooth Base'
        smod.iterations = self.smooth_iterations
        
        bme.free()
        
        print('Took %f seconds to finish entire operator' % (time.time() - start_global))
         
        return
        
class D3PLINT_OT_ortho_model_base(bpy.types.Operator):
    """Simple ortho base with height 5 - 50mm """
    bl_idname = "d3splint.ortho_base"
    bl_label = "Ortho model base"
    bl_options = {'REGISTER', 'UNDO'}
    
    base_height = bpy.props.FloatProperty(name = 'Base Height', default = 1, min = -50, max = 50,  description = 'Base height added in mm')
    
    maxilla = bpy.props.BoolProperty(name = 'Maxilla', default = False, description = 'Is this the upper or lower jaw')
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None and context.object.type == 'MESH':
            return True
        else:
            return False
        
    def execute(self, context):
        
        base_bme = bmesh.new()
        
        
        bme = bmesh.new()
        bme.from_mesh(context.object.data)
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        
        non_man_bmeds = [ed for ed in bme.edges if not ed.is_manifold]
        non_man_eds = [ed.index for ed in non_man_bmeds]
        
        
        non_man_vs = set()
        for ed in non_man_bmeds:
            non_man_vs.update([ed.verts[0], ed.verts[1]])
        non_man_vs = list(non_man_vs)
        
        
        min_x, max_x = non_man_vs[0].co[0], non_man_vs[0].co[0] 
        min_y, max_y = non_man_vs[0].co[1], non_man_vs[0].co[1]
        min_z, max_z = non_man_vs[0].co[2], non_man_vs[0].co[2]
        
        com = Vector((0,0,0))
        
        for v in non_man_vs:
            
            com += v.co
            
            if v.co[0] < min_x:
                min_x = v.co[0]
            if v.co[0] > max_x:
                max_x = v.co[0]
            if v.co[1] < min_y:
                min_y = v.co[1]
            if v.co[1] > max_y:
                max_y = v.co[1]
            if v.co[2] < min_z:
                min_z = v.co[2]
            if v.co[2] > max_z:
                max_z = v.co[2]
                
        com *= 1/len(non_man_vs)
        
        print('found the com and bound of the non manifold verts')
                
        loops = edge_loops_from_bmedges(bme, non_man_eds)
                
        print('there are %i non manifold loops' % len(loops))
                
        for ring in loops:
            
            if len(ring) < 100:
                print('Skipping small hole, likely error')
                continue 
            if ring[0] != ring[-1]:
            
                print('loop not a hole not or a loop')
                bme.free() 
            
                return {'FINISHED'}
        
            ring.pop() #ha ha, ring pop
        
            for vind in ring:
                if self.maxilla:
                    bme.verts[vind].co[2] = max_z + self.base_height
                else:
                    bme.verts[vind].co[2] = min_z - self.base_height
        
            
            f = bme.faces.new([bme.verts[vind] for vind in ring])
        
        bmesh.ops.recalc_face_normals(bme, faces = [f])
        
        
        z_filter = non_man_vs[0].co[2]
        
        for v in non_man_vs:
            base_bme.verts.new(v.co)
            if self.maxilla:
                base_bme.verts.new(v.co - self.base_height * Vector((0,0,1)))
            else:
                base_bme.verts.new(v.co + self.base_height * Vector((0,0,1)))
            
        base_bme.verts.ensure_lookup_table()
        geom = bmesh.ops.convex_hull(base_bme, input = base_bme.verts[:])
        
        verts_to_delete = set()
        
        for ele in geom['geom_interior']:
            if isinstance(ele, bmesh.types.BMVert):
                verts_to_delete.add(ele)
            
        for ele in geom['geom_unused']:
            if isinstance(ele, bmesh.types.BMVert):
                verts_to_delete.add(ele)
                    
        #bmesh.ops.delete(base_bme, geom = base_bme.faces[:], context = 3)
        
        bmesh.ops.delete(base_bme, geom = list(verts_to_delete), context = 1)
        
        
        eds_to_delete = []
        for ed in base_bme.edges:
            if ed.calc_face_angle(1) < .5:
                eds_to_delete.append(ed)
        
                    
        bmesh.ops.delete(base_bme, geom = eds_to_delete, context = 4)
        
        thickness_verts = []
        regular_verts = []
        for v in base_bme.verts:
            if abs(v.co[2] - z_filter) > .001:
                thickness_verts.append(v)
            else:
                regular_verts.append(v)
                
        bmesh.ops.delete(base_bme, geom = thickness_verts, context = 1)
        base_bme.edges.ensure_lookup_table()
        loops = edge_loops_from_bmedges(base_bme, [i for i in range(0, len(base_bme.edges))])
        
        base_bme.verts.ensure_lookup_table()
        locs = [base_bme.verts[i].co for i in loops[0]]
        even_locs, even_eds = space_evenly_on_path(locs, [(0,1),(1,0)], segments = 200)
        
        new_verts = []
        for co in even_locs:
            new_verts.append(base_bme.verts.new(co))
        
        base_bme.faces.new(new_verts)
        
        bmesh.ops.delete(base_bme, geom = regular_verts, context = 1)
        
        
        new_me = bpy.data.meshes.new('ortho base')
        new_ob = bpy.data.objects.new('Ortho Base', new_me)
        new_ob.matrix_world = context.object.matrix_world
        context.scene.objects.link(new_ob)
            
        base_bme.to_mesh(new_me)
        
        
        bme.to_mesh(context.object.data)
        bme.free()
        
                    
        return {'FINISHED'}    
    
class D3PLINT_OT_ortho_model_base_former(bpy.types.Operator):
    """Make Ortho Model Base Former"""
    bl_idname = "d3splint.ortho_base_former"
    bl_label = "Model Base Former"
    bl_options = {'REGISTER', 'UNDO'}
    
    base_thickness = bpy.props.FloatProperty(name = 'Base Thickness', default = 10, min = -50, max = 50,  description = 'Base height added in mm')
    
    molar_width = bpy.props.FloatProperty(name = 'Molar Width', default = 60, min = 10, max = 100,  description = 'Molar Width')
    molar_bevel = bpy.props.FloatProperty(name = 'Molar Bevel', default = 10, min = 2, max = 20,  description = 'Molar Bevel')
    
    
    molar_height = bpy.props.FloatProperty(name = 'Molar Height', default = 20, min = 2, max = 50,  description = 'Molar Height')
    bevel_angle = bpy.props.IntProperty(name = 'Bevel Angle', default = 45, min = 35, max = 70,  description = 'Bevel Angle')
    
    
    posterior_length =  bpy.props.FloatProperty(name = 'Posterior Length', default = 40, min = 15, max = 100,  description = 'Posterior Length')
   
    
    canine_width = bpy.props.FloatProperty(name = 'Canine Width', default = 45, min = 10, max = 100,  description = 'Canine Bevel')
    canine_height = bpy.props.FloatProperty(name = 'Canine Height', default = 10, min = 5, max = 100,  description = 'Canine Height')
    
    anterior_length =  bpy.props.FloatProperty(name = 'Anterior Length', default = 15, min = 5, max = 25,  description = 'Anterior Length')
    anterior_height =  bpy.props.FloatProperty(name = 'Anterior Height', default = 10, min = 5, max = 25,  description = 'Anterior Length')
    
    maxilla = bpy.props.BoolProperty(name = 'Maxilla', default = False, description = 'Is this the upper or lower jaw')
    
    solidify = bpy.props.BoolProperty(name = 'Solidify', default = False, description = 'Solidify the top surface for boolean joining')
    land = bpy.props.BoolProperty(name = 'Land', default = False, description = 'Make a Land/Dish like an actual base former')
    
    @classmethod
    def poll(cls, context):
        return True
        
    def execute(self, context):
        
        bme = bmesh.new()
        
        
        total_len = self.anterior_length + self.posterior_length
        
        
        v0 = Vector((0, 0, 0))
        
        
        adj = math.cos(self.bevel_angle * math.pi/180) * self.molar_bevel
        opp = math.sin(self.bevel_angle * math.pi/180) * self.molar_bevel
        
        
        v1 = Vector((.5 * (.5 * self.molar_width - adj), 0, 0))
        v2 = Vector((.5 * self.molar_width - adj, 0, 0))
        v3 = Vector((.5 * self.molar_width, opp, 0))
        
        v4 = Vector((0.5 * self.canine_width, self.posterior_length, 0))
        if self.maxilla:
            v5 = Vector((0, total_len, 0))
        else:
            #this gives room to bevel the point backward
            v5 = Vector((0, total_len + .5 * self.anterior_length, 0))
        
        v6 = v0 + Vector((0,0,self.base_thickness))
        v7 = v1 + Vector((0,0,self.base_thickness))
        v8 = v2 + Vector((0,0,self.molar_height))
        v9 = v3 + Vector((0,0,self.molar_height))
        v10 = v4 + Vector((0,0,self.canine_height))
        v11 = v5 + Vector((0,0,self.anterior_height))
        
        
        bmverts = []
        for co in [v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11]:
            bmverts.append(bme.verts.new(co))
            
            
        bme.faces.new((bmverts[0], bmverts[1], bmverts[7], bmverts[6]))
        bme.faces.new((bmverts[1], bmverts[2], bmverts[8], bmverts[7]))
        bme.faces.new((bmverts[2], bmverts[3], bmverts[9], bmverts[8]))
        bme.faces.new((bmverts[3], bmverts[4], bmverts[10], bmverts[9]))
        bme.faces.new((bmverts[4], bmverts[5], bmverts[11], bmverts[10]))
        bme.faces.new((bmverts[5], bmverts[4], bmverts[3], bmverts[2], bmverts[1], bmverts[0]))
        
        
        
        
        base_me = bpy.data.meshes.new('Base')
        base_ob = bpy.data.objects.new('Ortho Base', base_me)
        context.scene.objects.link(base_ob)
        bme.to_mesh(base_me)
        bme.free()
        
        
        
        
        mir = base_ob.modifiers.new('Mirror', type = 'MIRROR')
        
        if not self.maxilla:
            bgroup = base_ob.vertex_groups.new('Bevel')
            bgroup.add([5, 11], 1, type = 'REPLACE')
            
            bev = base_ob.modifiers.new('Bevel', type = 'BEVEL')
            bev.use_clamp_overlap = False
            bev.width = 1.2 * self.anterior_length
            bev.profile = 0.5
            bev.limit_method = 'VGROUP'
            bev.segments = 20
            bev.vertex_group = 'Bevel'
            bev.offset_type = 'DEPTH'
        
        
        if self.land:
            solid = base_ob.modifiers.new('Solidify', type = 'SOLIDIFY')
            solid.thickness = 3
            solid.offset = 1
        
        if self.solidify:
            rem = base_ob.modifiers.new('Remesh', type = 'REMESH')
            rem.octree_depth = 7
        
        base_ob.location = context.scene.cursor_location  
        return {'FINISHED'}   




class D3Splint_OT_auto_check_model(bpy.types.Operator):
    """Plane cut master model to create a minimal check model"""
    bl_idname = "d3splint.auto_check_model"
    bl_label = "Auto Check Model"
    bl_options = {'REGISTER', 'UNDO'}
    
    solver = bpy.props.EnumProperty(
        description="Boolean Method",
        items=(("BMESH", "Bmesh", "Faster/More Errors"),
               ("CARVE", "Carve", "Slower/Less Errors")),
        default = "BMESH")
    
    @classmethod
    def poll(cls, context):
        return True
    
    def invoke(self, context, event):
        
        return context.window_manager.invoke_props_dialog(self)
          
    def execute(self, context):
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        
        
        if not splint.finalize_splint:
            self.report({'WARNING'}, 'You have not finalized, I recommend finalizing the splint first and saving your .blend')
            
      
        model = bpy.data.objects.get(splint.model)
        if model == None:
            self.report({'ERROR'}, 'You master model is not in the scene')
            return {'CANCELLED'}
          
        a_base = bpy.data.objects.get('Auto Base')
        if a_base == None:
            self.report({'ERROR'}, 'You need an auto base object, caluculate undercuts to calculate it')
            return {'CANCELLED'}
           
           
        if 'Trim Base' in model.modifiers:
            mod = model.modifiers.get('Trim Base')
            mod.object = a_base
            mod.operation = 'DIFFERENCE'
            mod.solver = self.solver
        else:
            mod = model.modifiers.new('Trim Base', type = 'BOOLEAN')
            mod.object = a_base
            mod.operation = 'DIFFERENCE'
            mod.solver = self.solver  
        
        for ob in context.scene.objects:
            ob.hide = True
            
        model.hide = False
        
        return {'FINISHED'}
    


class D3Splint_OT_model_thicken(bpy.types.Operator):
    """Create Inner Thickness to save  3d printing resin"""
    bl_idname = "d3splint.model_wall_thicken"
    bl_label = "Thicken Model Wall"
    bl_options = {'REGISTER', 'UNDO'}
    
    radius = bpy.props.FloatProperty(default = 2.5, description = 'Thickness Offset', min = 1.0, max = 5.0)
    resolution = bpy.props.FloatProperty(default = .7, description = 'Mesh resolution.  1 coarse, .6 medium to .3 high_res')
    base_at_cursor = bpy.props.BoolProperty(default = True, description = 'Will use 3d cursor to auto plane cut the result')
    
    
    decimate = bpy.props.BoolProperty(default = False, description = 'Will decimate mesh first, faster for dense meshes')
    
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None:
            return True
        else:
            return False
        
    def execute(self, context):
        global_start = time.time()
        start = time.time()
        
        ob = context.object
        mx = ob.matrix_world
        imx = mx.inverted()
        
        ob_bme = bmesh.new()
        ob_bme.from_mesh(ob.data)
        ob_bme.verts.ensure_lookup_table()
        ob_bme.edges.ensure_lookup_table()
        ob_bme.faces.ensure_lookup_table()
        
        
        
        bvh = BVHTree.FromBMesh(ob_bme)
        if self.base_at_cursor:
            start = time.time()
            loc = context.scene.cursor_location
            if bversion() < '002.077.000':
                pt, no, seed, dist = bvh.find(imx * loc)
            else:
                pt, no, seed, dist = bvh.find_nearest(imx * loc)
                        
        
            base_faces = bme_linked_flat_faces(ob_bme, ob_bme.faces[seed], angle = 3)
            base_verts = set()
            for f in base_faces:
                base_verts.update(f.verts)
                
            base_verts = list(base_verts)
            for v in base_verts:
                v.co += 1.5 * self.radius * no
            
            print('took %f seconds to find flat base faces and extrude' % (time.time() - start))
            start = time.time()
        #scaffold
        tmp_me = bpy.data.meshes.new('Tmp Scaffold')
        tmp_ob = bpy.data.objects.new('Tmp Scaffold', tmp_me)
        ob_bme.to_mesh(tmp_me)
        context.scene.objects.link(tmp_ob)
        
        
        print('took %f seconds to initiate temp model' % (time.time() - start))
        start = time.time()
        
        tmp_ob.select = True
        context.scene.objects.active = tmp_ob
        tmp_ob.select = True
        
        #if len(tmp_ob.data.vertices)/100000 > 1.5 and self.decimate:
        #    mod = tmp_ob.modifiers.new('Decimate', type = 'DECIMATE')
        #    mod.ratio = 150000/len(tmp_ob.data.vertices)
        #    bpy.ops.object.modifier_apply(modifier = 'Decimate')
        
        #    print('took %f seconds to decimate temp model' % (time.time() - start))
        #    start = time.time()
        
        
        mod = tmp_ob.modifiers.new('Remesh', type = 'REMESH')
        mod.octree_depth = 6
        mod.mode = 'SMOOTH'
        bpy.ops.object.modifier_apply(modifier = 'Remesh')
        
        print('took %f seconds to remesh temp model' % (time.time() - start))
        start = time.time()
        
        bpy.ops.object.mode_set(mode = 'SCULPT')
        if not tmp_ob.use_dynamic_topology_sculpting:
            bpy.ops.sculpt.dynamic_topology_toggle()
            
        #go to sculpt mode and use detail flood
        context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
        
        
        
        
        if bversion() < '002.079.000':
            context.scene.tool_settings.sculpt.constant_detail = self.resolution * 5
        else:
            context.scene.tool_settings.sculpt.constant_detail_resolution = 1.2/self.resolution
        
        bpy.ops.sculpt.detail_flood_fill()
        
        print('took %f seconds to unify mesh density' % (time.time() - start))
        start = time.time()
        
        
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
        meta_data = bpy.data.metaballs.new('Meta Mesh')
        meta_obj = bpy.data.objects.new('Meta Surface', meta_data)
        meta_data.resolution = self.resolution
        meta_data.render_resolution = self.resolution
        context.scene.objects.link(meta_obj)
        
        R_prime = 1/.901 * (self.radius + .5219)
            
        for v in tmp_ob.data.vertices:
            mb = meta_data.elements.new(type = 'BALL')
            mb.radius = R_prime
            mb.co = v.co
            
        meta_obj.matrix_world = mx
        
    
        context.scene.update()
        
        
        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        new_ob = bpy.data.objects.new('MetaSurfaceMesh', me)
        context.scene.objects.link(new_ob)
        new_ob.matrix_world = mx
        
        print('took %f seconds to do volumetric offset' % (time.time() - start))
        start = time.time()
        
        #clean the outer shell off
        bme = bmesh.new()
        bme.from_object(new_ob, context.scene)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        total_faces = set(bme.faces[:])
        islands = []
        iters = 0
        while len(total_faces) and iters < 100:
            iters += 1
            seed = total_faces.pop()
            island = flood_selection_faces(bme, {}, seed, max_iters = 10000)
            islands += [island]
            total_faces.difference_update(island)
        
        
        
        #TODO, actually ray_cast a sample of each island to determine if it's inside or outside
        #TODO, calculate the bbox size of each island
        islands.sort(key = lambda x: len(x))
        
        if len(islands) != 2:
            print('there are %i islands' % len(islands))
        if len(islands) == 1:
            self.report({'ERROR'}, 'Model too small relative to offset')
            return {'CANCELLED'}
        elif len(islands) > 2:
            self.report({'WARNING'}, 'There may be interior voids that will fill with resin')
            
        bmesh.ops.delete(bme, geom = list(islands[-1]), context = 3)
        del_verts = []
        for v in bme.verts:
            if all([f in islands[-1] for f in v.link_faces]):
                del_verts += [v]        
        bmesh.ops.delete(bme, geom = del_verts, context = 1)    
        
        
        print('took %f seconds to detect and delete outer shell' % (time.time() - start))
        start = time.time()
        
        join_bmesh(bme, ob_bme, src_mx = None, trg_mx = None) #offset created in same space
        
        
        if self.base_at_cursor:
            
            
            gdict = bmesh.ops.bisect_plane(ob_bme, geom = ob_bme.faces[:]+ob_bme.edges[:]+ob_bme.verts[:], 
                               plane_co = pt - .1 * no, 
                               plane_no = no,
                               clear_outer = True)
                               
            cut_geom = gdict['geom_cut']
            ob_bme.edges.ensure_lookup_table()
            ob_bme.verts.ensure_lookup_table()
            
            cap_verts = [ele for ele in cut_geom if isinstance(ele, bmesh.types.BMVert)]
            cap_eds = [ele for ele in cut_geom if isinstance(ele, bmesh.types.BMEdge)]
            
            
            ob_bme.verts.ensure_lookup_table()
            ob_bme.edges.ensure_lookup_table()
            ob_bme.faces.ensure_lookup_table()
            
            loops = edge_loops_from_bmedges(ob_bme, [ed.index for ed in cap_eds])
            
            if len(loops) == 2:
                loop0 = max(loops, key = len)
                loop1 = min(loops, key = len)
                
                loop0.pop()
                loop1.pop()
                
                bv_loop0 = [ob_bme.verts[i] for i in loop0]
                bv_loop1 = [ob_bme.verts[i] for i in loop1]
                
                #get the loops in the same direction
                if clockwise_loop(bv_loop0, Vector((0,0,1))) != clockwise_loop(bv_loop1, Vector((0,0,1))):
                    bv_loop1.reverse()
                
                
                best_v = min(bv_loop1, key = lambda x: (x.co - bv_loop0[0].co).length)
                
                ind = bv_loop1.index(best_v)
                bv_loop1 = bv_loop1[ind:] + bv_loop1[0:ind]
                
                ind_1 = 0
                for i, v0 in enumerate(bv_loop0):
                    
                    v1 = bv_loop1[ind_1]
                    
                    if ind_1 != len(bv_loop1) -1:
                        v11 = bv_loop1[ind_1 + 1]
                    else:
                        v11 = bv_loop1[0]
                   
                    if i != len(bv_loop0) -1: 
                        v01 = bv_loop0[i + 1]
                    else:
                        v01 = bv_loop0[0]
                        
                    if (v11.co - v01.co).length < (v1.co - v01.co).length:
                        
                        f = ob_bme.faces.new([v01, v0, v1, v11])
                        
                        if f.normal.dot(no) < 0:
                            f.normal_flip()
                        if ind_1 < len(bv_loop1) -1:
                            ind_1 += 1
                        
                    else:
                        f = ob_bme.faces.new([v01, v0, v1])
                        if f.normal.dot(no) < 0:
                            f.normal_flip()
                #walk along each loop, bri
                
                
            #bmesh.ops.smooth_vert(ob_bme, verts = cap_verts, factor = 1)
            
            
            #bmesh.ops.bridge_loops(ob_bme, edges = cap_eds)
            print('took %f seconds to plane cut' % (time.time() - start))
            start = time.time()
            '''
            
            plane_me = bpy.data.meshes.new('Base Cut')
            plane_ob = bpy.data.objects.new('Base Cut', plane_me)
            plane_bme = bmesh.new()
            
            Z = no
            X = Vector((1,0,0)) - Vector((1,0,0)).dot(Z) * Z
            X.normalize()
            Y = Z.cross(X)
            
            #rotation matrix from principal axes
            R = Matrix.Identity(3)  #make the columns of matrix U, V, W
            R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
            R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
            R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2]
            
            R = R.to_4x4()
            
            T = Matrix.Translation(pt.dot(Z) * Z)
            
            bmesh.ops.create_grid(plane_bme, x_segments = 1, y_segments = 1, size = 50, matrix = T * R)
            plane_bme.to_mesh(plane_me)
            context.scene.objects.link(plane_ob)
            plane_ob.matrix_world = mx
            '''
            
        ob_bme.to_mesh(ob.data)
          
        context.scene.objects.unlink(meta_obj)
        bpy.data.objects.remove(meta_obj)
        bpy.data.metaballs.remove(meta_data)
        
        
        context.scene.objects.unlink(new_ob)
        bpy.data.objects.remove(new_ob)
        bpy.data.meshes.remove(me)
        
        context.scene.objects.unlink(tmp_ob)
        bpy.data.objects.remove(tmp_ob)
        bpy.data.meshes.remove(tmp_me)
        
        context.scene.objects.active = ob
        
        print('took %f seconds to join offset and to delete temp obs' % (time.time() - start))
        print('took %f seconds for the whole operation' % (time.time() - global_start))  
        return {'FINISHED'}
    
    def invoke(self, context, event):
        
        return context.window_manager.invoke_props_dialog(self)

class D3Splint_OT_model_thicken2(bpy.types.Operator):
    """Create Inner Thickness to save  3d printing resin"""
    bl_idname = "d3splint.model_wall_thicken2"
    bl_label = "Thicken Model Wall2"
    bl_options = {'REGISTER', 'UNDO'}
    
    radius = bpy.props.FloatProperty(default = 2.5, description = 'Thickness Offset', min = 1.0, max = 5.0)
    resolution = bpy.props.FloatProperty(default = .7, description = 'Mesh resolution.  1 coarse, .6 medium to .3 high_res')
    finalize = bpy.props.BoolProperty(default = True, description = 'Will Apply Modifier and delete inner object, uncheck to help diagnose problems')
    
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None:
            return True
        else:
            return False
        
    def execute(self, context):
        global_start = time.time()
        start = time.time()
        
        ob = context.object
        mx = ob.matrix_world
        imx = mx.inverted()
        
        #we will use this bmesh to extend the base, and create a scaffold
        ob_bme = bmesh.new()
        ob_bme.from_mesh(ob.data)
        ob_bme.verts.ensure_lookup_table()
        ob_bme.edges.ensure_lookup_table()
        ob_bme.faces.ensure_lookup_table()
        
        #use this for snapping cursor, later for interatve mode
        bvh = BVHTree.FromBMesh(ob_bme)
        
        start = time.time()
        loc = context.scene.cursor_location
        if bversion() < '002.077.000':
            pt, no, seed, dist = bvh.find(imx * loc)
        else:
            pt, no, seed, dist = bvh.find_nearest(imx * loc)
                    
        if (mx * pt - loc).length > 1:
            self.report({'ERROR'}, 'Need to place 3D cursor on model base and make sure model is selected')
            return {'CANCELLED'}
            
        base_faces = bme_linked_flat_faces(ob_bme, ob_bme.faces[seed], angle = 3)
        base_verts = set()
        for f in base_faces:
            base_verts.update(f.verts)
            
        base_verts = list(base_verts)
        for v in base_verts:
            v.co += 1.5 * self.radius * no
        
        print('took %f seconds to find flat base faces and extrude' % (time.time() - start))
        start = time.time()
        
        #We push the extruded flat base into a temporary object
        tmp_me = bpy.data.meshes.new('Tmp Scaffold')
        tmp_ob = bpy.data.objects.new('Tmp Scaffold', tmp_me)
        tmp_ob.matrix_world = mx
        ob_bme.to_mesh(tmp_me)
        context.scene.objects.link(tmp_ob)
        
        ob_bme.free()
        print('took %f seconds to initiate temp model' % (time.time() - start))
        start = time.time()
        
        tmp_ob.select = True
        context.scene.objects.active = tmp_ob
        tmp_ob.select = True
        
        mod = tmp_ob.modifiers.new('Remesh', type = 'REMESH')
        mod.octree_depth = 6
        mod.mode = 'SMOOTH'
        bpy.ops.object.modifier_apply(modifier = 'Remesh')
        
        print('took %f seconds to remesh temp model' % (time.time() - start))
        #start = time.time()
        
        #bpy.ops.object.mode_set(mode = 'SCULPT')
        #if not tmp_ob.use_dynamic_topology_sculpting:
        #    bpy.ops.sculpt.dynamic_topology_toggle()
            
        #go to sculpt mode and use detail flood
        #context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
        
 
        #if bversion() < '002.079.000':
        #    context.scene.tool_settings.sculpt.constant_detail = self.resolution * 5
        #else:
        #    context.scene.tool_settings.sculpt.constant_detail_resolution = 1.2/self.resolution
        
        #bpy.ops.sculpt.detail_flood_fill()
        
        #print('took %f seconds to unify mesh density' % (time.time() - start))
        #bpy.ops.object.mode_set(mode = 'OBJECT')
        start = time.time()
        
        meta_data = bpy.data.metaballs.new('Meta Mesh')
        meta_obj = bpy.data.objects.new('Meta Surface', meta_data)
        meta_data.resolution = self.resolution
        meta_data.render_resolution = self.resolution
        context.scene.objects.link(meta_obj)
        
        R_prime = 1/.901 * (self.radius + .5219)
            
        for v in tmp_ob.data.vertices:
            mb = meta_data.elements.new(type = 'BALL')
            mb.radius = R_prime
            mb.co = v.co
            
        meta_obj.matrix_world = mx
        context.scene.update()
        
        
        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        new_ob = bpy.data.objects.new('MetaSurfaceMesh', me)
        context.scene.objects.link(new_ob)
        new_ob.matrix_world = mx
        
        print('took %f seconds to do volumetric offset' % (time.time() - start))
        start = time.time()
        
        #clean the outer shell off
        bme = bmesh.new()
        bme.from_object(new_ob, context.scene)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        total_faces = set(bme.faces[:])
        islands = []
        iters = 0
        while len(total_faces) and iters < 100:
            iters += 1
            seed = total_faces.pop()
            island = flood_selection_faces(bme, {}, seed, max_iters = 10000)
            islands += [island]
            total_faces.difference_update(island)
        
        
        
        #TODO, actually ray_cast a sample of each island to determine if it's inside or outside
        #TODO, calculate the bbox size of each island
        islands.sort(key = lambda x: len(x))
        
        if len(islands) != 2:
            print('there are %i islands' % len(islands))
        if len(islands) == 1:
            self.report({'ERROR'}, 'Model too small relative to offset')
            return {'CANCELLED'}
        elif len(islands) > 2:
            self.report({'WARNING'}, 'There may be interior voids that will fill with resin')
            
        bmesh.ops.delete(bme, geom = list(islands[-1]), context = 3)
        del_verts = []
        for v in bme.verts:
            if all([f in islands[-1] for f in v.link_faces]):
                del_verts += [v]        
        bmesh.ops.delete(bme, geom = del_verts, context = 1)    
        
        
        print('took %f seconds to detect and delete outer shell' % (time.time() - start))
        start = time.time()
        
        
        for f in bme.faces:
            f.normal_flip()
            
        bme.to_mesh(new_ob.data)
        bme.free()
        
        new_ob.data.update()
        
        bool_mod = ob.modifiers.new('Boolean', type = 'BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.solver = 'CARVE'
        bool_mod.object = new_ob
        
        context.scene.objects.active = ob
        
        print('Finished the boolean operation in %f seconds' % (time.time() - start)) 
        start = time.time()
        
        if self.finalize:
            bpy.ops.object.modifier_apply(modifier = 'Boolean')
            context.scene.objects.unlink(new_ob)
            bpy.data.objects.remove(new_ob)
            bpy.data.meshes.remove(me)
             
                    
            print('Applied the boolean operation in %f seconds' % (time.time() - start)) 
            start = time.time()
        
        
        context.scene.objects.unlink(meta_obj)
        bpy.data.objects.remove(meta_obj)
        bpy.data.metaballs.remove(meta_data)
        
        
        context.scene.objects.unlink(tmp_ob)
        bpy.data.objects.remove(tmp_ob)
        bpy.data.meshes.remove(tmp_me)

        print('took %f seconds to delete temp obs' % (time.time() - start))
        start = time.time() 
        
        context.scene.update()
        
        print('took %f seconds to update the scene' % (time.time() - start))
        print('took %f seconds for the whole operation' % (time.time() - global_start))  
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        
        return context.window_manager.invoke_props_dialog(self)
 
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "radius")

class VerticaBasePoints(PointPicker): 
    def __init__(self,context,snap_type ='SCENE', snap_object = None):
        
        PointPicker.__init__(self, context, snap_type, snap_object)
        
        self.plane_ob = None
        
        mx = snap_object.matrix_world
        bme = bmesh.new()
        bme.from_mesh(snap_object.data)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        
        
        self.plane_center = Vector((0,0,0))
        
        
        self.bvh = BVHTree.FromBMesh(bme)
        
        #if len(bme.verts) < 10000:
        #    local_sample = [v.co for v in bme.verts]
        #    global_sample = [mx * co for co in local_sample]
        #else:
        #    sample_verts = random.sample(bme.verts[:], 10000)
        #    local_sample = [v.co for v in sample_verts]
        #    global_sample = [mx * co for co in local_sample]
        
        self.bme = bme
        
        #self.local_sample = local_sample
        #self.global_sample = global_sample
        
        
        #self.projected_points = []
        
        #record whether we have calculated the base or not
        self.base_preview = False    
        self.Z_projected = Vector((0,0,1))
        self.theta = 0    
        
    def add_vertical_point(self,context,x,y, label = None):
        
        if len(self.b_pts) != 3:
            return
        
        if not self.click_add_point(context, x, y, label = 'Plane Control'):
            return
        

        region = context.region
        rv3d = context.region_data
        coord = x, y
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        ray_target = ray_origin + (view_vector * 1000)
        view_direction = rv3d.view_rotation * Vector((0,0,-1))
        
        
        view_pt = .5 * (self.b_pts[1] + self.b_pts[2])
        
        #intersect at plane perpendicular to the view
        loc = intersect_line_plane(ray_origin, ray_target,view_pt, view_direction)
        self.plane_center = view_pt
        Z = self.b_pts[3] - view_pt
        Z.normalize()
        
        #bring down the plane point
        #r0 = self.b_pts[0] - self.plane_center
        #r1 = self.b_pts[1] - self.plane_center
        
        #if r0.dot(Z) < r1.dot(Z):
        #    self.plane_center += r0.dot(Z) * Z
        #else:
        #    self.plane_center += r1.dot(Z) * Z
        
        
        #constrain to plane  
        X = self.b_pts[1] - self.b_pts[2]
        L = X.length
        X = X - X.dot(Z) * Z
        X.normalize()
        
        Y = Z.cross(X)
        
        #rotation matrix from principal axes
        R = Matrix.Identity(4)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
        R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
        R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2]
        
        T = Matrix.Translation(self.plane_center)
        
        S = Matrix.Identity(3)
        S[0][0] = .5 * L + 20
        S[1][1] = .5 * L + 20
        
        #create bmesh
        grid_bme = bmesh.new()
        bmesh.ops.create_grid(grid_bme, x_segments = 200, y_segments = 200, size = 1, matrix = S)
        
        
        #new_object
        if 'Distal Cut' not in bpy.data.objects:
            me = bpy.data.meshes.new('Distal Cut')
            ob = bpy.data.objects.new('Distal Cut', me)
            context.scene.objects.link(ob)
        else:
            ob = bpy.data.objects.get('Distal Cut')
            ob.hide = False
        
        grid_bme.to_mesh(ob.data)
        grid_bme.free()
        
        self.plane_ob = ob    
        #link_to_scene
        
        ob.matrix_world = T * R
        #trannslate to center
        
        #R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        #R[0][0], R[0][1], R[0][2]  = Y[0] ,Z[0],  -X[0]
        #R[1][0], R[1][1], R[1][2]  = Y[1], Z[1],  -X[1]
        #R[2][0] ,R[2][1], R[2][2]  = Y[2], Z[2],  -X[2]
        
        #context.space_data.region_3d.view_rotation = R.to_quaternion()
        #context.space_data.region_3d.view_location = .5 * (self.b_pts[1] - self.b_pts[2])
    
    def orient_pane_ob(self):
        
        if self.plane_ob == None: return
        
        Z_base = self.normals[0]
        
        
        #constrain to plane  
        X = self.b_pts[1] - self.b_pts[2]

        Z = self.b_pts[3] - self.plane_center
        
        Z.normalize()
        
        
        theta = math.asin(Z.dot(Z_base))
        print("angle is %f" % (180.0 * theta/math.pi))
        
        Z_projected = Z - Z.dot(Z_base) * Z_base
        Z_projected.normalize()
        
        self.Z_projected = Z_projected
        self.theta = theta
        #enforce X perpendicular to Z
        X = X - X.dot(Z) * Z
        X.normalize()
        
        Y = Z.cross(X)
        
        #rotation matrix from principal axes
        R = Matrix.Identity(4)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
        R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
        R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2]
        
        T = Matrix.Translation(self.plane_center)

        self.plane_ob.matrix_world = T * R
        self.plane_ob.hide = False
        
    def mark_base(self, context, x,y, label = ''):
        
        if len(self.b_pts) != 0: return
        if not self.click_add_point(context, x, y, label = label):
            return
        
        if 'Base Plane' in bpy.data.objects:
            b_plane_ob = bpy.data.objects['Base Plane']
            
        else:
            bpln_bme = bmesh.new()
            bmesh.ops.create_circle(bpln_bme, cap_ends = True, cap_tris = True, segments = 24, diameter = 50)
            b_plane_me = bpy.data.meshes.new('Base Plane')
            b_plane_ob = bpy.data.objects.new('Base Plane', b_plane_me)
            context.scene.objects.link(b_plane_ob)
            bpln_bme.to_mesh(b_plane_me)
            bpln_bme.free()
        b_plane_ob.hide = False
        #constrain to plane  
        X = Vector((random.random(), random.random(), random.random()))
        
        Z = self.normals[0]
        Z.normalize()
        
        #enforce X perpendicular to Z
        X = X - X.dot(Z) * Z
        X.normalize()
        
        Y = Z.cross(X)
        
        #rotation matrix from principal axes
        R = Matrix.Identity(4)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
        R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
        R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2]
        
        T = Matrix.Translation(self.b_pts[0])
        b_plane_ob.matrix_world = T * R
        return True
        
    def orient_vertical_point(self,context,x,y, label = None):
        
        if len(self.b_pts) != 4:
            return
        
        region = context.region
        rv3d = context.region_data
        coord = x, y
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        ray_target = ray_origin + (view_vector * 1000)


        view_direction = rv3d.view_rotation * Vector((0,0,-1))
        view_pt = self.b_pts[3]
        
        #intersect at plane perpendicular to the view
        loc = intersect_line_plane(ray_origin, ray_target,view_pt, view_direction)
        
        #constrain to plane  
        #V = self.b_pts[0] - self.b_pts[1]
        #V.normalize()
        #pt = .5 * (self.b_pts[0] + self.b_pts[1])
        #loc = intersect_line_plane(ray_origin, ray_target,pt, V)
        
        self.b_pts[3]  = loc
        
        
        self.orient_pane_ob()
        
        
    def project_sample(self):
        
        start = time.time()
        
        mx = self.plane_ob.matrix_world
        imx = mx.inverted()
        
        pt = .5 * (self.b_pts[0] + self.b_pts[1])
        Z = self.b_pts[3] - pt
        Z.normalize()
        
        Zlocal = imx.to_3x3() * Z
        
        #local_projected_sample = []
        #start = time.time()
        #for co in self.local_sample:
        #    ok, loc, no, face_ind = self.plane_ob.ray_cast(co, -Zlocal)
        #    if ok:
        #        local_projected_sample += [mx * loc]
            
         
        #print('finished ray cast method in %f seconds' % (time.time() - start))
        #start = time.time()
        
        world_projected_sample = []
        #for co in self.global_sample:
        #    r = co - pt
        #    r_proj = co - r.dot(Z)*Z
        #    world_projected_sample += [r_proj]
        
        
        
        self.projected_points = world_projected_sample
        
        return
    
    def translate_up(self):
        
        pt = self.plane_center
        Z = self.b_pts[3] - pt
        Z.normalize()
        
        self.plane_center += Z
        self.b_pts[3] += Z
        self.orient_pane_ob()
        
    def translate_down(self):
        
        pt = self.plane_center
        Z = self.b_pts[3] - pt
        Z.normalize()
        
        self.plane_center -= Z
        self.b_pts[3] -= Z
        
        self.orient_pane_ob()
        
    def check_scene(self, context, event):
        
        if 'Pad Base' not in bpy.data.objects: return
        if 'Base Plane' not in bpy.data.objects: return
        if 'Distal Cut' not in bpy.data.objects: return
        
        
        pad_ob = bpy.data.objects.get('Pad Base')
        pad_me = pad_ob.data
        pad_me.calc_normals()
        pmx = pad_ob.matrix_world
        ipmx = pmx.inverted()
        p_nomx = ipmx.to_3x3().transposed()
        p_nomx.normalize()
        
        distal_ob = bpy.data.objects.get('Distal Cut')
        distal_me = pad_ob.data
        dmx = distal_ob.matrix_world
        idmx = dmx.inverted()
        d_nomx = idmx.to_3x3().transposed()
        
        mx = distal_ob.matrix_world
        imx = mx.inverted()
        no_mx = imx.to_3x3().transposed()
        
        base_ob = bpy.data.objects.get('Base Plane')
        base_me = pad_ob.data
        bmx = base_ob.matrix_world
        ibmx = bmx.inverted()
        b_nomx = ibmx.to_3x3().transposed()
        
        
        if len(self.b_pts) > 0:
            self.b_pts[0] = base_ob.matrix_world.to_translation()
            self.labels[0] = 'Base Plane'
            self.normals[0] = b_nomx * Vector((0,0,1))
        else:
            self.b_pts.append(base_ob.matrix_world.to_translation())
            self.labels.append('Base Plane')
            self.normals.append(b_nomx * Vector((0,0,1)))
            
        self.plane_center = distal_ob.matrix_world.to_translation()
        
        if len(self.b_pts) > 1:
            self.b_pts[1] = pad_ob.matrix_world * pad_me.vertices[0].co - .5 * p_nomx * pad_me.vertices[0].normal
            self.labels[1] = 'Posterior A'
            self.normals[1] = p_nomx * pad_me.vertices.normal
        else:
            self.b_pts.append(pad_ob.matrix_world * pad_me.vertices[0].co - .5 * p_nomx * pad_me.vertices[0].normal)
            self.labels.append('Posterior A')
            self.normals.append(p_nomx * pad_me.vertices[0].normal)
            
        if len(self.b_pts) > 2:
            self.b_pts[2] = pad_ob.matrix_world * pad_me.vertices[16].co - .5 * p_nomx * pad_me.vertices[0].normal
            self.labels[2] = 'Posterior B'
            self.normals[2] = p_nomx * pad_me.vertices[16].normal
        else:
            self.b_pts.append(pad_ob.matrix_world * pad_me.vertices[16].co - .5 * p_nomx * pad_me.vertices[0].normal)
            self.labels.append('Posterior B')
            self.normals.append(p_nomx * pad_me.vertices[16].normal)
            
        if len(self.b_pts) > 3:
            self.b_pts[3] = self.plane_center + 50 * no_mx * Vector((0,0,1))
            self.labels[3] = 'Plane Control'
            self.normals[3] = no_mx * Vector((0,0,1))
        else:
            self.b_pts.append(self.plane_center + 50 * no_mx * Vector((0,0,1)))
            self.labels.append('Plane Control')
            self.normals.append(no_mx * Vector((0,0,1)))
        self.plane_ob = distal_ob
        
        return
    def make_base(self, context):
        
        
        if 'Meta Base' in bpy.data.objects:
            meta_obj = bpy.data.objects.get('Meta Base')
            meta_data = meta_obj.data
        else:
            meta_data = bpy.data.metaballs.new('Meta Base')
            meta_obj = bpy.data.objects.new('Meta Base', meta_data)
            meta_data.resolution = 1
            meta_data.render_resolution = 1
            context.scene.objects.link(meta_obj)
        
        if 'Pad Base' in bpy.data.objects:
            pad_ob = bpy.data.objects.get('Pad Base')
            pad_me = pad_ob.data
        else:
            pad_me = bpy.data.meshes.new('Pad Base')
            pad_ob = bpy.data.objects.new('Pad Base', pad_me)
            context.scene.objects.link(pad_ob)
        pad_ob.hide = True
        #pad_ob.hide = False
        
        meta_obj.hide = False    
        meta_obj.matrix_world = self.plane_ob.matrix_world
        pad_ob.matrix_world = self.snap_ob.matrix_world
        
        
        base_no = self.normals[0]
        
        mx = self.snap_ob.matrix_world
        imx = mx.inverted()
        
        pmx = self.plane_ob.matrix_world
        ipmx = pmx.inverted()
        
        X = self.plane_ob.dimensions[0]
        Y = self.plane_ob.dimensions[1]
        
        #Plane Normal represented in Model Local coordinates 
        Zp = imx.to_3x3() * pmx.to_3x3() * Vector((0,0,1))
        Zp.normalize()
        
        #Base Normal represented in Model Local Coordinates
        Zb = imx.to_3x3() * base_no
        Zb.normalize()
        
        #Plane normal perpendicular to the base normal in Model Local Coordinates
        Zpb = Zp - Zp.dot(Zb) * Zb
        Zpb.normalize()
        
        #Zbpc is the corrected base normal in Vetical Base Plane Local Coordinates
        Z_base_in_plane = ipmx.to_3x3() * base_no
        Z_base_in_plane.normalize()
        Zbpc = Vector((0,0,1)) - Z_base_in_plane.dot(Vector((0,0,1))) * Z_base_in_plane
        
        #points in the Model local space
        p0 = imx * self.b_pts[1] 
        p1 = imx * self.b_pts[2]
        
        #base_pads
        pad_bme = bmesh.new()
        
        Vy = Vector((random.random(), random.random(), random.random()))
        Vy = Vy - Vy.dot(Zpb) * Zpb
        Vy.normalize()
        Vx = Vy.cross(Zpb)
        
        R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = Vx[0] ,Vy[0],  Zp[0]
        R[1][0], R[1][1], R[1][2]  = Vx[1], Vy[1],  Zp[1]
        R[2][0] ,R[2][1], R[2][2]  = Vx[2], Vy[2],  Zp[2]
        R = R.to_4x4()
        
        T0 = Matrix.Translation(p0 + .5 * Zpb)
        T1 = Matrix.Translation(p1 + .5 * Zpb)
        
        bmesh.ops.create_circle(pad_bme,
                                cap_ends = True,
                                cap_tris = True, 
                                segments = 15,
                                diameter = .45 * (p0-p1).length,
                                matrix = T0 * R)
        
        bmesh.ops.create_circle(pad_bme,
                                cap_ends = True,
                                cap_tris = True, 
                                segments = 15,
                                diameter =  .45 * (p0-p1).length,
                                matrix = T1 * R)
        
        
        pad_bme.verts.ensure_lookup_table()
        pad_bme.edges.ensure_lookup_table()
        pad_bme.faces.ensure_lookup_table()
        
        padBVH = BVHTree.FromBMesh(pad_bme)
        
        pad_bme.to_mesh(pad_me)
        pad_bme.free()
        
        overlap_pairs = self.bvh.overlap(padBVH)
        
        eds = set()
        for i, n in overlap_pairs:
            f = self.bme.faces[i]
            for e in f.edges:
                eds.add(e)
        vertical_locations = []
        pad_locs = []
        #closest_grid_poitns:
        grid_inds = set()
        pad_loc_dict = {}
        for ed in list(eds):
            v = ed.verts[1].co - ed.verts[0].co
            v.normalize()
            r = ed.calc_length()
            loc, no, ind, d = padBVH.ray_cast(ed.verts[0].co, v, r)
            if loc:
                p_loc = ipmx * mx * loc
                
                
                #if p_loc[2] < 0: continue
                
                #now we need to project these Npb cuts onto the vertical base
                p_prime =  intersect_line_plane(p_loc, p_loc - 20 * Zbpc ,Vector((0,0,0)), Vector((0,0,1)))
                if not p_prime:
                    print('no hit')
                    p_prime =  intersect_line_plane(p_loc, p_loc + 20 * Zbpc ,Vector((0,0,0)), Vector((0,0,1)))
                    if not p_prime:
                        print('still no hit')
                        
                i = math.floor(200 * (p_prime[0] + X/2)/X)
                j = math.floor(200 * (p_prime[1] + Y/2)/Y)
                
                if i >= 0 and i < 200 and j >= 0 and j < 200:
                    grid_inds.add(j * 200 + i)
                    grid_inds.add(j * 200 + i + 1)
                    grid_inds.add((j+1) * 200 + i)
                    grid_inds.add((j+1) * 200 + i+1)
                
        
        #now going to fill in the grid where the extrusions
        #scan vertircal using grid inds
        
        def check_set_rows(n_rows, n_columns, reference_set, update_set):
            for i in range(0,n_rows):
                start = None
                end = None
                for j in range(0,n_columns):
                    ind = i * n_columns + j
            
                    if ind in reference_set:
                        if not start:
                            start = ind
                        else:
                            end = ind
            
                if start and end:
                    update_set.update([m for m in range(start, end+1)])
                    
        def check_set_columns(n_rows, n_columns, reference_set, update_set):
            for j in range(0,n_columns):
                
                start = None
                end = None
                row = []
            
                for i in range(0,n_rows):
                    ind = i * n_columns + j
                    
                    if start:
                        row += [ind]
                    if ind in reference_set:
                        if not start:
                            start = ind
                            row.append(ind)
                        else:
                            end = ind            
            
                if start and end:
                    final = row.index(end)
                    update_set.update(row[:final])
                        
        #verts go from bottom left corner, left to right then upward
        extrude_inds = set()
        
        
        check_set_columns(200, 200, grid_inds, extrude_inds)
        check_set_rows(200, 200, extrude_inds, extrude_inds)
        check_set_columns(200, 200, extrude_inds, extrude_inds)
        check_set_rows(200, 200, extrude_inds, extrude_inds)
           
        #project the base grid up to the extrusion pads
        for i in list(extrude_inds):
            self.plane_ob.data.vertices[i].select = True
            co = imx * pmx * self.plane_ob.data.vertices[i].co
            loc, no, ind, d = self.bvh.ray_cast(co, Zpb, 30)
            if d == None: continue
            
            rA = loc - p0
            rB = loc - p1
            D = .45 * (p0 - p1).length
            if rA.length > D and rB.length > D: continue
            
            rAz = rA.dot(Zpb)
            rBz = rB.dot(Zpb)
            
            if rA < rB and rAz > .5: continue
            if rB < rA and rBz > .5: continue
            
            for i in range(4,math.floor(d/.25)):
                vertical_locations += [ipmx * mx * (loc - i * .25 * Zpb)]
            
        
        vertical_locations2 = []
        for v in self.plane_ob.data.vertices:
            co = v.co
            loc, no, ind, d =  self.bvh.find_nearest(imx * pmx * co)
            if loc:
                if d < 3:
                    extrude_inds.add(v.index)
                    
                    loc, no, ind, d = self.bvh.ray_cast(imx * pmx * co, Zp, 4)
                    if d == None: continue
                    for i in range(1,math.floor(d/.25)):
                        vertical_locations2 += [co + i * .25 * Vector((0,0,1))]
                    continue
            
            #only allows 8 mm of extension up to model base    
            loc, no, ind, d = self.bvh.ray_cast(imx * pmx * co, Zp, 6)
            if loc:
                extrude_inds.add(v.index)
                
                for i in range(1,math.floor(d/.25)):
                    vertical_locations2 += [co + i * .25 * Vector((0,0,1))]
                
        
        
        
        check_set_rows(200, 200, extrude_inds, extrude_inds)
        check_set_columns(200, 200, extrude_inds, extrude_inds)
        check_set_rows(200, 200, extrude_inds, extrude_inds)
        check_set_columns(200, 200, extrude_inds, extrude_inds)
        
        
                
        final_inds = list(extrude_inds)
        #Plane projection in WORLD space
        pt = .5 * (self.b_pts[1] + self.b_pts[2])
        Z = self.b_pts[3] - pt
        Z.normalize()
        X = self.b_pts[1] - self.b_pts[2]
        X.normalize()
        Y = Z.cross(X)
        

        base_locations = []
        for ind in final_inds:
            base_locations += [self.plane_ob.data.vertices[ind].co]    
        #Now add metaballs into Metaball coordinate space which
        #is oriented in the same way was the Clipping plane
        
        
        total_locations = base_locations + vertical_locations + pad_locs
        #total_locations = vertical_locations
        
        N = len(meta_data.elements)
        J = len(total_locations)
        
        to_delete = []
        for i in range(0, max([N,J])):
            
            if i <= (J-1) and i <= (N-1):
                mb = meta_data.elements[i]
                mb.co = total_locations[i]
                mb.radius = 2
                
            elif i > (J-1) and i <= (N-1):
                mb = meta_data.elements[i]
                to_delete += [mb]
                
            elif i <= (J-1) and i > (N-1):
                mb = meta_data.elements.new(type = 'BALL')
                mb.radius = 2
                mb.co = total_locations[i]
            else:
                print('Situation Im not prepared for')
        
        for mb in to_delete:
            meta_data.elements.remove(mb)        
        
        self.base_preview = True
        self.plane_ob.hide = True
        
        return
    
    def delete_recent(self):
        
        if len(self.b_pts):
            self.b_pts.pop()
            self.normals.pop()
            self.labels.pop()
                       
    def finish(self, context):
        
        start = time.time()
        interval_start = start
        
        if not self.base_preview:
            print('making base since there is no preview')
            self.make_base(context)
            
        #if 'Meta Base' not in bpy.data.objects: return
        #if 'Distal Cut' not in bpy.data.objects: return
        #if 'Base Plane' not in bpy.data.objects: return
        
        
        distal_cut = bpy.data.objects.get('Distal Cut')
        bplane = bpy.data.objects.get('Base Plane')
                                      
                                      
                                         
        meta_obj = bpy.data.objects.get('Meta Base')
        mx = meta_obj.matrix_world
        imx = mx.inverted()
        
        me = meta_obj.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        me.name = self.snap_ob.name + ':Print Base'
        bme = bmesh.new()
        bme.from_mesh(me)
        
        bplane = bpy.data.objects.get('Base Plane')
        bmx = bplane.matrix_world
        ibmx = bmx.inverted()
        
        pt = bmx.to_translation()
        no = ibmx.to_3x3().transposed() * Vector((0,0,1))
        
        
        local_pt = imx * (pt - .1 * no)
        local_no = imx.to_3x3() * no
        
        gdict = bmesh.ops.bisect_plane(bme, geom = bme.faces[:]+bme.edges[:]+bme.verts[:], 
                               plane_co = local_pt, 
                               plane_no = local_no,
                               clear_outer = True)
        
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        eds_non_man = [ed for ed in bme.edges if len(ed.link_faces)  == 1]
        
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in eds_non_man])
        for l in loops:
            if l[0] != l[-1]: continue
            l.pop()
            bme.faces.new([bme.verts[i] for i in l])
        
        
        print_base = bpy.data.objects.new(self.snap_ob.name + ':Print Base', me)
        bme.to_mesh(me)
        bme.free()
        
        mx = meta_obj.matrix_world
        print_base.matrix_world = mx
        context.scene.objects.link(print_base)
        
        for ob in context.scene.objects:
            ob.hide = True
            
        
        if 'Distal Cut' in self.snap_ob.modifiers:
            dmod = self.snap_ob.modifiers['Distal Cut']
        else:
            dmod = self.snap_ob.modifiers.new('Distal Cut', type = 'BOOLEAN')    
        if 'Vertical Base' in self.snap_ob.modifiers:
            vmod = self.snap_ob.modifiers['Add Base']
        else:
            vmod = self.snap_ob.modifiers.new('Add Base', type = 'BOOLEAN')
            
        dmod.operation = 'DIFFERENCE'
        dmod.solver = 'CARVE'
        vmod.operation = 'UNION'
        
        dmod.object = distal_cut
        vmod.object = print_base
        
        self.snap_ob.hide = False
        
        context.scene.update()
        final_me = self.snap_ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        
        for mod in self.snap_ob.modifiers:
            self.snap_ob.modifiers.remove(mod)
            
        self.snap_ob.data = final_me
        
        #
    def draw_extra(self, context):

        if len(self.b_pts) != 4: return
     
        region = context.region  
        rv3d = context.space_data.region_3d
        
        bgl_utils.draw_polyline_from_coordinates(context, [self.plane_center, self.b_pts[3]], 2, color = (.1,1,.1,1))
        bgl_utils.draw_polyline_from_coordinates(context, [self.b_pts[1], self.b_pts[2]], 2, color = (.1,1,.1,1))
        
        
        vec_p = self.b_pts[3] - self.plane_center
        vec_p.normalize()
        
        vec_base = self.Z_projected
        
        vec_mid = .5 * (vec_base + vec_p)
        vec_mid.normalize()
        
        
        angle_loc = self.plane_center + 10 * vec_mid
        
        angle = str(abs(180 * self.theta / math.pi))[0:4]
        
        vector2d = view3d_utils.location_3d_to_region_2d(region, rv3d, angle_loc)
        blf.position(0, vector2d[0], vector2d[1], 0)
                
        blf.draw(0, angle)
        
        #if len(self.projected_points):
        #    bgl_utils.draw_3d_points(context, self.projected_points, 1, color = (.1, .1, .1, 1))        
        #elif len(self.global_sample):
        #    bgl_utils.draw_3d_points(context, self.global_sample, 1, color = (.1, .1, .1, 1))
        
        return
    
def landmarks_draw_callback(self, context):  
    self.crv.draw(context)
    self.crv.draw_extra(context)
    self.help_box.draw()
    prefs = get_settings()
    r,g,b = prefs.active_region_color
    outline_region(context.region,(r,g,b,1))  
     
    
class D3Tool_OT_model_vertical_base(bpy.types.Operator):
    """Click Landmarks to Add Base on Back Side of Object"""
    bl_idname = "d3tool.model_vertical_base"
    bl_label = "Vertical Print Base"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        if context.object == None: return False
        return True
    
    def modal_nav(self, event):
        events_nav = {'MIDDLEMOUSE', 'WHEELINMOUSE','WHEELOUTMOUSE', 'WHEELUPMOUSE','WHEELDOWNMOUSE'} #TODO, better navigation, another tutorial
        handle_nav = False
        handle_nav |= event.type in events_nav

        if handle_nav: 
            return 'nav'
        return ''
    
    def modal_main(self,context,event):
        # general navigation
        nmode = self.modal_nav(event)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'

        
        if event.type == 'UP_ARROW' and event.value == 'PRESS':
            self.crv.translate_up()
            return 'main'
        
        elif event.type == 'DOWN_ARROW' and event.value == 'PRESS':
            self.crv.translate_down()
            return 'main'
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            
            
            x, y = event.mouse_region_x, event.mouse_region_y
            
            
            if len(self.crv.b_pts) == 0:
                txt = "Base Plane"
                if not self.crv.mark_base(context, x,y, label = txt):
                    return 'main'
                
                
                help_txt = "Left click on posterior heel of model side A"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                return 'main'
            
            
            if len(self.crv.b_pts) == 1:
                txt = "Posterior Side 1"
                
                if not self.crv.click_add_point(context, x,y, label = txt):
                    return 'main'
                
                help_txt = "Left click on back of model on side B"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                return 'main'
        
            elif len(self.crv.b_pts) == 2:
                txt = "Posterior Side 2"
                
                if not self.crv.click_add_point(context, x,y, label = txt):
                    return 'main'
                
                help_txt = "Left Click on vertical part of model near midline"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                
                return 'main'
        
        
            elif len(self.crv.b_pts) == 3:
                txt = "Vertical Orientation"
                self.crv.add_vertical_point(context, x,y, label = txt)
                help_txt = "Change view and click to place vertical orientation \n Use Up and Dn Arrows to translate plane \n Press B to preview the base \n Press enter to finalize"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                self.help_box.fit_box_height_to_text_lines()
                
                return 'main'
        
            else:
                self.crv.orient_vertical_point(context, x,y)
                return 'main'
                    
            return 'main'
        
        if event.type == 'DEL' and event.value == 'PRESS':
            self.crv.delete_recent()
            
            if len(self.crv.b_pts) == 0:
                help_txt = "Left click on the bottom flat portion of the model"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                return 'main'
            
            
            if len(self.crv.b_pts) == 1:

                help_txt = help_txt = "Left click on posterior heel of model side A"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                return 'main'
        
            elif len(self.crv.b_pts) == 2:
                
                help_txt = help_txt = "Left click on posterior heel of model side B"
                
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                
                return 'main'
        
        
            elif len(self.crv.b_pts) == 3:
                help_txt = "Left Click on vertical part of model near midline"
                self.help_box.raw_text = help_txt
                self.help_box.format_and_wrap_text()
                
                return 'main'
            
            return 'main'
            
        if event.type == 'RET' and event.value == 'PRESS':
            if len(self.crv.b_pts) != 4:
                return 'main'
            self.finish(context)
            return 'finish'
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            return 'cancel' 

        elif event.type == 'P' and event.value == 'PRESS':
            self.crv.project_sample()
            
            return 'main'
        
        elif event.type == 'B' and event.value == 'PRESS':
            self.crv.make_base(context)
            
            return 'main'
        
        elif event.type == 'C' and event.value == 'PRESS':
            self.crv.check_scene(context, context.scene)
            return 'main'
        
        return 'main'
    
        
    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #context.space_data.show_manipulator = True
            
            #if nmode == 'finish':
            #   context.space_data.transform_manipulators = {'TRANSLATE', 'ROTATE'}
            #else:
            #    context.space_data.transform_manipulators = {'TRANSLATE'}
            #clean up callbacks
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def invoke(self,context, event):
        
        model = context.object
        
        for ob in context.scene.objects:
            if ob != context.object:
                ob.hide = True
                
        self.crv = VerticaBasePoints(context,snap_type ='OBJECT', snap_object = model)
        
        
        #TODO, tweak the modifier as needed
        help_txt = "Distal Plane Cut and Print Base \n \n First, Left click on a flat part of the model base"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(landmarks_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        return {'RUNNING_MODAL'}

    def finish(self, context):

        self.crv.finish(context)
        

class D3PLINT_OT_base_and_hollow(bpy.types.Operator):
    """Base the models selected and hollow them out """
    bl_idname = "d3splint.simple_base_and_hollow"
    bl_label = "Model Base and Hollow"
    bl_options = {'REGISTER', 'UNDO'}
    
    base_height = bpy.props.FloatProperty(name = 'Base Height', default = 3, min = 0, max = 50,  description = 'Base height added in mm')
    #smooth_zone = bpy.props.FloatProperty(name = 'Smooth Zone', default = .5, min = .2, max = 2.0,  description = 'Width of border smoothing zone in mm')
    smooth_iterations = bpy.props.IntProperty(name = 'Smooth Iterations', default = 10, min = 0, max = 50,  description = 'Iterations to smooth the smoothing zone')
    #reverse = bpy.props.BoolProperty(name = 'Reverse Z direction', default = False, description = 'Use if auto detection detects base direction wrong')
    
    mode_items = {('BEST_FIT','BEST_FIT','BEST_FIT'), ('LOCAL_Z','LOCAL_Z','LOCAL_Z'),('WORLD_Z','WORLD_Z','WORLD_Z')}
    mode = bpy.props.EnumProperty(name = 'Base Mode', items = mode_items, default = 'WORLD_Z')
    
    batch_mode = bpy.props.BoolProperty(name = 'Batch Mode', default = False, description = 'Will do all selected models, may take 1 minute per model, ')
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None and context.object.type == 'MESH':
            return True
        else:
            return False
        
    
        
    def invoke(self,context,event):
        
        return context.window_manager.invoke_props_dialog(self)
        
    
    def execute(self,context):
        
        if self.batch_mode:
            for ob in context.selected_objects:
                if ob.type != 'MESH': continue
                
                self.exe_tool(context, ob)
   
        else:
            self.exe_tool(context, context.object)
            
        return {'FINISHED'}
        
    def exe_tool(self, context, ob):
        
        def clean_geom(bme):
            #make sure there are no node_verts
            #make sure no loose triangles
            
            #first pass, collect all funky edges
            funky_edges = [ed for ed in bme.edges if len(ed.link_faces) != 2]
            
            
            degenerate_eds = [ed for ed in funky_edges if len(ed.link_faces) > 2]
            loose_eds = [ed for ed in funky_edges if len(ed.link_faces) == 0]
            non_man_eds = [ed for ed in funky_edges if len(ed.link_faces) == 1]
            
            if len(degenerate_eds):
                print('found %i degenerate edges' % len(degenerate_eds))
                bmesh.ops.split_edges(bme, edges = degenerate_eds, verts = [])
                
                #now need to run again, and hopefully delete loose triangles
                return -1
                
            if len(loose_eds):
                loose_vs = set()
                for ed in loose_eds:
                    vs = [v for v in ed.verts if len(v.link_faces) == 0]
                    loose_vs.update(vs)
                print('Deleting %i loose edges' % len(loose_eds))    
                bmesh.ops.delete(bme, geom = loose_eds, context = 4)
                bmesh.ops.delete(bme, geom = list(loose_vs), context = 1)
                
                #deleteing loose eds has no effect on existing perimeter edges
                #no need to return
                
            perim_verts = set()
            perim_faces = set()
            for ed in non_man_eds:
                perim_verts.update([ed.verts[0], ed.verts[1]])
                if len(ed.link_faces) == 1:
                    perim_faces.add(ed.link_faces[0])
            
            #first check for loose triangles
            bad_triangles = []
            for f in perim_faces:
                check = [ed for ed in f.edges if ed in non_man_eds]
                if len(check) == 3 or len(check) ==2:
                    bad_triangles.append(f)
            
            if len(bad_triangles):
                bad_verts = set()
                bad_edges = set()
                for f in bad_triangles:
                    del_verts = [v for v in f.verts if len(v.link_faces) == 1]
                    del_edges = [ed for ed in f.edges if len(ed.link_faces) == 1]
                    bad_verts.update(del_verts)
                    bad_edges.update(del_edges)
                bmesh.ops.delete(bme, geom = bad_triangles, context = 3)
                bmesh.ops.delete(bme, geom = list(bad_edges), context = 4)
                bmesh.ops.delete(bme, geom = list(bad_verts), context = 1)
                print('Deleting %i loose and flag/dangling triangles' % len(bad_triangles))
                
                #this affects the perimeter, will need to do another pass
                #could also remove bad_fs from perimeter fs...
                #for now laziness do another pass
                return -1
            
            
            #fill small angle coves
            #initiate the front and calc angles
            angles = {}
            neighbors = {}
            for v in perim_verts:
                ang, va, vb = calc_angle(v)
                angles[v] = ang
                neighbors[v] = (va, vb)    
                 
            
            iters = 0 
            start = time.time()
            N = len(perim_verts)
            new_fs = []
            coved = False
            while len(perim_verts) > 3 and iters < 2 * N:
                iters += 1
                
                v_small = min(perim_verts, key = angles.get)
                smallest_angle = angles[v_small]
                
                va, vb = neighbors[v_small]
                
                vec_a = va.co - v_small.co
                vec_b = vb.co - v_small.co
                vec_ab = va.co - vb.co
                
                
                Ra, Rb = vec_a.length, vec_b.length
                
                R_13 = .67*Ra + .33*Rb
                R_12 = .5*Ra + .5*Rb
                R_23 = .33*Ra + .67*Rb

                vec_a.normalize()
                vec_b.normalize()
                v_13 = vec_a.lerp(vec_b, .33) #todo, verify lerp
                v_12 = vec_a.lerp(vec_b, .5)
                v_23 = vec_a.lerp(vec_b, .67)
                
                v_13.normalize()
                v_12.normalize()
                v_23.normalize()
                
                if smallest_angle < math.pi/180 * 120:
                    try:
                        #f = bme.faces.new((va, v_small, vb))
                        f = bme.faces.new((vb, v_small, va))
                        new_fs += [f]
                        f.normal_update()
                        coved = True
                        
                        #update angles and neighbors
                        ang_a, vaa, vba = calc_angle(va)
                        ang_b, vab, vbb = calc_angle(vb)
                        
                        angles[va] = ang_a
                        angles[vb] = ang_b
                        neighbors[va] = (vaa, vba)
                        neighbors[vb] = (vab, vbb)
                        perim_verts.remove(v_small)
                        
                    except ValueError:
                        print('concavity with face on back side')
                        angles[v_small] = 2*math.pi
            
            
                else:
                    
                    print('finished coving all small angle concavities')
                    print('Coved %i verts' % len(new_fs))
                    for f in new_fs:
                        f.select_set(True)
                    break
            if coved:
                print('Coved returning early')
                return -1
            
                     
            node_verts = []
            end_verts = []
            for v in perim_verts:
                check = [ed for ed in v.link_edges if ed in non_man_eds]
                if len(check) != 2:
                    if len(check) > 2:
                        node_verts.append(v)
                    elif len(check) == 1:
                        print("found an endpoint of an unclosed loop")
                        end_verts.append(v)
            
            
            if len(node_verts):
                for v in node_verts:
                    bmesh_fns.bme_rip_vertex(bme, v)
                
                #ripping changes the perimeter and topology, try again
                print('ripping %i node vertices' % len(node_verts))
                return -1
    
    
        
        start_global = time.time()
        
        
        mx = ob.matrix_world
        imx = mx.inverted()
        
        bme = bmesh.new()
        bme.from_mesh(ob.data)
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        

        start = time.time()
        clean_iterations = 0
        test = -1
        while clean_iterations < 20 and test == -1:
            print('Cleaning iteration %i' % clean_iterations)
            clean_iterations += 1
            test = clean_geom(bme) 
        
        
        print('took %f seconds to clean geometry and edges' % (time.time() - start))
        start = time.time()
        
        #update everything
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        bme.verts.index_update()
        bme.edges.index_update()
        bme.faces.index_update()
        #bme.to_mesh(context.object.data)
        #context.object.data.update()
        #bme.free()
        #return {'FINISHED'}
        
        non_man_eds = [ed for ed in bme.edges if len(ed.link_faces) == 1]        
        
        for f in bme.faces:
            f.select_set(False)
        for ed in non_man_eds:
            ed.select_set(True)
        
        #bme.to_mesh(context.object.data)
        #context.object.data.update()
        #bme.free()
        #return {'FINISHED'}
        
        
        non_man_inds = [ed.index for ed in non_man_eds]
        loops = edge_loops_from_bmedges(bme, non_man_inds)
        
        
        #if loops[0][0] != loops[0][-1]:
        #    print('Not a closed loop!')
        #    print(loops[0][0:20])
        #    print(loops[0][len(loops[0])-20:])
        
        #if len(loops[0]) != len(set(loops[0])):
        #    print('doubles in the loop')
        #    seen = set()
        #    uniq = []
        #    for x in loops[0]:
        #        if x not in seen:
        #            uniq.append(x)
        #            seen.add(x)

        if len(loops)>1:
            biggest_loop = max(loops, key = len)
            self.report({'WARNING'}, 'There are multiple holes in mesh')
            
            for l in loops:
                if l != biggest_loop:
                    print(l)
        else:
            biggest_loop = loops[0]
            
        if biggest_loop[0] != biggest_loop[-1]:
            print('Biggest loop not a hole!')
            bme.free() 
            return {'FINISHED'}
        
        biggest_loop.pop()
        final_eds = [ed for ed in non_man_eds if all([v.index in biggest_loop for v in ed.verts])]
        
        
        print('took %f seconds to identify single perimeter loop' % (time.time() - start))
        start = time.time()
        
        relax_loops_util(bme, final_eds, iterations = 3, influence = .5, override_selection = True, debug = True)
        
        #get the total median point of model
        total_com = Vector((0,0,0))
        for v in bme.verts:
            total_com += v.co
        total_com *= 1/len(bme.verts)
        
        loop_verts = [bme.verts[i] for i in biggest_loop]
        
        locs = [v.co for v in loop_verts]
        com = Vector((0,0,0))
        for v in locs:
            com += v
        com *= 1/len(locs)
            
        if self.mode == 'BEST_FIT':
            
            plane_vector = com - total_com
            no = odcutils.calculate_plane(locs, itermax = 500, debug = False)
            if plane_vector.dot(no) < 0:
                no *= -1
            
            Z = no
            
            print('took %f seconds to calculate best fit plane' % (time.time() - start))
            start = time.time()
        
        elif self.mode == 'WORLD_Z':
            Z = imx.to_3x3() * Vector((0,0,1))
        else:
            Z = Vector((0,0,1))
        
        #Z should point toward the occlusal always
        direction = 0
        for f in bme.faces:
            direction += f.calc_area() * f.normal.dot(Z)
        
        if direction < 0:
            #flip Z            
            Z *= -1
                
    
        print('took %f seconds to identify average face normal' % (time.time() - start))
        start = time.time()
        
        Z.normalize()
        minv = min(loop_verts, key = lambda x: (x.co - com).dot(Z))
        
        print('took %f seconds to identify average smallest vert' % (time.time() - start))
        start = time.time()
          
        #select one extra boundary of verts to smooth
        smooth_verts = set(loop_verts)
        for v in loop_verts:
            neighbors = [ed.other_vert(v) for ed in v.link_edges]
            smooth_verts.update(neighbors)
            
        
        gdict = bmesh.ops.extrude_edge_only(bme, edges = final_eds)
        bme.edges.ensure_lookup_table()
        newer_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
        newer_verts = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
    
        for v in newer_verts:
            v.co += -.1 * Z
            
    
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        relax_loops_util(bme, newer_edges, iterations = 10, influence = .5, override_selection = True, debug = True)
            
            
        gdict = bmesh.ops.extrude_edge_only(bme, edges = newer_edges)
        bme.edges.ensure_lookup_table()
        bme.verts.ensure_lookup_table()
        new_verts = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
        new_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
        
        
        for v in new_verts:
            
            co_flat = v.co +  (minv.co - v.co).dot(Z) * Z
            
            v.co = co_flat - self.base_height * Z
            
        
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in new_edges])  
            
        loops[0].pop()
        f = bme.faces.new([bme.verts[i] for i in loops[0]])
        
        
        #base face should point away from occlusal
        f.normal_update()
        if f.normal.dot(Z) > 0:
            f.normal_flip()
        
        
        bme.to_mesh(ob.data)
        ob.data.update()
        
        if 'Smooth Base' not in ob.vertex_groups:
            sgroup = ob.vertex_groups.new('Smooth Base')
        else:
            sgroup = ob.vertex_groups.get('Smooth Base')
        sgroup.add([v.index for v in smooth_verts], 1, type = 'REPLACE')
        
        if 'Smoooth Base' not in ob.modifiers:
            smod = ob.modifiers.new('Smooth Base', type = 'SMOOTH')
        else:
            smod = ob.modifiers['Smooth Base']
        smod.vertex_group = 'Smooth Base'
        smod.iterations = self.smooth_iterations
        
        bme.free()
        
        print('Took %f seconds to finish entire operator' % (time.time() - start_global))
         
        return
    
def register():
    bpy.utils.register_class(D3SPLINT_OT_paint_model)
    bpy.utils.register_class(D3SPLINT_OT_delete_sculpt_mask)
    bpy.utils.register_class(D3SPLINT_OT_keep_sculpt_mask)
    bpy.utils.register_class(D3SPLINT_OT_delete_islands)
    bpy.utils.register_class(D3SPLINT_OT_mask_to_convex_hull)
    bpy.utils.register_class(D3PLINT_OT_simple_model_base)
    bpy.utils.register_class(D3PLINT_OT_ortho_model_base)
    bpy.utils.register_class(D3PLINT_OT_ortho_model_base_former)
    bpy.utils.register_class(D3SPLINT_OT_close_painted_hole)
    bpy.utils.register_class(D3Splint_OT_model_thicken)
    bpy.utils.register_class(D3Splint_OT_model_thicken2)
    bpy.utils.register_class(D3SPLINT_OT_remove_ragged_edges)
    bpy.utils.register_class(D3Tool_OT_model_vertical_base)
    bpy.utils.register_class(D3Splint_OT_auto_check_model)
    bpy.utils.register_class(D3SPLINT_OT_remesh_decimate)
    #bpy.utils.register_class(D3SPLINT_OT_sculpt_model_undo)
    
def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_paint_model)
    bpy.utils.unregister_class(D3SPLINT_OT_delete_sculpt_mask)
    bpy.utils.unregister_class(D3SPLINT_OT_keep_sculpt_mask)
    bpy.utils.unregister_class(D3SPLINT_OT_delete_islands)
    bpy.utils.unregister_class(D3SPLINT_OT_mask_to_convex_hull)
    bpy.utils.unregister_class(D3PLINT_OT_simple_model_base)
    bpy.utils.unregister_class(D3PLINT_OT_ortho_model_base)
    bpy.utils.unregister_class(D3PLINT_OT_ortho_model_base_former)
    bpy.utils.unregister_class(D3SPLINT_OT_close_painted_hole)
    bpy.utils.unregister_class(D3Splint_OT_model_thicken)
    bpy.utils.unregister_class(D3Splint_OT_model_thicken2)
    bpy.utils.unregister_class(D3SPLINT_OT_remove_ragged_edges)
    bpy.utils.unregister_class(D3Tool_OT_model_vertical_base)
    bpy.utils.unregister_class(D3Splint_OT_auto_check_model)
    bpy.utils.unregister_class(D3SPLINT_OT_remesh_decimate)
    #bpy.utils.unregister_class(D3SPLINT_OT_sculpt_model_undo)
    
if __name__ == "__main__":
    register()