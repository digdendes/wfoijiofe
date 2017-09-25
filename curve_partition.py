'''
Created on Mar 25, 2017

@author: Patrick
'''
import bpy
import bmesh
from mathutils.kdtree import KDTree
from mathutils import Vector
from mesh_cut import edge_loops_from_bmedges, space_evenly_on_path
import math




class opendental_ot_PartitionCurve(bpy.types.Operator):
    """Convert to mesh and partition irregular 3d curve boundaries"""
    bl_idname = "object.curve_partition"
    bl_label = "Partition and Fill Curve"
    bl_options = {'REGISTER','UNDO'}

    n_partitions = bpy.props.IntProperty(default = 15)
    max_edge = bpy.props.FloatProperty(default = 15)
    
    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        C = context

        me = C.object.to_mesh(C.scene, apply_modifiers = True, settings = 'PREVIEW')
        
        bme = bmesh.new()
        bme.from_mesh(me)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        
        #verts in order
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in bme.edges])
        if len(loops) > 1:
            print('need a single loop')    

        loop = loops[0]
        loop.pop()  #cyclic
        #don't need that one any more
        
        coords = [bme.verts[i].co for i in loop]
        spaced_verts, spaced_eds = space_evenly_on_path(coords, [(0,1),(1,0)], 300)
        bme.free()
        print(len(spaced_verts))
        
        #build our search tree
        kd = KDTree(len(spaced_verts))
        for i,v in enumerate(spaced_verts):
            kd.insert(v,i)
        kd.balance()
        
        bme2 = bmesh.new()
        bme2.verts.ensure_lookup_table()
        bme2.edges.ensure_lookup_table()
        
        for v in spaced_verts:
            bme2.verts.new(v)
        bme2.verts.ensure_lookup_table()
        bme2.edges.ensure_lookup_table()
        
        for ed in spaced_eds:
            v0, v1 = ed
            bme2.edges.new((bme2.verts[v0],bme2.verts[v1]))
            
            
        bme2.verts.index_update()
        bme2.verts.ensure_lookup_table()
        bme2.edges.index_update()
        bme2.edges.ensure_lookup_table()
        
        loops = edge_loops_from_bmedges(bme2, [ed.index for ed in bme2.edges])
        loop = loops[0]
        loop.pop()
        
        
        def euc_dist(v1, v2):
            
            return (v1.co - v2.co).length
            
        
        def split_loop(vert_loop_inds):
            best_pairs = {}

                
            def geo_dist(v1,v2):
                N = len(vert_loop_inds)
                n = vert_loop_inds.index(v1.index)
                m = vert_loop_inds.index(v2.index)

                return min(math.fmod(N + m - n,N),math.fmod(N + n - m,N))
                

            for i in vert_loop_inds:
                v1 = bme2.verts[i]
                pfactor = 0
                match = None
                link_verts = [ed.other_vert(v1) for ed in v1.link_edges]
                
                for loc, ind, dist in kd.find_range(v1.co, self.max_edge):
                    
                    if ind == i: continue #prevent divide by 0
                    if ind not in vert_loop_inds: continue #filter by this loop
                    v2 = bme2.verts[ind]
                    
                    if v2 in link_verts: continue  #prevent neighbors    
                    
                    fac = geo_dist(v1,v2)/euc_dist(v1,v2)
                    
                    if fac > pfactor: #if a better match is found, keep it
                        pfactor = fac
                        match = v2
                        
                best_pairs[v1] = (match, pfactor)
            
         
            vs = [bme2.verts[i] for i in vert_loop_inds]
            v1 = max(vs, key = lambda x: best_pairs[x][1])
        
            #connect the best pair
            v2, pfactor = best_pairs[v1]
        
            try:
                #split the index loop into 2
                ind1 = min(vert_loop_inds.index(v1.index), vert_loop_inds.index(v2.index))
                ind2 = max(vert_loop_inds.index(v1.index), vert_loop_inds.index(v2.index))
                
                print('splitting loop at ind1: %i and ind2: %i' % (ind1, ind2))
                print('creating edge between vert: %i and vert: %i' % (v1.index, v2.index))
                loop0 = vert_loop_inds[ind1:ind2+1]
                loop1 = vert_loop_inds[0:ind1+1] + vert_loop_inds[ind2:]
                
                print(vert_loop_inds)
                print('\n')
                print(loop0)
                print('\n')
                print(loop1)
                
                bme2.edges.new((v1, v2))
                bme2.verts.ensure_lookup_table()
                bme2.edges.ensure_lookup_table()
                
                return loop0, loop1
            except:
                print('cant add edge between vert: %i and vert: %i' % (v1.index, v2.index))
                return vert_loop_inds, []
        
        loops = [loop]
        for n in range(0,self.n_partitions):
            
            print('\n')
            print('PARTITION # %i' % (n+1))
            biggest_loop = max(loops, key = len)
            
            if len(biggest_loop) < 20:
                break
            loop1, loop2 = split_loop(biggest_loop)
            
            if loop2 != []:
                loops.remove(biggest_loop)
                loops += [loop1, loop2]
            else:
                break
        
        new_faces = []
        bme2.faces.ensure_lookup_table()
         
        for loop in loops:
            new_faces.append(bme2.faces.new([bme2.verts[i] for i in loop]))
            
        bme2.faces.ensure_lookup_table()
        bmesh.ops.triangulate(bme2, faces = new_faces)    
                
        new_ob = bpy.data.objects.new('Partitioned', me)
        C.scene.objects.link(new_ob)
        bme2.to_mesh(me)
        bme2.free()
        
        return {'FINISHED'}

def register():
    bpy.utils.register_class(opendental_ot_PartitionCurve)

def unregister():
    bpy.utils.unregister_class(opendental_ot_PartitionCurve)

