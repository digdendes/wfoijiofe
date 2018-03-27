'''
Created on Oct 8, 2015

@author: Patrick
'''
import time
import math

import bpy
import bmesh
import bgl

from mathutils import Vector, Matrix, Color, kdtree
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_point_line, intersect_line_plane
from bpy_extras import view3d_utils
import numpy as np

from ..bmesh_fns import flood_selection_edge_loop, edge_loops_from_bmedges
from ..cut_algorithms import cross_section_2seeds_ver1, path_between_2_points
from .. import common_drawing
from ..common_utilities import bversion, sort_objects_by_angles, delta_angles

from ...mesh_cut import flood_selection_faces

def bme_rip_vertex_and_offset(bme, bmvert, offset = .01):
    
    fs = [f for f in bmvert.link_faces]
    
    for f in fs:
        vs = [v for v in f.verts]  #these come in order
        new_v = bme.verts.new(bmvert.co)
        
        #find the ripping vert
        ind = vs.index(bmvert)
        #replace it with the new vertex
        vs[ind] = new_v
        
        #create a new face
        new_f = bme.faces.new(vs)
        
        center = new_f.calc_center_median()
        
        delta = center - new_v.co
        delta.normalize()
        new_v.co += offset * delta #perturb the vertext to prevent bad geom
        
        if new_f.normal.dot(f.normal) < 0:
            new_f.normal = -1 * new_f.normal
    bmesh.ops.delete(bme, geom = [bmvert], context = 1)
def relax_bmesh(bme, verts, exclude, iterations = 1, spring_power = .1):
    '''
    takes verts
    '''
    for j in range(0,iterations):
        deltas = dict()
        #edges as springs
        for i, bmv0 in enumerate(verts):
            
            if bmv0.index in exclude: continue
            
            avg_loc = Vector((0,0,0))           
            for ed in bmv0.link_edges:
                avg_loc += ed.other_vert(bmv0).co
            avg_loc *= 1/len(bmv0.link_edges)
                
            deltas[bmv0.index] = spring_power * (avg_loc - bmv0.co)  #todo, normalize this to average spring length?
                  
        for i in deltas:
            bme.verts[i].co += deltas[i]
                       
def collapse_short_edges(bm,boundary_edges, interior_edges,threshold=.5):
    '''
    collapses edges shorter than threshold * average_edge_length
    '''
    ### collapse short edges
    edges_len_average = sum(ed.calc_length() for ed in interior_edges)/len(interior_edges)

    boundary_verts = set()
    for ed in boundary_edges:
        boundary_verts.update([ed.verts[0], ed.verts[1]])
        
    interior_verts = set()
    for ed in interior_edges:
        interior_verts.update([ed.verts[0], ed.verts[1]])
        
    interior_verts.difference_update(boundary_verts)
    bmesh.ops.remove_doubles(bm,verts=list(interior_verts),dist=edges_len_average*threshold)

def average_edge_cuts(bm,edges_boundary, edges_interior, cuts=1):
    ### subdivide long edges
    edges_count = len(edges_boundary)
    shortest_edge = min(edges_boundary, key = lambda x: x.calc_length())
    shortest_l = shortest_edge.calc_length()
    
    edges_len_average = sum(ed.calc_length() for ed in edges_boundary)/edges_count

    spread = edges_len_average/shortest_l
    if spread > 5:
        print('seems to be a large difference in edge lenghts')
        print('going to use 1/2 average edge ength as target instead of min edge')
        target = .5 * edges_len_average
    else:
        target = shortest_l
        
    subdivide_edges = []
    for edge in edges_interior:
        cut_count = int(edge.calc_length()/target)*cuts
        if cut_count < 0:
            cut_count = 0
        if not edge.is_boundary:
            subdivide_edges.append([edge,cut_count])
    for edge in subdivide_edges:
        bmesh.ops.subdivide_edges(bm,edges=[edge[0]],cuts=edge[1]) #perhaps....bisect and triangulate
                       
def triangle_fill_loop(bm, eds):
    geom_dict = bmesh.ops.triangle_fill(bm,edges=eds,use_beauty=True)
    if geom_dict["geom"] == []:
        return False, geom_dict
    else:
        return True, geom_dict

def triangulate(bm,fs):
    new_geom = bmesh.ops.triangulate(bm,faces=fs, ngon_method = 0, quad_method = 1) 
    return new_geom

def smooth_verts(bm, verts_smooth, iters = 10):
    for i in range(iters):
        #bmesh.ops.smooth_vert(bm,verts=smooth_verts,factor=1.0,use_axis_x=True,use_axis_y=True,use_axis_z=True)    
        bmesh.ops.smooth_vert(bm,verts=verts_smooth,factor=1.0,use_axis_x=True,use_axis_y=True,use_axis_z=True)    
   
def clean_verts(bm, interior_faces):
    ### find corrupted faces
    faces = []     
    for face in interior_faces:
        i = 0
        for edge in face.edges:
            if not edge.is_manifold:
                i += 1
        if i == len(face.edges):
            faces.append(face)
    print('deleting %i lonely faces' % len(faces))                 
    bmesh.ops.delete(bm,geom=faces,context=5)

    edges = []
    for face in bm.faces:
        i = 0
        for vert in face.verts:
            if not vert.is_manifold and not vert.is_boundary:
                i+=1
        if i == len(face.verts):
            for edge in face.edges:
                if edge not in edges:
                    edges.append(edge)
    print('collapsing %i loose or otherwise strange edges' % len(edges))
    bmesh.ops.collapse(bm,edges=edges)
            
    verts = []
    for vert in bm.verts:
        if len(vert.link_edges) in [3,4] and not vert.is_boundary:
            verts.append(vert)
            
    print('dissolving %i weird verts after collapsing edges' % len(verts))
    bmesh.ops.dissolve_verts(bm,verts=verts)

