#####
#
# Copyright 2014 Alex Tsui, modifications by Patrick Moore
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#####

#
# http://wiki.blender.org/index.php/Dev:2.5/Py/Scripts/Guidelines/Addons
#
import os
import bpy
import mathutils
import bmesh

from bpy.props import (BoolProperty,
    FloatProperty,
    StringProperty,
    EnumProperty,
    )
from bpy_extras.io_utils import (ImportHelper,
    ExportHelper,
    unpack_list,
    unpack_face_list,
    axis_conversion,
    )


def load(context, filepath):
    # Parse mesh data from OFF file
    #return a BMesh instance
    # TODO: Add support for NOFF and COFF
    
    bme = bmesh.new()
    
    filepath = os.fsencode(filepath)
    file = open(filepath, 'r')
    file.readline()
    vcount, fcount, ecount = [int(x) for x in file.readline().split()]
    verts = []
    facets = []
    edges = []
    i=0
    while i<vcount:
        line = file.readline()
        try:
            px, py, pz = [float(x) for x in line.split()]
        except ValueError:
            i=i+1
            continue
        verts.append(bme.verts.new((px, py, pz)))
        i=i+1

    i=0;
    while i<fcount:
        line = file.readline()
        try:
            splitted  = line.split()
            ids   = list(map(int, splitted))
            if len(ids) > 3:
                f_ids = tuple(ids[1:])
                bme.faces.new([verts[i] for i in f_ids])
                
        except ValueError:
            i=i+1
            continue
        i=i+1

    bme.verts.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    return bme

def save(context, obj, filepath,
    global_matrix = None):
    
    # Export the selected mesh
    APPLY_MODIFIERS = True # TODO: Make this configurable
    if global_matrix is None:
        global_matrix = mathutils.Matrix()
    scene = context.scene
    
    
    #assumed object has triangulate modifier
    bme = bmesh.new()
    bme.from_object(obj, scene)
    
    # Apply the inverse transformation
    obj_mat = obj.matrix_world
    bme.transform(global_matrix * obj_mat)

    # Write geometry to file
    filepath = os.fsencode(filepath)
    fp = open(filepath, 'w')
    fp.write('OFF\n')

    fp.write('%d %d 0\n' % (len(bme.verts), len(bme.faces)))

    for i, vert in enumerate(bme.verts):
        fp.write('%.16f %.16f %.16f' % vert.co[:])
        fp.write('\n')

    #for facet in facets:
    for i, facet in enumerate(bme.faces):
        fp.write('%d' % len(facet.verts))
        for v in facet.verts:
            fp.write(' %d' % v.index)
        fp.write('\n')

    fp.close()
    bme.free()
    return

