'''
Created on Jan 28, 2018

@author: Patrick Moore
modified from Antonio Mendoza
https://www.dropbox.com/s/mlugwkzrbp0vsos/vtools_saveIncremental.py?dl=0

'''

 
import bpy
import os 
import glob 
from bpy.props import *
from bpy_extras.io_utils import ExportHelper
 
def getVersion(p_fileName):
     
    version = ""
    nameLeng = len(p_fileName)
    cont = nameLeng - 1
    isNumber = p_fileName[cont].isdigit()
     
    while cont >= 0 and isNumber:
         
        version = p_fileName[cont] + version
        cont = cont - 1
        isNumber = p_fileName[cont].isdigit()
     
    if version == "":
        version = "NONE"
         
    return version
 
def incrementVersion(p_version):
     
    nameLeng = len(p_version)
    cont = nameLeng - 1

    nVersion = int(p_version)
    nVersion += 1
    version = str(nVersion)
     
    while len(version) < len(p_version):
        version = "0" + version
         
    return version
     
 
def hasVersion(p_fileName):
     
    cont = len(p_fileName) - 1
    isNumber = p_fileName[cont].isdigit()
     
    return isNumber
 
def getVersionPosition(p_fileName):
     
    i = len(p_fileName) - 1
    while p_fileName[i] != "_":
        i = i - 1
    i += 1
     
    return i 
     
def getIncrementedFile(p_file="", p_inIncFolder = True):
     
    incrementedFile = ""
    file = p_file
    baseName= os.path.basename(file)
    folder = os.path.dirname(file)
    fileName = os.path.splitext(baseName)[0]
    versionFolderName = ""
    ftype = os.path.splitext(baseName)[1]
    version = getVersion(fileName)
    newVersion = ""
     
    #if there is not a first version file, create the new one
    if version == "NONE":
        versionFolderName = "autosave_" + fileName
        version = "000"
        fileName = fileName + "_000"
         
    newVersion = incrementVersion(version) 
    numVersions = fileName.count(version)
    if numVersions >= 1:
        posVersion = getVersionPosition(fileName)
        print("ver: ", posVersion)
        fileName = fileName[:posVersion]
        newFileName = fileName + newVersion
    else:
        newFileName = fileName.replace(version,newVersion)
         
         
    newFullFileName = newFileName + ftype
     
     
    if p_inIncFolder:
         
        versionFolder = os.path.join(folder,versionFolderName)
        incrementedFile = os.path.join(versionFolder, newFullFileName)
         
    else:
        incrementedFile = os.path.join(folder, newFullFileName)
     
    return incrementedFile 
 
def getLastVersionFile(p_file = ""):
     
    #look into the version folder for the last one
    #if there is not anything, return an empty string
     
    lastFile = ""
    file = p_file
    baseName= os.path.basename(file)
    folder = os.path.dirname(file)
    fileName = os.path.splitext(baseName)[0]
    versionFolderName = "autosave_" + fileName    
    versionFolder = os.path.join(folder,versionFolderName)
 
    if os.path.exists(versionFolder):
        filesToSearch = os.path.join(versionFolder, "*.blend")
        if len(filesToSearch) > 0:
            blendFiles = sorted(glob.glob(filesToSearch))
            lastFile = blendFiles[len(blendFiles)-1]
    else:
        os.makedirs(versionFolder)
           
    return lastFile
     
     
def saveIncremental():
     
    # check if it has version, 
    # if it has a version in the name save in the same folder with a version up number,
    # if not, save a new version within the version folder.
     
    currentFile = bpy.data.filepath
    baseName= os.path.basename(currentFile)
    currentFileName= os.path.splitext(baseName)[0]
    newFile = ""
         
    hasVersion = getVersion(currentFileName)
 
    if hasVersion == "NONE":
         
        # save in the version folder
        lastFile = getLastVersionFile(p_file = currentFile)
        if lastFile == "":
            lastFile = currentFile
         
        newFile = getIncrementedFile(p_file = lastFile, p_inIncFolder = True)
        bpy.ops.wm.save_as_mainfile(filepath=currentFile, copy=False)
        bpy.ops.wm.save_as_mainfile(filepath=newFile, copy=True)
         
         
    else:
         
        # save a new version in file current
        newFile = getIncrementedFile(p_file = currentFile, p_inIncFolder = False)
        bpy.ops.wm.save_as_mainfile(filepath=newFile)
      
    return os.path.basename(newFile)
 
class VTOOLS_OP_saveIncremental(bpy.types.Operator):
    bl_idname = "wm.splint_saveincremental"
    bl_label = "D3Splint Save and Copy"
     
    def execute(self,context):
         
        if bpy.data.is_saved == True:
            savedFileName = saveIncremental()
            textReport = savedFileName + "version saved"
            self.report({'INFO'},textReport)
                    
        else:
            bpy.ops.wm.save_as_mainfile('INVOKE_DEFAULT')
             
             
        return {'FINISHED'}   
     
      
def register():
    bpy.utils.register_class(VTOOLS_OP_saveIncremental)
    
    #addShortcut()
    
def unregister():
    bpy.utils.unregister_class(VTOOLS_OP_saveIncremental)

     
    