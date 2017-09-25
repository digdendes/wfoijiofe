'''
Created on Apr 22, 2017

@author: Patrick

make blender key map match Blue Sky Bio
http://blendervisionpro.blogspot.com/2015/03/viewport-navigation-without-middle.html

#undo, redo state etc
https://docs.blender.org/api/blender_python_api_current/bpy.types.Operator.html
https://blender.stackexchange.com/questions/7631/python-make-an-operator-update-ui-after-executed/7635#7635

'''
#Python Imports
import math
import os

#Blender Python Imports
import bpy
import bmesh
from mathutils import Vector, Matrix, Color
from mathutils.bvhtree import BVHTree
from io_scene_obj.import_obj import load as loadobj
from io_mesh_stl import blender_utils, stl_utils

#ODC imports
from mesh_cut import space_evenly_on_path, grow_selection_to_find_face, edge_loops_from_bmedges
from odcutils import get_settings
from bmesh_fns import join_objects

def face_neighbors_strict(bmface):
    neighbors = []
    for ed in bmface.edges:
        if not (ed.verts[0].is_manifold and ed.verts[1].is_manifold):
            if len(ed.link_faces) == 1:
                print('found an ed, with two non manifold verts')
            continue
        neighbors += [f for f in ed.link_faces if f != bmface]
        
    return neighbors

def flood_selection_by_verts(bme, selected_faces, seed_face, max_iters = 1000):
    '''
    bme - bmesh
    selected_faces - should create a closed face loop to contain "flooded" selection
    if an empty set, selection willg grow to non manifold boundaries
    seed_face - a face within/out selected_faces loop
    max_iters - maximum recursions to select_neightbors
    
    return - set of faces
    '''
    total_selection = set([f for f in selected_faces])
    levy = set([f for f in selected_faces])  #it's funny because it stops the flood :-)

    new_faces = set(face_neighbors_strict(seed_face)) - levy
    iters = 0
    while iters < max_iters and new_faces:
        iters += 1
        new_candidates = set()
        for f in new_faces:
            new_candidates.update(face_neighbors_strict(f))
            
        new_faces = new_candidates - total_selection
        
        if new_faces:
            total_selection |= new_faces    
    if iters == max_iters:
        print('max iterations reached')    
    return total_selection
#these valuse now stored in addon preferences
#space_x = 2
#space_y = 2
#border = 2
#n_columns = 6
#depth CEJ to TiBase Platform
#This is to the lowest point of the CEJ, eg, the facial
#cyl_depth = 4
#ti_base_diameter = 3.5


#widths dictionary
#https://www.slideshare.net/priyankachowdhary7/dental-anatomy-physiology-of-permanent-teeth
#cej_delta = difference in height of proximal CEJ to bucco-lingual CEJ
#tooth_data[tooth_number] = MD_width_cej, BL_width_cej, CEJ_delta_m, cej_delta_d

tooth_data = {}
tooth_data[8], tooth_data[9]   = (7.0, 6.0, 3.5, 2.5),  (7.0, 6.0, 3.5, 2.5)
tooth_data[7],tooth_data[10]   = (5.5, 4.9, 2.7, 2.0),  (5.5, 4.9, 2.7, 2.0)  #*I made these up
tooth_data[6],tooth_data[11]   = (5.5, 7.0, 2.5, 1.5),  (5.5, 7.0, 2.5, 1.5)
tooth_data[5],tooth_data[12]   = (5.0, 8.0, 1.0, 0.0),  (5.0, 8.0, 1.0, 0.0)
tooth_data[4],tooth_data[13]   = (5.0, 8.0, 1.0, 0.0),  (5.0, 8.0, 1.0, 0.0)
tooth_data[3],tooth_data[14]   = (8.0, 10.0, 1.0, 0.0), (8.0, 10.0, 1.0, 0.0)
tooth_data[2],tooth_data[15]   = (7.8, 9.8, 1.0, 0.0),  (7.8, 9.8, 1.0, 0.0)   #I made these up too
tooth_data[1],tooth_data[16]   = (7.8, 9.8, 1.0, 0.0),  (7.8, 9.8, 1.0, 0.0)   #I made these up too
tooth_data[25],tooth_data[24]  = (3.5, 5.3, 3.0, 2.0),  (3.5, 5.3, 3.0, 2.0)
tooth_data[26],tooth_data[23]  = (4.0, 5.8, 3.0, 2.0),  (4.0, 5.8, 3.0, 2.0)
tooth_data[27],tooth_data[22]  = (5.5, 7.0, 2.5, 1.5),  (5.5, 7.0, 2.5, 1.5)
tooth_data[28],tooth_data[21]  = (5.0, 6.5, 1.0, 0.0),  (5.0, 6.5, 1.0, 0.0) 
tooth_data[29],tooth_data[20]  = (5.2, 6.7, 1.0, 0.0),  (5.2, 6.7, 1.0, 0.0) # I made these up
tooth_data[30],tooth_data[19]  = (9.2, 9.0, 1.0, 0.0),  (9.2, 9.0, 1.0, 0.0)
tooth_data[31],tooth_data[18]  = (9.0, 8.8, 1.0, 0.0),  (9.0, 8.8, 1.0, 0.0)
tooth_data[32],tooth_data[17]  = (8.7, 8.6, 1.0, 0.0),  (9.0, 8.8, 1.0, 0.0)


tooth_to_text = {}
tooth_to_text[1] = 'UR8'
tooth_to_text[2] = 'UR7'
tooth_to_text[3] = 'UR6'
tooth_to_text[4] = 'UR5'
tooth_to_text[5] = 'UR4'
tooth_to_text[6] = 'UR3'
tooth_to_text[7] = 'UR2'
tooth_to_text[8] = 'UR1'
tooth_to_text[9] = 'UL1'
tooth_to_text[10] = 'UL2'
tooth_to_text[11] = 'UL3'
tooth_to_text[12] = 'UL4'
tooth_to_text[13] = 'UL5'
tooth_to_text[14] = 'UL6'
tooth_to_text[15] = 'UL7'
tooth_to_text[16] = 'UL8'            
tooth_to_text[17] = 'LL8'
tooth_to_text[18] = 'LL7'
tooth_to_text[19] = 'LL6'
tooth_to_text[20] = 'LL5'
tooth_to_text[21] = 'LL4'
tooth_to_text[22] = 'LL3'
tooth_to_text[23] = 'LL2'
tooth_to_text[24] = 'LL1'
tooth_to_text[25] = 'LR1'
tooth_to_text[26] = 'LR2'
tooth_to_text[27] = 'LR3'
tooth_to_text[28] = 'LR4'
tooth_to_text[29] = 'LR5'
tooth_to_text[30] = 'LR6'
tooth_to_text[31] = 'LR7'
tooth_to_text[32] = 'LR8'              
            
