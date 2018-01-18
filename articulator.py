'''
Created on Jul 5, 2017

@author: Patrick
'''
import math

import bpy
import bmesh
import math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from bpy.props import FloatProperty, IntProperty, BoolProperty, EnumProperty

import tracking
import splint_cache

def saw_tooth(frame):
    #amplitude  to 0 to 1
    #period of 30 frames
    
    r = math.fmod(frame, 30)
    return r/30
    
def thirty_steps(frame):
    r = math.floor(frame/30)/30
    return r


def three_way_envelope_l(frame):
    #protrusion
    print('Frame number %i' % frame)
    if frame < 60:
        R = .2 + .8 * abs(math.sin(math.pi * frame/120))
            
            
    #right excursion
    elif frame >= 60 and frame < 120:
        R = .2 + .8 * abs(math.sin(math.pi * (frame-60)/120))
            
    #left excursion
    elif frame >=120 and frame < 180:
        R = .2
        
    else:
        R = .2
        
    return R
            
    
    
def three_way_envelope_r(frame):
    #protrusion
    print('Frame number %i' % frame)
    if frame < 60:
        R = .2 + .8 * abs(math.sin(math.pi * frame/120))
             
    #right excursion
    elif frame >= 60 and frame < 120:
        R = .2        
            
    #left excursion
    elif frame >=120 and frame < 180:
        R = .2 + .8 * abs(math.sin(math.pi * (frame-120)/120))
        
    else:
        R = .2
        
    return R
    
def find_bone_drivers(amature_object, bone_name):
    # create an empty dictionary to store all found bones and drivers in
    boneDict = {}

    # iterate over all bones of the active object
    for bone in amature_object.pose.bones:

        # iterate over all drivers now
        # this should give better performance than the other way around
        # as most armatures have more bones than drivers
        foundDrivers = []
        for d in amature_object.animation_data.drivers:

            # a data path looks like this: 'pose.bones["Bone.002"].scale'
            # search for the full bone name including the quotation marks!
            if ('"%s"' % bone.name) in d.data_path:

                # we now have identified that there is a driver 
                # which refers to a bone channel
                foundDrivers.append(d)

        # if there are drivers, add an item to the dictionary
        if foundDrivers:
            print ('adding drivers of bone %s to Dictionary' % bone.name)

            # the dictionary uses the bone name as the key, and the
            # found FCurves in a list as the values
            boneDict[bone.name] = foundDrivers

    if bone_name in boneDict.keys():
        return boneDict[bone_name]
    else:
        return []
    
    
 
def load_driver_namespace():   
    
    if 'saw_tooth' not in bpy.app.driver_namespace:
        bpy.app.driver_namespace['saw_tooth'] = saw_tooth
    
    if 'thirty_steps' not in bpy.app.driver_namespace:
        bpy.app.driver_namespace['thirty_steps'] = thirty_steps
    
    if 'threeway_envelope_r' not in bpy.app.driver_namespace:
        bpy.app.driver_namespace['threeway_envelope_r'] = three_way_envelope_r
    
    if 'threeway_envelope_' not in bpy.app.driver_namespace:
        bpy.app.driver_namespace['threeway_envelope_l'] = three_way_envelope_l


            
    
