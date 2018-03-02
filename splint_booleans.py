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
import time
import tracking
from bpy.props import FloatProperty, BoolProperty, IntProperty, EnumProperty
import common_utilities
from common_utilities import get_settings
  
class D3SPLINT_OT_splint_cork_boolean(Operator):
    """Use external boolean engine when fast Blender solver has errors"""
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
            tracking.trackUsage("D3Splint:FAILEDCorkBoolean")
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
        
        tracking.trackUsage("D3Splint:SplintBooleanCORK")
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


class D3SPLINT_OT_splint_finish_booleans(bpy.types.Operator):
    """Finish the Booleans"""
    bl_idname = "d3splint.splint_finish_booleans"
    bl_label = "Finalize the Splint (no blockout)"
    bl_options = {'REGISTER', 'UNDO'}
    
    method_order = EnumProperty(
        description="Method Order",
        items=(("SUBTRACT", "Subtract", "Subtracts Blockout wax, then subtracts Passive Spacer"),
               ("JOIN", "Join", "Joins the Blockout and Passive, then subtracts from Splint")),
        default = "JOIN")
    
    solver = EnumProperty(
        description="Boolean Method",
        items=(("BMESH", "Bmesh", "Faster/More Errors"),
               ("CARVE", "Carve", "Slower/Less Errors")),
        default = "BMESH")
    
    use_blockout = BoolProperty(default = True, name = "Remove Undercuts", description = 'Will add 2nd Boolean operation to remove undercuts.  Will add ~30 seconds to calc time')
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        
        prefs = common_utilities.get_settings()
        if not prefs.non_clinical_use:
            self.report({'ERROR'}, 'You must certify non-clinical use in your addon preferences or in the panel')
            return {'CANCELLED'}
        
        if splint.finalize_splint:
            self.report({'WARNING'}, 'You have already finalized, this will remove or alter existing modifiers and try again')
            
        Shell = bpy.data.objects.get('Splint Shell')
        Passive = bpy.data.objects.get('Passive Spacer')

        if Shell == None:
            self.report({'ERROR'}, 'Need to calculate splint shell first')
            return {'CANCELLED'}
        
        if Passive == None:
            self.report({'ERROR'}, 'Need to make passive spacer first')    
            return {'CANCELLED'}
        
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode = 'OBJECT')
        
        tracking.trackUsage("D3Splint:FinishBoolean",None)    
        
        
        #don't add multiple boolean modifiers
        if 'Passive Fit' not in Shell.modifiers:
            bool_mod = Shell.modifiers.new('Passive Fit', type = 'BOOLEAN')
            bool_mod.operation = 'DIFFERENCE'
        
        bool_mod.solver = self.solver
            
        #update in case they changed the spacer
        bool_mod.object = Passive
        Passive.hide = True 
        
        bme = bmesh.new()
        bme.from_object(Shell, context.scene)
        bme.faces.ensure_lookup_table()
        bme.verts.ensure_lookup_table()
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
        
        
        if 'Final Splint' not in bpy.data.objects:
            me = bpy.data.meshes.new('Final Splint')
            ob = bpy.data.objects.new('Final Splint', me)
            context.scene.objects.link(ob)
            ob.matrix_world = Shell.matrix_world
        else:
            ob = bpy.data.objects.get('Final Splint')
            me = ob.data
            
        bme.to_mesh(me)
        bme.free()
        
        for obj in context.scene.objects:
            obj.hide = True
            
        context.scene.objects.active = ob
        ob.select = True
        ob.hide = False
        
        tmodel = bpy.data.objects.get('Trimmed_Model')
        #make sure user can verify no intersections
        if tmodel:
            tmodel.hide = False

        splint.finalize_splint = True
        return {'FINISHED'}

   
