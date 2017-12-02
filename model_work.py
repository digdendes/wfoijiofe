'''
Created on Aug 20, 2017

@author: Patrick
'''

import math

import bpy
import bmesh
from mathutils.bvhtree import BVHTree

from mesh_cut import flood_selection_faces, edge_loops_from_bmedges,\
    space_evenly_on_path, bound_box

from bmesh_fns import join_bmesh, bme_linked_flat_faces    
from mathutils import Vector, Matrix
import odcutils
from common_utilities import bversion
from loops_tools import relax_loops_util
import time

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
        mask = bme.verts.layers.paint_mask.verify()
        bme.verts.ensure_lookup_table()
        delete = []
        for v in bme.verts:
            if v[mask] > 0:
                delete.append(v)

        bmesh.ops.delete(bme, geom = delete, context = 1)
        
        bme.to_mesh(context.object.data)
        bme.free()
        context.object.data.update()
        
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
            self.repoort({'ERROR'}, 'This tool only closes one hole at a time! Clear Paint or make sure boundary is completley selected')
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

class D3PLINT_OT_simple_model_base(bpy.types.Operator):
    """Simple ortho base with height 5 - 50mm """
    bl_idname = "d3splint.simple_base"
    bl_label = "Simple model base"
    bl_options = {'REGISTER', 'UNDO'}
    
    base_height = bpy.props.FloatProperty(name = 'Base Height', default = 10, min = -50, max = 50,  description = 'Base height added in mm')
    
    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and context.object != None and context.object.type == 'MESH':
            return True
        else:
            return False
        
    def execute(self, context):
        
        ob = context.object
        bme = bmesh.new()
        bme.from_mesh(context.object.data)
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        non_man_eds = [ed for ed in bme.edges if len(ed.link_faces) ==1]
        non_man_inds = [ed.index for ed in non_man_eds]
        
        
        loops = edge_loops_from_bmedges(bme, non_man_inds)
                
                
        if len(loops)>1:
            biggest_loop = max(loops, key = len)
            self.report({'WARNING'}, 'There are multiple holes in mesh, may want to UNDO and use override if model is 2 parts, /n Otherwise repair holes first')
        else:
            biggest_loop = loops[0]
            
        
        if biggest_loop[0] != biggest_loop[-1]:
            
            print('Biggest loop not a hole!')
            bme.free() 
            
            return {'FINISHED'}
        
        biggest_loop.pop()
        
        final_eds = [ed for ed in non_man_eds if all([v.index in biggest_loop for v in ed.verts])]
        relax_loops_util(bme, final_eds, iterations = 10, influence = .5)
        
        loop_verts = [bme.verts[i] for i in biggest_loop]
        minv = min(loop_verts, key = lambda x: x.co[2])
        maxv = max(loop_verts, key = lambda x: x.co[2])
        
        bbox = [Vector(v) for v in ob.bound_box]
        bmax = max(bbox,  key = lambda x: x[2])
        bmin = min(bbox,  key = lambda x: x[2])
        
        r_neg = minv.co[2] - bmin[2]
        r_pos = maxv.co[2] - bmax[2]
        
        
        if abs(r_neg) > abs(r_pos):
            Zflat = maxv.co[2]
            Z = Vector((0,0,1))
            zz = 1
        else:
            Zflat = minv.co[2]
            Z = Vector((0,0,-1))
            zz = -1
        
        
        gdict = bmesh.ops.extrude_edge_only(bme, edges = non_man_eds)
        bme.edges.ensure_lookup_table()
        newer_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
        newer_verts = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
        
        for v in newer_verts:
            v.co[2] = Zflat + .1 *zz
            
        gdict = bmesh.ops.extrude_edge_only(bme, edges = newer_edges)
        bme.edges.ensure_lookup_table()
        bme.verts.ensure_lookup_table()
        new_verts = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
        new_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
        for v in new_verts:
            v.co[2] = Zflat + self.base_height * zz 
            
        
        loops = edge_loops_from_bmedges(bme, [ed.index for ed in new_edges])
        loops[0].pop()
        f = bme.faces.new([bme.verts[i] for i in loops[0]])
        
        
        f.normal_update()
        if f.normal.dot(Z) < 0:
            f.normal_flip()
        
        
        bme.to_mesh(context.object.data)
        bme.free()
        context.object.data.update()             
        return {'FINISHED'}
        
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
            
        for v in tmp_ob.data.vertices:
            mb = meta_data.elements.new(type = 'BALL')
            mb.radius = self.radius
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
            
            '''
            gdict = bmesh.ops.bisect_plane(ob_bme, geom = ob_bme.faces[:]+ob_bme.edges[:]+ob_bme.verts[:], 
                               plane_co = pt - .1 * no, 
                               plane_no = no,
                               clear_outer = True)
                               
            cut_geom = gdict['geom_cut']
            ob_bme.edges.ensure_lookup_table()
            ob_bme.verts.ensure_lookup_table()
            
            cap_verts = [ele for ele in cut_geom if isinstance(ele, bmesh.types.BMVert)]
            cap_eds = [ele for ele in cut_geom if isinstance(ele, bmesh.types.BMEdge)]
            
            
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
    
if __name__ == "__main__":
    register()