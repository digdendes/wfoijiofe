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
from common_utilities import get_settings

def saw_tooth(frame):
    #amplitude  to 0 to 1
    #period of 30 frames
    
    r = math.fmod(frame, 30)
    return r/30
    
def thirty_steps(frame):
    r = math.floor(frame/30)/30
    return r



def full_envelope_with_relax(frame, condy_length, resolution, use_relax, relax_length, right_left):
    
    if frame > resolution * (resolution + 1):
        frame = resolution * (resolution + 1)
        
    factor = min(1, condy_length/8)
    
    
    r_factor = min(1, relax_length/2)
    
    if frame < resolution**2:
        if right_left == 'R':
            R = .2 + factor * .8 * math.fmod(frame,resolution)/resolution
        else:
            R = .2 + factor * .8 * math.floor(frame/resolution)/resolution
            
            
    else:#retrusion
    
        R = .2 - r_factor * .2 * (frame - resolution**2)/resolution
        
        
    return R



def three_way_envelope_l(frame, factor, resolution):
    #protrusion
    if frame < resolution:
        R = .2 + factor * .8 * abs(math.sin(math.pi * frame/(2*resolution)))
                   
    #right excursion
    elif frame >= resolution and frame < 2 * resolution:
        R = .2 + factor * .8 * abs(math.sin(math.pi * (frame-resolution)/(2*resolution)))
            
    #left excursion
    elif frame >=2*resolution and frame < 3*resolution:
        R = .2
        
    else:
        R = .2
        
    return R
            
    
    
def three_way_envelope_r(frame, factor, resolution):
    #protrusion
    if frame < resolution:
        R = .2 + factor * .8 * abs(math.sin(math.pi * frame/(2*resolution)))
             
    #right excursion
    elif frame >= resolution and frame < 2 * resolution:
        R = .2        
            
    #left excursion
    elif frame >=2*resolution and frame < 3*resolution:
        R = .2 + factor * .8 * abs(math.sin(math.pi * (frame-2*resolution)/(2*resolution)))
        
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


    if 'full_envelope_with_relax' not in bpy.app.driver_namespace:
        bpy.app.driver_namespace['full_envelope_with_relax'] = full_envelope_with_relax
        
def occlusal_surface_frame_change(scene):

    if not len(scene.odc_splints): return
    n = scene.odc_splint_index
    splint = scene.odc_splints[n]
    #TODO...get the models better?
    plane = bpy.data.objects.get('Dynamic Occlusal Surface')
    jaw = bpy.data.objects.get(splint.opposing)
    
    if plane == None: return
    if jaw == None: return
    
    mx_jaw = jaw.matrix_world
    mx_pln = plane.matrix_world
    imx_j = mx_jaw.inverted()
    imx_p = mx_pln.inverted()
    
    bvh = splint_cache.mesh_cache['bvh']
    if splint.jaw_type == 'MAXILLA':
        Z = Vector((0,0,1))
    else:
        Z = Vector((0,0,-1))
    for v in plane.data.vertices:
        
        a = mx_pln * v.co
        b = mx_pln * (v.co + 10 * Z)
        
        hit = bvh.ray_cast(imx_j * a, imx_j * b - imx_j * a)
        
        if hit[0]:
            #check again
            hit2 = bvh.ray_cast(hit[0], imx_j * b - hit[0])
            
            if hit2[0]:
                v.co = imx_p * mx_jaw * hit[0]
            else:
                v.co = imx_p * mx_jaw * hit[0]            
    