class D3SPLINT_OT_generate_articulator(bpy.types.Operator):
    """Create Arcon Style semi adjustable articulator from parameters"""
    bl_idname = "d3splint.generate_articulator"
    bl_label = "Create Arcon Articulator"
    bl_options = {'REGISTER', 'UNDO'}
    
    intra_condyle_width = IntProperty(default = 110, description = 'Width between condyles in mm')
    condyle_angle = IntProperty(default = 20, description = 'Condyle inclination')
    bennet_angle = FloatProperty(default = 7.5, description = 'Height of rim')
    
    incisal_guidance = FloatProperty(default = 10, description = 'Incisal Guidance Angle')
    canine_guidance = FloatProperty(default = 10, description = 'Canine Lateral Guidance Angle')
    guideance_delay_ant = FloatProperty(default = .1, description = 'Anterior movement before guidance starts')
    guideance_delay_lat = FloatProperty(default = .1, description = 'Lateral movement before guidance starts')
    
    auto_mount = BoolProperty(default = True, description = 'Use if Upper and Lower casts are already in mounted position')
    @classmethod
    def poll(cls, context):
        
        return True
    
    def execute(self, context):
        tracking.trackUsage("D3Tool:GenArticulator",str((self.intra_condyle_width,
                                                         self.intra_condyle_width,
                                                         self.bennet_angle,
                                                         self.canine_guidance,
                                                         self.incisal_guidance)))
        context.scene.frame_start = 0
        context.scene.frame_end = 180
        context.scene.frame_set(0)
        
        #add 2 bezier paths named right and left condyle, move them to the condyle width
        if 'Articulator' in bpy.data.objects:
            #start fresh
            art_arm = bpy.data.objects.get('Articulator')
            n = context.scene.odc_splint_index
            splint = context.scene.odc_splints[n]
            opposing = splint.get_mandible()
            Model = bpy.data.objects.get(opposing)
            if Model:
                for cons in Model.constraints:
                    if cons.type == 'CHILD_OF' and cons.target == art_arm:
                        Model.constraints.remove(cons)
            
            context.scene.objects.unlink(art_arm)
            art_data = art_arm.data
            
            bpy.data.objects.remove(art_arm)
            bpy.data.armatures.remove(art_data)
            
        if 'Right Condyle Path' in bpy.data.curves:
            rcp_obj = bpy.data.objects.get("RCP")
            lcp_obj = bpy.data.objects.get("LCP")
            
            rcp = bpy.data.curves.get('Right Condyle Path')
            lcp = bpy.data.curves.get('Left Condyle Path')
            
        else:
            rcp = bpy.data.curves.new('Right Condyle Path', type = 'CURVE')
            lcp = bpy.data.curves.new('Left Condyle Path', type = 'CURVE')
        
        
            rcp.splines.new('BEZIER')
            lcp.splines.new('BEZIER')
        
            rcp.splines[0].bezier_points.add(count = 1)
            lcp.splines[0].bezier_points.add(count = 1)
        
            rcp_obj = bpy.data.objects.new("RCP",rcp)
            lcp_obj = bpy.data.objects.new("LCP",lcp)
            
            context.scene.objects.link(rcp_obj)
            context.scene.objects.link(lcp_obj)
        
        
        rcp.splines[0].bezier_points[0].handle_left_type = 'AUTO'
        rcp.splines[0].bezier_points[0].handle_right_type = 'AUTO'
        lcp.splines[0].bezier_points[0].handle_left_type = 'AUTO'
        lcp.splines[0].bezier_points[0].handle_right_type = 'AUTO'
        
        rcp.splines[0].bezier_points[1].handle_left_type = 'AUTO'
        rcp.splines[0].bezier_points[1].handle_right_type = 'AUTO'
        lcp.splines[0].bezier_points[1].handle_left_type = 'AUTO'
        lcp.splines[0].bezier_points[1].handle_right_type = 'AUTO'
        
        
        #track lenght
        rcp.splines[0].bezier_points[0].co = Vector((-2,0, 0))
        lcp.splines[0].bezier_points[0].co = Vector((-2,0, 0))
        
        
        rcp.splines[0].bezier_points[1].co = Vector((8,0,0))
        lcp.splines[0].bezier_points[1].co = Vector((8,0,0))
        
        rcp.dimensions = '3D'
        lcp.dimensions = '3D'
        
        
        rcp_obj.location = Vector((0, -0.5 * self.intra_condyle_width, 0))
        lcp_obj.location = Vector((0, 0.5 * self.intra_condyle_width, 0))
        
        lcp_obj.rotation_euler[1] = self.condyle_angle/180 * math.pi
        rcp_obj.rotation_euler[1] = self.condyle_angle/180 * math.pi
        
        lcp_obj.rotation_euler[2] = -self.bennet_angle/180 * math.pi
        rcp_obj.rotation_euler[2] = self.bennet_angle/180 * math.pi
        
        
        
        ant_guidance = Vector((math.cos(self.incisal_guidance*math.pi/180), 0, -math.sin(self.incisal_guidance*math.pi/180)))
        rcan_guidance = Vector((0, math.cos(self.canine_guidance*math.pi/180), -math.sin(self.canine_guidance*math.pi/180)))
        lcan_guidance = Vector((0, -math.cos(self.canine_guidance*math.pi/180), -math.sin(self.canine_guidance*math.pi/180)))
        
        ant_guidance.normalize()
        rcan_guidance.normalize()
        lcan_guidance.normalize()
        
        
        bme = bmesh.new()
        
        v0 = Vector((0,-.5 * self.guideance_delay_lat, 0))
        v1 = v0 + Vector((self.guideance_delay_ant, 0, 0))
        v2 = v1 + 15 * ant_guidance
        
        v3 = Vector((0,.5 * self.guideance_delay_lat, 0))
        v4 = v3 + Vector((self.guideance_delay_ant, 0, 0))
        v5 = v4 + 15 * ant_guidance
        
        v6 = v0 + 15 * lcan_guidance
        v7 = v1 + 15 * lcan_guidance
        v8 = v2 + 15 * lcan_guidance
        
        v9 = v3 + 15 * rcan_guidance
        v10 = v4 + 15 * rcan_guidance
        v11 = v5 + 15 * rcan_guidance
        vecs = [v0,v1,v2,v3, v4,v5,v6,v7,v8,v9,v10,v11]
        
        vs = [bme.verts.new(v) for v in vecs]
        
        bme.faces.new((vs[0],vs[3],vs[4],vs[1]))
        bme.faces.new((vs[1], vs[4],vs[5],vs[2]))
        
        bme.faces.new((vs[3], vs[9],vs[10],vs[4]))
        bme.faces.new((vs[6], vs[0],vs[1],vs[7]))
        
        bme.faces.new((vs[4], vs[10],vs[11],vs[5]))
        bme.faces.new((vs[7], vs[1],vs[2],vs[8]))
        
        if 'Guide Table' in bpy.data.objects:
            guide_object = bpy.data.objects.get('Guide Table')
            guide_data = guide_object.data
            
        else:
            guide_data = bpy.data.meshes.new('Guide Table')
            guide_object = bpy.data.objects.new('Guide Table', guide_data)
            context.scene.objects.link(guide_object)
            guide_object.location = Vector((99.9, 0, -60))  #TODO, incisal edge location
        
        bme.to_mesh(guide_data)
        
        
        
        
            
        art_data = bpy.data.armatures.new('Articulator')
        art_data.draw_type = 'STICK'
        art_arm = bpy.data.objects.new('Articulator',art_data)
        context.scene.objects.link(art_arm)
        
        art_arm.select = True
        context.scene.objects.active = art_arm
        bpy.ops.object.mode_set(mode = 'EDIT')
            
            
        bpy.ops.armature.bone_primitive_add(name = "Right Condyle")
        bpy.ops.armature.bone_primitive_add(name = "Left Condyle")
        bpy.ops.armature.bone_primitive_add(name = "Mand Bow Silent")
        bpy.ops.armature.bone_primitive_add(name = "Mandibular Bow")
        bpy.ops.armature.bone_primitive_add(name = "Guide Pin")
        
        bpy.ops.object.mode_set(mode = 'OBJECT')
        bpy.ops.object.mode_set(mode = 'EDIT')
        
        b = art_arm.data.edit_bones.get("Right Condyle")
        b.head.xyz = Vector((0,0,0))
        b.tail.xyz = Vector((0,0,10))
        
        b = art_arm.data.edit_bones.get("Left Condyle")
        b.head.xyz = Vector((0,0,0))
        b.tail.xyz = Vector((0,0,10))
        
        b = art_arm.data.edit_bones.get('Mand Bow Silent')
        b.head.xyz = Vector((0,0,0))
        b.tail.xyz = Vector((100,0,0))
        
        b = art_arm.data.edit_bones.get('Mandibular Bow')
        b.head.xyz = Vector((0,0,0))
        b.tail.xyz = Vector((100,0,0))
        
        #notice this bone points up, because the head will snap to guide plane
        b = art_arm.data.edit_bones.get('Guide Pin')
        b.head.xyz = Vector((100,0, -60))
        b.tail.xyz = Vector((100,0, 0))
        
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
        bpy.ops.object.mode_set(mode = 'POSE')
        #now set the pose constrints
        if 'threeway_envelope_r' not in bpy.app.driver_namespace:
            bpy.app.driver_namespace['threeway_envelope_r'] = three_way_envelope_r
        if 'threeway_envelope_l' not in bpy.app.driver_namespace:
            bpy.app.driver_namespace['threeway_envelope_l'] = three_way_envelope_l
                
        pboneR = art_arm.pose.bones.get('Right Condyle')
        cons = pboneR.constraints.new(type = 'FOLLOW_PATH')
        cons.target = rcp_obj
        cons.use_fixed_location = True
        d = cons.driver_add('offset_factor').driver
        v = d.variables.new()
        v.name = "frame"
        v.targets[0].id_type = 'SCENE'
        v.targets[0].id = context.scene
        v.targets[0].data_path = "frame_current"
        d.expression = "threeway_envelope_r(frame)"
        
        
        pboneL = art_arm.pose.bones.get('Left Condyle')
        cons = pboneL.constraints.new(type = 'FOLLOW_PATH')
        cons.target = lcp_obj
        cons.use_fixed_location = True
        d = cons.driver_add('offset_factor').driver
        v = d.variables.new()
        v.name = "frame"
        v.targets[0].id_type = 'SCENE'
        v.targets[0].id = context.scene
        v.targets[0].data_path = "frame_current"
        d.expression = "threeway_envelope_l(frame)"
        
        cons = pboneR.constraints.new(type = 'LOCKED_TRACK')
        cons.target = art_arm
        cons.subtarget = "Left Condyle"
        cons.track_axis = "TRACK_NEGATIVE_Z"
        cons.lock_axis = "LOCK_Y"
        
        cons = pboneL.constraints.new(type = 'LOCKED_TRACK')
        cons.target = art_arm
        cons.subtarget = "Right Condyle"
        cons.track_axis = 'TRACK_NEGATIVE_Z'
        cons.lock_axis = "LOCK_Y"
        
        #update the pose posititions
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.object.mode_set(mode = 'POSE')
        
        pboneBow = art_arm.pose.bones.get('Mand Bow Silent')
        cons = pboneBow.constraints.new('CHILD_OF')
        cons.target = art_arm
        cons.subtarget = 'Left Condyle'
        cons.inverse_matrix = pboneL.matrix.inverted()

        bpy.ops.object.mode_set(mode = 'EDIT')
        cons.influence = .5
        bpy.ops.object.mode_set(mode = 'POSE')
        
        cons = pboneBow.constraints.new('CHILD_OF')
        cons.target = art_arm
        cons.subtarget = 'Right Condyle'
        cons.inverse_matrix = pboneR.matrix.inverted()
        
        
        bpy.ops.object.mode_set(mode = 'EDIT')
        cons.influence = .5
        bpy.ops.object.mode_set(mode = 'POSE')
        
        pbonePin = art_arm.pose.bones.get('Guide Pin')
        cons = pbonePin.constraints.new(type = 'CHILD_OF')
        cons.target = art_arm
        cons.use_rotation_x = False
        cons.use_rotation_y = False
        cons.subtarget = 'Mand Bow Silent'
        cons.inverse_matrix = pboneBow.matrix.inverted()
        
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.object.mode_set(mode = 'POSE')
        
        cons = pbonePin.constraints.new(type = 'SHRINKWRAP')
        cons.target = guide_object
        cons.shrinkwrap_type = 'PROJECT'
        cons.project_axis = "NEG_Y"
        
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.object.mode_set(mode = 'POSE')
        
        pboneBow2 = art_arm.pose.bones.get("Mandibular Bow")
        cons = pboneBow2.constraints.new(type = 'CHILD_OF')
        cons.target = art_arm
        cons.subtarget = 'Mand Bow Silent'
        
        
        cons = pboneBow2.constraints.new(type = 'LOCKED_TRACK')
        cons.target = art_arm
        cons.subtarget = 'Guide Pin'
        cons.head_tail = 1
        cons.track_axis = 'TRACK_Y'
        cons.lock_axis = 'LOCK_Z'
        
        
        cons = pboneBow2.constraints.new(type = 'TRACK_TO')
        cons.target = art_arm
        cons.subtarget = 'Guide Pin'
        cons.head_tail = 1
        cons.track_axis = 'TRACK_Y'
        cons.up_axis = 'UP_Z'
        #https://blender.stackexchange.com/questions/19602/child-of-constraint-set-inverse-with-python
         
        bpy.ops.object.mode_set(mode = 'OBJECT')
        bpy.ops.view3d.viewnumpad(type = 'RIGHT')
        
        if not self.auto_mount:
            return {'FINISHED'}
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        
        opposing = splint.get_mandible()
        Model = bpy.data.objects.get(opposing)
        splint.ops_string += 'GenArticulator:'
        if not Model:
            self.report({'WARNING'},"Please use mark opposing model and then mount")
            return {'Finished'}
            
        cons = Model.constraints.new(type = 'CHILD_OF')
        cons.target = art_arm
        cons.subtarget = 'Mandibular Bow'
        
        mx = art_arm.matrix_world * art_arm.pose.bones['Mandibular Bow'].matrix
        cons.inverse_matrix = mx.inverted()
        
        #write the lower jaw BVH to cache for fast ray_casting
        OppModel = bpy.data.objects.get(splint.opposing)
        bme = bmesh.new()
        bme.from_mesh(OppModel.data)    
        bvh = BVHTree.FromBMesh(bme)
        splint_cache.write_mesh_cache(OppModel, bme, bvh)
        
        art_arm['bennet_angle'] = self.bennet_angle
        art_arm['intra_condyly_width'] = self.intra_condyle_width
        art_arm['incisal_guidance'] = self.incisal_guidance 
        art_arm['canine_guidance'] =  self.canine_guidance
        art_arm['condyle_angle'] =  self.condyle_angle
            
        return {'FINISHED'}

    
    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)