def calc_angle(v):
                
    #use link edges and non_man eds
    eds_non_man = [ed for ed in v.link_edges if len(ed.link_faces) == 1]
    if len(eds_non_man) == 0:
        print('this is not a hole perimeter vertex')
        return 2 * math.pi, None, None
    
    if len(eds_non_man) == 1:
        print('This is a loose edge')  
        return  2 * math.pi, None, None
    eds_all = [ed for ed in v.link_edges]
    
    #shift list to start with a non manifold edge if needed
    base_ind = eds_all.index(eds_non_man[0])
    eds_all = eds_all[base_ind:] + eds_all[:base_ind]
    
    #vector representation of edges
    eds_vecs = [ed.other_vert(v).co - v.co for ed in eds_all]
    
    if len(eds_non_man) > 2:
        print("more than 2 non manifold edges, loop self intersects or there is a dangling edge")
        return 2 * math.pi, None, None
    
    va = eds_non_man[0].other_vert(v)
    vb = eds_non_man[1].other_vert(v)
    
    
    
    Va = va.co - v.co
    Vb = vb.co - v.co
    
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
                #print('keep normals consistent reverse')
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
                print("BIG BIG PROBLEMS")
                return angle, vb, va


def triangulate_fill(bme, verts, max_iters, res, smooth_iters = 1):
    '''
    edges need to form a closed loop with no nodes
    '''    
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    new_fs = []
    new_vs = []
    
    #initiate the front and calc angles
    angles = {}
    neighbors = {}
    
    for v in verts:
        ang, va, vb = calc_angle(v)
        angles[v] = ang
        neighbors[v] = (va, vb)
    front = set(verts)   
    iters = 0 
    start = time.time()
    
    while len(front) > 3 and iters < max_iters:
        iters += 1
        
        v_small = min(front, key = angles.get)
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
        
        if smallest_angle < math.pi/180 * 75:
            try:
                #f = bme.faces.new((va, v_small, vb))
                
                f = bme.faces.new((vb, v_small, va))
                new_fs += [f]
                f.normal_update()
                f.select_set(True)
                
            except ValueError:
                print('concavity with face on back side')
                angles[v_small] = 2*math.pi
        
            
        elif smallest_angle < math.pi/180 * 135:
            
            v_new_co = v_small.co + R_12 * v_12
            small_a = (va.co - v_new_co).length < res
            small_b = (vb.co - v_new_co).length < res
            
            if vec_ab.length < res:
                f = bme.faces.new((vb, v_small, va))
                new_fs += [f]
                f.normal_update()
                f.select_set(True)
                
            elif small_a or small_b:
                f = bme.faces.new((vb, v_small, va))
                f.normal_update()
                new_fs += [f]
                f.select_set(True)
            else:
                v_new = bme.verts.new(v_new_co)
                new_vs += [v_new]
                
                f1 = bme.faces.new((v_new, v_small, va))
                f2 = bme.faces.new((vb, v_small, v_new))
                new_fs += [f1, f2]
                f1.normal_update()
                f2.normal_update()

                f1.select_set(True)
                f2.select_set(True)
                
                front.add(v_new)                        
                v_new.normal_update()
                ang, v_na, v_nb = calc_angle(v_new)
                angles[v_new] = ang
                neighbors[v_new] = (v_na, v_nb)
                v_new.select_set(True)
                

        else:
            v_new_co = v_small.co + R_12 * v_12
            v_new_coa = v_small.co + R_13 * v_13
            v_new_cob = v_small.co + R_23 * v_23
            
            
            short_a = (va.co - v_new_coa).length
            short_mid = (v_new_coa - v_new_cob).length
            short_b = (vb.co - v_new_cob).length
            
            if short_a + short_mid + short_b < res:
                f = bme.faces.new((vb, v_small, va))
                f.normal_update()
                new_fs += [f]
                #f.select_set(True)
                
            elif short_a < res or short_b < res or short_mid < res:
                
                v_new = bme.verts.new(v_new_co)
                new_vs += [v_new]
                f1 = bme.faces.new((v_new, v_small, va))
                f2 = bme.faces.new((vb, v_small, v_new))
                
                #f1.select_set(True)
                #f2.select_set(True)
                new_fs += [f1, f2]
                f1.normal_update()
                f2.normal_update()

                front.add(v_new)                        
                v_new.normal_update()
                ang, v_na, v_nb = calc_angle(v_new)
                angles[v_new] = ang
                neighbors[v_new] = (v_na, v_nb)
                v_new.select_set(True)
            
            else:
                v_new_a = bme.verts.new(v_new_coa)
                v_new_b = bme.verts.new(v_new_cob)
                new_vs += [v_new_a, v_new_b]
                f1 = bme.faces.new((v_new_a, v_small, va))
                f2 = bme.faces.new((v_new_b, v_small, v_new_a))
                f3 = bme.faces.new((vb, v_small, v_new_b))
                new_fs += [f1, f2, f3]
                
                f1.normal_update()
                f2.normal_update()
                f3.normal_update()
            
                #f1.select_set(True)
                #f2.select_set(True)
                #f3.select_set(True)
                
                #update the 2 newly created verts
                front.update([v_new_a, v_new_b])
            
                v_new_a.normal_update()
                ang, v_na, v_nb = calc_angle(v_new_a)
                angles[v_new_a] = ang
                neighbors[v_new_a] = (v_na, v_nb)

                v_new_b.normal_update()
                ang, v_na, v_nb = calc_angle(v_new_b)
                angles[v_new_b] = ang
                neighbors[v_new_b] = (v_na, v_nb)

        front.remove(v_small)
        angles.pop(v_small, None)
        neighbors.pop(v_small, None)
    
        va.normal_update()
        ang, v_na, v_nb = calc_angle(va)
        angles[va] = ang
        neighbors[va] = (v_na, v_nb)

    
        vb.normal_update()
        ang, v_na, v_nb = calc_angle(vb)
        angles[vb] = ang
        neighbors[vb] = (v_na, v_nb) 

    print('done at %i iterations' % iters)
    finish = time.time()
    print('Took %f seconds to fill' % (finish-start))
        
    if len(front) <= 3:
        print('hooray, reached the end')
        
        if len(front) == 3:
            face = list(front)
            
            avg_normal = Vector((0,0,0))
            for v in face:
                v.normal_update()
                avg_normal += v.normal
                
            avg_normal *= 1/3
            avg_normal.normalize()
            
            new_f = bme.faces.new(face)
            new_f.select_set(True)
            new_f.normal_update()
            
            if new_f.normal.dot(avg_normal) < 0:
                print('flipping final face normal')
                new_f.normal_flip()
                
            new_fs += [new_f]
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        
        print('smoothing %i new verts' % len(new_vs))
        
        exclude = {}
        start = time.time()
        relax_bmesh(bme, new_vs, exclude, iterations= smooth_iters, spring_power = .2)
        
        finish = time.time()
        print('Took %f seconds to smooth' % (finish-start))
        #for i in range(0, smooth_iters):
        #    bmesh.ops.smooth_vert(bme, verts = new_vs, factor = 1)
        

    #for f in new_fs:
    #    f.select_set(True)
    #for v in new_vs:
    #    v.select_set(True)

