'''
Created on Jul 14, 2017

adapted from MCPrep credit to Patrick Crawford, Google LLC
https://raw.githubusercontent.com/TheDuckCow/MCprep/master/MCprep_addon/tracking.py
'''
# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# -----------------------------------------------------------------------------
# Structure plan
# -----------------------------------------------------------------------------

"""
Key funcitonality:
- Send notice when first installing the addon and enabling (first time only)
-- (Try to get unique identifier to prevent doubling?)
x Track when functions are used
-- Track how often used, just keep local number/count usage
-- keep unique ID for user... could scramble timestamp first installed+userpath?
-- could do sneaky parsing of other blender folders to see if addon found & has pre-existing ID
-- (relative only pathing ofc)
xx Try to send in background when using
-- and if failed save to file & set flag to try again later
- Feedback form?? >> direct emails to support@theduckcow.com could do
- Consideirng both google analytics pinging as well as DB pushes? one or the other
- when asking to enable tracking, second popup to say hey, advanced too?
-- open advanced settings, fields for more details/could also be in that conditional popup
- Request for feedback? popup also after some interval if not used?

Things to track/push
- when installed (by default, agreed to on download)
- FORCE them to agree to terms of use in addon panel before doing anything???
(personal thing/specific to this addon)
- track date.. different from submission timestamp potentially
- addon version
- additional tracking (optional):
-- blender version
xx OS running
-- optional profiler info? e.g. tick your age range, # eyars experince w/ blender, etc


"""


"""data testing dump

curl -X POST -d '{"timestamp":0,"version":"v2.9.9","blender":"2.77","status":"New install"}' 'https://mcprep-1aa04.firebaseio.com/1/track/install_dev.json'

curl -X GET 'https://mcprep-1aa04.firebaseio.com/1/SECRET.json'


https://firebase.google.com/docs/reference/security/database/#variables

https://firebase.google.com/docs/reference/rest/database/
https://firebase.google.com/docs/reference/rest/database/user-auth

"""

import os
import socket
import json
import http.client
import requests
import platform
import threading
import bpy
import math
import random
from datetime import datetime

from hashlib import sha1
from uuid import getnode as get_mac
from common_utilities import get_settings
#from . import conf


# -----------------------------------------------------------------------------
# global vars
# -----------------------------------------------------------------------------


idname = "custom_apg"

# -----------------------------------------------------------------------------
# utilities
# -----------------------------------------------------------------------------

