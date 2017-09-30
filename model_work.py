'''
Created on Aug 20, 2017

@author: Patrick
'''
import bpy
import bmesh
from mesh_cut import flood_selection_faces, edge_loops_from_bmedges

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
        
        new_me = bpy.data.meshes.new("hull")
        new_ob = bpy.data.objects.new("hull", new_me)
        new_ob.matrix_world = context.object.matrix_world
        context.scene.objects.link(new_ob)
        
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
def register():
    bpy.utils.register_class(D3SPLINT_OT_paint_model)
    bpy.utils.register_class(D3SPLINT_OT_delete_sculpt_mask)
    bpy.utils.register_class(D3SPLINT_OT_keep_sculpt_mask)
    bpy.utils.register_class(D3SPLINT_OT_delete_islands)
    bpy.utils.register_class(D3SPLINT_OT_mask_to_convex_hull)
    bpy.utils.register_class(D3PLINT_OT_simple_model_base)
    
def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_paint_model)
    bpy.utils.unregister_class(D3SPLINT_OT_delete_sculpt_mask)
    bpy.utils.unregister_class(D3SPLINT_OT_keep_sculpt_mask)
    bpy.utils.unregister_class(D3SPLINT_OT_delete_islands)
    bpy.utils.unregister_class(D3SPLINT_OT_mask_to_convex_hull)
    bpy.utils.unregister_class(D3PLINT_OT_simple_model_base)
    
if __name__ == "__main__":
    register()