def calc_angle_cove(v, cove_verts):
    '''
    Coves are going to have a corner that has 3 non man edges
    
    cove_verts - Dict of verts within the cove (eg the "front")
    '''
                
    #use link edges and non_man eds
    eds_non_man = [ed for ed in v.link_edges if len(ed.link_faces) in {1, 0}]
    
    if len(eds_non_man) == 0:
        print('this is not a hole perimeter vertex')
        return 2 * math.pi, None, None
    
    if len(eds_non_man) == 1:
        print('This is a loose edge')  
        return  2 * math.pi, None, None
    
    if len(eds_non_man) == 3:
        print('this is a cove corner')
        
        
        for ed in eds_non_man:
            if not all([v in cove_verts for v in ed.verts]):
                eds_non_man.remove(ed)
                break
        if len(eds_non_man) == 3:
            print('failed to successfully handle the corner cove vert')
            return  2 * math.pi, None, None
        
    eds_all = [ed for ed in v.link_edges]
    
    #shift list to start with a non manifold edge if needed
    base_ind = eds_all.index(eds_non_man[0])
    eds_all = eds_all[base_ind:] + eds_all[:base_ind]
    
    #vector representation of edges
    eds_vecs = [ed.other_vert(v).co - v.co for ed in eds_all]
    
    if len(eds_non_man) > 2:
        print("more than 2 non manifold edges, loop self intersects or there is a dangling edge")
        return 2 * math.pi, None, None
    
    va = eds_non_man[0].other_vert(v)
    vb = eds_non_man[1].other_vert(v)
    
    
    
    Va = va.co - v.co
    Vb = vb.co - v.co
    
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
                #print('keep normals consistent reverse')
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
                print("BIG BIG PROBLEMS")
                return angle, vb, va

