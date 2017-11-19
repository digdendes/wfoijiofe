'''
Created on Aug 20, 2017

@author: Patrick
'''

import math

import bpy
import bmesh
from mesh_cut import flood_selection_faces, edge_loops_from_bmedges,\
    space_evenly_on_path
from mathutils import Vector, Matrix
import odcutils


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
        
        
        for loop in loops:
            if loop[0] == loop[-1]:
                loop.pop()
            
            if len(loop) < 3: continue
                
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
        
        bme = bmesh.new()
        bme.from_mesh(context.object.data)
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        non_man_eds = [ed.index for ed in bme.edges if not ed.is_manifold]
        loops = edge_loops_from_bmedges(bme, non_man_eds)
                
                
        if len(loops)>1:
            biggest_loop = max(loops, key = len)
        else:
            biggest_loop = loops[0]
            
        
        if biggest_loop[0] != biggest_loop[-1]:
            
            print('Biggest loop not a hole!')
            bme.free() 
            
            return {'FINISHED'}
        
        biggest_loop.pop()
        
        com = Vector((0,0,0))
        for vind in biggest_loop:
            com += bme.verts[vind].co
        com *= 1/len(biggest_loop)
        
        for vind in biggest_loop:
            bme.verts[vind].co[2] = com[2] + self.base_height
        
        bme.faces.new([bme.verts[vind] for vind in biggest_loop])
        bmesh.ops.recalc_face_normals(bme, faces = bme.faces)
        bme.to_mesh(context.object.data)
        bme.free()             
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
    
    
if __name__ == "__main__":
    register()