class D3SPLINT_OT_generate_articulator(bpy.types.Operator):
    """Create Arcon Style semi adjustable articulator from parameters \n or modify the existing articulator
    """
    bl_idname = "d3splint.generate_articulator"
    bl_label = "Create Arcon Articulator"
    bl_options = {'REGISTER', 'UNDO'}
    
    intra_condyle_width = IntProperty(name = "Intra-Condyle Width", default = 110, description = 'Width between condyles in mm')
    condyle_angle = IntProperty(name = "Condyle Angle", default = 20, description = 'Condyle inclination in the sagital plane')
    bennet_angle = FloatProperty(name = "Bennet Angle", default = 7.5, description = 'Bennet Angle: Condyle inclination in the axial plane')
    
    incisal_guidance = FloatProperty(name = "Incisal Guidance", default = 10, description = 'Incisal Guidance Angle')
    canine_guidance = FloatProperty(name = "Canine Guidance", default = 10, description = 'Canine Lateral Guidance Angle')
    guidance_delay_ant = FloatProperty(name = "Anterior Guidance Delay", default = .1, description = 'Anterior movement before guidance starts')
    guidance_delay_lat = FloatProperty(name = "Canine Guidance Delay", default = .1, description = 'Lateral movement before canine guidance starts')
    
    auto_mount = BoolProperty(default = True, description = 'Use if Upper and Lower casts are already in mounted position')
    
    resolution = IntProperty(name = 'Resolution',default = 30, min = 10, max = 50, description = 'Number of steps along each condyle to animate')
    factor = FloatProperty(name = 'Range of Motion', default = 5, min = 1, max = 8.0, description = 'Distance down condylaer inclines to use in motion')
    
    
    @classmethod
    def poll(cls, context):
        
        return True
    
    def invoke(self, context, event):
        
        if 'Articulator' in bpy.data.objects:
            art_arm = bpy.data.objects.get('Articulator')
            
            if art_arm.get('bennet_angle'):
                self.bennet_angle  =  art_arm.get('bennet_angle')
            if art_arm.get('intra_condyl_width'):
                self.intra_condyle_width = art_arm['intra_condyly_width'] 
            if art_arm.get('incisal_guidance'):
                self.incisal_guidance = art_arm['incisal_guidance']   
            if art_arm.get('canine_guidance'):
                self.canine_guidance = art_arm['canine_guidance'] 
            if art_arm.get('condyle_angle'):
                self.condyle_angle = art_arm['condyle_angle']  
            if art_arm.get('guidance_delay_ant'):
                self.guidance_delay_ant = art_arm['guidance_delay_ant']
            if art_arm.get('guidance_delay_lat'):
                self.guidance_delay_lat = art_arm['guidance_delay_lat']
            
        else:
            settings = get_settings()
        
            self.intra_condyle_width = settings.def_intra_condyle_width
            self.condyle_angle = settings.def_condyle_angle
            self.bennet_angle = settings.def_bennet_angle
        
            self.incisal_guidance = settings.def_incisal_guidance 
            self.canine_guidance = settings.def_canine_guidance
            self.guidance_delay_ant = settings.def_guidance_delay_ant
            self.guidance_delay_lat = settings.def_guidance_delay_lat
        
        return context.window_manager.invoke_props_dialog(self)
    
    
    def execute(self, context):
        tracking.trackUsage("D3Tool:GenArticulator",str((self.intra_condyle_width,
                                                         self.intra_condyle_width,
                                                         self.bennet_angle,
                                                         self.canine_guidance,
                                                         self.incisal_guidance)))
        context.scene.frame_start = 0
        context.scene.frame_end = 3 * self.resolution
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
        
        v0 = Vector((0,-.5 * self.guidance_delay_lat, 0))
        v1 = v0 + Vector((self.guidance_delay_ant, 0, 0))
        v2 = v1 + 15 * ant_guidance
        
        v3 = Vector((0,.5 * self.guidance_delay_lat, 0))
        v4 = v3 + Vector((self.guidance_delay_ant, 0, 0))
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
        #d.expression = "threeway_envelope_r(frame) * " + str(self.range_of_motion)[0:3]
        
        cfactor = min(8.0, self.factor/8.0)
        d.expression = 'threeway_envelope_r(frame,'  + str(cfactor)[0:4] + ',' + str(self.resolution) + ')'
        
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
        #d.expression = "threeway_envelope_l(frame) * " + str(self.range_of_motion)[0:3]
        d.expression = 'threeway_envelope_l(frame,'  + str(cfactor)[0:4] + ',' + str(self.resolution) + ')'
        
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
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        maxilla = splint.get_maxilla()
        Maxilla = bpy.data.objects.get(maxilla)
        if Maxilla:
            for ob in context.scene.objects:
                ob.select = False
            Maxilla.hide = False
            context.scene.objects.active = Maxilla
            Maxilla.select = True
        #bpy.ops.view3d.viewnumpad(type = 'RIGHT')
        
        bpy.ops.d3splint.enable_articulator_visualizations()
        
        #save settings to object
        art_arm['bennet_angle'] = self.bennet_angle
        art_arm['intra_condyle_width'] = self.intra_condyle_width
        art_arm['incisal_guidance'] = self.incisal_guidance 
        art_arm['canine_guidance'] =  self.canine_guidance
        art_arm['condyle_angle'] =  self.condyle_angle
        art_arm['guidance_delay_ant'] = self.guidance_delay_ant
        art_arm['guidance_delay_lat'] = self.guidance_delay_ant
        splint.ops_string += 'GenArticulator:'
        
        if not self.auto_mount:
            return {'FINISHED'}
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        
        mandible = splint.get_mandible()
        Mandible = bpy.data.objects.get(mandible)
        

        if Mandible:
            
        
            Mandible.hide = False    
            cons = Mandible.constraints.new(type = 'CHILD_OF')
            cons.target = art_arm
            cons.subtarget = 'Mandibular Bow'
        
            mx = art_arm.matrix_world * art_arm.pose.bones['Mandibular Bow'].matrix
            cons.inverse_matrix = mx.inverted()
        
        #write the lower jaw BVH to cache for fast ray_casting
        OppModel = bpy.data.objects.get(splint.opposing)
        if OppModel != None:
            bme = bmesh.new()
            bme.from_mesh(OppModel.data)    
            bvh = BVHTree.FromBMesh(bme)
            splint_cache.write_mesh_cache(OppModel, bme, bvh)
        
        
            
        return {'FINISHED'}

    
    


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
    
    resolution = IntProperty(name = "Condyle Steps", default = 30, min = 10, max = 50, description = 'Number of steps to divide the condylar path into.  More gives smoother surface')
    
    range_of_motion = FloatProperty(name = "Range of Motion", default = 5, min = 1.0, max = 8.0, description = 'Length in mm to move along the condylar paths')
    
    use_relax = BoolProperty(name = 'Use Relax Ramp', default = False)
    relax_ramp_length = FloatProperty(name = 'Relax Ramp Length', min = 0.1, max = 2.0, description = 'Length of condylar path to animate, typically .2 to 1.0', default = 0.8)
    
    
    
    @classmethod
    def poll(cls, context):
        
        if 'Articulator' not in bpy.data.objects:
            return False
        
        return True
    
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
      
    def execute(self, context):
        
        factor = min(1, self.range_of_motion/8)
        factor_r = min(2, self.relax_ramp_length/2)
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
            #double resolution
            dl.expression = '.2 + .8 * abs(sin(pi * frame/' + str(4 * self.resolution)[0:4] +  ')) * ' + str(factor)[0:4]
            dr.expression = '.2 + .8 * abs(sin(pi * frame/' + str(4 * self.resolution)[0:4] +  ')) * ' + str(factor)[0:4]
           
           
            context.scene.frame_start = 0
            context.scene.frame_end = 2 * self.resolution
           
           
        elif self.mode == 'RIGHT_EXCURSION':
            #double resolution
            dr.expression = '.2'
            dl.expression = '.2 + .8 * abs(sin(pi * frame/' + str(4 * self.resolution)[0:4] +  ')) * ' + str(factor)[0:4]
            context.scene.frame_start = 0
            context.scene.frame_end = context.scene.frame_end = 2 * self.resolution
            
            
        elif self.mode == 'LEFT_EXCURSION':
            #double resolution
            dr.expression = '.2 + .8 * abs(sin(pi * frame/' + str(4 * self.resolution)[0:4] +  ')) * ' + str(factor)[0:4]
            dl.expression = '.2'
            context.scene.frame_start = 0
            context.scene.frame_end = context.scene.frame_end = 2 * self.resolution
            
            
        elif self.mode == 'RELAX_RAMP':
            #double resolution
            dr.expression = '.2 - .2 * abs(sin(pi * frame/' + str(4 * self.resolution)[0:4] + ')) * ' + str(factor_r)[0:4]
            dl.expression = '.2 - .2 * abs(sin(pi * frame/' + str(4 * self.resolution)[0:4] + ')) * ' + str(factor_r)[0:4]
            context.scene.frame_start = 0
            context.scene.frame_end = 2 * self.resolution
            
        elif self.mode == '3WAY_ENVELOPE':
            
            if 'threeway_envelope_r' not in bpy.app.driver_namespace:
                bpy.app.driver_namespace['threeway_envelope_r'] = three_way_envelope_r
            if 'threeway_envelope_l' not in bpy.app.driver_namespace:
                bpy.app.driver_namespace['threeway_envelope_l'] = three_way_envelope_l
            
            dl.expression = 'threeway_envelope_l(frame,'  + str(factor) + ',' + str(self.resolution)[0:4] + ')'
            dr.expression = 'threeway_envelope_r(frame,'  + str(factor) + ',' + str(self.resolution)[0:4] + ')'
        
            context.scene.frame_start = 0
            context.scene.frame_end = 3 * self.resolution
            
            
                
        elif self.mode == 'FULL_ENVELOPE':
            #full_envelope_with_relax(frame, condy_length, resolution, use_relax, relax_length, right_left) 
            if 'full_envelope_with_relax' not in bpy.app.driver_namespace:
                bpy.app.driver_namespace['full_envelope_with_relax'] = full_envelope_with_relax
            
            variables = [str(self.range_of_motion)[0:4], str(self.resolution), str(self.use_relax), str(self.relax_ramp_length)[0:4]]
            
            variables_r = ','.join(variables) + ',"R"'
            variables_l = ','.join(variables) + ',"L"'
            
            
            dr.expression = "full_envelope_with_relax(frame," + variables_r + ')'
            dl.expression = "full_envelope_with_relax(frame," + variables_l + ')'
        
            print(dr.expression)
            print(dl.expression)
            context.scene.frame_start = 0
            context.scene.frame_end = self.resolution * (self.resolution +1)
            
        return {'FINISHED'}