def triangulate_fill_cove(bme, verts, max_iters, res, smooth_iters = 1):
    '''
    verts should form a vert chain in order
    '''    
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    new_fs = []
    new_vs = []
    
    #initiate the front and calc angles
    angles = {}
    neighbors = {}
    
    
    average_normal = Vector((0,0,0))
    for v in verts:
        average_normal += v.normal
        
    average_normal *= 1/len(verts)
    average_normal.normalize()
    
    bridge_verts = []
    bridge_V = verts[-1].co - verts[0].co
    
    steps = math.floor(bridge_V.length/.2)  #todo, calc avg edge length
    res = bridge_V.length/steps
    bridge_V.normalize()
    for i in range(1, steps):
        co = verts[0].co + i * res * bridge_V
        v = bme.verts.new(co)
        v.normal = average_normal
        bridge_verts += [v]
        
    cove_verts = verts + bridge_verts
    
    front = set(cove_verts)    
    for v in verts:
        ang, va, vb = calc_angle_cove(v, front)
        angles[v] = ang
        neighbors[v] = (va, vb)
    front = set(verts)   
    iters = 0 
    start = time.time()
    
    while len(front) > 3 and iters < max_iters:
        iters += 1
        
        v_small = min(front, key = angles.get)
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
        
        if smallest_angle < math.pi/180 * 75:
            try:
                #f = bme.faces.new((va, v_small, vb))
                
                f = bme.faces.new((vb, v_small, va))
                new_fs += [f]
                f.normal_update()
                
            except ValueError:
                print('concavity with face on back side')
                angles[v_small] = 2*math.pi
        
            
        elif smallest_angle < math.pi/180 * 135:
            
            v_new_co = v_small.co + R_12 * v_12
            small_a = (va.co - v_new_co).length < res
            small_b = (vb.co - v_new_co).length < res
            
            if vec_ab.length < res:
                f = bme.faces.new((vb, v_small, va))
                new_fs += [f]
                f.normal_update()

                
            elif small_a or small_b:
                f = bme.faces.new((vb, v_small, va))
                f.normal_update()
                new_fs += [f]

            else:
                v_new = bme.verts.new(v_new_co)
                new_vs += [v_new]
                
                f1 = bme.faces.new((v_new, v_small, va))
                f2 = bme.faces.new((vb, v_small, v_new))
                new_fs += [f1, f2]
                f1.normal_update()
                f2.normal_update()

                
                front.add(v_new)                        
                v_new.normal_update()
                ang, v_na, v_nb = calc_angle_cove(v_new, front)
                angles[v_new] = ang
                neighbors[v_new] = (v_na, v_nb)

                

        else:
            v_new_co = v_small.co + R_12 * v_12
            v_new_coa = v_small.co + R_13 * v_13
            v_new_cob = v_small.co + R_23 * v_23
            
            
            short_a = (va.co - v_new_coa).length
            short_mid = (v_new_coa - v_new_cob).length
            short_b = (vb.co - v_new_cob).length
            
            if short_a + short_mid + short_b < res:
                f = bme.faces.new((vb, v_small, va))
                f.normal_update()
                new_fs += [f]
                #f.select_set(True)
                
            elif short_a < res or short_b < res or short_mid < res:
                
                v_new = bme.verts.new(v_new_co)
                new_vs += [v_new]
                f1 = bme.faces.new((v_new, v_small, va))
                f2 = bme.faces.new((vb, v_small, v_new))
                
                #f1.select_set(True)
                #f2.select_set(True)
                new_fs += [f1, f2]
                f1.normal_update()
                f2.normal_update()

                front.add(v_new)                        
                v_new.normal_update()
                ang, v_na, v_nb = calc_angle_cove(v_new, front)
                angles[v_new] = ang
                neighbors[v_new] = (v_na, v_nb)
                v_new.select_set(True)
            
            else:
                v_new_a = bme.verts.new(v_new_coa)
                v_new_b = bme.verts.new(v_new_cob)
                new_vs += [v_new_a, v_new_b]
                f1 = bme.faces.new((v_new_a, v_small, va))
                f2 = bme.faces.new((v_new_b, v_small, v_new_a))
                f3 = bme.faces.new((vb, v_small, v_new_b))
                new_fs += [f1, f2, f3]
                
                f1.normal_update()
                f2.normal_update()
                f3.normal_update()
            
                #f1.select_set(True)
                #f2.select_set(True)
                #f3.select_set(True)
                
                #update the 2 newly created verts
                front.update([v_new_a, v_new_b])
            
                v_new_a.normal_update()
                ang, v_na, v_nb = calc_angle_cove(v_new_a, front)
                angles[v_new_a] = ang
                neighbors[v_new_a] = (v_na, v_nb)

                v_new_b.normal_update()
                ang, v_na, v_nb = calc_angle(v_new_b, front)
                angles[v_new_b] = ang
                neighbors[v_new_b] = (v_na, v_nb)

        front.remove(v_small)
        angles.pop(v_small, None)
        neighbors.pop(v_small, None)
    
        va.normal_update()
        ang, v_na, v_nb = calc_angle_cove(va, front)
        angles[va] = ang
        neighbors[va] = (v_na, v_nb)

    
        vb.normal_update()
        ang, v_na, v_nb = calc_angle_cove(vb, front)
        angles[vb] = ang
        neighbors[vb] = (v_na, v_nb) 

    print('done at %i iterations' % iters)
    finish = time.time()
    print('Took %f seconds to fill' % (finish-start))
        
    if len(front) <= 3:
        print('hooray, reached the end')
        
        if len(front) == 3:
            face = list(front)
            
            avg_normal = Vector((0,0,0))
            for v in face:
                v.normal_update()
                avg_normal += v.normal
                
            avg_normal *= 1/3
            avg_normal.normalize()
            
            new_f = bme.faces.new(face)
            new_f.select_set(True)
            new_f.normal_update()
            
            if new_f.normal.dot(avg_normal) < 0:
                print('flipping final face normal')
                new_f.normal_flip()
                
            new_fs += [new_f]
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        
        print('smoothing %i new verts' % len(new_vs))
        
        exclude = {}
        start = time.time()
        relax_bmesh(bme, new_vs, exclude, iterations= smooth_iters, spring_power = .2)
        
        finish = time.time()
        print('Took %f seconds to smooth' % (finish-start))


class NodeVert(object):
    def __init__(self,bme, bmvert):
        
        self.bmvert = bmvert
        
    def find_loop(self, bmedge):
        '''
        based on faces at the node, figure out which way to walk
        '''
        return
    
    
    
class MeshHole(object):
    '''
    '''
    
    def __init__(self,bme, bmverts = [], bmedges = [], target_res = 1):
        
        self.bme = bme
        self.bmedges = bmedges
        self.bmverts = bmverts

        self.center = None
        self.normal = None
        self.calc_normal()
        
        
        self.center = Vector((0,0,0))
        self.calc_center()
        
    
    def calc_fit_plane(self):
        return
    
    def get_edge_lengths(self):
        
        lens = [ed.calc_length() for ed in self.bmedges]
        
        avg_len = np.mean(lens)
        min_len = min(lens)
        max_len = max(lens)
        
        
        
        for ed in self.bmedges:
            L = ed.calc_length()
            avg_len += L

        return
    
    def verify_fillable(self):
        return
    
    def remove_problems(self):
        return
    
    def calc_center(self):
        com = Vector((0,0,0))
        for v in self.bmverts:
            com += v.co
            
        com *= 1/len(self.bmverts)
        self.center = com
        return
    
    def calc_normal(self):
        
        avg_normal = Vector((0,0,0))
        n_faces = 0
        for ed in self.bmedges:
            for f in ed.link_faces:
                n_faces += 1
                avg_normal += f.normal
            
        avg_normal = 1/n_faces * avg_normal
        avg_normal.normalize()
        self.normal = avg_normal
        
    def find_nodes(self, itermax = 20):
        
        iters = 0
        for v in self.bmverts:
            n_eds = len([ed for ed in v.link_edges if len(ed.link_faces) == 1])
            if n_eds != 2:
                print('Found a node')
        
        return
    
    def split_node(self, bmv):
        return    
        
    def fill_hole(self):
        
        triangulate_fill(self.bme, self.bmverts, 1000, .3, smooth_iters = 1)
        
        #todo, succes
        #TODO try,except, etc
        return
    
    def draw(self):
        
        #draw the boundary loop
        #draw the n_verts in the center
        
        #draw circle to close it
        return