class D3SPLINT_OT_splint_finish_booleans2(bpy.types.Operator):
    """Finish the Booleans"""
    bl_idname = "d3splint.splint_finish_booleans2"
    bl_label = "Finalize the Splint (2 Object Method)"
    bl_options = {'REGISTER', 'UNDO'}
    
    method_order = EnumProperty(
        description="Method Order",
        items=(("SUBTRACT", "Subtract", "Subtracts Blockout wax, then subtracts Passive Spacer"),
               ("JOIN", "Join", "Joins the Blockout and Passive, then subtracts from Splint")),
        default = "JOIN")
    
    solver1 = EnumProperty(
        description="Boolean Method",
        items=(("BMESH", "Bmesh", "Faster/More Errors"),
               ("CARVE", "Carve", "Slower/Less Errors")),
        default = "BMESH")
    
    solver2 = EnumProperty(
        description="Boolean Method",
        items=(("BMESH", "Bmesh", "Faster/More Errors"),
               ("CARVE", "Carve", "Slower/Less Errors")),
        default = "BMESH")
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def invoke(self,context,event):
        
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        prefs = get_settings()
        if not prefs.non_clinical_use:
            self.report({'ERROR'}, 'You must certify non-clinical use in your addon preferences or in the panel')
            return {'CANCELLED'}
        
        if splint.finalize_splint:
            self.report({'WARNING'}, 'You have already finalized, this will remove or alter existing modifiers and try again')
            
        Shell = bpy.data.objects.get('Splint Shell')
        Passive = bpy.data.objects.get('Passive Spacer')
        Blockout = bpy.data.objects.get('Blockout Wax')
        
        
        if Shell == None:
            self.report({'ERROR'}, 'Need to calculate splint shell first')
            return {'CANCELLED'}
        
        if Passive == None:
            self.report({'ERROR'}, 'Need to make passive spacer first')    
            return {'CANCELLED'}
        
        if Blockout == None and self.use_blockout == True:
            self.report({'ERROR'}, 'Need to blockout trimmed model first')    
            return {'CANCELLED'}
        
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode = 'OBJECT')
        
        start = time.time()
        #don't add multiple boolean modifiers
        
        
        
        if 'Final Splint' not in bpy.data.objects:
            me = Shell.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            ob = bpy.data.objects.new('Final Splint', me)
            context.scene.objects.link(ob)
            ob.matrix_world = Shell.matrix_world
        else:
            ob = bpy.data.objects.get('Final Splint')
            me = ob.data
            
        a_base = bpy.data.objects.get('Auto Base')
        if 'Trim Base' in ob.modifiers and a_base != None:
            mod = ob.modifiers.get('Trim Base')
            mod.object = a_base
            mod.operation = 'DIFFERENCE'
            mod.solver = self.solver1
        else:
            mod = ob.modifiers.new('Trim Base', type = 'BOOLEAN')
            mod.object = a_base
            mod.operation = 'DIFFERENCE'
            mod.solver = self.solver1  
            
        if self.method_order == 'JOIN':
            #Structure is   Shell - (Blockout + Passive)
            
            #Blockout Wax Needs a union modifier
            if 'Join Passive' in Blockout.modifiers:
                mod = Blockout.modifiers.get('Join Passive')
                mod.object = Passive
                mod.operation = 'UNION'
                mod.solver = self.solver1
            else:
                mod = Blockout.modifiers.new('Join Passive', type = 'BOOLEAN')
                mod.object = Passive
                mod.operation = 'UNION'
                mod.solver = self.solver1
            
            
            #Final Spint need only 1 boolean operation
            if 'Passive Spacer' in ob.modifiers:
                mod = ob.modifiers.get('Passive Spacer')
                ob.modifiers.remove(mod)
                
            if 'Subtract Blockout' in ob.modifiers:
                mod = ob.modifiers.get('Subtract Blockout')
                mod.object = Blockout
                mod.operation = 'DIFFERENCE'
                mod.solver = self.solver2
            else:
                mod = ob.modifiers.new('Subtract Blockout', type = 'BOOLEAN')
                mod.object = Blockout
                mod.operation = 'DIFFERENCE'
                mod.solver = self.solver2
            
        elif self.method_order == 'SUBTRACT':
            
            #Strucure is
            #Shell - Blockout - Passive
            
            #Blockout Wax MUST NOT have modifier
            if 'Join Passive' in Blockout.modifiers:
                mod = Blockout.modifiers.get('Join Passive')
                Blockout.modifiers.remove(mod)
                Blockout.update_tag()
                
            if 'Subtract Blockout' in ob.modifiers:
                mod = ob.modifiers.get('Subtract Blockout')
                mod.object = Blockout
                mod.operation = 'DIFFERENCE'
                mod.solver = self.solver1
            else:
                mod = ob.modifiers.new('Subtract Blockout', type = 'BOOLEAN')
                mod.object = Blockout
                mod.operation = 'DIFFERENCE'
                mod.solver = self.solver1
                
            if 'Passive Spacer' not in ob.modifiers:
                bool_mod = ob.modifiers.new('Passive Spacer', type = 'BOOLEAN')
                bool_mod.operation = 'DIFFERENCE'
                bool_mod.object = Passive
                bool_mod.solver = self.solver2  #Bmesh is too likely to create bad cuts
            else:
                bool_mod = ob.modifiers.get('Passive Spacer')
                bool_mod.operation = 'DIFFERENCE'
                bool_mod.object = Passive
                bool_mod.solver = self.solver2  ##Bmesh is too likely to create bad cuts
            
        
        for obj in context.scene.objects:
            obj.hide = True
            
        context.scene.objects.active = ob
        ob.select = True
        ob.hide = False
        ob.update_tag()
        context.scene.update()
            
        completion_time = time.time() - start
        print('competed the boolean subtraction in %f seconds' % completion_time)   
        splint.finalize_splint = True
        tracking.trackUsage("D3Splint:FinishBoolean",(self.solver1,self.solver2, self.method_order, str(completion_time)[0:4]))
        
        tmodel = bpy.data.objects.get('Trimmed_Model')
        #make sure user can verify no intersections
        if tmodel:
            tmodel.hide = False
    
        
        return {'FINISHED'}