class D3SPLINT_OT_splint_open_pin_on_articulator(bpy.types.Operator):
    """Open Pin on Articulator.  Pin increments are assumed 1mm at 85mm from condyles"""
    bl_idname = "d3splint.open_pin_on_articulator"
    bl_label = "Change Articulator Pin"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    amount = FloatProperty(name = 'Pin Setting', default = 0.5, step = 10, min = -3.0, max = 6.0)
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
    
        context.space_data.show_manipulator = True
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

class D3SPLINT_OT_articulator_view(bpy.types.Operator):
    """View the scene in a way that makes sense for assessing articulation"""
    bl_idname = "d3splint.articulator_view"
    bl_label = "Articulator VIew"
    bl_options = {'REGISTER', 'UNDO'}
    
    

    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        if not len(context.scene.odc_splints):
            return {'CANCELLED'}
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        Articulator = bpy.data.objects.get('Articulator')
        
        Max = bpy.data.objects.get(splint.get_maxilla())
        Mand = bpy.data.objects.get(splint.get_mandible())
        
        for ob in bpy.data.objects:
            ob.hide = True
        if Articulator:
            Articulator.hide = False
        if Max:
            Max.hide = False
        if Mand:
            Mand.hide = False
            
        return {'FINISHED'}
        
        
class D3SPLINT_OT_splint_create_functional_surface(bpy.types.Operator):
    """Create functional surface using envelope of motion on articulator"""
    bl_idname = "d3splint.splint_animate_articulator"
    bl_label = "Animate on Articulator"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    
    modes = ['PROTRUSIVE', 'RIGHT_EXCURSION', 'LEFT_EXCURSION', 'RELAX_RAMP', '3WAY_ENVELOPE','FULL_ENVELOPE']
    mode_items = []
    for m in modes:
        mode_items += [(m, m, m)]
        
    mode = EnumProperty(name = 'Articulator Mode', items = mode_items, default = 'FULL_ENVELOPE')
    resolution = IntProperty(name = 'Resolution', description = "Number of steps along the condyle to create surface.  10-40 is reasonable.  Larger = Slower", default = 20)
    range_of_motion = FloatProperty(name = 'Range of Motion', min = 2, max = 8, description = 'Distance to allow translation down condyles', default = 0.8)
    use_relax = BoolProperty(name = 'Use Relax Ramp', default = False)
    relax_ramp_length = FloatProperty(name = 'Relax Ramp Length', min = 0.1, max = 2.0, description = 'Length of condylar path to animate, typically .2 to 1.0', default = 0.8)
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def invoke(self, context, event):
        
        settings = get_settings()
        
        self.resolution = settings.def_condylar_resolution
        self.range_of_motion = settings.def_range_of_motion
        
        return context.window_manager.invoke_props_dialog(self)
        
    def execute(self, context):
        splint = context.scene.odc_splints[0]
        Model = bpy.data.objects.get(splint.opposing)
        Master = bpy.data.objects.get(splint.model)
        
        Art = bpy.data.objects.get('Articulator')
        
        if Model == None:
            self.report({'ERROR'}, 'No Opposing Model')
            return {'CANCELLED'}
        
        if Art == None:
            self.report({'ERROR'}, 'You need to Generate Articulator or set initial articulator values first')
            return {'CANCELLED'}
        
        
        if not splint_cache.is_object_valid(Model):
            splint_cache.clear_mesh_cache()
            bme = bmesh.new()
            
            bme.from_mesh(Model.data)    
            bme.faces.ensure_lookup_table()
            bme.verts.ensure_lookup_table()
            
            bvh = BVHTree.FromBMesh(bme)
            splint_cache.write_mesh_cache(Model, bme, bvh)
        
        
        bpy.ops.d3splint.articulator_mode_set(mode = self.mode, 
                                              resolution = self.resolution, 
                                              range_of_motion = self.range_of_motion, 
                                              use_relax = self.use_relax,
                                              relax_ramp_length = self.relax_ramp_length)
        
        #filter the occlusal surface verts
        Plane = bpy.data.objects.get('Dynamic Occlusal Surface')
        if Plane == None:
            self.report({'ERROR'}, 'Need to mark occlusal curve on opposing object to get reference plane')
            return {'CANCELLED'}
        
        Shell = bpy.data.objects.get('Splint Shell')
        if Shell == None:
            self.report({'WARNING'}, 'There is no splint shell, however this OK.')
            
        if Shell:
            
            if len(Shell.modifiers):
                Shell.select = True
                Shell.hide = False
                context.scene.objects.active = Shell
                
                for mod in Shell.modifiers:
                    bpy.ops.object.modifier_apply(modifier = mod.name)
            
            bme = bmesh.new()
            bme.from_mesh(Plane.data)
            bme.verts.ensure_lookup_table()
            
            #reset occusal plane if animate articulator has happened already
            if "AnimateArticulator" in splint.ops_string:
                for v in bme.verts:
                    v.co[2] = 0
                
            mx_p = Plane.matrix_world
            imx_p = mx_p.inverted()
            
            mx_s = Shell.matrix_world
            imx_s = mx_s.inverted()
            
            keep_verts = set()
            if splint.jaw_type == 'MAXILLA':
                Z = Vector((0,0,1))
            else:
                Z = Vector((0,0,-1))
            for v in bme.verts:
                ray_orig = mx_p * v.co
                ray_target = mx_p * v.co + 5 * Z
                ok, loc, no, face_ind = Shell.ray_cast(imx_s * ray_orig, imx_s * ray_target - imx_s*ray_orig)
            
                if ok:
                    keep_verts.add(v)
        
            print('there are %i keep verts' % len(keep_verts))
            front = set()
            for v in keep_verts:
        
                immediate_neighbors = [ed.other_vert(v) for ed in v.link_edges if ed.other_vert(v) not in keep_verts]
            
                front.update(immediate_neighbors)
                front.difference_update(keep_verts)
            
            keep_verts.update(front)
        
            for i in range(0,10):
                new_neighbors = set()
                for v in front:
                    immediate_neighbors = [ed.other_vert(v) for ed in v.link_edges if ed.other_vert(v) not in front]
                    new_neighbors.update(immediate_neighbors)
                    
                keep_verts.update(front)
                front = new_neighbors
                
            delete_verts = [v for v in bme.verts if v not in keep_verts]
            bmesh.ops.delete(bme, geom = delete_verts, context = 1)
            bme.to_mesh(Plane.data)
        
        
        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                ob.hide = True
            elif ob.type == 'CURVE':
                ob.hide = True
                
        Model.hide = False
        Master.hide = False
        Plane.hide = False
        

        tracking.trackUsage("D3Splint:CreateSurface",None)
        context.scene.frame_current = -1
        context.scene.frame_current = 0
        splint.ops_string += 'AnimateArticulator:'
        print('adding the handler!')
        
        handlers = [hand.__name__ for hand in bpy.app.handlers.frame_change_pre]
        
        if occlusal_surface_frame_change.__name__ not in handlers:
            bpy.app.handlers.frame_change_pre.append(occlusal_surface_frame_change)
        
        else:
            print('handler already in there')
        
        context.space_data.show_backface_culling = False    
        bpy.ops.screen.animation_play()
        
        return {'FINISHED'}
    