class D3Splint_OT_articulator_set_mode(bpy.types.Operator):
    """Change the Movement Mode of the artigulator"""
    bl_idname = "d3splint.articulator_mode_set"
    bl_label = "Articulator Mode Set"
    bl_options = {'REGISTER', 'UNDO'}
    
    modes = ['PROTRUSIVE', 'RIGHT_EXCURSION', 'LEFT_EXCURSION', 'RELAX_RAMP', '3WAY_ENVELOPE','FULL_ENVELOPE']
    mode_items = []
    for m in modes:
        mode_items += [(m, m, m)]
        
    mode = EnumProperty(name = 'Articulator Mode', items = mode_items, default = 'PROTRUSIVE')
    
    
    @classmethod
    def poll(cls, context):
        
        if 'Articulator' not in bpy.data.objects:
            return False
        
        return True
    
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
      
    def execute(self, context):
        
        #Double Set scene to frame 0
        context.scene.frame_set(0)
        context.scene.frame_set(0)
        
        
        art_arm = bpy.data.objects.get('Articulator')
        
        
        drivers_l = find_bone_drivers(art_arm, 'Left Condyle')
        drivers_r = find_bone_drivers(art_arm, 'Right Condyle')
        
        if len(drivers_l) > 1:
            print('oh oh, there should be only one')
            return {'CANCELLED'}
        
        if len(drivers_r) > 1:
            print('uh oh, there should be only one')
            return {'CANCELLED'}
            
            
        dl = drivers_l[0].driver
        dr = drivers_r[0].driver
        
        
        
        if self.mode == 'PROTRUSIVE':
            dl.expression = '.2 + .8 * abs(sin(pi * frame/120))'
            dr.expression = '.2 + .8 * abs(sin(pi * frame/120))'
           
           
            context.scene.frame_start = 0
            context.scene.frame_end = 60
           
           
        elif self.mode == 'RIGHT_EXCURSION':
        
            dr.expression = '.2'
            dl.expression = '.2 + .8 * abs(sin(pi * frame/120))'
            context.scene.frame_start = 0
            context.scene.frame_end = 60
            
            
        elif self.mode == 'LEFT_EXCURSION':
            dr.expression = '.2 + .8 * abs(sin(pi * frame/120))'
            dl.expression = '.2'
            context.scene.frame_start = 0
            context.scene.frame_end = 60
            
            
        elif self.mode == 'RELAX_RAMP':
            dr.expression = '.2 - .2 * abs(sin(pi * frame/120))'
            dl.expression = '.2 - .2 * abs(sin(pi * frame/120))'
            context.scene.frame_start = 0
            context.scene.frame_end = 60
            
        elif self.mode == '3WAY_ENVELOPE':
            
            if 'threeway_envelope_r' not in bpy.app.driver_namespace:
                bpy.app.driver_namespace['threeway_envelope_r'] = three_way_envelope_r
            if 'threeway_envelope_l' not in bpy.app.driver_namespace:
                bpy.app.driver_namespace['threeway_envelope_l'] = three_way_envelope_l
            #protrusion
            dl.expression = 'threeway_envelope_l(frame)'
            dr.expression = 'threeway_envelope_r(frame)'
        
            context.scene.frame_start = 0
            context.scene.frame_end = 180
            
            
                
        elif self.mode == 'FULL_ENVELOPE':
            
            dr.expression = ".2 + .8 * fmod(frame,30)/30"
            dl.expression = ".2 + .8 * floor(frame/30)/30"
        
            context.scene.frame_start = 0
            context.scene.frame_end = 900
            
        return {'FINISHED'}