#TODO, make this an import helper
class OPENDENTAL_OT_heal_import_abutment(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "opendental.heal_import_abutment"
    bl_label = "Import Abutment File"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        
        prefs = get_settings()
        if prefs.heal_tibase_file == '':
            return False
        if context.mode != 'OBJECT':
            return False
        return True
    
    def execute(self,context):
        prefs = get_settings()
        file_path = prefs.heal_tibase_file
        
        if not os.path.exists(file_path):
            self.report({'ERROR'}, 'Must Select File abve')
            
        file_name = os.path.basename(file_path)
        
        suff =  file_name[len(file_name)-4:]
        if suff not in {'.stl', '.obj'}:
            self.report({'ERROR'}, 'Must be obj or stl format. Ply coming soon')
        
        old_obs = [ob.name for ob in bpy.data.objects]
        if suff == '.stl':
            global_matrix = Matrix.Identity(4)
            objName = bpy.path.display_name(os.path.basename(file_path))
            tris, tri_nors, pts = stl_utils.read_stl(file_path)
            tri_nors = None
            blender_utils.create_and_link_mesh(objName, tris, tri_nors, pts, global_matrix)
            
        
        elif suff == '.obj':
            loadobj(context, file_path)
            
        new_obs = [ob for ob in bpy.data.objects if ob.name not in old_obs]
        bpy.ops.object.select_all(action = 'DESELECT')
        for ob in new_obs:
            ob.select = True
            ob.name = "TiBase:Master"
            context.scene.objects.active = ob
        
        old_obs = [ob.name for ob in bpy.data.objects]
        bpy.ops.mesh.separate(type = 'LOOSE') 
        new_obs = [ob.name for ob in bpy.data.objects if ob.name not in old_obs]
        if len(new_obs):
            self.report({'WARNING'},'Multiple Objects imported, only "Tibase:Master" will be used')
            
        bpy.ops.object.origin_set(type = 'ORIGIN_GEOMETRY', center = 'BOUNDS')
        bpy.ops.object.location_clear()  
        return {'FINISHED'}

            
class OPENDENTAL_OT_heal_mark_platform(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "opendental.heal_mark_tibase_shoulder"
    bl_label = "Mark Shoulder of TiBase"
    #bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if "TiBase:Master" not in bpy.data.objects:
            return False
        return True
    
    def execute(self,context):
        
        ti_base_ob = bpy.data.objects.get('TiBase:Master')
        me = ti_base_ob.data
        
        cursor_loc = context.scene.cursor_location
        
        mx = ti_base_ob.matrix_world
        imx = mx.inverted()
        
        ok, new_loc, no, ind = ti_base_ob.closest_point_on_mesh(imx * cursor_loc)
        
        z = no
        f = ti_base_ob.data.polygons[ind]
        x = me.vertices[f.edge_keys[0][0]].co - me.vertices[f.edge_keys[0][1]].co
        x.normalize()
        y = z.cross(x)
        
        R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = x[0] ,y[0],  z[0]
        R[1][0], R[1][1], R[1][2]  = x[1], y[1],  z[1]
        R[2][0] ,R[2][1], R[2][2]  = x[2], y[2],  z[2]
        T = R.to_4x4()
        T_inv = T.inverted()    
        #undo rotation
        me.transform(T_inv)
        
        #find the z height
        platform_z = me.polygons[ind].center
        
        delta = Vector((0,0,-platform_z[2]))
        
        T = Matrix.Translation(delta)
        me.transform(T)
        
        #ti_base_ob.matrix_world = Matrix.Identity(4)
        ti_base_ob.update_tag()
        context.scene.update()
        
        bb = ti_base_ob.bound_box
        
        x_c, y_c, z_c = 0, 0, 0
        
        for i in range(0,8):
            x_c += bb[i][0]
            y_c += bb[i][1]
            z_c += bb[i][2]
        x_c *= 1/8
        y_c *= 1/8
        z_c *= 1/8
        
        cent_v = Vector((-x_c, -y_c, 0))
        T = Matrix.Translation(cent_v)
        me.transform(T)
        
        ti_base_ob.matrix_world = Matrix.Identity(4)
        context.scene.cursor_location = Vector((0,0,0))
        bpy.ops.view3d.view_center_cursor()
        bpy.ops.ed.undo_push(message = "mark shoulder")
        return {'FINISHED'}

class OPENDENTAL_OT_heal_mark_timing(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "opendental.heal_mark_tibase_timing"
    bl_label = "Mark Timing of TiBase"
    #bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if "TiBase:Master" not in bpy.data.objects:
            return False
        return True
    
    def execute(self,context):
        
        ti_base_ob = bpy.data.objects.get('TiBase:Master')
        me = ti_base_ob.data
        
        cursor_loc = context.scene.cursor_location
        
        mx = ti_base_ob.matrix_world
        imx = mx.inverted()
        
        ok, new_loc, no, ind = ti_base_ob.closest_point_on_mesh(imx * cursor_loc)
        
        y = no
        z = Vector((0,0,1))
        x = y.cross(z)
        
        R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = x[0] ,y[0],  z[0]
        R[1][0], R[1][1], R[1][2]  = x[1], y[1],  z[1]
        R[2][0] ,R[2][1], R[2][2]  = x[2], y[2],  z[2]
        T = R.to_4x4()
        T_inv = T.inverted()    
        #undo rotation
        me.transform(T_inv)
        bpy.ops.ed.undo_push(message = "mark timing")
        return {'FINISHED'}
    
class OPENDENTAL_OT_heal_remove_internal(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "opendental.heal_remove_internal"
    bl_label = "Remove Internal Geometry"
    #bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if "TiBase:Master" not in bpy.data.objects:
            return False
        return True
    
    def execute(self,context):
        
        ti_base_ob = bpy.data.objects.get('TiBase:Master')
        
        bme = bmesh.new()
        bme.from_mesh(ti_base_ob.data)
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        max_vz = max(bme.verts, key = lambda x: x.co[2])
        min_vz = min(bme.verts, key = lambda x: x.co[2])
        
        z_max = max_vz.co[2]
        z_min = min_vz.co[2]
        
        
        #remove top and bottom 0.2mm
        
        bmesh.ops.bisect_plane(bme, geom = bme.faces[:]+bme.edges[:]+bme.verts[:], 
                               plane_co = Vector((0,0,z_max - 0.2)), 
                               plane_no = Vector((0,0,1)),
                               clear_outer = True)
                               
        
        bmesh.ops.bisect_plane(bme, geom = bme.faces[:]+bme.edges[:]+bme.verts[:], 
                               plane_co = Vector((0,0,z_min + 0.2)), 
                               plane_no = Vector((0,0,-1)),
                               clear_outer = True)
        
        min_vx = min(bme.verts, key = lambda x: x.co[0]**2 + x.co[1]**2)  #smallest radii vert
        
        #todo, safety
        start_face = [f for f in min_vx.link_faces][0]
        
        interior_faces = flood_selection_by_verts(bme, set([]), start_face, 10000)
        
        if len(interior_faces) == len(bme.faces):
            err_me = bpy.data.meshes.new('Tibase:Error')
            err_ob = bpy.data.objects.new('Tibase:Error', err_me)
            
            err_ob.matrix_world = ti_base_ob.matrix_world
            bme.to_mesh(err_me)
            context.scene.objects.link(err_ob)
            
            self.report({'ERROR'},"Results attempted to delete entire object! Returning copy for inspection")
            bme.free()
            return {'CANCELLED'}
        
        bmesh.ops.delete(bme, geom = list(interior_faces), context = 5)
        
        bme.edges.ensure_lookup_table()
        bme.verts.ensure_lookup_table()
        cap_eds = [ed.index for ed in bme.edges if len(ed.link_faces) == 1]
        
        loops = edge_loops_from_bmedges(bme, cap_eds)
        
        caps = []
        for v_loop in loops:
            if v_loop[0] == v_loop[-1]:
                v_loop.pop()
            vs = [bme.verts[i] for i in v_loop]        
            
            f = bme.faces.new(vs)
            
            if f.calc_center_bounds()[2] < 0:
                print('points down')
                f.normal = Vector((0,0,-1))
            else:
                print('points up')
                f.normal = Vector((0,0,1))
            
            
            caps += [f]

        for f in caps:
            new_geom = bmesh.ops.extrude_face_region(bme, geom = [f])  
            for v in new_geom['geom']:
                if isinstance(v, bmesh.types.BMVert):
                    
                    if v.co[2] > 0:
                        v.co[2] += 0.2
                    else:
                        v.co[2] -= 0.2
        
        bmesh.ops.delete(bme, geom = caps, context = 5)                       
        #bmesh.ops.triangulate(bme, faces = caps)
        bme.faces.ensure_lookup_table()
        bmesh.ops.recalc_face_normals(bme, faces = bme.faces[:])
        
        
        bme.to_mesh(ti_base_ob.data)
        ti_base_ob.update_tag()
        context.scene.update()
        bpy.ops.ed.undo_push(message = "remove internal")
        return {'FINISHED'}


class OPENDENTAL_OT_ucla_remove_timing(bpy.types.Operator):
    """Cut's the abutment at the 3D Cursor and extrudes it downard.  Click above timing/hex and will be converted to cylinder"""
    bl_idname = "opendental.ucla_remove_timing"
    bl_label = "Remove Timing Geometry"
    #bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if "TiBase:Master" not in bpy.data.objects:
            return False
        return True
    
    def execute(self,context):
        
        
        ti_base_ob = bpy.data.objects.get('TiBase:Master')
        mx = ti_base_ob.matrix_world
        
        imx = mx.inverted()
        cursor_loc = context.scene.cursor_location
        ok, new_loc, no, ind = ti_base_ob.closest_point_on_mesh(imx * cursor_loc)
        
        bme = bmesh.new()
        bme.from_mesh(ti_base_ob.data)
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        max_vz = max(bme.verts, key = lambda x: x.co[2])
        min_vz = min(bme.verts, key = lambda x: x.co[2])
        
        z_max = max_vz.co[2]
        z_min = min_vz.co[2]
        
        
        #cut at the cursor location
        gdict = bmesh.ops.bisect_plane(bme, geom = bme.faces[:]+bme.edges[:]+bme.verts[:], 
                               plane_co = new_loc, 
                               plane_no = Vector((0,0,1)),
                               clear_inner = True)
                               
   

        
       
        cut_geom = gdict['geom_cut']
        
         
        bme.edges.ensure_lookup_table()
        bme.verts.ensure_lookup_table()
        
        cap_eds = [ele for ele in cut_geom if isinstance(ele, bmesh.types.BMEdge)]
        
        gdict = bmesh.ops.extrude_edge_only(bme, edges = cap_eds)  
    
        eds = [ed.index for ed in gdict['geom'] if isinstance(ed, bmesh.types.BMEdge)]
       
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        
        loops = edge_loops_from_bmedges(bme, eds)
        
        for vloop in loops:
            vloop.pop()
            vs = [bme.verts[i] for i in vloop]
            
            for v in vs:
                v.co[2] = z_min
        
            f = bme.faces.new(vs)
        
        #bmesh.ops.triangulate(bme, faces = caps)
        bme.faces.ensure_lookup_table()
        bmesh.ops.recalc_face_normals(bme, faces = bme.faces[:])
        
        
        bme.to_mesh(ti_base_ob.data)
        ti_base_ob.update_tag()
        context.scene.update()
        bpy.ops.ed.undo_push(message = "remove timing")
        return {'FINISHED'}
    
class OPENDENTAL_OT_heal_generate_profiles(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "opendental.heal_generate_profiles"
    bl_label = "Generate CEJ Profiles"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        
        if "TiBase:Master" not in bpy.data.objects:
            return False
        
        cejs = [ob.name for ob in bpy.data.objects if ':CEJ' in ob.name]
        if len(cejs) > 0:
            return False
        
        
        return True
    

    def execute(self, context):
        prefs = get_settings()
        
        n_columns = prefs.heal_n_cols
        border_space = prefs.heal_block_border
        inter_space = prefs.heal_inter_space_x
        cyl_depth = prefs.heal_abutment_depth
        
        ti_base_obj = bpy.data.objects['TiBase:Master']
        ti_base_diameter = ti_base_obj.dimensions[0]  #needs to be oriented correctly
        
        bme = bmesh.new()
        bme.from_mesh(ti_base_obj.data)
        new_me = bpy.data.meshes.new('UCLA_dup')
        bme.to_mesh(new_me)
        bme.free()
        
        teeth = [i+1 for i in range(0,32) if prefs.heal_teeth[i]]
        
        #now sort teeth by quadrant
        UR = [i for i in teeth if i < 9]
        UL = [i for i in teeth if i > 8 and i < 17]
        LR = [i for i in teeth if i > 24]
        LL = [i for i in teeth if i > 16 and i < 25]
        
        LR.reverse()
        LL.reverse()
        
        teeth = LR + LL + UR + UL
        
        
        if len(teeth) == 0:
            self.report({'ERROR'}, 'Need to select teeth to generate template for')
            
        n_rows = math.ceil(len(teeth)/n_columns)
        print("There should be %i rows" % n_rows)
        
        prev_y = border_space #start border space above x-axis.  May add more room for text label at bottom        
        x_border = 0

        for i in range(0,n_rows):
            
            prev_width = border_space
            
            row_height = max([tooth_data[teeth[m]][1] for m in range(i*n_columns, (i+1)*n_columns) if m < len(teeth)])
            
            print(row_height)
            
            for j in range(0,n_columns):
                n = i*n_columns + j
                if n > len(teeth) - 1: continue  #reached the end of last row
            
                tooth_number = teeth[n]
                t_data = tooth_data[tooth_number]
                
                #this will build left to right, bottom to top
                x_pos = prev_width + t_data[0]/2
                
                if x_border < prev_width + t_data[0]:
                    x_border = prev_width + t_data[0]
                
                y_pos = prev_y + row_height/2
                
                prev_width += t_data[0] + inter_space
   
                md_w = t_data[0]
                bl_w = t_data[1]
                delta_m = t_data[2]
                delta_d = t_data[3]
                
                crv_data = bpy.data.curves.new(str(tooth_number) + ":CEJ", 'CURVE')
                crv_data.splines.new('BEZIER')
                crv_data.splines[0].bezier_points[0].handle_left_type = 'AUTO'
                crv_data.splines[0].bezier_points[0].handle_right_type = 'AUTO'
                crv_data.dimensions = '3D'
                crv_obj = bpy.data.objects.new(str(tooth_number) + ":CEJ",crv_data)
                bpy.context.scene.objects.link(crv_obj)
                
                crv_data.splines[0].bezier_points.add(count = 7)
                crv_data.splines[0].use_cyclic_u = True
                    
                for k in range(0,8):
                    bp = crv_data.splines[0].bezier_points[k]
                    bp.handle_right_type = 'AUTO'
                    bp.handle_left_type = 'AUTO'
                    
                    x = md_w/2 * math.cos(k * 2*  math.pi/8)
                    y = bl_w/2 * math.sin(k * 2 * math.pi/8)
                    
                    if x > 0:
                        z = delta_m * math.cos(k * 2*  math.pi/8)**3
                    else:
                        z = -delta_d * math.cos(k * 2*  math.pi/8)**3
                    
                    #this code keeps the mesials pointed to midline
                    if tooth_number > 8 and tooth_number < 25:
                        x *= -1
                    
                    #this code keeps facial toward outside of block 
                    if tooth_number > 16:
                        y *= -1
                        
                    bp.co = Vector((x,y,z))
                
                crv_obj.location = Vector((x_pos,y_pos,cyl_depth))
                
                new_ob = bpy.data.objects.new(str(tooth_number) + ":TiBase", new_me)
                context.scene.objects.link(new_ob)
                #TODO, matrix world editing
                
                if tooth_number > 16:
                    R = Matrix.Rotation(math.pi, 4, Vector((0,0,1)))
                else:
                    R = Matrix.Identity(4)
                    
                T = Matrix.Translation(Vector((x_pos, y_pos, 0)))
                new_ob.matrix_world = T * R
                
                
            prev_y += row_height + inter_space
            
            
        
        box_y = prev_y - inter_space + border_space
        box_x = x_border + border_space
        
        #print(box_y, box_x)
        
        #old_obs = [ob.name for ob in bpy.data.objects]
        #bpy.ops.mesh.primitive_cube_add(radius = 0.5)
        #cube = [ob for ob in bpy.data.objects if ob.name not in old_obs][0]
        
        #cube.scale[0] = box_x
        #cube.scale[1] = box_y
        #cube.scale[2] = cyl_depth + 2 + 2 + 2
        
        #cube.location[0] = box_x/2
        #cube.location[1] = box_y/2
        #cube.location[2] = -cyl_depth/2 + .5
        
        #cube.draw_type = 'WIRE'
        #cube.name = 'Templates Base'
        #mod = cube.modifiers.new(type = 'BEVEL', name = 'Bevel')
        #mod.width = .05
        return {'FINISHED'}
    
    
class OPENDENTAL_OT_heal_database_curve_profiles(bpy.types.Operator):
    """please draw me?"""
    bl_idname = "opendental.heal_database_curve_profiles"
    bl_label = "Database Curve CEJ Profiles"
    bl_options = {'REGISTER', 'UNDO'}
    
    inter_space_x = bpy.props.FloatProperty(name = 'horizontal', default = 2.0)
    inter_space_y = bpy.props.FloatProperty(name = 'vertical', default = 2.0)
    middle_space_x = bpy.props.FloatProperty(name = 'middle', default = 2.0)
    cyl_depth = bpy.props.FloatProperty(name = 'depth', default = 5.0)
    
    @classmethod
    def poll(cls, context):
        
        if "TiBase:Master" not in bpy.data.objects:
            return False
        
        return True
    
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Layout and Position")
        col.prop(self, "cyl_depth")
        col.prop(self, "inter_space_x")
        col.prop(self, "inter_space_y")
        col.prop(self, "middle_space_x")
        
    def invoke(self,context, event):
        prefs = get_settings()
        
        #get initial settings form preferences default
        #load them into operator settings for undo/redo
        self.inter_space_x = prefs.heal_inter_space_x
        self.inter_space_y = prefs.heal_inter_space_y
        self.middle_space_x = prefs.heal_middle_space_x
        self.cyl_depth = prefs.heal_abutment_depth
        
        
        return self.execute(context)
        
    def execute(self, context):
        
        prefs = get_settings()
        
        inter_space_x = self.inter_space_x
        inter_space_y = self.inter_space_y
        middle_space_x = self.middle_space_x
        cyl_depth = self.cyl_depth
        
        ti_base_obj = bpy.data.objects['TiBase:Master']
        
        bme = bmesh.new()
        bme.from_mesh(ti_base_obj.data)
        new_me = bpy.data.meshes.new('UCLA_dup')
        bme.to_mesh(new_me)
        bme.free()
        
        teeth = [i+1 for i in range(0,32) if prefs.heal_teeth[i]]
        
        if len(teeth) == 0:
            self.report({'ERROR'}, 'Need to select teeth to generate templates for')
            return {'CANCELLED'}
        
        if not all([str(tooth) in bpy.data.curves for tooth in teeth]):
            self.report({'ERROR'}, 'Database templates not available, generate generic templates')
            return {'CANCELLED'}
        
        #get all the tooth_objects into the scene
        for tooth in teeth:
            new_ob = bpy.data.objects.new(str(tooth)+":CEJ", bpy.data.curves[str(tooth)])
            new_ob.matrix_world = Matrix.Identity(4)
            context.scene.objects.link(new_ob)
            
        #sort teeth by quadrant
        UR = [i for i in teeth if i < 9]
        UL = [i for i in teeth if i > 8 and i < 17]
        LR = [i for i in teeth if i > 24]
        LL = [i for i in teeth if i > 16 and i < 25]
        
        UR.reverse() #list from midlin outward
        LL.reverse()
        
        
        for i, quad in enumerate([UR, UL, LL, LR]):
            
            if i == 0:
                x_dir = Vector((-1,0,0))
                y_dir = Vector((0,1,0))
            if i == 1:
                x_dir = Vector((1,0,0))
                y_dir = Vector((0,1,0))
            if i == 2:
                x_dir = Vector((1,0,0))
                y_dir = Vector((0,-1,0))
            if i == 3:
                x_dir = Vector((-1,0,0))
                y_dir = Vector((0,-1,0))
                
            
        
            row_height = max([bpy.data.objects.get(str(tooth) +":CEJ").dimensions[1] for tooth in quad])
                    
            y_pos = y_dir * (row_height/2 + inter_space_y)
            x_pos = x_dir * (middle_space_x/2 - inter_space_x) # middle space gets added inititally
            z_pos = Vector((0,0,cyl_depth))
            
            for tooth in quad:
                
                if tooth > 16:
                    #rotate 180
                    R = Matrix.Rotation(math.pi, 4, Vector((0,0,1)))
                    print('TBA on matrices')
                else:
                    R = Matrix.Identity(4)
        
                cej_ob = bpy.data.objects.get(str(tooth)+":CEJ")
        
                x_pos = x_pos + x_dir *(inter_space_x + cej_ob.dimensions[0]/2)
        
                T = Matrix.Translation(x_pos + y_pos + z_pos)
                
                cej_ob.matrix_world = T
        
                new_ob = bpy.data.objects.new(str(tooth) + ":TiBase", new_me)
                context.scene.objects.link(new_ob)
                
                T = Matrix.Translation(x_pos + y_pos)
                new_ob.matrix_world = T * R

                x_pos = x_pos + x_dir *cej_ob.dimensions[0]/2
        
        return {'FINISHED'}
    
class OPENDENTAL_OT_heal_database_profiles(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "opendental.heal_database_profiles"
    bl_label = "Database CEJ Profiles"
    bl_options = {'REGISTER', 'UNDO'}
    
    inter_space_x = bpy.props.FloatProperty(name = 'horizontal', default = 2.0)
    inter_space_y = bpy.props.FloatProperty(name = 'vertical', default = 2.0)
    middle_space_x = bpy.props.FloatProperty(name = 'middle', default = 2.0)
    cyl_depth = bpy.props.FloatProperty(name = 'depth', default = 5.0)
    
    @classmethod
    def poll(cls, context):
        
        if "TiBase:Master" not in bpy.data.objects:
            return False
        
        return True
    
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Layout and Position")
        col.prop(self, "cyl_depth")
        col.prop(self, "inter_space_x")
        col.prop(self, "inter_space_y")
        col.prop(self, "middle_space_x")
        
    def invoke(self,context, event):
        prefs = get_settings()
        
        #get initial settings form preferences default
        #load them into operator settings for undo/redo
        self.inter_space_x = prefs.heal_inter_space_x
        self.inter_space_y = prefs.heal_inter_space_y
        self.middle_space_x = prefs.heal_middle_space_x
        self.cyl_depth = prefs.heal_abutment_depth
        
        return self.execute(context)
        
    def execute(self, context):
        prefs = get_settings()
        

        prefs = get_settings()
        
        inter_space_x = self.inter_space_x
        inter_space_y = self.inter_space_y
        middle_space_x = self.middle_space_x
        cyl_depth = self.cyl_depth

        ti_base_obj = bpy.data.objects['TiBase:Master']
                
        bme = bmesh.new()
        bme.from_mesh(ti_base_obj.data)
        new_me = bpy.data.meshes.new('UCLA_dup')
        bme.to_mesh(new_me)
        bme.free()
        
        teeth = [i+1 for i in range(0,32) if prefs.heal_teeth[i]]
        
        if len(teeth) == 0:
            self.report({'ERROR'}, 'Need to select teeth to generate template for')
            return {'CANCELLED'}
        
        if not all([str(tooth) in bpy.data.meshes for tooth in teeth]):
            self.report({'ERROR'}, 'Database templates not available, generate generic templates')
            return {'CANCELLED'}
        
        #get all the tooth_objects into the scene
        for tooth in teeth:
            new_ob = bpy.data.objects.new(str(tooth)+":CEJ", bpy.data.meshes[str(tooth)])
            new_ob.matrix_world = Matrix.Identity(4)
            context.scene.objects.link(new_ob)
            
        #sort teeth by quadrant
        UR = [i for i in teeth if i < 9]
        UL = [i for i in teeth if i > 8 and i < 17]
        LR = [i for i in teeth if i > 24]
        LL = [i for i in teeth if i > 16 and i < 25]
        
        UR.reverse() #list from midlin outward
        LL.reverse()
        
        for i, quad in enumerate([UR, UL, LL, LR]):
            
            if i == 0:
                x_dir = Vector((-1,0,0))
                y_dir = Vector((0,1,0))
            if i == 1:
                x_dir = Vector((1,0,0))
                y_dir = Vector((0,1,0))
            if i == 2:
                x_dir = Vector((1,0,0))
                y_dir = Vector((0,-1,0))
            if i == 3:
                x_dir = Vector((-1,0,0))
                y_dir = Vector((0,-1,0))
                
            
        
            row_height = max([bpy.data.objects.get(str(tooth) +":CEJ").dimensions[1] for tooth in quad])
                    
            y_pos = y_dir * (row_height/2 + inter_space_y)
            x_pos = x_dir * (middle_space_x/2 - inter_space_x) # middle space gets added inititally
            z_pos = Vector((0,0,cyl_depth))
            
            for tooth in quad:
                
                if tooth > 16:
                    #rotate 180
                    R = Matrix.Rotation(math.pi, 4, Vector((0,0,1)))
                    print('TBA on matrices')
                else:
                    R = Matrix.Identity(4)
        
                cej_ob = bpy.data.objects.get(str(tooth)+":CEJ")
        
                x_pos = x_pos + x_dir *(inter_space_x + cej_ob.dimensions[0]/2)
        
                T = Matrix.Translation(x_pos + y_pos + z_pos)
                
                cej_ob.matrix_world = T
        
                new_ob = bpy.data.objects.new(str(tooth) + ":TiBase", new_me)
                context.scene.objects.link(new_ob)
                
                T = Matrix.Translation(x_pos + y_pos)
                new_ob.matrix_world = T * R

                x_pos = x_pos + x_dir *cej_ob.dimensions[0]/2
        
        return {'FINISHED'}


class OPENDENTAL_OT_heal_mesh_convert(bpy.types.Operator):
    """Make smooth connection between CEJ and UCLA collar"""
    bl_idname = "opendental.heal_mesh_convert"
    bl_label = "Convert CEJ Curves"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    shape_factor = bpy.props.FloatProperty(name = "Shape Factor", default = 0.05, step = 1)
    
    @classmethod
    def poll(cls, context):
        
        if "TiBase:Master" not in bpy.data.objects:
            return False

        return True
    
    def execute(self, context):
        prefs = get_settings()
    
        cyl_depth = prefs.heal_abutment_depth

        cej_objects = [ob for ob in bpy.data.objects if ':CEJ' in ob.name]
        z_max = 0
        
        for ob in cej_objects:
            bb = ob.bound_box
            for v in bb:
                loc = ob.matrix_world * Vector(v)

                if loc[2] > z_max:
                    z_max = loc[2]  
            
        if len(cej_objects) == 0:
            self.report({'ERROR'},'No CEJ Profiles, generate profiles first')
            
    
        for ob in cej_objects:
            #works for curves or existing mesh
            me = ob.to_mesh(bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
            
            name = ob.name.replace(":CEJ",":TiBase")
            tibase = bpy.data.objects.get(name)
            if not tibase:
                continue
            
            bme = bmesh.new()
            bme.from_mesh(me)
            bme.edges.ensure_lookup_table()
            bme.verts.ensure_lookup_table()
            
            eds = [ed.index for ed in bme.edges]
            loops = edge_loops_from_bmedges(bme, eds)
            
            loop = loops[0]
            loop.pop()
            
            locs = [bme.verts[i].co for i in loop]
            
            
            spaced_locs, eds = space_evenly_on_path(locs, [(0,1),(1,0)], 64) #TODO...increase res a little
            
            bme.free()
            
            bme = bmesh.new()
            bme.verts.ensure_lookup_table()
            bme.edges.ensure_lookup_table()
            new_verts = []
            for co in spaced_locs:
                new_verts += [bme.verts.new(co)]
                
            bme.verts.ensure_lookup_table()
            cej_eds = []
            for ed in eds:
                cej_eds += [bme.edges.new((new_verts[ed[0]],new_verts[ed[1]]))]
            
            center = ob.matrix_world.inverted() * tibase.location
            T = Matrix.Translation(center)
            circle_data = bmesh.ops.create_circle(bme, cap_ends = False, segments = 64, diameter = tibase.dimensions[0]/2 + .1, matrix = T)
            #for bmv in circle_data['verts']:
                #bmv.co[2] -= cyl_depth
                
            circle_eds = [ed for ed in bme.edges if ed not in cej_eds]
            
            top_geom = bmesh.ops.extrude_edge_only(bme, edges = cej_eds)
            
            bottom_geom = bmesh.ops.extrude_edge_only(bme, edges = circle_eds)
            
            top_verts  = [v for v in top_geom['geom'] if isinstance(v, bmesh.types.BMVert)]
            for v in top_verts:
                v.co[2] = z_max + 2 - cyl_depth
            
            bme.faces.new(top_verts)
            
            bottom_verts = [v for v in bottom_geom['geom'] if isinstance(v, bmesh.types.BMVert)]  
            for v in bottom_verts:
                v.co[2] -= .1
            
            bme.faces.new(bottom_verts)
            
            for ed in cej_eds:
                ed.select_set(True)
            for ed in circle_eds:
                ed.select_set(True)
            
            bme.faces.ensure_lookup_table()
            bmesh.ops.recalc_face_normals(bme, faces = bme.faces)
               
            new_me = bpy.data.meshes.new(ob.name.replace('CEJ','Profile'))
            new_ob = bpy.data.objects.new(ob.name.replace('CEJ','Profile'), new_me)
            bpy.context.scene.objects.link(new_ob)
            new_ob.matrix_world = ob.matrix_world
            
            bme.to_mesh(new_me)
            bme.free()
            
            context.scene.objects.active = new_ob
            new_ob.select = True
        
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.mesh.select_all(action = 'DESELECT')
            context.tool_settings.mesh_select_mode = [False, True, False]
            bpy.ops.mesh.select_non_manifold()
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.mesh.bridge_edge_loops(number_cuts=8, 
                                    interpolation='LINEAR', 
                                    smoothness=0.5,
                                    profile_shape_factor=self.shape_factor)
                                    
            bpy.ops.object.mode_set(mode = 'OBJECT')
            
               
        return {"FINISHED"}
    
class OPENDENTAL_OT_heal_generate_box(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "opendental.heal_generate_box"
    bl_label = "Generate Box"
    bl_options = {'REGISTER', 'UNDO'}
    
    bottom_trim = bpy.props.FloatProperty(name = "Bottom Trim", default = .001)
    bevel_width = bpy.props.FloatProperty(name = "Bevel Width", default = 3)
    
    border_x = bpy.props.FloatProperty(name = "Horizontal Border", default = 2)
    border_y = bpy.props.FloatProperty(name = "Vertical Border", default = 5)
    
    @classmethod
    def poll(cls, context):
        profs = [ob.name for ob in bpy.data.objects if 'Profile' in ob.name]
        if len(profs) == 0:
            return False
        return True
    
    def invoke(self, context, event):
        prefs = get_settings()
        
        self.bevel_width = prefs.heal_bevel_width
        self.border_x = prefs.heal_block_border_x
        self.border_y = prefs.heal_block_border_y
        
        return self.execute(context)
        
    def execute(self, context):
    
        profile_obs = [ob for ob in bpy.data.objects if 'Profile' in ob.name]
        base_obs = [ob for ob in bpy.data.objects if ":TiBase" in ob.name] #notice master is TiBase:Master
        
        prefs = get_settings()
        
        start_bb = profile_obs[0].bound_box
        mx = profile_obs[0].matrix_world
        start = mx * Vector(start_bb[0])
        x_max, y_max, z_max = start[0], start[1], start[2]
        x_min, y_min, z_min = start[0], start[1], start[2]
        
        for ob in profile_obs:
            bb = ob.bound_box
            for v in bb:
                loc = ob.matrix_world * Vector(v)
                if loc[0] > x_max:
                    x_max = loc[0]
                if loc[1] > y_max:
                    y_max = loc[1]
                if loc[2] > z_max:
                    z_max = loc[2]
                    
                if loc[0] < x_min:
                    x_min = loc[0]
                if loc[1] < y_min:
                    y_min = loc[1]
                
        for ob in base_obs:
            bb = ob.bound_box
            for v in bb:
                loc = ob.matrix_world * Vector(v)
                if loc[2] < z_min:
                    z_min = loc[2]    
                    
        box_top = z_max - 1.89  #epsilon
        box_bottom = z_min + self.bottom_trim
        
        box_x = x_max + self.border_x
        box_y = y_max + self.border_y
        
        box_x_min = x_min - self.border_x
        box_y_min = y_min - self.border_y
        
        old_obs = [ob.name for ob in bpy.data.objects]
        bpy.ops.mesh.primitive_cube_add(radius = 0.5, location = Vector((0,0,0)))
        cube = [ob for ob in bpy.data.objects if ob.name not in old_obs][0]
        cube.name = "Templates Base"
        me = cube.data
        
        me.vertices[0].co = Vector((box_x_min,box_y_min, box_bottom))
        me.vertices[1].co = Vector((box_x_min,box_y_min,box_top))
        me.vertices[2].co = Vector((box_x_min, box_y,box_bottom))
        me.vertices[3].co = Vector((box_x_min ,box_y, box_top))
        me.vertices[4].co = Vector((box_x, box_y_min, box_bottom))
        me.vertices[5].co =Vector((box_x, box_y_min, box_top))
        me.vertices[6].co = Vector((box_x, box_y, box_bottom ))
        me.vertices[7].co = Vector((box_x, box_y, box_top))
        
        for v in me.vertices:
            v.select = False
        for ed in me.edges:
            ed.select = False
            
        for f in me.polygons:
            f.select = False
            
        context.tool_settings.mesh_select_mode = [False, True, False]
        
        inds = [0,1,3,4,6,7,9,10]
        
        for ind in inds:
            me.edges[ind].select = True

        context.scene.objects.active = cube
        bpy.ops.object.select_all(action = 'DESELECT')
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.mesh.bevel(offset_type = "OFFSET", offset = self.bevel_width)
        
        bpy.ops.mesh.select_all(action = 'SELECT')
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
        if "Box Mat" not in bpy.data.materials:
            mat = bpy.data.materials.new('Box Mat')
            mat.diffuse_color = Color((0.08, .08, .8))
        else:
            mat = bpy.data.materials.get('Box Mat')
        
        # Assign it to object
        if cube.data.materials:
            # assign to 1st material slot
            cube.data.materials[0] = mat
        else:
            # no slots
            cube.data.materials.append(mat)    
        
        mod = cube.modifiers.new('Remesh', type = 'REMESH')
        mod.octree_depth = 6
        mod.sharpness = 1
          
        return {"FINISHED"}    

class OPENDENTAL_OT_heal_generate_text(bpy.types.Operator):
    """Generate Label above/below the UCLA wells"""
    bl_idname = "opendental.heal_generate_text"
    bl_label = "Generate Labels"
    bl_options = {'REGISTER', 'UNDO'}
    
    font_size = bpy.props.FloatProperty(default = 3.0, description = "Text Size")
    
    @classmethod
    def poll(cls, context):
        profs = [ob.name for ob in bpy.data.objects if 'Profile' in ob.name]
        if len(profs) == 0:
            return False
        return True
    

    def execute(self, context):
    
        profile_obs = [ob for ob in bpy.data.objects if 'Profile' in ob.name]
        prefs = get_settings
        #goal is 5mm x 5mm text?
        
        ys = []
    
        for ob in profile_obs:
            bb = ob.bound_box
            for v in bb:
                loc = ob.matrix_world * Vector(v)
                ys += [loc[1]]
        
        max_y = max(ys)
        min_y = min(ys)
        
        zs = []
        t_base = bpy.data.objects.get('Templates Base')
        bb = t_base.bound_box
        for v in bb:
            loc = t_base.matrix_world * Vector(v)
            zs += [loc[2]]
            
        max_z = max(zs)
        
        for ob in profile_obs:
            a = len(ob.name) - 8
            name = ob.name[0:a]
            msg = tooth_to_text[int(name)]
            
            txt_crv = bpy.data.curves.new(name + ':Label', type = 'FONT')
            txt_crv.body = msg
            txt_crv.align_x = 'CENTER'
            txt_ob = bpy.data.objects.new(name + ':Label', txt_crv)
            
            txt_crv.extrude = 1
            txt_crv.size = self.font_size
            txt_crv.resolution_u = 5
            txt_crv.offset = .02  #thicken up the letters a little
            context.scene.objects.link(txt_ob)
            txt_ob.update_tag()
            context.scene.update()
                   
            if int(name) > 16:
                y = min_y - 1 - txt_ob.dimensions[1]
            else:
                y = max_y + 1
                

            txt_ob.parent = ob
            txt_ob.matrix_world = Matrix.Translation(Vector((ob.location[0], y, max_z)))
                
        return {"FINISHED"}

class OPENDENTAL_OT_heal_custom_text(bpy.types.Operator):
    """Place Custom Text at 3D Cursor on template Box"""
    bl_idname = "opendental.heal_custom_text"
    bl_label = "Custom Label"
    bl_options = {'REGISTER', 'UNDO'}
    
    font_size = bpy.props.FloatProperty(default = 3.0, description = "Text Size")
    
    align_y = ['BOTTOM', 'CENTER', 'TOP']
    items_align_y = []
    for index, item in enumerate(align_y):
        items_align_y.append((item, item, item))
    
    print(items_align_y)    
    y_align = bpy.props.EnumProperty(items = items_align_y, name = "Vertical Alignment", default = 'BOTTOM')
    
    
    align_x = ['LEFT', 'CENTER', 'TOP']
    items_align_x = []
    for index, item in enumerate(align_x):
        items_align_x.append((item, item, item))
    x_align = bpy.props.EnumProperty(items = items_align_x, name = "Horizontal Alignment", default = 'LEFT')
    
    @classmethod
    def poll(cls, context):
        
        if "Templates Base" not in bpy.data.objects:
            return False
        return True
            
    def execute(self, context):
        context.scene.update()
        
        prefs = get_settings()
        
        t_base = bpy.data.objects.get("Templates Base")
        #t_base = context.object
        
        mx = t_base.matrix_world
        imx = t_base.matrix_world.inverted()
        mx_norm = imx.transposed().to_3x3()
        
        cursor_loc = context.scene.cursor_location
        
        ok, new_loc, no, ind = t_base.closest_point_on_mesh(imx * cursor_loc)
        
        X = Vector((1,0,0))
        Y = Vector((0,1,0))
        Z = Vector((0,0,1))
        
        #figure out which face the cursor is on
        direct = [no.dot(X), no.dot(Y), no.dot(Z)]
        
        if direct[0]**2 > 0.9:
            
            if direct[0] < 0:
                z = -X
                y = Z
                x = -Y
            else:
                z = X
                y = Z
                x = Y
        elif direct[1]**2 > 0.9:
            if direct[1] < 0:
                z = -Y
                y = Z
                x = X
            else:
                z = Y
                y = Z
                x = -X
            
        elif direct[2]**2 > 0.9:
            if direct[2] < 0:
                z = -Z
                y = -Y
                x = X
            else:
                z = Z
                y = Y
                x = X
        else:
            self.report({'ERROR'},"Text on beveled surfaces not supported")
            return {'CANCELLED'}
        #currently, the base should not be scaled or rotated...but perhaps it may be later
        x = mx_norm * x
        y = mx_norm * y
        z = mx_norm * z    
        
        txt_crv = bpy.data.curves.new('Custom:Label', type = 'FONT')
        txt_crv.body = prefs.heal_custom_text
        txt_crv.align_x = 'LEFT'
        txt_crv.align_y = 'BOTTOM'
        txt_ob = bpy.data.objects.new('Custom:Label', txt_crv)
            
        txt_crv.extrude = 1
        txt_crv.size = self.font_size
        txt_crv.resolution_u = 5
        txt_crv.offset = .02  #thicken up the letters a little
        context.scene.objects.link(txt_ob)
        txt_ob.update_tag()
        context.scene.update()
        
        #handle the alignment
        translation = mx * new_loc
        
        bb = txt_ob.bound_box
        max_b = max(bb, key = lambda x: Vector(x)[1])
        max_y = max_b[1]
        
        if self.x_align == 'CENTER':
            delta_x = 0.5 * txt_ob.dimensions[0]
            translation = translation - delta_x * x           
        elif self.x_align == 'RIGHT':
            delta_x = txt_ob.dimensions[0]
            translation = translation - delta_x * x 
            
        if self.y_align == 'CENTER':
            delta_y = 0.5 * max_y
            translation = translation - delta_y * y
        elif self.y_align == 'TOP':
            delta_y = max_y
            translation = translation - delta_y * y
        #build the rotation matrix which corresponds
        R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = x[0] ,y[0],  z[0]
        R[1][0], R[1][1], R[1][2]  = x[1], y[1],  z[1]
        R[2][0] ,R[2][1], R[2][2]  = x[2], y[2],  z[2]
        R = R.to_4x4()
       
        T = Matrix.Translation(translation)
        
        txt_ob.matrix_world = T * R
                   
        return {"FINISHED"}
    
class OPENDENTAL_OT_heal_emboss_text(bpy.types.Operator):
    """Joins all text label objects and booean subtraction from the template block"""
    bl_idname = "opendental.heal_emboss_text"
    bl_label = "Emboss Text Into Block"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        
        if "Templates Base" not in bpy.data.objects:
            return False
        return True
    

    def execute(self, context):
    
        t_base = bpy.data.objects.get("Templates Base")

        labels = [ob for ob in bpy.data.objects if ob.type == 'FONT']
        
        
        label_final = join_objects(labels, name = 'Text Labels')
        
        context.scene.objects.link(label_final)
        
        #subtract the whole thing from the template block
        mod = t_base.modifiers.new(type = 'BOOLEAN', name = 'Boolean')
        mod.operation = 'DIFFERENCE'
        mod.object = label_final
        
        t_base.draw_type = 'SOLID'
        
        for ob in labels:
            ob.hide = True
        label_final.hide = True
            
        t_base.hide = False
        t_base.select = True
        bpy.context.scene.objects.active = t_base
           
        return {"FINISHED"} 
    
    
class OPENDENTAL_OT_heal_create_final_template(bpy.types.Operator):
    """Solidifies the template box and subtracts the abutment and emergence profiles"""
    bl_idname = "opendental.heal_create_final_template"
    bl_label = "Boolean All Objects"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        
        if "Templates Base" not in bpy.data.objects:
            return False
        return True
    

    def execute(self, context):
    
        t_base = bpy.data.objects.get("Templates Base")

        profiles = [ob for ob in bpy.data.objects if "Profile" in ob.name]
        
        base_obs = [ob for ob in bpy.data.objects if ":TiBase" in ob.name]
        
        bpy.ops.object.select_all(action = 'DESELECT')
        
        profiles_joined = join_objects(profiles, 'Final Profiles')
        bases_joined = join_objects(base_obs, 'Final Bases')
        
        bme = bmesh.new()
        bme.from_mesh(bases_joined.data)
        bme.faces.ensure_lookup_table()
        bmesh.ops.recalc_face_normals(bme, faces = bme.faces[:])
        bme.to_mesh(bases_joined.data)
        bme.free()
        
        context.scene.objects.link(profiles_joined)
        context.scene.objects.link(bases_joined)
        
        
        #solidify the ti_base
        mod = bases_joined.modifiers.new(type = 'SOLIDIFY', name = 'OFFSET')
        mod.offset = 1
        mod.thickness = 0.15
        #mod.use_even_offset = True
        #mod.use_quality_normals = True 
        mod.use_rim_only = True 
        
        #join the tibase to the profiles
        mod = profiles_joined.modifiers.new(type = 'BOOLEAN', name = 'Boolean')
        mod.operation = 'UNION'
        mod.object = bases_joined
        
        #subtract the whole thing from the template block
        mod = t_base.modifiers.new(type = 'BOOLEAN', name = 'Boolean')
        mod.operation = 'DIFFERENCE'
        mod.object = profiles_joined
        
        t_base.draw_type = 'SOLID'
        
        for ob in bpy.data.objects:
            ob.hide = True
            
        t_base.hide = False
        t_base.select = True
        bpy.context.scene.objects.active = t_base
           
        return {"FINISHED"} 


             
def register():
    bpy.utils.register_class(OPENDENTAL_OT_heal_import_abutment)
    bpy.utils.register_class(OPENDENTAL_OT_heal_mark_platform)
    bpy.utils.register_class(OPENDENTAL_OT_heal_mark_timing)
    bpy.utils.register_class(OPENDENTAL_OT_heal_remove_internal)
    bpy.utils.register_class(OPENDENTAL_OT_ucla_remove_timing)
    #bpy.utils.register_class(OPENDENTAL_OT_heal_generate_profiles)
    bpy.utils.register_class(OPENDENTAL_OT_heal_database_profiles)
    bpy.utils.register_class(OPENDENTAL_OT_heal_database_curve_profiles)
    bpy.utils.register_class(OPENDENTAL_OT_heal_mesh_convert)
    bpy.utils.register_class(OPENDENTAL_OT_heal_generate_box)
    bpy.utils.register_class(OPENDENTAL_OT_heal_generate_text)
    bpy.utils.register_class(OPENDENTAL_OT_heal_custom_text)
    bpy.utils.register_class(OPENDENTAL_OT_heal_emboss_text)
    bpy.utils.register_class(OPENDENTAL_OT_heal_create_final_template)
    
    
    #bpy.utils.register_module(__name__)
   
def unregister():
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_import_abutment)
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_mark_platform)
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_mark_timing)
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_remove_internal)
    bpy.utils.unregister_class(OPENDENTAL_OT_ucla_remove_timing)
    #bpy.utils.unregister_class(OPENDENTAL_OT_heal_generate_profiles)
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_database_profiles)
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_database_curve_profiles)
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_mesh_convert)
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_generate_box)
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_generate_text)
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_custom_text)
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_emboss_text)
    bpy.utils.unregister_class(OPENDENTAL_OT_heal_create_final_template)
    

    
if __name__ == "__main__":
    register()