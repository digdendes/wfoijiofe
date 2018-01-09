'''
Created on Dec 26, 2017

@author: Patrick
'''
import math
import random
import time
from collections import Counter
import numpy as np 

import bpy
import bgl
import blf
import bmesh
from mathutils import Matrix, Vector, Color
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
from bpy_extras import view3d_utils
from bpy.props import BoolProperty, FloatProperty, IntProperty
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_vector_3d, region_2d_to_location_3d, region_2d_to_origin_3d

from common_drawing import draw_3d_points, draw_polyline_from_3dpoints
from points_picker import PointPicker
from textbox import TextBox
from bmesh_curvature import points_within_radius, CuspWaterDroplet, vector_average,\
    curvature_on_mesh, calculate_plane
import tracking
from errno import EOPNOTSUPP


class D3Splint_automatic_opposing_surface(bpy.types.Operator):
    """Semi Automatic and User Guided occlusal plane generator"""
    bl_idname = "d3splint.watershed_cusp_surface_finder"
    bl_label = "Automatic Opposing Cusp Surface"

    
    def draw_callback_water_drops(self, context):
        
        mx = self.ob.matrix_world
        
        draw_3d_points(context, [self.com], (1,.1,1,.5), 6)
        if not self.consensus_generated:
            for droplet in self.drops:
                vs = [mx * self.bme.verts[i].co for i in droplet.ind_path]
            
                #draw_3d_points(context, vs, (.2,.3,.8,1), 2)
                draw_3d_points(context, [vs[-1]], (1,.3,.3,1), 3)
                #draw_3d_points(context, [vs[0]], (.3,1,.3,1), 4)
        
        if self.consensus_generated:
            
            vs = [mx * self.bme.verts[i].co for i in self.consensus_list]
            draw_3d_points(context, vs, (.2,.8,.8,1), 5)
            
        if self.sorted_by_value:
            vs = [mx * self.bme.verts[i].co for i in self.best_verts]
            draw_3d_points(context, vs, (.8,.8,.2,1), 3)
        
        
        if len(self.clipped_verts):
            vs = [mx * v for v in self.clipped_verts]
            draw_3d_points(context, vs, (1,.3,1,1), 4)
            
            
        if len(self.bez_curve):
            vs = [mx * v for v in self.bez_curve]
            draw_polyline_from_3dpoints(context, vs, (.2,1,.2,1), 3)
            draw_3d_points(context, vs, (.2,1,.2,1), 5)
        #if len(self.polyline):
            #draw_polyline_from_3dpoints(context, self.polyline, (1,1,.2,1), 2)
            
        #    for i, v in enumerate(self.polyline):
        #        msg = str(i)
        #        draw_3d_text(context, v, msg, 20)
                         
    def roll_droplets(self,context):
        count_rolling = 0
        for drop in self.drops:
            #if self.splint.jaw_type == 'MANDIBLE':
            if not drop.peaked:
                drop.roll_uphill()
                count_rolling += 1
            #else:
            #    if not drop.settled:
            #        drop.roll_downhill()
            #        count_rolling += 1
                
        return count_rolling

    def build_concensus(self,context):
        
        list_inds = [drop.dn_vert.index for drop in self.drops]
        vals = [drop.dnH for drop in self.drops]
        
        
        unique = set(list_inds)
        unique_vals = [vals[list_inds.index(ind)] for ind in unique]
        
        
        print('there are %i droplets' %len(list_inds))
        print('ther are %i unique maxima' % len(unique))
    
        best = Counter(list_inds)
        
        consensus_tupples = best.most_common(self.consensus_count)
        self.consensus_list = [tup[0] for tup in consensus_tupples]
        self.consensus_dict = {}  #throw it all away?
        
        #map consensus to verts.  Later we will merge into this dict
        for tup in consensus_tupples:
            self.consensus_dict[tup[0]] = tup[1]
            
        #print(self.consensus_list)
        self.consensus_generated = True
        
    
    def sort_by_value(self,context):
        
        list_inds = [drop.dn_vert.index for drop in self.drops]
        vals = [drop.dnH for drop in self.drops]
        
        
        unique_inds = list(set(list_inds))
        unique_vals = [vals[list_inds.index(ind)] for ind in unique_inds]
        
        bme_inds_by_val = [i for (v,i) in sorted(zip(unique_vals, unique_inds))]
        self.best_verts = bme_inds_by_val[0:self.consensus_count]
        self.sorted_by_value = True
    
    
    def merge_close_consensus_points(self):
        '''
        cusps usually aren't closer than 2mm
        actually we aren't merging, we just toss the one with less votes
        '''
        
        #consensus list is sorted with most voted for locations first
        #start at back of list and work forward
        to_remove = []
        new_verts = []
        l_co = [self.bme.verts[i].co for i in self.consensus_list]
        N = len(l_co)
        for i, pt in enumerate(l_co):
            
            #if i in to_remove:
            #    continue
            
            ds, inds, vs = points_within_radius(pt, l_co, 7)
            
            if len(vs):
                new_co = Vector((0,0,0))
                for v in vs:
                    new_co += v
                new_co += pt
                new_co *= 1/(len(vs) + 1)
            else:
                new_co = pt
                
            new_verts.append(new_co)
                        
            for j in inds:
                if j > i:
                    to_remove.append(j)  
               
            
        to_remove = list(set(to_remove))
        to_remove.sort(reverse = True)
        
        print('removed %i too close consensus points' % len(to_remove))
        print(to_remove)
        for n in to_remove:
            l_co.pop(n)
            
        
        
        self.clipped_verts = new_verts
        
        return
        
    def fit_cubic_consensus_points(self):
        '''
        let i's be indices in the actual bmesh
        let j's be arbitrary list comprehension indices
        let n's be the incidices in our consensus point lists range 0,len(consensus_list)
        '''
        
        pass
    
        '''
        l_co = self.clipped_verts
        
        
        com, no = calculate_plane(l_co)  #an easy way to estimate occlusal plane
        no.normalize()
        
        
        #neigbors = set(l_co)
        box = bbox(l_co)
        
        diag = (box[1]-box[0])**2 + (box[3]-box[2])**2 + (box[5]-box[4])**2
        diag = math.pow(diag,.5)
        
        #neighbor_path = [neighbors.pop()]
        
        #establish a direction
        #n, v, d  = closest_point(neighbor_path[0], list(neighbors))
        #if d < .2 * diag:
        #    neighbor_path.append(v)
        
        #ended = Fase
        #while len(neighbors) and not ended:   
        #   n, v, d  = closest_point(neighbor_path[0], list(neighbors)
        
        #flattened spokes
        rs = [v - v.dot(no)*v - com for v in l_co]
        
        R0 = rs[random.randint(0,len(rs)-1)]
        
        theta_dict = {}
        thetas = []
        for r, v in zip(rs,l_co):
            angle = r.angle(R0)
            
            if r != R0:
                rno = r.cross(R0)
                if rno.dot(no) < 0:
                    angle *= -1
                    angle += 2 * math.pi
            
            theta_dict[round(angle,4)] = v
            thetas.append(round(angle,4))
        
        print(thetas)
        thetas.sort()
        print(thetas)
        diffs = [thetas[i]-thetas[i-1] for i in range(0,len(thetas))]
        n = diffs.index(max(diffs)) # -1
        theta_shift = thetas[n:] + thetas[:n]
        
        self.polyline = [theta_dict[theta] for theta in theta_shift]
        #inds_in_order = [theta_dict[theta] for theta in thetas]
        #self.polyline = [l_co[i] for i in inds_in_order]
        
        self.com = com

        l_bpts = cubic_bezier_fit_points(self.polyline, 1, depth=0, t0=0, t3=1, allow_split=True, force_split=False)
        self.bez_curve = []
        N = 20
        for i,bpts in enumerate(l_bpts):
            t0,t3,p0,p1,p2, p3 = bpts
            

            new_pts = [cubic_bezier_blend_t(p0,p1,p2,p3,i/N) for i in range(0,N)]
            
            self.bez_curve.extend(new_pts)  
    '''         

    def invoke(self,context, event):
        
        splint = context.scene.odc_splints[0]
        
        if splint.jaw_type == 'MAXILLA':
            opposing = splint.get_mandible()
        else:
            opposing = splint.get_maxilla()
        
        #models need to be fairly mounted with local Z alligned to occluasl plane
        
        ob = bpy.data.objects.get(opposing)
        
        if not ob:
            self.report({'ERROR'},'Opposing object not indicated')
            return {'CANCELLED'}
    
        self.ob = ob  
        self.bme = bmesh.new()
        self.bme.from_mesh(ob.data)
        self.bme.verts.ensure_lookup_table()
        self.bme.faces.ensure_lookup_table()
        
        print("starting curvature calclation")
        start = time.time()
        if 'max_curve' not in self.bme.verts.layers.float:
            curvature_on_mesh(self.bme)
        
        print('tootk %f seconds to put curvature' % (time.time() - start))
        curv_id = self.bme.verts.layers.float['max_curve']
        
        #let's roll 10000 water droplets
        #sample = 10000 / len(self.bme.verts)
        #rand_sample = list(set([random.randint(0,len(self.bme.verts)-1) for i in range(math.floor(sample * len(self.bme.verts)))]))
        #sel_verts = [self.bme.verts[i] for i in rand_sample]
        
        sel_verts = random.sample(self.bme.verts[:], 10000)
        
        
        
        if splint.jaw_type == 'MANDIBLE':
            pln_no = Vector((0,0,1))
        else:
            pln_no = Vector((0,0,-1))
        
        pln_pt = Vector((0,0,0)) - 10 * pln_no
        
        self.drops = [CuspWaterDroplet(v, pln_pt, pln_no, curv_id) for v in sel_verts]
        
        self.consensus_count = 20
        self.consensus_list = []
        self.consensus_dict = {}
        self.consensus_generated = False
        self.bez_curve = []
        self.polyline = []
        self.clipped_verts = []
        self.com = self.ob.location
        
        
        self.best_verts = []
        self.sorted_by_value = False
        
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self.draw_callback_water_drops, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
    
        return {'RUNNING_MODAL'}
    
    def modal(self,context,event):
        context.area.tag_redraw()
        
        if event.type == 'RET' and event.value == 'PRESS':
            for drop in self.drops:
                for i in drop.ind_path:
                    self.bme.verts[i].select = True
            
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self.bme.to_mesh(self.ob.data)
            self.bme.free()
            
            return {'FINISHED'}
          
        
        
        elif event.type == 'Q' and event.value == 'PRESS':
            n_rolling = self.roll_droplets(context)
            
            iters = 0
            while n_rolling > 5 and iters < 400:
                n_rolling = self.roll_droplets(context)
                iters += 1
                
            if iters >= 399:
                print('too much rolling')    
            
            self.consensus_count = 20    
            self.build_concensus(context)
            
            l_co = [self.bme.verts[i].co for i in self.consensus_list]
            test_no = vector_average([self.bme.verts[i].normal for i in self.consensus_list])
            test_no.normalize()
            pt, pno = calculate_plane(l_co)
            
            
            if pno.dot(test_no) < 0:
                pno *= -1
            
            self.pln_pt = pt - 5*pno
            self.pln_no = pno
                
            mx = self.ob.matrix_world
            imx = mx.inverted()
            no_mx = mx.transposed().inverted().to_3x3()
            
            
            Z = no_mx * pno
            loc = mx * pt - 5 * Z
            
            ob_y = no_mx * Vector((0,1,0))
            X = ob_y.cross(Z)
            Y = Z.cross(X)
            
            Z.normalize()
            Y.normalize()
            X.normalize()
            
            wmx = Matrix.Identity(4)
            wmx[0][0], wmx[1][0], wmx[2][0] = X[0], X[1], X[2]
            wmx[0][1], wmx[1][1], wmx[2][1] = Y[0], Y[1], Y[2]
            wmx[0][2], wmx[1][2], wmx[2][2] = Z[0], Z[1], Z[2]
            wmx[0][3], wmx[1][3], wmx[2][3] = loc[0], loc[1], loc[2]
            
            #circ_bm = bmesh.new()
            #bmesh.ops.create_circle(circ_bm, cap_ends = True, cap_tris = False, segments = 10, diameter = .5 *min(context.object.dimensions) + .5 *max(context.object.dimensions))
            
            # Finish up, write the bmesh into a new mesh
            #me = bpy.data.meshes.new("Occlusal Plane")
            #circ_bm.to_mesh(me)
            #circ_bm.free()

            # Add the mesh to the scene
            #scene = bpy.context.scene
            #obj = bpy.data.objects.new("Object", me)
            #scene.objects.link(obj)
            #obj.matrix_world = wmx
            return {'RUNNING_MODAL'}
        
        
        elif event.type == 'W' and event.value == 'PRESS':
            curv_id = self.bme.verts.layers.float['max_curve']
            
            start = time.time()
            cut_geom = self.bme.faces[:] + self.bme.verts[:] + self.bme.edges[:]
            bmesh.ops.bisect_plane(self.bme, geom = cut_geom, dist = .000001, plane_co = self.pln_pt, plane_no = self.pln_no, use_snap_center = False, clear_outer=False, clear_inner=True)
            self.bme.verts.ensure_lookup_table()
            self.bme.faces.ensure_lookup_table()
            
            
            rand_sample = list(set([random.randint(0,len(self.bme.verts)-1) for i in range(math.floor(.2 * len(self.bme.verts)))]))
            self.drops = [CuspWaterDroplet(self.bme.verts[i], self.pln_pt, self.pln_no, curv_id) for i in rand_sample]
            dur = time.time() - start
            print('took %f seconds to cut the mesh and generate drops' % dur)
            
            start = time.time()
            n_rolling = self.roll_droplets(context)
            iters = 0
            while n_rolling > 10 and iters < 100:
                n_rolling = self.roll_droplets(context)
                iters += 1
            
            self.consensus_count = 80
            self.build_concensus(context)
            
            dur = time.time() - start
            print('took %f seconds to roll the drops' % dur)
            return {'RUNNING_MODAL'}
               
        elif event.type == 'UP_ARROW' and event.value == 'PRESS':
            n_rolling = self.roll_droplets(context)
            
            iters = 0
            while n_rolling > 10 and iters < 100:
                n_rolling = self.roll_droplets(context)
                iters += 1
            return {'RUNNING_MODAL'}
        
        
        elif event.type == 'LEFT_ARROW' and event.value == 'PRESS':
            self.consensus_count -= 5
            self.build_concensus(context)
            return {'RUNNING_MODAL'}
        
        elif event.type == 'RIGHT_ARROW' and event.value == 'PRESS':
            self.consensus_count += 5
            self.build_concensus(context)
            return {'RUNNING_MODAL'}
        
        elif event.type == 'C' and event.value == 'PRESS':
            self.build_concensus(context) 
            return {'RUNNING_MODAL'}
        
        elif event.type == 'M' and event.value == 'PRESS':
            self.merge_close_consensus_points()
            return {'RUNNING_MODAL'}
            
        elif event.type == 'B' and event.value == 'PRESS' and self.consensus_generated:
            self.fit_cubic_consensus_points()
            return {'RUNNING_MODAL'}
            
        elif event.type == 'S' and event.value == 'PRESS':
            self.sort_by_value(context)
            return {'RUNNING_MODAL'}
                   
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self.bme.to_mesh(self.ob.data)
            self.bme.free()
            return {'CANCELLED'}
        else:
            return {'PASS_THROUGH'}
        