class D3SPLINT_OT_splint_finish_booleans3(bpy.types.Operator):
    """Finish the Booleans"""
    bl_idname = "d3splint.splint_finish_booleans3"
    bl_label = "Finalize the Splint"
    bl_options = {'REGISTER', 'UNDO'}
    
    solver = EnumProperty(
        description="Boolean Method",
        items=(("BMESH", "Bmesh", "Faster/More Errors"),
               ("CARVE", "Carve", "Slower/Less Errors"),
               ("CORK", "Cork", "Slowest/Least Errors, Not re-implemented yet")),
        default = "BMESH")
  
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    

    def invoke(self,context,event):
        
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        prefs = get_settings()
        if not prefs.non_clinical_use:
            self.report({'ERROR'}, 'You must certify non-clinical use in your addon preferences or in the panel')
            return {'CANCELLED'}
        
        if splint.finalize_splint:
            self.report({'WARNING'}, 'You have already finalized, this will remove or alter existing modifiers and try again')
        
        if self.solver == 'CORK':
            self.report({'ERROR'}, 'The Cork engine has not been set up with this new method')
            return {'CANCELLED'}
         
        Shell = bpy.data.objects.get('Splint Shell')
        Refractory = bpy.data.objects.get('Refractory Model')
        
        if Shell == None:
            self.report({'ERROR'}, 'Need to calculate splint shell first')
            return {'CANCELLED'}
        
        if Refractory == None:
            self.report({'ERROR'}, 'Need to make refractory model first')    
            return {'CANCELLED'}
        
        
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode = 'OBJECT')
        
        start = time.time()
        #don't add multiple boolean modifiers
        
        
        
        if 'Final Splint' not in bpy.data.objects:
            me = Shell.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            ob = bpy.data.objects.new('Final Splint', me)
            context.scene.objects.link(ob)
            ob.matrix_world = Shell.matrix_world
        else:
            ob = bpy.data.objects.get('Final Splint')
            me = ob.data
            
        a_base = bpy.data.objects.get('Auto Base')
        if 'Trim Base' in ob.modifiers and a_base != None:
            mod = ob.modifiers.get('Trim Base')
            mod.object = a_base
            mod.operation = 'DIFFERENCE'
            mod.solver = self.solver
        else:
            mod = ob.modifiers.new('Trim Base', type = 'BOOLEAN')
            mod.object = a_base
            mod.operation = 'DIFFERENCE'
            mod.solver = self.solver 
            
    
        #Final Spint need only 1 boolean operation
        if 'Refractory Model' in ob.modifiers:
            mod = ob.modifiers.get('Passive Spacer')
            
        else:
            mod = ob.modifiers.new('Refractory Model', type = 'BOOLEAN')
        mod.object = Refractory
        mod.operation = 'DIFFERENCE'
        mod.solver = self.solver
        
        for obj in context.scene.objects:
            obj.hide = True
            
        context.scene.objects.active = ob
        ob.select = True
        ob.hide = False
        ob.update_tag()
        context.scene.update()
            
        completion_time = time.time() - start
        print('competed the boolean subtraction in %f seconds' % completion_time)   
        splint.finalize_splint = True
        tracking.trackUsage("D3Splint:FinishBoolean3",(self.solver, str(completion_time)[0:4]))
        
        tmodel = bpy.data.objects.get('Trimmed_Model')
        #make sure user can verify no intersections
        if tmodel:
            tmodel.hide = False
    
        
        return {'FINISHED'}
    
    