class MeshIsland(object):
    '''
    '''
    
    def __init__(self,bme, bmfaces = [], bmedges = [], perim_verts = []):
        
        self.bme = bme
        self.bmfaces = bmfaces
        self.bmedges = bmedges
        
        self.normal = Vector((0,0,0))
        self.calc_normal()
        
        verts = set()
        for f in bmfaces:
            verts.update(f.verts[:])
            
        self.bmverts = list(verts)
        self.perim_verts = perim_verts
        
        self.center = Vector((0,0,0))
        self.calc_center()
        
    def bridge_to_hole(self, MeshHole):
        return
        
    def calc_center(self):
        com = Vector((0,0,0))
        for v in self.bmverts:
            com += v.co
            
        com = 1/len(self.bmverts) * com
        self.center = com
        return
    
    def calc_normal(self):
        
        avg_normal = Vector((0,0,0))
        for f in self.bmfaces:
            avg_normal += f.normal
            
        avg_normal = 1/len(self.bmfaces) * avg_normal
        
        self.normal = avg_normal
        
    def delete_island(self):
        bmesh.ops.delete(self.bme, geom = self.bmverts, context = 1)
        self.bme.verts.ensure_lookup_table()
        self.bme.edges.ensure_lookup_table()
        self.bme.faces.ensure_lookup_table()
    
    def draw(self):
        
        #draw the boundary loop
        #draw the n_verts in the center
        
        #draw circle to close it
        return
        