class D3SPLINT_OT_splint_reset_functional_surface(bpy.types.Operator):
    """Flatten the Functional Surface and Re-Set it"""
    bl_idname = "d3splint.reset_functional_surface"
    bl_label = "Reset Functional Surface"
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
        splint = context.scene.odc_splints[n]
        
        #filter the occlusal surface verts
        Plane = bpy.data.objects.get('Dynamic Occlusal Surface')
        if Plane == None:
            self.report({'ERROR'}, 'Need to mark occlusal curve on opposing object to get reference plane')
            return {'CANCELLED'}
        
        bme_shell = bmesh.new()
        
        bme = bmesh.new()
        bme.from_mesh(Plane.data)
        bme.verts.ensure_lookup_table()
        
        #reset occusal plane if animate articulator has happened already
        
        for v in bme.verts:
            v.co[2] = 0
        
            
            
        bme.to_mesh(Plane.data)
        Plane.data.update()
        return {'FINISHED'}
    
    
   
class D3SPLINT_OT_splint_restart_functional_surface(bpy.types.Operator):
    """Turn the functional surface calculation on"""
    bl_idname = "d3splint.start_surface_calculation"
    bl_label = "Start Surface Calculation"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        tracking.trackUsage("D3Splint:RestartFunctionalSurface",None)
        print('removing the handler')
        
        
        handlers = [hand.__name__ for hand in bpy.app.handlers.frame_change_pre]
        
        if occlusal_surface_frame_change.__name__ not in handlers:
        
            bpy.app.handlers.frame_change_pre.append(occlusal_surface_frame_change)
        
        else:
            print('alrady added')
            
        return {'FINISHED'}
    
    