def internet(host="8.8.8.8", port=53, timeout=3):
    """
    simple internet connectivity check (credit stackexchange)
    Host: 8.8.8.8 (google-public-dns-a.google.com)
    OpenPort: 53/tcp
    Service: domain (DNS/TCP)
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except:
        return False


def hardware_key():
    mac = get_mac()
    if (mac >> 40)%2:
        final_key = '1'*40
        
    else:
        typical_mac = ':'.join(("%012X" % mac)[i:i+2] for i in range(0, 12, 2))
        hex_mac = hex(mac)
    
        SHA = sha1(hex_mac.encode())
        key = SHA.hexdigest()
        final_key = key.upper()
    
    return final_key

def lat_long_error(loc):
    #adapted from
    #https://gis.stackexchange.com/questions/75528/understanding-terms-in-length-of-degree-formula/75535#75535
    locs = loc.split(',')
    lat, lon = float(locs[0]), float(locs[1])
    
    m1 = 111132.92     
    m2 = -559.82      
    m3 = 1.175         
    m4 = -0.0023      
    p1 = 111412.84    
    p2 = -93.5         
    p3 = 0.118        

    
    latlen = m1 + (m2 * math.cos(2 * lat)) + (m3 * math.cos(4 * lat)) + (m4 * math.cos(6 * lat))
    longlen = (p1 * math.cos(lat)) + (p2 * math.cos(3 * lat)) + (p3 * math.cos(5 * lat))
    
    deltlat = 20000/latlen
    deltlon = 20000/longlen
    
    return (lat + random.uniform(-1,1) * deltlat, lon + random.uniform(-1,1) * deltlon)

def request_to_ipinfo():
    ''' return a json from the request '''
    full_url = 'https://ipinfo.io/json'
    headers = {'User-Agent': 'curl/7.30.0'}
    try:
        req = requests.get(full_url, headers=headers)
    except:
        return 'Unknown', 'Unknown', 'Unknown'
    
    j = req.json()
    if req.status_code == 200:
        return j['city'], j['country'], j['loc']
    else:
        return 'Unknown', 'Unknown', 'Unknown'

def quick_lic_check():
    prefs = get_settings() 
    license_ley = prefs.heal_license_key
    raw_key = license_ley.replace('-','')
        
    if len(raw_key) == 0:
        res = {'status':'FAILED'}      
    elif len(raw_key) != 16:
        res = {'status':'FAILED'}         
    else:
        res = checkLicense(raw_key)
    return res  

# -----------------------------------------------------------------------------
# primary class implementation
# -----------------------------------------------------------------------------
    
class Singleton_tracking(object):

    def __init__(self):
        self._verbose = False
        self._tracking_enabled = False
        self._appurl = ""
        self._failsafe = False
        self._dev = False
        self._port = 443
        self._background = False
        self._bg_thread = []
        self._version = ""
        self._addon = __package__.lower()
        self._tracker_json = os.path.join(os.path.dirname(__file__),
                            self._addon+"_optimize.json")
        self._tracker_idbackup = os.path.join(os.path.dirname(__file__),
                            os.pardir,self._addon+"_optimizeid.json")
        
        self._hardware_id = hardware_key()
        self.json = {}
        self._ip_location_info = {"city":None, "country":None, "loc":None}

        
    # -------------------------------------------------------------------------
    # Getters and setters
    # -------------------------------------------------------------------------

    @property
    def tracking_enabled(self):
        return self._tracking_enabled
    @tracking_enabled.setter
    def tracking_enabled(self, value):
        self._tracking_enabled = bool(value)
        self.enable_tracking(False, value)

    @property
    def verbose(self):
        return self._verbose
    @verbose.setter
    def verbose(self, value):
        try:
            self._verbose = bool(value)
        except:
            raise ValueError("Verbose must be a boolean value")

    @property
    def appurl(self):
        return self._appurl
    @appurl.setter
    def appurl(self, value):
        if value[-1] == "/":
            value = value[:-1]
        self._appurl = value

    @property
    def failsafe(self):
        return self._failsafe
    @failsafe.setter
    def failsafe(self, value):
        try:
            self._failsafe = bool(value)
        except:
            raise ValueError("failsafe must be a boolean value")

    @property
    def dev(self):
        return self._dev
    @dev.setter
    def dev(self, value):
        try:
            self._dev = bool(value)
        except:
            raise ValueError("background must be a boolean value")

    @property
    def background(self):
        return self._background
    @background.setter
    def background(self, value):
        try:
            self._background = bool(value)
        except:
            raise ValueError("background must be a boolean value")

    @property
    def version(self):
        return self._version
    @version.setter
    def version(self, value):
        self._version = value


    # -------------------------------------------------------------------------
    # Public functions
    # -------------------------------------------------------------------------

    def enable_tracking(self, toggle=True, enable=True):
        # respect toggle primarily
        if toggle == True:
            self._tracking_enabled = not self._tracking_enabled
        else:
            self._tracking_enabled = enable

        # update static json
        self.json["enable_tracking"] = self._tracking_enabled
        self.save_tracker_json()    

    def initialize_bg_and_track_install(self, appurl, version, track_install):
        """Ran as module registers, does internet calls in background.

        Will check for internet, grab IP location if any, and save for reuse
        on subsequent usage calls, and finally check if already/register new
        install.
        """

        self._appurl = appurl
        self._version = version
        args = (track_install,)
        bg_thread = threading.Thread(
            target=self.initialize,
            args=args)
        bg_thread.start()
        return bg_thread
    
    def initialize(self, track_install):
        """Initialization function to be ran fully in background thread.

        Gets location via IP address, and afterwards registers install.
        """
        if not internet():
            print('no internet')
            return  # don't do rest of installing steps, since no connection
        
        city, country, loc = request_to_ipinfo()
        new_loc = lat_long_error(loc)  # replace loc with new_loc?
        self._ip_location_info = {
            "city":city, "country":country, "loc":str(loc)
        }

        # run register-install related code; if previously installed, skip
        self.set_tracker_json()
        if not self.json["status"] and self.json["install_id"]:
            if self.json["hardware"] == self._hardware_id:
                print('already installed...')
                return
        
        if not track_install:
            print("Skipping track install")
            return
        elif self.verbose:
            print("Tracking install")
        
        if self.dev==True:
            location = "/1/track/install_dev.json/"
        else:
            location = "/1/track/install.json"

        # for compatibility to prior blender (2.75?)
        try:
            bversion = str(bpy.app.version)
        except:
            bversion = "unknown"

        # capture re-installs/other status events
        if self.json["status"]==None:
            status = "New install"
        else:
            status = self.json["status"]
            self.json["status"]=None
            self.save_tracker_json()

        self.json["install_date"] = str(datetime.now())
        
        payload = json.dumps({
                "blender":bversion,
                "coord": self._ip_location_info["loc"],
                "city": self._ip_location_info["city"],
                "country": self._ip_location_info["country"],
                "hardware":self._hardware_id,
                "platform":platform.system()+":"+platform.release(),
                "status":status,
                "timestamp": {".sv": "timestamp"},
                "usertime":self.json["install_date"],
                "version":self.version,
            })

        # run request in this thread, which should already be background
        resp = self.request('POST', location, payload)
        
        print('This is the installed tracking response from server')
        print(resp)

        # assumes input is the server response (dictionary format)
        if type(resp) != type({'name':'ID'}):
            print('some kind of failure')
            print(resp)
            return
        elif "name" not in resp:
            print('some kind of failure')
            print(resp)
            return

        self.json["install_id"] = resp["name"]
        self.save_tracker_json()
        self.save_tracker_idbackup()
        return

        # create the local file
        # push into BG push update info if true
        # create local cache file locations
        # including search for previous

    # interface request, either launches on main or background
    def request(self, method, path, payload, background=False, callback=None):
        if method not in ["POST","PUT","GET","DELETE"]:
            raise ValueError("Method must be POST, PUT, or GET")


        if background==False:
            return self.raw_request(method, path, payload, callback)
            
        else:
            # launch the daemon

            # if self._async_checking == True:
            #     return
            if self._verbose: print("Starting background thread")
            bg_thread = threading.Thread(target=self.raw_request, args=(method, path, payload, callback))
            bg_thread.daemon = True
            #self._bg_threads.append(bg_thread)
            bg_thread.start()

            return "Thread launched"

    # raw request, may be in background thread or main
    def raw_request(self, method, path, payload, callback=None):
        # convert url into domain
        url = self._appurl.split("//")[1]
        url = url.split("/")[0]

        connection = http.client.HTTPSConnection(url, self._port)
        try:
            connection.connect()
            if self.verbose:print("Connection made to "+str(path))
        except:
            print("Connection not made, verify connectivity; intended: "+str(path))
            return {'status':'NO_CONNECTION'}

        if method=="POST" or method=="PUT":
            connection.request(method, path, payload)
        elif method == "GET": # GET
            connection.request(method, path)
        elif method == "DELETE":
            connection.request(method, path)
        else:
            raise ValueError("raw_request input must be GET, POST, or PUT")

        raw = connection.getresponse().read()
        
        print('raw response from connection')
        print(raw)
        
        resp = json.loads( raw.decode() )
        if self._verbose:print("Response: "+str(resp))    

        if callback != None:
            if self._verbose:print("Running callback")
            callback(resp)

        return resp



    def set_tracker_json(self):
        if self._tracker_json == None:
            raise ValueError("optimization file is not defined")

        if os.path.isfile(self._tracker_json)==True:
            with open(self._tracker_json) as data_file:
                self.json = json.load(data_file)
            if self._verbose:print("Read in json settings from optimization file")
        
        if not os.path.isfile(self._tracker_json) or "status" not in self.json:
            # set data structure
            if self._verbose: print("Resetting json data")
            self.json = {
                "install_date":None,
                "install_id":None,
                "enable_tracking":False,
                "status":None,
                "metadata":{},
                "hardware":self._hardware_id
            }

            if os.path.isfile(self._tracker_idbackup):
                with open(self._tracker_idbackup) as data_file:
                    idbackup = json.load(data_file)
                    if self._verbose:print("Reinstall, getting idname")
                    if "idname" in idbackup:
                        self.json["install_id"] = idbackup["idname"]
                        self.json["status"] = "re-install"
                        self.json["install_date"] = idbackup["date"]
                        if "hardware" in idbackup:
                            self.json["hardware"] = idbackup["hardware"]
                        else:
                            self.json["hardware"] = self._hardware_id
            self.save_tracker_json()

        # update any other properties if necessary from json
        self._tracking_enabled = self.json["enable_tracking"]


    def save_tracker_json(self):

        jpath = self._tracker_json
        outf = open(jpath,'w')
        data_out = json.dumps(self.json,indent=4)
        outf.write(data_out)
        outf.close()
        if self._verbose:
            print("Wrote out json settings to file, with the contents:")
            print(self.json)

    def save_tracker_idbackup(self):

        jpath = self._tracker_idbackup
        
        if "install_id" in self.json and self.json["install_id"] != None:
            outf = open(jpath,'w')
            idbackup = {"idname":self.json["install_id"], 
                        "date":self.json["install_date"],
                        "hardware":self.json["hardware"]}
            
            data_out = json.dumps(idbackup,indent=4)
            outf.write(data_out)
            outf.close()
            #if self._verbose:
            print("Wrote out backup settings to file, with the contents:")
            print(idbackup)
            #end iff

    # def tracking(set='disable'):

    # def checkenable_tracking(): # ie has initial install check been done?
    # ^ similar as above, maybe unnecessary

    # def usageStat(function): # actually run push; function is key for what was ran/what to record
        # allow more complex info?



# -----------------------------------------------------------------------------
# Create the Singleton instance
# -----------------------------------------------------------------------------


Tracker = Singleton_tracking()
    

# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------



class toggleenable_tracking(bpy.types.Operator):
    """Toggle anonymous usage tracking to help the developers, disabled by default. The only data tracked is what functions are used, and the timestamp of the addon installation"""
    bl_idname = idname+".toggle_enable_tracking"
    bl_label = "Toggle opt-in for analytics tracking"
    options = {'REGISTER', 'UNDO'}

    tracking = bpy.props.EnumProperty(
        items = [('toggle', 'Toggle', 'Toggle operator use tracking'),
                ('enable', 'Enable', 'Enable operator use tracking'),
                ('disable', 'Disable', 'Disable operator use tracking (if already on)')],
        name = "tracking")

    def execute(self, context):
        if self.tracking == "toggle":
            Tracker.enable_tracking(toggle=True)
        elif self.tracking == "enable":
            Tracker.enable_tracking(toggle=False, enable=True)
        else:
            Tracker.enable_tracking(toggle=False, enable=False)
        return {'FINISHED'}


class popup_feedback(bpy.types.Operator):
    bl_idname = idname+".popup_feedback"
    bl_label = "Thanks for using {}!".format(idname)
    options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):

        # seems that only the first url open works here,
        # so many need to create operators that are just url open operations
        # for the other in-popup items.

        row = self.layout.row()
        self.layout.split()
        row = self.layout.row()
        row.label("See the latest")
        p = row.operator("wm.url_open","on the website")
        p.url = "http://theduckcow.com/dev/blender/mcprep/"

        row = self.layout.row()
        row.label("Want to support development?")
        p = row.operator("wm.url_open","Consider donating")
        p.url = "bit.ly/donate2TheDuckCow"

        self.layout.split()
        col = self.layout.column()
        col.alignment='CENTER'
        col.label("PRESS OKAY TO OPEN SURVEY BELOW")
        self.layout.split()
        col = self.layout.column()
        col.scale_y = 0.7
        col.label("Responding to the survey helps drive what devleopment is worked on")
        col.label("and identify those nasty bugs. You help everyone by responding!")

    def execute(self, context):
        bpy.ops.wm.url_open(url="bit.ly/MCprepSurvey")

        return {'FINISHED'}


# -----------------------------------------------------------------------------
# additional functions
# -----------------------------------------------------------------------------


def trackInstalled(background=None):
    return "Install tracked separately."

def trackUsage(function, param=None, background=None):
    
    #if Tracker.tracking_enabled == False: return # skip if not opted in
    #if conf.internal_change == True: return # skip if internal run

    #if Tracker.verbose: print("Tracking usage: "+function +", param: "+str(param))
    print("Tracking usage: "+function +", param: "+str(param))
    
    # if no override set, use default
    if background == None:
        background = Tracker.background

    def runUsage(background):

        if Tracker.dev==True:
            location = "/1/track/usage_dev.json"
        else:
            location = "/1/track/usage.json"
        
        # for compatibility to prior blender (2.75?)
        try:
            bversion = str(bpy.app.version)
        except:
            bversion = "unknown"
        
        payload = json.dumps({
                "blender":bversion,
                "coord": Tracker._ip_location_info["loc"],
                "city": Tracker._ip_location_info["city"],
                "country": Tracker._ip_location_info["country"],
                "hardware":Tracker._hardware_id,
                "function":function,
                "param":str(param),
                "timestamp":{".sv": "timestamp"},
                "usertime":str(datetime.now()),
                "version":Tracker.version
            })

        resp = Tracker.request('POST', location, payload, background)
        print(resp)
    if Tracker.failsafe == True:
        try:
            runUsage(background)
        except:
            pass
    else:
        runUsage(background)


def registerKey(lkey, background=None):
    

    if Tracker.dev==True:
        location = "/1/track/register_dev.json"
    else:
        location = "/1/track/register.json"

    payload = json.dumps({
            "timestamp": {".sv": "timestamp"},
            "usertime":str(datetime.now()),
            "hardware":Tracker._hardware_id,
            "license":lkey
            })

    resp = Tracker.request('POST', location, payload, background, callback = None)



def checkLicense(lkey, background=None):
    

    if Tracker.dev==True:
        location = "/1/track/auth_dev.json"
    else:
        location = "/1/track/auth.json"

    payload = json.dumps({
            "hardware":Tracker._hardware_id,
            "license":lkey
            })

    resp = Tracker.request('POST', location, payload, background=False, callback = None)
    
    if 'name' in resp:
        if Tracker.dev == True:
            location = '/1/track/auth_dev/' + resp['name'] + ".json"
        else:
            location = '/1/track/auth/' + resp['name'] + ".json"
        resp = Tracker.request('DELETE', location, payload = {}, background = False)
        return {'status':'AUTHORIZED'}
    
    elif 'status' in resp:
        print(resp)
        return resp
    else:
        return {'status':'FAILED'}
        

# -----------------------------------------------------------------------------
# registration related
# -----------------------------------------------------------------------------


def register(bl_info):
    
    # will launch backgorund thread which tracks install
    Tracker.initialize_bg_and_track_install(
        appurl = "https://occlusal-guard-beta.firebaseio.com",
        version = str(bl_info["version"]),
        track_install = True
        )

    prefs = get_settings()
    
    if prefs.dev == True:
        Tracker.dev = True
    else:
        Tracker.dev = False
        
    if Tracker.dev == True:
        Tracker.verbose = False
        Tracker.background = True # test either way
        Tracker.failsafe = False # test either way
        Tracker.tracking_enabled = True # enabled automatically for testing
    else:
        Tracker.verbose = False
        Tracker.background = True
        Tracker.failsafe = True
        Tracker.tracking_enabled = True # User accepted on download

    # trackInstalled()  # ran through the initialize function above

def unregister():
    pass


if __name__ == "__main__":
    register({"bl_info":(1,0,7)})
