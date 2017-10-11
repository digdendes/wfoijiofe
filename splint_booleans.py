import os, platform
import bpy
from bpy.types import Operator

import cork
from cork.cork_fns import cork_boolean
from cork.lib import get_cork_filepath, validate_executable
from cork.exceptions import *
   
class D3SPLINT_OT_splint_boolean_(Operator):
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

        me = bpy.data.meshes.new('Final Splint')
        ob = bpy.data.objects.new('Final Splint', me)
        context.scene.objects.link(ob)
        bme.to_mesh(me)
        bme.free()
        
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
    bpy.utils.register_class(D3SPLINT_OT_splint_boolean_)


def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_splint_boolean_)
