from .exceptions import *
import os, sys, platform


def get_cork_filepath():
    folderpath = os.path.dirname(os.path.abspath(__file__))
    
    if platform.system() == "Windows":
        cork_exe =os.path.join(folderpath,*['win','wincork.exe'])
        
    elif "Mac" in platform.system():
        cork_exe =os.path.join(folderpath,*['mac','cork'])
        
    elif "Linux" in platform.system():
        cork_exe =os.path.join(folderpath,*['linux','cork'])
        
    else:
        cork_exe = ''
        
    return cork_exe

def validate_executable(filepath):
    """returns True if file is valid and executable"""
    import os

    if not os.path.isfile(filepath):
        raise InvalidPathException(filepath)

    if not os.access(filepath, os.X_OK):
        raise NonExecutableException(filepath)

    return True