def landmarks_draw_callback(self, context):  
    self.crv.draw(context)
    self.help_box.draw()    
    
class D3SPLINT_OT_splint_manual_auto_surface(bpy.types.Operator):
    """Help make a nice flat plane"""
    bl_idname = "d3splint.splint_manual_flat_plane"
    bl_label = "Define Occlusal Contacts"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls,context):
        return True
    
    def modal_nav(self, event):
        events_nav = {'MIDDLEMOUSE', 'WHEELINMOUSE','WHEELOUTMOUSE', 'WHEELUPMOUSE','WHEELDOWNMOUSE'} #TODO, better navigation, another tutorial
        handle_nav = False
        handle_nav |= event.type in events_nav

        if handle_nav: 
            return 'nav'
        return ''
    
    def modal_main(self,context,event):
        # general navigation
        nmode = self.modal_nav(event)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            
            x, y = event.mouse_region_x, event.mouse_region_y
            self.crv.click_add_point(context, x,y, label = None)
            
            return 'main'
        
        #TODO, right click to delete misfires
        if event.type == 'DEL' and event.value == 'PRESS':
            self.crv.click_delete_point()
            return 'main'
            
        if event.type == 'RET' and event.value == 'PRESS':
            self.finish(context)
            return 'finish'
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            return 'cancel' 

        return 'main'
    
        
    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #context.space_data.show_manipulator = True
            
            if nmode == 'finish':
                context.space_data.transform_manipulators = {'TRANSLATE', 'ROTATE'}
            else:
                context.space_data.transform_manipulators = {'TRANSLATE'}
            #clean up callbacks
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def invoke(self,context, event):
        n = context.scene.odc_splint_index
        self.splint = context.scene.odc_splints[n]    
        
        if self.splint.jaw_type == 'MANDIBLE':
            model = self.splint.get_maxilla()
        else:
            model = self.splint.get_mandible()
        
        
        if model == '' or model not in bpy.data.objects:
            self.report({'ERROR'}, "Need to mark the Upper and Lower model first!")
            return {'CANCELLED'}
            
        
        Model = bpy.data.objects[model]
            
        for ob in bpy.data.objects:
            ob.select = False
            
            if ob != Model:
                ob.hide = True
        Model.select = True
        Model.hide = False
        context.scene.objects.active = Model
        
        if self.splint.jaw_type == 'MAXILLA':
            bpy.ops.view3d.viewnumpad(type = 'TOP')
        
        else:
            bpy.ops.view3d.viewnumpad(type = 'BOTTOM')
        
        bpy.ops.view3d.view_selected()
        self.crv = PointPicker(context,snap_type ='OBJECT', snap_object = Model)
        context.space_data.show_manipulator = False
        context.space_data.transform_manipulators = {'TRANSLATE'}
        v3d = bpy.context.space_data
        v3d.pivot_point = 'MEDIAN_POINT'
        
        
        #TODO, tweak the modifier as needed
        help_txt = "DRAW LANDMARK POINTS\n Click on the cusps you want"
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(landmarks_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        return {'RUNNING_MODAL'}

    def finish(self, context):
        #ray cast the entire grid into
        
        if 'Posterior Plane' in bpy.data.objects:
            Plane = bpy.data.objects['Posterior Plane']
                
        else:
            me = bpy.data.meshes.new('Posterior Plane')
            Plane = bpy.data.objects.new('Posterior Plane', me)
            context.scene.objects.link(Plane)
        
        pbme = bmesh.new()
        pbme.verts.ensure_lookup_table()
        pbme.edges.ensure_lookup_table()
        pbme.faces.ensure_lookup_table()
        bmesh.ops.create_grid(pbme, x_segments = 200, y_segments = 200, size = 39.9)
        pbme.to_mesh(Plane.data)
        
        pt, pno = calculate_plane(self.crv.b_pts)
        
        if self.splint.jaw_type == 'MANDIBLE':
            Zw = Vector((0,0,-1))
            Xw = Vector((1,0,0))
            Yw = Vector((0,-1,1))
            
        else:
            Zw = Vector((0,0,1))
            Xw = Vector((1,0,0))
            Yw = Vector((0,1,0))
            
        Z = pno
        Z.normalize()
        
        if Zw.dot(Z) < 0:
            Z *= -1
            
        Y = Z.cross(Xw)
        X = Y.cross(Z)
            
        
        R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
        R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
        R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2]
        
        R = R.to_4x4()
        T = Matrix.Translation(pt - 5 * Z)
        
        Plane.matrix_world = T * R
    
        pmx = Plane.matrix_world
        ipmx = pmx.inverted()
        
        bme_pln = bmesh.new()
        bme_pln.from_mesh(Plane.data)
        bme_pln.verts.ensure_lookup_table()
        bme_pln.edges.ensure_lookup_table()
        bme_pln.faces.ensure_lookup_table()
        bvh = BVHTree.FromBMesh(bme_pln)
        
        key_verts = {}
        
        for loc in self.crv.b_pts:

            res = bvh.ray_cast(ipmx * loc, -Z, 30)
            if res[0] != None:
                
                f = bme_pln.faces[res[2]]
                for v in f.verts:
                    key_verts[v] = ipmx * loc
                    v.select_set(True)
                
                continue
            
            res = bvh.ray_cast(ipmx * loc, Z, 30)
            if res[0] != None:
                
                f = bme_pln.faces[res[2]]
                for v in f.verts:
                    key_verts[v] = ipmx * loc
                    v.select_set(True)
                
                continue
        
        #bme_pln.to_mesh(Plane.data)
        #bme_pln.free()
        #return
        kdtree = KDTree(len(key_verts))
        for v in key_verts.keys():
            kdtree.insert(v.co, v.index)
        
        kdtree.balance()
        to_delete = []
        for v in bme_pln.verts:
            if v in key_verts:
                v.co[2] = key_verts[v][2]
                continue
                
            results = kdtree.find_range(v.co, .5)
            if len(results):
                N = len(results)
                r_total = 0
                v_new = Vector((0,0,0))
                for res in results:
                    r_total += 1/res[2]
                    v_new += (1/res[2]) * key_verts[bme_pln.verts[res[1]]]
                        
                v_new *= 1/r_total
                v.co[2] = v_new[2]
                continue
                        
            results = kdtree.find_range(v.co, 6)
            if len(results):
                N = len(results)
                r_total = 0
                v_new = Vector((0,0,0))
                for res in results:
                    r_total += (1/res[2])**2
                    v_new += ((1/res[2])**2) * key_verts[bme_pln.verts[res[1]]]
                        
                v_new *= 1/r_total
                v.co[2] = v_new[2]
                continue
            
            to_delete += [v]
            
        bmesh.ops.delete(bme_pln, geom = to_delete, context = 1)
        bme_pln.to_mesh(Plane.data)
        Plane.data.update()
        
        smod = Plane.modifiers.new('Smooth', type = 'SMOOTH')
        smod.iterations = 5
        smod.factor = 1
        tracking.trackUsage("D3Splint:SplintManualSurface",None)