class D3SPLINT_OT_splint_open_pin_on_articulator(bpy.types.Operator):
    """Open Pin on Articulator.  Pin increments are assumed 1mm at 85mm from condyles"""
    bl_idname = "d3splint.open_pin_on_articulator"
    bl_label = "Change Articulator Pin"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    amount = FloatProperty(name = 'Pin Setting', default = 0.5, step = 10, min = -3.0, max = 3.0)
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def invoke(self,context,event):
        tracking.trackUsage("D3Splint:ChangePinSetting",None)
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        if context.scene.frame_current != 0:
            self.report({'WARNING'}, "The articulator is not at the 0 position, resetting it to 0 before changing pin")
            context.scene.frame_current = 0
            context.scene.frame_set(0)
            context.scene.frame_set(0)
            
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n] #TODO better knowledge for multiple splints
        if not splint.landmarks_set:
            self.report({'ERROR'}, 'You must set landmarks to get an approximate mounting')
            return {'CANCELLED'}
        
        mandible = splint.get_mandible()
        maxilla = splint.get_maxilla()
        
        Model = bpy.data.objects.get(mandible)
        Master = bpy.data.objects.get(maxilla)
        if not Model:
            self.report({'ERROR'},"Please set opposing model")
            return {'CANCELLED'}
        
        Articulator = bpy.data.objects.get('Articulator')
        if Articulator == None:
            self.report({'ERROR'},"Please use Add Arcon Articulator function")
            return {'CANCELLED'}
        
        if context.scene.frame_current != 0:
            context.scene.frame_current = -1
            context.scene.frame_current = 0
            context.scene.frame_set(0)
        
        re_mount = False
        
        constraints = []
        if len(Model.constraints):
            re_mount = True
            for cons in Model.constraints:
                cdata = {}
                cdata['type'] = cons.type
                cdata['target'] = cons.target
                cdata['subtarget'] = cons.subtarget
                constraints += [cdata]
                Model.constraints.remove(cons) 
            
            
        
        radians = self.amount/85
        
        R = Matrix.Rotation(radians, 4, 'Y')
        Model.matrix_world = R * Model.matrix_world
        
        if re_mount:
            
            cons = Model.constraints.new(type = 'CHILD_OF')
            cons.target = Master
            cons.inverse_matrix = Master.matrix_world.inverted()
             
            cons = Model.constraints.new(type = 'CHILD_OF')
            cons.target = Articulator
            cons.subtarget = 'Mandibular Bow'
        
            mx = Articulator.matrix_world * Articulator.pose.bones['Mandibular Bow'].matrix
            cons.inverse_matrix = mx.inverted()
    
        return {'FINISHED'}

