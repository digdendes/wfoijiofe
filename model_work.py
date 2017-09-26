'''
Created on Aug 20, 2017

@author: Patrick
'''
import bpy
import bmesh
from mesh_cut import flood_selection_faces

class OPENDENTAL_OT_paint_model(bpy.types.Operator):
    '''Use sculpt mask to mark parts of model'''
    bl_idname = "opendental.enter_sculpt_paint_mask"
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

class OPENDENTAL_OT_finish_paint(bpy.types.Operator):
    '''Finish painting by re-entering object mode'''
    bl_idname = "opendental.finish_pain"
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
      
class OPENDENTAL_OT_delete_sculpt_mask(bpy.types.Operator):
    '''Delete painted parts of mesh'''
    bl_idname = "opendental.delete_sculpt_mask"
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


class OPENDENTAL_OT_keep_sculpt_mask(bpy.types.Operator):
    '''Delete everything not painted'''
    bl_idname = "opendental.delete_sculpt_mask_inverse"
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
        
        return {'FINISHED'}


class OPENDENTAL_OT_mask_to_convex_hull(bpy.types.Operator):
    '''Turn painted area into convex hull'''
    bl_idname = "opendental.sculpt_mask_qhull"
    bl_label = "Sculpt Mask to convex hull"
    bl_options = {'REGISTER','UNDO'}

    @classmethod
    def poll(cls, context):
        
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
        
        out_geom = bmesh.ops.convex_hull(bme, input = bme.verts[:])
        
        print('out geom')
        
        new_me = bpy.data.meshes.new("hull")
        new_ob = bpy.data.objects.new("hull", new_me)
        new_ob.matrix_world = context.object.matrix_world
        context.scene.objects.link(new_ob)
        
        bme.to_mesh(new_me)
        bme.free()
        context.object.data.update()
        
        bpy.ops.paint.mask_flood_fill(mode = 'VALUE', value = 0)
        return {'FINISHED'}
        
class OPENDENTAL_OT_delete_islands(bpy.types.Operator):
    '''Delete small disconnected pieces of mesh'''
    bl_idname = "opendental.delete_islands"
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


def register():
    bpy.utils.register_class(OPENDENTAL_OT_paint_model)
    bpy.utils.register_class(OPENDENTAL_OT_delete_sculpt_mask)
    bpy.utils.register_class(OPENDENTAL_OT_keep_sculpt_mask)
    bpy.utils.register_class(OPENDENTAL_OT_delete_islands)
    bpy.utils.register_class(OPENDENTAL_OT_mask_to_convex_hull)
    
def unregister():
    bpy.utils.unregister_class(OPENDENTAL_OT_paint_model)
    bpy.utils.unregister_class(OPENDENTAL_OT_delete_sculpt_mask)
    bpy.utils.unregister_class(OPENDENTAL_OT_keep_sculpt_mask)
    bpy.utils.unregister_class(OPENDENTAL_OT_delete_islands)
    bpy.utils.unregister_class(OPENDENTAL_OT_mask_to_convex_hull)
    
if __name__ == "__main__":
    register()