class HoleManager(object):
    '''
    A class which manages user non manifold edges of a mesh and an interactive
    filling proccess as well as mesh cleaning
    '''
    def __init__(self,context, obj):   
        self.ob = obj
        self.bme = bmesh.new()
        self.bme.from_mesh(obj.data)
        self.bme.verts.ensure_lookup_table()
        self.bme.edges.ensure_lookup_table()
        self.bme.faces.ensure_lookup_table()
        
        self.islands = []  #list of MeshIsland
        self.island_sets = []
        self.holes = []
        self.smallest_hole = None
        self.find_holes()
        
        self.hovered = None
        #list of set() of BMFaces
        #self.bvh = BVHTree.FromBMesh(self.bme)
        
    def identify_and_clean_bad_geometry(self):
        
        
        #verts with < 2 edges
        loose_verts = []
        for v in self.bme.verts:
            if len(v.link_edges) < 2:
                loose_verts += [v]
                
        
        print('deleting %i loose verts' % len(loose_verts))
        #clean loose verts   
        bmesh.ops.delete(self.bme, geom = loose_verts, context = 1)
        
        self.bme.verts.ensure_lookup_table()
        self.bme.edges.ensure_lookup_table()
        self.bme.faces.ensure_lookup_table()        
        
        #delete edges without faces by deleting their verts w/o faces
        #edges > 2 faces and #edges with no faces
        
        multi_edges = []
        
                
        to_delete = []
        for ed in self.bme.edges:
            if len(ed.link_faces) == 0:
                for v in ed.verts:
                    if len(v.link_faces) == 0:
                        to_delete.append(v)
     
            elif len(ed.link_faces) > 2:
                multi_edges += [ed]

        to_delete = list(set(to_delete))
        print('deleting %i loose edges' % len(to_delete))
        if len(to_delete):
            bmesh.ops.delete(self.bme, geom = to_delete, context = 1)       
            self.bme.verts.ensure_lookup_table()
            self.bme.edges.ensure_lookup_table()
            self.bme.faces.ensure_lookup_table()
        
        print('deleting %i multi face edges' % len(multi_edges))
        if len(multi_edges) > 0:
            bmesh.ops.delete(self.bme, geom = multi_edges, context = 4)
            self.bme.verts.ensure_lookup_table()
            self.bme.edges.ensure_lookup_table()
            self.bme.faces.ensure_lookup_table()
        
        lonely_faces = []
        for f in self.bme.faces:
            if all(len(ed.link_faces) == 1 for ed in f.edges):
                lonely_faces += [f]
                
        print('there are %i lonely faces' % len(lonely_faces))           
        
        lonely_verts = []
        for f in lonely_faces:
            for v in f.verts:
                if len(v.link_faces) == 1:
                    lonely_verts += [v]
        
        bmesh.ops.delete(self.bme, geom = lonely_faces, context = 3)
        bmesh.ops.delete(self.bme, geom = lonely_verts, context = 1)
        
        #loose parts < 100 faces
        total_faces = set(self.bme.faces[:])
        islands = []
        iters = 0
        while len(total_faces) and iters < 100:
            iters += 1
            seed = total_faces.pop()
            island = flood_selection_faces(self.bme, {}, seed, max_iters = 10000)
            islands += [island]
            total_faces.difference_update(island)
            
        
        islands.sort(key = len)
        continent = max(islands, key = len)
        L = len(continent)
        
        
        to_del_faces = set()
        total_faces = set(self.bme.faces[:])
        
        large_islands = []
        n_delete_islands = 0
        for isl in islands:
            if len(isl) < 200:
                to_del_faces.update(isl)
                print('adding an island with %i faces' % len(isl))
                n_delete_islands += 1
            elif len(isl) < L:
                large_islands += [isl]
        
        #self.bad_geometry['ISLANDS'] = large_islands
        
        print('deleted %i small islands' % n_delete_islands)
        print('there are %i large islands remaining' % len(large_islands))
         
        bmesh.ops.delete(self.bme, geom = list(to_del_faces), context = 3)
        del_verts = []
        for v in self.bme.verts:
            if all([f in to_del_faces for f in v.link_faces]):
                del_verts += [v]        
        
        bmesh.ops.delete(self.bme, geom = del_verts, context = 1)
        
        del_edges = []
        for ed in self.bme.edges:
            if len(ed.link_faces) == 0:
                del_edges += [ed]
        bmesh.ops.delete(self.bme, geom = del_edges, context = 4) 
        

        self.island_sets = large_islands
        self.bme.verts.ensure_lookup_table()
        self.bme.edges.ensure_lookup_table()
        self.bme.faces.ensure_lookup_table()        
        
    def find_holes(self):
        
        #first, make a big cleanup pass
        self.identify_and_clean_bad_geometry()
        
        self.holes = []
        eds_one_face = [ed for ed in self.bme.edges if len(ed.link_faces) == 1]
        
        verts = set()
        for ed in eds_one_face:
            verts.update([ed.verts[0], ed.verts[1]])
        
        #find  nodes
        nodes = []
        for v in verts:
            n_eds = len([ed for ed in v.link_edges if ed in eds_one_face])
            if n_eds != 2:
                nodes += [v]
        
        if len(nodes):
            print('found %i node verts' % len(nodes))        
            for v in nodes:
                bme_rip_vertex_and_offset(self.bme, v, offset = .01)
                
            self.bme.verts.ensure_lookup_table()
            self.bme.edges.ensure_lookup_table()
            self.bme.faces.ensure_lookup_table()
            
            #make another cleannup pass
            self.identify_and_clean_bad_geometry()
            
            eds_one_face = [ed for ed in self.bme.edges if len(ed.link_faces) == 1]
        

            
        non_man_ed_loops = edge_loops_from_bmedges(self.bme, [ed.index for ed in eds_one_face], ret = {'VERTS','EDGES'})
        
        for vs, eds in zip(non_man_ed_loops['VERTS'], non_man_ed_loops['EDGES']):
            
            if vs[0] != vs[-1]: 
                print('not a closed loop')
                continue

            
            bmeds = [self.bme.edges[i] for i in eds]
            bmvs = [self.bme.verts[i] for i in vs]
            
            test_f = bmeds[0].link_faces[0]
            island_test = False
            island_set = None
            for i, isl in enumerate(self.island_sets):
                if test_f in isl:
                    island_test = True
                    island_set = isl
            
            if not island_test:
                if len(bmeds) < 2000:
                    self.holes += [MeshHole(self.bme, bmverts = bmvs, bmedges = bmeds)]
            else:
                new_island = MeshIsland(self.bme, bmfaces=list(island_set), bmedges=bmeds, perim_verts=bmvs)
                if not new_island:continue
                self.islands += [new_island]
                
                
        print('there are %i holes!' % len(self.holes))
        
        self.bme.to_mesh(self.ob.data)
        self.ob.data.update()
    
    
    def snap_smallest_hole(self, context):
        if len(self.holes) == 0: return
        
        smallest_hole = min(self.holes, key = lambda x: len(x.bmverts))
        
        self.snap_view_to_element(smallest_hole, context)
        
    def fill_smallest_hole(self):
        
        if len(self.holes) == 0: return
        
        smallest_hole = min(self.holes, key = lambda x: len(x.bmverts))
        smallest_hole.fill_hole()
        self.holes.remove(smallest_hole)
        
        self.bme.to_mesh(self.ob.data)
        self.ob.data.update()
        
        if len(self.holes) == 0:
            self.smallest_hole = None
            return
        else:
            self.smallest_hole = min(self.holes, key = lambda x: len(x.bmverts))
        
          
    def ray_cast_holes(self, context,x,y):
        
        return
    
    def snap_view_to_element(self,element, context):
        
        mx = self.ob.matrix_world
        
        mx_no = mx.inverted().transposed().to_3x3()
        
        center = mx * element.center
        Z = mx_no * element.normal
        Z.normalize()
        
        x= center - mx * element.bmverts[0].co
        
        X = x - x.dot(Z) * Z
        X.normalize()
        
        Y = Z.cross(X)
        
        Rmx = Matrix.Identity(3)
        Rmx[0][0], Rmx[0][1], Rmx[0][2]  = X[0] ,Y[0],  Z[0]
        Rmx[1][0], Rmx[1][1], Rmx[1][2]  = X[1], Y[1],  Z[1]
        Rmx[2][0] ,Rmx[2][1], Rmx[2][2]  = X[2], Y[2],  Z[2]
        
        quat = Rmx.to_quaternion()
        
        v3d = context.space_data
        rv3d = v3d.region_3d
        rv3d.view_rotation = quat
        rv3d.view_location = center
        rv3d.view_distance = 15
        
        rv3d.update()
        context.scene.cursor_location = center
        
               
    def click_add_point(self,context,x,y):
        '''
        x,y = event.mouse_region_x, event.mouse_region_y
        
        this will add a point into the bezier curve or
        close the curve into a cyclic curve
        '''
        region = context.region
        rv3d = context.region_data
        coord = x, y
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        ray_target = ray_origin + (view_vector * 1000)
        mx = self.cut_ob.matrix_world
        imx = mx.inverted()
    
        if bversion() < '002.077.000':
            loc, no, face_ind = self.cut_ob.ray_cast(imx * ray_origin, imx * ray_target)
            if face_ind == -1: 
                self.selected = -1
                return
        else:
            res, loc, no, face_ind = self.cut_ob.ray_cast(imx * ray_origin, imx * ray_target - imx * ray_origin)
        
            if not res:
                self.selected = -1
                return
            
        if self.hovered[0] and 'NON_MAN' in self.hovered[0]:
            
            if self.cyclic:
                self.selected = -1
                return
            
            ed, wrld_loc = self.hovered[1]
            
            if len(self.pts) == 0:
                self.start_edge = ed
            elif len(self.pts) and not self.start_edge:
                self.selected = -1
                return
            
            elif len(self.pts) and self.start_edge:
                self.end_edge = ed
                
            self.pts += [wrld_loc] 
            self.cut_pts += [imx * wrld_loc]
            #self.cut_pts += [loc]
            self.face_map += [ed.link_faces[0].index]
            self.normals += [view_vector]
            self.selected = len(self.pts) -1
        
        if self.hovered[0] == None and not self.end_edge:  #adding in a new point at end
            self.pts += [mx * loc]
            self.cut_pts += [loc]
            #self.normals += [no]
            self.normals += [view_vector] #try this, because fase normals are difficult
            self.face_map += [face_ind]
            self.selected = len(self.pts) -1
                
        if self.hovered[0] == 'POINT':
            self.selected = self.hovered[1]
            if self.hovered[1] == 0 and not self.start_edge:  #clicked on first bpt, close loop
                #can not  toggle cyclic any more, once it's on it remains on
                if self.cyclic:
                    return
                else:
                    self.cyclic = True
            return
         
        elif self.hovered[0] == 'EDGE':  #cut in a new point
            self.pts.insert(self.hovered[1]+1, mx * loc)
            self.cut_pts.insert(self.hovered[1]+1, loc)
            self.normals.insert(self.hovered[1]+1, view_vector)
            self.face_map.insert(self.hovered[1]+1, face_ind)
            self.selected = self.hovered[1] + 1
            
            if len(self.new_cos):
                self.make_cut()
            return
    
    def click_delete_point(self, mode = 'mouse'):
        if mode == 'mouse':
            if self.hovered[0] != 'POINT': return
            
            self.pts.pop(self.hovered[1])
            self.cut_pts.pop(self.hovered[1])
            self.normals.pop(self.hovered[1])
            self.face_map.pop(self.hovered[1])
            print('')
            print('DELETE POINT')
            print(self.hovered)
            print('')
            
            if self.end_edge != None and self.hovered[1] == len(self.cut_pts): #notice not -1 because we popped 
                print('deteted last non man edge')
                self.end_edge = None
                self.new_cos = []
                self.selected = -1
                
                return
              
        
        else:
            if self.selected == -1: return
            self.pts.pop(self.selected)
            self.cut_pts.pop(self.selected)
            self.normals.pop(self.selected)
            self.face_map.pop(self.selected)
            
        if len(self.new_cos):
            self.make_cut()
 
    def hover_non_man(self,context,x,y):
        return 
        region = context.region
        rv3d = context.region_data
        coord = x, y
        self.mouse = Vector((x, y))
        
        loc3d_reg2D = view3d_utils.location_3d_to_region_2d
        
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        ray_target = ray_origin + (view_vector * 1000)
        mx = self.cut_ob.matrix_world
        imx = mx.inverted()
        if bversion() < '002.077.000':
            loc, no, face_ind = self.cut_ob.ray_cast(imx * ray_origin, imx * ray_target)
            
        else:
            res, loc, no, face_ind = self.cut_ob.ray_cast(imx * ray_origin, imx * ray_target - imx * ray_origin)
        
        if len(self.non_man_points):
            co3d, index, dist = self.kd.find(mx * loc)

            #get the actual non man vert from original list
            close_bmvert = self.bme.verts[self.non_man_bmverts[index]] #stupid mapping, unreadable, terrible, fix this, because can't keep a list of actual bmverts
            close_eds = [ed for ed in close_bmvert.link_edges if not ed.is_manifold]
            if len(close_eds) == 2:
                bm0 = close_eds[0].other_vert(close_bmvert)
                bm1 = close_eds[1].other_vert(close_bmvert)
            
                a0 = bm0.co
                b   = close_bmvert.co
                a1  = bm1.co 
                
                inter_0, d0 = intersect_point_line(loc, a0, b)
                inter_1, d1 = intersect_point_line(loc, a1, b)
                
                screen_0 = loc3d_reg2D(region, rv3d, mx * inter_0)
                screen_1 = loc3d_reg2D(region, rv3d, mx * inter_1)
                screen_v = loc3d_reg2D(region, rv3d, mx * b)
                
                if not screen_0 and screen_1 and screen_v:
                    return
                screen_d0 = (self.mouse - screen_0).length
                screen_d1 = (self.mouse - screen_1).length
                screen_dv = (self.mouse - screen_v).length
                
                if 0 < d0 <= 1 and screen_d0 < 20:
                    self.hovered = ['NON_MAN_ED', (close_eds[0], mx*inter_0)]
                    return
                elif 0 < d1 <= 1 and screen_d1 < 20:
                    self.hovered = ['NON_MAN_ED', (close_eds[1], mx*inter_1)]
                    return
                elif screen_dv < 20:
                    if abs(d0) < abs(d1):
                        self.hovered = ['NON_MAN_VERT', (close_eds[0], mx*b)]
                        return
                    else:
                        self.hovered = ['NON_MAN_VERT', (close_eds[1], mx*b)]
                        return
                    
    def hover(self,context,x,y):
        '''
        hovering happens in mixed 3d and screen space, 20 pixels thresh for points, 30 for edges
        40 for non_man
        '''
        if len(self.holes) == 0 and len(self.islands) == 0:
            self.hovered = None
            return
        
        region = context.region
        rv3d = context.region_data
        coord = x, y
        self.mouse = Vector((x, y))
        
        loc3d_reg2D = view3d_utils.location_3d_to_region_2d
        
        
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        ray_target = ray_origin + (view_vector * 1000)
        mx = self.ob.matrix_world
        imx = mx.inverted()
        #loc, no, face_ind = self.cut_ob.ray_cast(imx * ray_origin, imx * ray_target)
        ''' '''
        
        
        def dist(element):
            
            v3 = mx * element.center
            v = loc3d_reg2D(region, rv3d, v3)
            if v == None:
                return 100000000
            diff = v - Vector((x,y))
            return diff.length

        closest_2d_element = min(self.holes + self.islands, key = dist)
        
        screen_dist = dist(closest_2d_element)
        if screen_dist < 20:
            self.hovered = closest_2d_element
            return
        
        if bversion() < '002.077.000':
            loc, no, face_ind = self.ob.ray_cast(imx * ray_origin, imx * ray_target)
            if face_ind == -1: 
                #do some shit
                self.hovered = None
                return None
        else:
            res, loc, no, face_ind = self.ob.ray_cast(imx * ray_origin, imx * ray_target - imx * ray_origin)
            if not res:
                self.hovered = None
                return None
            
        def dist3d(element):
            
            v3 = element.center
            if v3 == None:
                return 100000000
            delt = v3 -  loc
            return delt.length
            
        closest_3d_element = min(self.holes + self.islands, key = dist3d)
        
        
        screen_dist_3d = dist(closest_3d_element)
        
        if screen_dist_3d  < 20:
            self.hovered = closest_3d_element
            return

    def process_hovered_element(self):
        if self.hovered == None: return
        
        if isinstance(self.hovered, MeshHole):
            
            self.hovered.fill_hole()
            self.holes.remove(self.hovered)
        
            self.bme.to_mesh(self.ob.data)
            self.ob.data.update()
        
            self.hovered = None
        elif isinstance(self.hovered, MeshIsland):
            
            self.hovered.delete_island()
            self.islands.remove(self.hovered)
            self.hovered = None
            self.bme.to_mesh(self.ob.data)
            self.ob.data.update()
        
                         
    def draw(self,context):
        pass


    def draw3d(self,context):
        #ADAPTED FROM POLYSTRIPS John Denning @CGCookie and Taylor University
        #if len(self.pts) == 0: return
        
        region,r3d = context.region,context.space_data.region_3d
        view_dir = r3d.view_rotation * Vector((0,0,-1))
        view_loc = r3d.view_location - view_dir * r3d.view_distance
        if r3d.view_perspective == 'ORTHO': view_loc -= view_dir * 1000.0
        
        bgl.glEnable(bgl.GL_POINT_SMOOTH)
        bgl.glDepthRange(0.0, 1.0)
        bgl.glEnable(bgl.GL_DEPTH_TEST)
        
        
        
        def set_depthrange(near=0.0, far=1.0, points=None):
            if points and len(points) and view_loc:
                d2 = min((view_loc-p).length_squared for p in points)
                d = math.sqrt(d2)
                d2 /= 10.0
                near = near / d2
                far = 1.0 - ((1.0 - far) / d2)
            if r3d.view_perspective == 'ORTHO':
                far *= 0.9999
            near = max(0.0, min(1.0, near))
            far = max(near, min(1.0, far))
            bgl.glDepthRange(near, far)
            #bgl.glDepthRange(0.0, 0.5)
            
        def draw3d_points(context, points, color, size):
            #if type(points) is types.GeneratorType:
            #    points = list(points)
            if len(points) == 0: return
            bgl.glColor4f(*color)
            bgl.glPointSize(size)
            set_depthrange(0.0, 0.997, points)
            bgl.glBegin(bgl.GL_POINTS)
            for coord in points: bgl.glVertex3f(*coord)
            bgl.glEnd()
            bgl.glPointSize(1.0)
            

        def draw3d_polyline(context, points, color, thickness, LINE_TYPE, zfar=0.997):
            
            if len(points) == 0: return
            # if type(points) is types.GeneratorType:
            #     points = list(points)
            if LINE_TYPE == "GL_LINE_STIPPLE":
                bgl.glLineStipple(4, 0x5555)  #play with this later
                bgl.glEnable(bgl.GL_LINE_STIPPLE)  
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glColor4f(*color)
            bgl.glLineWidth(thickness)
            set_depthrange(0.0, zfar, points)
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for coord in points: bgl.glVertex3f(*coord)
            bgl.glEnd()
            bgl.glLineWidth(1)
            if LINE_TYPE == "GL_LINE_STIPPLE":
                bgl.glDisable(bgl.GL_LINE_STIPPLE)
                bgl.glEnable(bgl.GL_BLEND)  # back to uninterrupted lines
                
        bgl.glLineWidth(1)
        bgl.glDepthRange(0.0, 1.0)
        
        if len(self.holes):
            
            color = (.1, .9, .1, 1)
            draw3d_points(context, [self.ob.matrix_world * ele.center for ele in self.holes], color, 8) 
            for hole in self.holes:
                color = (.2,.5,.2,1)
                
                if hole == self.hovered:
                    color = (.8, .8, .1, 1)
                    
                draw3d_polyline(context,[self.ob.matrix_world * v.co for v in hole.bmverts], color, 5, 'GL_LINE_STRIP')
            
        if len(self.islands):
            color = (.1, .9, .1, 1)
            draw3d_points(context, [self.ob.matrix_world * ele.center for ele in self.islands], color, 8)
            for isl in self.islands:
                color = (.8, .2, .2, 1)
                if isl == self.hovered:
                    color = (.8, .8, .1, 1)
                draw3d_polyline(context,[self.ob.matrix_world * v.co for v in isl.perim_verts], color, 5, 'GL_LINE_STRIP')
            
                  
        bgl.glLineWidth(1)
        bgl.glDepthRange(0.0, 1.0)
        
        
        
        

        
    
        
        
        
        