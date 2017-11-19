import bpy
import bmesh
import time

from mathutils import Vector, Matrix



def silouette_brute_force(context, ob, view, world = True, smooth = True, debug = False):
    '''
    args:
      ob - mesh object
      view - Mathutils Vector
      
    return:
       new mesh of type Mesh (not BMesh)
    '''
    if debug:
        start = time.time()
        
    #careful, this can get expensive with multires    
    bme = bmesh.new()
    bme.from_object(ob, context.scene)
    bme.normal_update()
    
    #keep track of the world matrix
    mx = ob.matrix_world
    
    if world:
        #meaning the vector is in world coords
        #we need to take it back into local
        i_mx = mx.inverted()
        view = i_mx.to_quaternion() * view
    
    if debug:
        face_time = time.time()
        print("took %f to initialze the bmesh" % (face_time - start))
        
    face_directions = [[0]] * len(bme.faces)
    
    for f in bme.faces:
        if debug > 1:
            print(f.normal)
        
        face_directions[f.index] = f.normal.dot(view)
    
    
    if debug:
        edge_time = time.time()
        print("%f seconds to test the faces" % (edge_time - face_time))
        
        if debug > 2:
            print(face_directions)
            
    delete_edges = []
    keep_verts = set()
    
    for ed in bme.edges:
        if len(ed.link_faces) == 2:
            silhouette = face_directions[ed.link_faces[0].index] * face_directions[ed.link_faces[1].index]
            if silhouette < 0:
                keep_verts.add(ed.verts[0])
                keep_verts.add(ed.verts[1])
            else:
                delete_edges.append(ed)
    if debug > 1:
        print("%i edges to be delted" % len(delete_edges))
        print("%i verts to be deleted" % (len(bme.verts) - len(keep_verts)))
    if debug:
        delete_time = time.time()
        print("%f seconds to test the edges" % (delete_time - edge_time))
        
    delete_verts = set(bme.verts) - keep_verts
    delete_verts = list(delete_verts)
    
    
    #https://svn.blender.org/svnroot/bf-blender/trunk/blender/source/blender/bmesh/intern/bmesh_operator_api.h
    bmesh.ops.delete(bme, geom = bme.faces, context = 3)
    bmesh.ops.delete(bme, geom = delete_verts, context = 1)
    #bmesh.ops.delete(bme, geom = delete_edges, context = 2)  #presuming the delte enum is 0 = verts, 1 = edges, 2 = faces?  who knows.
    
    
    return bme