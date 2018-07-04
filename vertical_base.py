'''
Created on Jun 19, 2018

@author: Patrick
'''
import bpy
import time

class D3MODEL_OT_batch_vertical_base(bpy.types.Operator):
    """Apply distal cut and vertical base to all selected models"""
    bl_idname = "d3model.batch_vertical_base"
    bl_label = "Vertical Base Batch"
    bl_options = {'REGISTER', 'UNDO'}


    def execute(self, context):
        
        
        sel_obs = [ob for ob in bpy.data.objects if ob.select and not ob.hide]
        
        base_obs = [ob for ob in bpy.data.objects if ":Print Base" in ob.name]
        
        if len(base_obs) > 1:
            self.report({'ERROR'}, "There are too many print bases.  Delete extra pring base objects")
        
            return {'CANCELLED'}
        
        
        if len(base_obs) == 0:
            self.report({'ERROR'}, "There is no print base to add, you need to do the interactive vertical base first")
            return {'CANCELLED'}
        
        print_base = base_obs[0]
        if print_base in sel_obs:
            self.obs.remove(print_base)
            
            
        distal_cut = bpy.data.objects.get('Distal Cut')
        if not distal_cut:
            self.report({'ERROR'}, "There is no distal cut, you need to do the interactive vertical base first")
            return {'CANCELLED'}
    
        
        if distal_cut in sel_obs:
            sel_obs.remove(distal_cut)
            
        start = time.time()
        interval_start = time.time()    
        for ob in sel_obs:
            
            print('adding base to ' + ob.name)
            if 'Distal Cut' in ob.modifiers:
                dmod = ob.modifiers['Distal Cut']
            else:
                dmod = ob.modifiers.new('Distal Cut', type = 'BOOLEAN')    
                
            if 'Vertical Base' in ob.modifiers:
                vmod = ob.modifiers['Add Base']
            else:
                vmod = ob.modifiers.new('Add Base', type = 'BOOLEAN')
                
            dmod.operation = 'DIFFERENCE'
            dmod.solver = 'CARVE'
            vmod.operation = 'UNION'
            #vmod.solver = 'CARVE'
            
            dmod.object = distal_cut
            vmod.object = print_base
            
            
            old_data = ob.data
            context.scene.update()
            final_me = ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            
            ob.modifiers.clear()
            
            #for mod in self.snap_ob.modifiers:
            #    self.snap_ob.modifiers.remove(mod)
                
            ob.data = final_me
            
            if old_data.users == 0:
                bpy.data.meshes.remove(old_data)
                
            print('finished %s in %s seconds' % (ob.name, str(time.time() - interval_start)[0:4]))
            interval_start = time.time()
            
        print('Finished all modes in %f seconds' % (time.time() - start))
def register():
    bpy.utils.register_class(D3MODEL_OT_batch_vertical_base)

    
def unregister():
    bpy.utils.unregister_class(D3MODEL_OT_batch_vertical_base)
    
