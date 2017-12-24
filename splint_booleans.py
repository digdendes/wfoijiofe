import os, platform
import bpy
import bmesh
from bpy.types import Operator

from mesh_cut import flood_selection_faces, edge_loops_from_bmedges,\
    space_evenly_on_path, bound_box, contract_selection_faces, \
    face_neighbors_by_vert, flood_selection_faces_limit
    
import cork
from cork.cork_fns import cork_boolean
from cork.lib import get_cork_filepath, validate_executable
from cork.exceptions import *
   
class D3SPLINT_OT_splint_cork_boolean(Operator):
    """"""
    bl_idname = "d3guard.splint_cork_boolean"
    bl_label = "Splint Cork Boolean"
    bl_description = ""

    
    @classmethod
    def poll(cls, context):
        return True

    def exec(self, context):
        try:
            bme = cork_boolean(context, self._cork, "-diff", self._base, self._plane)
        except Exception as e:
            print('error in line 24')
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        
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
        
        me = bpy.data.meshes.new('Final Splint')
        ob = bpy.data.objects.new('Final Splint', me)
        context.scene.objects.link(ob)
        bme.to_mesh(me)
        bme.free()
        
        for obj in context.scene.objects:
            obj.hide = True
            
        context.scene.objects.active = ob
        ob.select = True
        ob.hide = False
        
        return {'FINISHED'}

    def invoke(self, context, event):
        cork = get_cork_filepath()

        try:
            validate_executable(cork)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


        spacer = bpy.data.objects.get('Passive Spacer')
        shell = bpy.data.objects.get('Splint Shell')
        base_teeth = bpy.data.objects.get('Based_Model')
        
        if not shell:
            self.report({'ERROR'}, 'Need to calculate the shell first')
            return {'CANCELLED'}
        
        if not spacer:
            self.report({'ERROR'}, 'Need to calculate the passivity offset')
            return {'CANCELLED'}
        
        self._cork = cork
        print("did you get the cork executable?")
        print(self._cork)
        
        self._plane = spacer
        self._base = shell

        return self.exec(context)



# ############################################################
# Registration
# ############################################################

def register():
    # the order here determines the UI order
    bpy.utils.register_class(D3SPLINT_OT_splint_cork_boolean)


def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_splint_cork_boolean)