class D3SPLINT_OT_recover_mandible_mounting(bpy.types.Operator):
    """Recover original bite/mount relationship when models were first imported"""
    bl_idname = "d3splint.recover_mounting_relationship"
    bl_label = "Recover Mandibular Mounting"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n] #TODO better knowledge for multiple splints
        
        if context.scene.frame_current != 0:
            self.report({'WARNING'}, "The articulator is not at the 0 position, resetting it to 0 before recovering moutn")
            context.scene.frame_current = 0
            context.scene.frame_set(0)
            context.scene.frame_set(0)
            
        if not splint.landmarks_set:
            self.report({'ERROR'}, 'You must set landmarks to have saved mounting')
            return {'CANCELLED'}
        
        
        if "Mandibular Orientation" not in bpy.data.objects:
            self.report({'ERROR'}, 'Unfortunately, the mounting backup is not present.  Did you delete it?')
            return {'CANCELLED'}
        
        mandible = splint.get_mandible()
        maxilla = splint.get_maxilla()
        
        Model = bpy.data.objects.get(mandible)
        Master = bpy.data.objects.get(maxilla)
        
        if not Model:
            self.report({'ERROR'},"It is not clear which model is the mandible.  Have you set model and set opposing?")
            return {'CANCELLED'}
        
        if not Master:
            self.report({'ERROR'},"It is not clear which model is the maxilla.  Have you set model and set opposing?")
            return {'CANCELLED'}
        
        
        Orientation = bpy.data.objects.get('Mandibular Orientation')
        mx_recover = Orientation.matrix_world
        
        if context.scene.frame_current != 0:
            context.scene.frame_current = -1
            context.scene.frame_current = 0
            context.scene.frame_set(0)
        
        re_mount = False
        
        constraints = []
        if len(Model.constraints):
            re_mount = True
            for cons in Model.constraints:
                cdata = {}
                cdata['type'] = cons.type
                cdata['target'] = cons.target
                cdata['subtarget'] = cons.subtarget
                constraints += [cdata]
                Model.constraints.remove(cons) 
            
            
        

        Model.matrix_world = mx_recover
        
        Articulator = bpy.data.objects.get('Articulator')
        
        if re_mount:
            
            cons = Model.constraints.new(type = 'CHILD_OF')
            cons.target = Master
            cons.inverse_matrix = Master.matrix_world.inverted()
             
            if Articulator:
                cons = Model.constraints.new(type = 'CHILD_OF')
                cons.target = Articulator
                cons.subtarget = 'Mandibular Bow'
        
                mx = Articulator.matrix_world * Articulator.pose.bones['Mandibular Bow'].matrix
                cons.inverse_matrix = mx.inverted()
    
        return {'FINISHED'}

      
def register():
    bpy.utils.register_class(D3SPLINT_OT_generate_articulator)
    bpy.utils.register_class(D3Splint_OT_articulator_set_mode)
    bpy.utils.register_class(D3SPLINT_OT_splint_open_pin_on_articulator)
    bpy.utils.register_class(D3SPLINT_OT_recover_mandible_mounting)
    
    
def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_generate_articulator)
    bpy.utils.unregister_class(D3Splint_OT_articulator_set_mode)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_open_pin_on_articulator)
    bpy.utils.unregister_class(D3SPLINT_OT_recover_mandible_mounting)
    
if __name__ == "__main__":
    register()