class D3SPLINT_OT_splint_stop_functional_surface(bpy.types.Operator):
    """Stop functional surface calculation to improve responsiveness"""
    bl_idname = "d3splint.stop_surface_calculation"
    bl_label = "Stop Surface Calculation"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        tracking.trackUsage("D3Splint:StopFunctionalSurface",None)
        print('removing the handler')
        
        
        handlers = [hand.__name__ for hand in bpy.app.handlers.frame_change_pre]
        
        if occlusal_surface_frame_change.__name__ in handlers:
        
            bpy.app.handlers.frame_change_pre.remove(occlusal_surface_frame_change)
        
        else:
            print('alrady removed')
            
        return {'FINISHED'}
        
def register():
    bpy.utils.register_class(D3SPLINT_OT_generate_articulator)
    bpy.utils.register_class(D3SPLINT_OT_articulator_view)
    bpy.utils.register_class(D3Splint_OT_articulator_set_mode)
    bpy.utils.register_class(D3SPLINT_OT_splint_open_pin_on_articulator)
    bpy.utils.register_class(D3SPLINT_OT_recover_mandible_mounting)
    bpy.utils.register_class(D3SPLINT_OT_splint_create_functional_surface)
    bpy.utils.register_class(D3SPLINT_OT_splint_stop_functional_surface)
    bpy.utils.register_class(D3SPLINT_OT_splint_restart_functional_surface)
    bpy.utils.register_class(D3SPLINT_OT_splint_reset_functional_surface)
    
    
def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_generate_articulator)
    bpy.utils.unregister_class(D3SPLINT_OT_articulator_view)
    bpy.utils.unregister_class(D3Splint_OT_articulator_set_mode)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_open_pin_on_articulator)
    bpy.utils.unregister_class(D3SPLINT_OT_recover_mandible_mounting)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_create_functional_surface)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_stop_functional_surface)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_restart_functional_surface)
    bpy.utils.unregister_class(D3SPLINT_OT_splint_reset_functional_surface)
    
if __name__ == "__main__":
    register()