class D3SPLINT_OT_splint_subtract_posterior_surface(bpy.types.Operator):
    """Subtract Posterior Surface from Shell"""
    bl_idname = "d3splint.subtract_posterior_surface"
    bl_label = "Subtract Posterior Surface from Shell"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    #sculpt to
    sculpt_to = bpy.props.BoolProperty(default = False, description = "Not only remove but pull some of the shell down to touch")
    snap_limit = bpy.props.FloatProperty(default = 2.0, min = .25, max = 5.0, description = "Max distance the shell will snap to")
    remesh = bpy.props.BoolProperty(default = True, description = "Not only remove but pull some of the shell down to touch")
    @classmethod
    def poll(cls, context):
        #if context.mode == "OBJECT" and context.object != None and context.object.type == 'CURVE':
        #    return True
        #else:
        #    return False
        return True
    
    def execute(self, context):
        
        if not len(context.scene.odc_splints):
            self.report({'ERROR'}, 'Need to start a splint by setting model first')
            return {'CANCELLED'}
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        
        Model = bpy.data.objects.get(splint.model)
        Shell = bpy.data.objects.get('Splint Shell')
        Plane = bpy.data.objects.get('Posterior Plane')

        
        if Shell == None:
            self.report({'ERROR'}, 'Need to calculate splint shell first')
            return {'CANCELLED'}
        if Plane == None:
            self.report({'ERROR'}, 'Need to generate functional surface first')
            return {'CANCELLED'}
        
        if len(Shell.modifiers):
            old_data = Shell.data
            new_data = Shell.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            
        
            
            for mod in Shell.modifiers:
                Shell.modifiers.remove(mod)
            
            Shell.data = new_data
            bpy.data.meshes.remove(old_data)
        
        high_verts = []
        bme = bmesh.new()
        bme.from_mesh(Plane.data)
        bme.verts.ensure_lookup_table()
        
        bvh  = BVHTree.FromObject(Model, context.scene)
        
        mx_p = Plane.matrix_world
        imx_p = mx_p.inverted()
        
        mx_s = Model.matrix_world
        imx_s = mx_s.inverted()
        
        if splint.jaw_type == 'MAXILLA':
            Z = Vector((0,0,1))
        else:
            Z = Vector((0,0,-1))
            
        for v in bme.verts:
            ray_orig = mx_p * v.co
            ray_target = mx_p * v.co - 5 * Z
            ray_target2 = mx_p * v.co + .8 * Z
            
            loc, no, face_ind, d = bvh.ray_cast(imx_s * ray_orig, imx_s * ray_target - imx_s*ray_orig, 5)
        
            if loc:
                high_verts += [v]
                v.co = imx_p * (mx_s * loc - 0.8 * Z)
            else:
                loc, no, face_ind, d = bvh.ray_cast(imx_s * ray_orig, imx_s * ray_target2 - imx_s*ray_orig, .8)
                if loc:
                    high_verts += [v]
                    v.co = imx_p * (mx_s * loc - 0.8 * Z)
        
        if len(high_verts):
            self.report({'WARNING'}, 'Sweep surface intersected upper model, corrected it for you!')
            
            mat = bpy.data.materials.get("Bad Material")
            if mat is None:
                # create material
                mat = bpy.data.materials.new(name="Bad Material")
                mat.diffuse_color = Color((1,.3, .3))
        
                Plane.data.materials.append(mat)
            
            for v in high_verts:
                for f in v.link_faces:
                    f.material_index = 1
            bme.to_mesh(Plane.data)
            
        bme.free()
        Plane.data.update()
        context.scene.update()
        
        n = context.scene.odc_splint_index
        splint = context.scene.odc_splints[n]
        

        #Do a manual ray cast to the underlying data...use BVH in future?   Nah
        sbme = bmesh.new()
        sbme.from_mesh(Shell.data)
        sbme.verts.ensure_lookup_table()
        
        for v in sbme.verts:
            ray_orig = mx_s * v.co
            ray_target = mx_s * v.co + 5 * Z
            ray_target2 = mx_s * v.co - self.snap_limit * Z
            ok, loc, no, face_ind = Plane.ray_cast(imx_p * ray_orig, imx_p * ray_target - imx_p*ray_orig)
            
            if ok:
                v.co = imx_s * (mx_p * loc)
               
        
            if self.sculpt_to:
                if abs(v.normal.dot(Z)) < .2: continue
                
                
                ok, loc, no, face_ind = Plane.ray_cast(imx_p * ray_orig, imx_p * ray_target2 - imx_p*ray_orig, distance = self.snap_limit)
                if ok:
                    v.co = imx_s * (mx_p * loc)
                    
        sbme.to_mesh(Shell.data)
        Shell.data.update()
                
        Plane.hide = True
        Shell.hide = False
        Model.hide = False
        
        if self.remesh:
            context.scene.objects.active = Shell
            Shell.select = True
            bpy.ops.object.mode_set(mode = 'SCULPT')
            if not Shell.use_dynamic_topology_sculpting:
                bpy.ops.sculpt.dynamic_topology_toggle()
            context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
            context.scene.tool_settings.sculpt.constant_detail_resolution = 2
            bpy.ops.sculpt.detail_flood_fill()
            bpy.ops.object.mode_set(mode = 'OBJECT')
        
        splint.ops_string += 'SubtractPosteriorSurface:'
        return {'FINISHED'}
                    
def register():
    bpy.utils.register_class(D3SPLINT_OT_splint_manual_auto_surface)
    bpy.utils.register_class(D3SPLINT_OT_splint_subtract_posterior_surface)
    
def unregister():
    bpy.utils.unregister_class(D3SPLINT_OT_splint_manual_auto_surface) 
    bpy.utils.unregister_class(D3SPLINT_OT_splint_subtract_posterior_surface)