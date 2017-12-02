'''
Created on Nov 25, 2017

@author: Patrick
'''
import bpy
from mathutils import Vector, Matrix, Quaternion
from bmesh_fns import join_objects


class D3Splint_place_text_on_model(bpy.types.Operator):
    """Place Custom Text at 3D Cursor on template Box"""
    bl_idname = "d3splint.place_text_on_model"
    bl_label = "Custom Label"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    message = bpy.props.StringProperty(default = '')
    font_size = bpy.props.FloatProperty(default = 3.0, description = "Text Size", min = 1, max = 7)
    depth = bpy.props.FloatProperty(default = 1.0, description = "Text Depth", min = .2, max = 7)
    
    align_y = ['BOTTOM', 'CENTER', 'TOP']
    items_align_y = []
    for index, item in enumerate(align_y):
        items_align_y.append((item, item, item))
       
    y_align = bpy.props.EnumProperty(items = items_align_y, name = "Vertical Alignment", default = 'BOTTOM')
    align_x = ['LEFT', 'CENTER', 'RIGHT']
    items_align_x = []
    for index, item in enumerate(align_x):
        items_align_x.append((item, item, item))
    x_align = bpy.props.EnumProperty(items = items_align_x, name = "Horizontal Alignment", default = 'LEFT')
    
    invert = bpy.props.BoolProperty(default = False, description = "Mirror text")
    spin = bpy.props.BoolProperty(default = False, description = "Spin text 180")
    @classmethod
    def poll(cls, context):
        
        return True
            
    
    def invoke(self, context, event):
        
        
        return context.window_manager.invoke_props_dialog(self)

        
    def execute(self, context):
        context.scene.update()
        
    
        
        t_base = context.object
        #t_base = context.object
        
        mx = t_base.matrix_world
        imx = t_base.matrix_world.inverted()
        mx_norm = imx.transposed().to_3x3()
        
        cursor_loc = context.scene.cursor_location
        
        ok, new_loc, no, ind = t_base.closest_point_on_mesh(imx * cursor_loc)
        
        v3d = context.space_data
        rv3d = v3d.region_3d
        vrot = rv3d.view_rotation  
        
        
        X = vrot * Vector((1,0,0))
        Y = vrot * Vector((0,1,0))
        Z = vrot * Vector((0,0,1))
        
        #currently, the base should not be scaled or rotated...but perhaps it may be later
        #x = mx_norm * x
        #y = mx_norm * y
        #z = mx_norm * z    
        
        #if self.spin:
        #    x *= -1
        #    y *= -1
        
        if 'Emboss Boss' in bpy.data.curves:    
            txt_crv = bpy.data.curves.get('Emboss Boss')
            txt_ob = bpy.data.objets.get('Emboss Boss')
            txt_crv.body = self.message
        
        else:
            txt_crv = bpy.data.curves.new('Emboss Boss', type = 'FONT')
            txt_crv.body = self.message
        
        
            txt_crv.align_x = 'LEFT'
            txt_crv.align_y = 'BOTTOM'
            txt_ob = bpy.data.objects.new('Emboss Boss', txt_crv)
            context.scene.objects.link(txt_ob)
            
        #txt_crv.extrude = 1
        txt_crv.size = self.font_size
        txt_crv.resolution_u = 5
        #txt_crv.offset = .02  #thicken up the letters a little
        
        txt_ob.update_tag()
        
        context.scene.update()
        
        #handle the alignment
        translation = mx * new_loc
        
        bb = txt_ob.bound_box
        max_b = max(bb, key = lambda x: Vector(x)[1])
        max_y = max_b[1]
        
        if self.x_align == 'CENTER':
            delta_x = 0.5 * txt_ob.dimensions[0]
            if (self.spin and self.invert) or (self.invert and not self.spin):
                translation = translation + delta_x * X
            else:
                translation = translation - delta_x * X           
        elif self.x_align == 'RIGHT':
            delta_x = txt_ob.dimensions[0]
            
            if self.invert:
                translation = translation + delta_x * X 
            else:
                translation = translation - delta_x * X 
            
        if self.y_align == 'CENTER':
            delta_y = 0.5 * max_y
            translation = translation - delta_y * Y
        elif self.y_align == 'TOP':
            delta_y = max_y
            translation = translation - delta_y * Y
        #build the rotation matrix which corresponds
        R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
        R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
        R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2]
        R = R.to_4x4()

        S = Matrix.Identity(4)
        
        if self.invert:
            S[0][0] = -1
              
        T = Matrix.Translation(translation)
        
        txt_ob.matrix_world = T * R * S
        mod = txt_ob.modifiers.new('Shrinkwrap', type = 'SHRINKWRAP')
        mod.wrap_method = 'PROJECT'
        mod.use_project_z = True
        mod.use_negative_direction = True
        mod.use_positive_direction = True
        mod.target = context.object
        
        tmod = txt_ob.modifiers.new('Triangulate', type = 'TRIANGULATE')
        
        smod = txt_ob.modifiers.new('Smooth', type = 'SMOOTH')
        smod.use_x = False
        smod.use_y = False
        smod.use_z = True
        smod.factor = 1
        smod.iterations = 2000
        
        
        solid = txt_ob.modifiers.new('Solidify', type = 'SOLIDIFY')
        solid.thickness = self.depth
        solid.offset = 0
                   
        return {"FINISHED"}