class D3SPLINT_OT_splint_finish_booleans_bite(bpy.types.Operator):
    """Finish the Booleans"""
    bl_idname = "d3splint.splint_finish_bite_boolean"
    bl_label = "Finalize the Bite Splint"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    solver = EnumProperty(
        description="Boolean Method",
        items=(("BMESH", "Bmesh", "Faster/More Errors"),
               ("CARVE", "Carve", "Slower/Less Errors")),
        default = "BMESH")
    
     
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        
        prefs = get_settings()
        if not prefs.non_clinical_use:
            self.report({'ERROR'}, 'You must certify non-clinical use in your addon preferences or in the panel')
            return {'CANCELLED'}
        
        if splint.finalize_splint:
            self.report({'WARNING'}, 'You have already finalized, this will remove or alter existing modifiers and try again')
         
        if splint.workflow_type != 'BITE_POSITIONER':
            self.report({'ERROR'}, 'This splint is not a bite positioner workflow, change it to use this function')
            return {'CANCELLED'}
        
        Shell = bpy.data.objects.get('Splint Shell')
        Maxilla = bpy.data.objects.get(splint.get_maxilla())
        Mandible = bpy.data.objects.get(splint.get_mandible())
        
        
        if Shell == None:
            self.report({'ERROR'}, 'Need to calculate the bite wafer first')
            return {'CANCELLED'}
        
        if Maxilla == None:
            self.report({'ERROR'}, 'Need to mark the maxillary modelfirst')    
            return {'CANCELLED'}
        
        if Mandible == None:
            self.report({'ERROR'}, 'Need to mark the mandible first')    
            return {'CANCELLED'}
        
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode = 'OBJECT')
        
        start = time.time()
        #don't add multiple boolean modifiers
        
        if 'Final Splint' not in bpy.data.objects:
            me = Shell.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            ob = bpy.data.objects.new('Final Splint', me)
            context.scene.objects.link(ob)
            ob.matrix_world = Shell.matrix_world
        else:
            ob = bpy.data.objects.get('Final Splint')
            me = ob.data
        
            
        #Blockout Wax Needs a union modifier
        if 'Subtract Mandible' in ob.modifiers:
            mod = ob.modifiers.get('Subtract Mandible')
            mod.object = Mandible
            mod.operation = 'DIFFERENCE'
            mod.solver = self.solver
        else:
            mod = ob.modifiers.new('Subtract Mandible', type = 'BOOLEAN')
            mod.object = Mandible
            mod.operation = 'DIFFERENCE'
            mod.solver = self.solver
            
            
        if 'Subtract Maxilla' in ob.modifiers:
            mod = ob.modifiers.get('Subtract Maxilla')
            mod.object = Maxilla
            mod.operation = 'DIFFERENCE'
            mod.solver = self.solver
        else:
            mod = ob.modifiers.new('Subtract Maxilla', type = 'BOOLEAN')
            mod.object = Maxilla
            mod.operation = 'DIFFERENCE'
            mod.solver = self.solver
            
        

        for obj in context.scene.objects:
            obj.hide = True
            
        context.scene.objects.active = ob
        ob.select = True
        ob.hide = False
         
        completion_time = time.time() - start
        print('competed the boolean subtraction in %f seconds' % completion_time)   
        splint.finalize_splint = True
        tracking.trackUsage("D3Splint:FinishBiteBoolean",(self.solver, str(completion_time)[0:4]))
        return {'FINISHED'}    
# ############################################################
# Registration
# ############################################################

def register():
    # the order here determines the UI order
    bpy.utils.register_class(D3SPLINT_OT_splint_cork_boolean)
    bpy.utils.register_class(D3SPLINT_OT_splint_finish_booleans)
    bpy.utils.register_class(D3SPLINT_OT_splint_finish_booleans2)
    bpy.utils.register_class(D3SPLINT_OT_splint_finish_booleans3)
    bpy.utils.register_class(D3SPLINT_OT_splint_finish_booleans_bite)


def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_splint_cork_boolean)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_finish_booleans)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_finish_booleans2)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_finish_booleans3)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_finish_booleans_bite)
