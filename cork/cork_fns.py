import bpy

from .exceptions import *
from . import io_mesh_off


def has_triangulate_modifier(ob):
    """if there is an existent modifier, that's all we need"""
    for modifier in ob.modifiers:
        if modifier.type == 'TRIANGULATE' and \
            modifier.show_render:
                return True


def create_triangulate_modifier(ob):
    """if there is no triangulate modifier creates a new one"""
    if not has_triangulate_modifier(ob):
        return ob.modifiers.new('Cork Triangulation', 'TRIANGULATE')
    else:
        return None


def delete_triangulate_modifier(ob, modifier):
    """remove previously created modifier"""
    if modifier:
        ob.modifiers.remove(modifier)


def cork_boolean(context, cork, method, base, plane):
    '''
    context - blender context
    cork - filepath to cork executable
    method - 'UNION', 'DIFFERENCE', 'INTERSECTION', 'XOR' etc
    base - The OPERAND  obejct blender object 
    plane - The OPERATOR object blender object 
    '''
    import os
    import subprocess
    import tempfile
    import shutil

    try:
        dirpath = tempfile.mkdtemp()
    except Exception as E:
        raise InvalidTemporaryDir(E)

    filepath_base = os.path.join(dirpath, 'base.off')
    filepath_plane = os.path.join(dirpath, 'plane.off')
    filepath_result = os.path.join(dirpath, 'result.off')

    # export base
    print("Exporting file \"{0}\"".format(filepath_base))
    modifier = create_triangulate_modifier(base)
    io_mesh_off.save(context, base, filepath_base)
    delete_triangulate_modifier(base, modifier)
    
    # export  to OFF
    print("Exporting file \"{0}\"".format(filepath_plane))
    
    modifier = create_triangulate_modifier(plane)
    io_mesh_off.save(context, plane, filepath_plane)
    delete_triangulate_modifier(plane, modifier)
    
    # call cork with arguments
    print("{0} {1} {2} {3} {4}".format(cork, method, filepath_base, filepath_plane, filepath_result))
    try:
        subprocess.call((cork, method, filepath_base, filepath_plane, filepath_result))
    except Exception as error:
        print('error in line 74')
        raise error

    # import resulting OFF mesh
    print("Importing file \"{0}\"".format(filepath_result))
    
    result_bmesh = io_mesh_off.load(context, filepath=filepath_result)
    
    # cleanup temporary folder
    shutil.rmtree(dirpath)

    return result_bmesh