class D3Splint_emboss_text_on_model(bpy.types.Operator):
    """Joins all emboss text label objects and boolean add/subtraction from the object"""
    bl_idname = "d3tool.remesh_and_emboss_text"
    bl_label = "Emboss Text Into Object"
    bl_options = {'REGISTER', 'UNDO'}
    
    positive = bpy.props.BoolProperty(default = True, description = 'Add text vs subtract text')
    
    @classmethod
    def poll(cls, context):
        
        return True
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    
    def execute(self, context):
        

        labels = [ob for ob in bpy.data.objects if ob.type == 'FONT' and 'Emboss' in ob.name]
        
        if len(labels) == 0:
            self.report({'ERROR'}, 'Need to add Emboss like a Boss text')
            return {'CACELLED'}
        
        ob0 = labels[0]
        
        if len(ob0.modifiers) == 0 and 'Shrinkwrap' not in ob0.modifiers:
            self.report({'WARNING'}, 'No idea which model to emboss upon, choosing context')
            
            if not context.object:
                self.report({'ERROR'}, 'No idea what object and no selected object')
                return {'CANCELLED'}
            elif context.object.type != 'MESH':
                self.report({'ERROR'}, 'No idea what object and selected object is not MESH type')
                return {'CANCELLED'}
            
            model = context.object
        else:
            model = ob0.modifiers.get('Shrinkwrap').target
            
        all_obs = [ob.name for ob in bpy.data.objects]
        
        bpy.ops.object.select_all(action = 'DESELECT')
        for ob in labels:
            
            bpy.ops.object.select_all(action = 'DESELECT')
            ob.select = True
            ob.hide = False
            context.scene.objects.active = ob
            
            old_obs = [eob.name for eob in bpy.data.objects]
            
            bpy.ops.object.convert(target='MESH', keep_original=True)
            ob.select = False
            
            new_ob = [eob for eob in bpy.data.objects if eob.name not in old_obs][0]
            
            new_ob.select = True
            context.scene.objects.active = new_ob
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.mesh.select_all(action = 'SELECT')
            bpy.ops.mesh.remove_doubles()
            bpy.ops.mesh.separate(type = 'LOOSE')
            bpy.ops.object.mode_set(mode = 'OBJECT')
            bpy.ops.object.origin_set(type = 'ORIGIN_GEOMETRY', center = 'BOUNDS')
            
    
        labels_new = [ob for ob in bpy.data.objects if ob.name not in all_obs]    
        for ob in labels_new:
            mod = ob.modifiers.new('Remesh', type = 'REMESH')
            mod.octree_depth = 5
            ob.update_tag()
        
        context.scene.update()
        label_final = join_objects(labels_new, name = 'Text Labels')
        
        for ob in labels_new:
            bpy.ops.object.select_all(action = 'DESELECT')
            context.scene.objects.unlink(ob)
            me = ob.data
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(me)
             
        context.scene.objects.link(label_final)
        
        label_final.select = True
        context.scene.objects.active = label_final
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.mesh.select_all(action = 'SELECT')
        bpy.ops.mesh.normals_make_consistent()
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
        #subtract the whole thing from the template block
        mod = model.modifiers.new(type = 'BOOLEAN', name = 'Boolean')
        mod.solver = 'CARVE'
        mod.object = label_final
        if self.positive:
            mod.operation = 'UNION'
        else:
            mod.operation = 'DIFFERENCE'
        
        label_final.hide = True
        return {"FINISHED"}
    
def register():
    bpy.utils.register_class(D3Splint_place_text_on_model)
    bpy.utils.register_class(D3Splint_emboss_text_on_model)
   
def unregister():
    bpy.utils.unregister_class(D3Splint_place_text_on_model)
    bpy.utils.unregister_class(D3Splint_emboss_text_on_model)