import os
import platform
import subprocess
import sysconfig
import threading
import sys
import bpy
import logging
import binascii
import requests
from logging.handlers import TimedRotatingFileHandler
from logging import Formatter
from bpy.types import Menu, Operator
from bpy.app.handlers import persistent
from helix_blender_plugin import bl_info, Helix_Blender_build
from xml.dom import minidom

#setting app and python path
if platform.system() == 'Windows':
    app_path = str(os.path.dirname(__file__)) + "\\HelixBlenderPlugin.exe"
    proc_cmd = [app_path]
    config_path = str(os.path.dirname(__file__)) + "\\logs\\config.xml"
    logpath = str(os.path.dirname(__file__)) + "\\logs\\run.log"

else:
    os.chdir(str(os.path.dirname(__file__)))
    app_path = (str(os.path.dirname(__file__)) + "/HelixBlenderPlugin")
    proc_cmd = [app_path]
    config_path = str(os.path.dirname(__file__)) + "/logs/config.xml"
    logpath = str(os.path.dirname(__file__)) + "/logs/run.log"

bl_debug = False
dam_proc = None
loadFilePath = None
rThread = None

logger = logging.getLogger(__name__)
handler = TimedRotatingFileHandler(filename=logpath, when='D', interval=1, backupCount=15, encoding='utf-8', delay=False)
formatter = Formatter(fmt='%(asctime)s [%(filename)s:%(lineno)d] : %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
handler.setFormatter(formatter)
logger.addHandler(handler)

def get_logger():
    file = minidom.parse(config_path)
    models = file.getElementsByTagName('log_level')
    log_val = str(models[0].firstChild.data)
    if log_val in ["INFO", "NOTSET"]:
        return log_val
    else:
        return "NOTSET"

log_level = get_logger()
logger.setLevel(eval("logging" + "." + log_level))
logger.info("New session launched in Blender")
logger.info("Log level " + log_level)
        
def openFileThread():
    logger.info("Open file thread started")
    global loadFilePath 
    global rThread
    while True:
        if dam_proc and psutil.pid_exists(dam_proc.pid):
            output = str(dam_proc.stdout.readline())
            output = output[2:-5]
            dam_proc.stdout.flush()
            logger.info("DAM output " + output)
            if len(output) == 0:
                continue
            else:
                loadFilePath = output  
        else:
            logger.info("Open file thread finished")
            rThread = None
            break  

def loadFileTimed():
    global loadFilePath
    if not loadFilePath:
        return 0.1
    try:
        logger.info("Loading file in Blender " + str(loadFilePath))
        bpy.ops.wm.open_mainfile("INVOKE_DEFAULT", filepath = loadFilePath, display_file_selector=False)
        loadFilePath = None
    except Exception as e:
        logger.info(str(e))
    finally:
        loadFilePath = None
        return 0.1
    return 0.1

def saveFileTimed():
    global blender_render_proc

    if blender_render_proc and psutil.pid_exists(blender_render_proc.pid):
        output = str(blender_render_proc.stdout.readline())
        output = output[2:-3]
        blender_render_proc.stdout.flush()
        if len(output) > 0:
            logger.info("blender render proc output " + output)
            if output == "Blender quit":
                logger.info("rendering finished ")
                setPreviewAttr()
                writeToProc("s")
                return None
        return 0.1

    else:
        if platform.system() == "Windows":
            logger.info("rendering finished ")
            setPreviewAttr()
            writeToProc("s")
            return None
        return None


if platform.system() == "Windows":
    bpy.app.timers.register(loadFileTimed) 

def writeToProc(event):
    if dam_proc and psutil.pid_exists(dam_proc.pid):
        fp = str(bpy.data.filepath)
        if platform.system() == "Windows":
            pList = fp.split("\\\\")
            fp = chr(92).join(pList)   
        val = event + fp + "\n"
        bval = bytes(val, 'utf-8')
        logger.info("Event type "+ str(event))
        logger.info("File loaded " + fp)
        dam_proc.stdin.write(bval)
        dam_proc.stdin.flush()
        return

def setPreviewAttr():
    blend_filepath = str(os.path.abspath(bpy.data.filepath))  # active blend file
    blend_dirpath, blend_filename = os.path.split(blend_filepath)
    logger.info("current directory " + blend_dirpath)
    logger.info("active blend file " + blend_filename)

    if platform.system() == "Windows":
        pList = blend_filepath.split("\\")
        blend_filepath = chr(92).join(pList)

    curr_dir = os.getcwd()
    os.chdir(blend_dirpath)
    logger.info("active directory" + os.getcwd())

    # set preview image path in the active blend file directory
    preview_filepath = os.path.join(blend_dirpath, "preview.jpg")

    if not os.path.exists(preview_filepath):
        logger.info("unable to generate preview image from Blender")
        writeToProc("s")
        return None

    # set headers post call
    headers = {
        'X-P4ROOT': blend_dirpath,
        'X-P4CHARSET': 'utf8',
    }

    # convert preview image to hex string
    with open(preview_filepath, 'rb') as f:
        hex_data = binascii.hexlify(f.read()).decode()

    #delete preview image
    if os.path.exists(preview_filepath):
        os.remove(preview_filepath)

    # set body parameter for attribute API
    json_data = {
        "flags": ["-e", "-n", "preview", "-v", hex_data],
        "files": [blend_filepath],
    }

    try:
        # post request for setting preview attribute
        logger.info("post call to preview attribute")
        response_API = requests.post('http://localhost:3002/api/v1/attribute', headers=headers, json=json_data)
        logger.info("response " + str(response_API.text))
        logger.info("status " + str(response_API.status_code))

    except Exception as e:
        logger.info("Exception from rest call >> " + str(e))

    finally:
        os.chdir(curr_dir)


@persistent
def generateOnLoadFile(dummy):
    ''' On loading a file in Blender, this function writes a "f"+"filepath" (loaded file path) string to dam process '''
    if platform.system() == "Windows":
        bpy.app.timers.register(loadFileTimed)
    writeToProc("f")

@persistent
def generateOnSaveFile(dummy):
    ''' On saving a file in Blender, this function writes a "s"+"filepath" (saved file path) string to dam process '''
    writeToProc("r")
    global blender_render_proc
    bpy.app.timers.register(saveFileTimed)
    proc_cmd=[bpy.app.binary_path,
              "-b", bpy.data.filepath,
              "--python", os.path.join(os.path.dirname(__file__), "preview_generation.py")]
    blender_render_proc = subprocess.Popen( proc_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

class DamLogin(Operator):
    '''Launch "Helix DAM" from here'''
    bl_idname = "helix_blender_plugin.damlogin"
    bl_label = "DAM UI"

    def execute(self, context):
        ''' This method execute when user clicks on "Helix DAM" button.
            Starts a DAM process if it is not running already and write initials "i" + "host pid" + "filepath".
            for aready running DAM process, try to send relaunch signal "l". '''
        global dam_proc
        global rThread
        global psutil
        from .site_packages import psutil

        if generateOnLoadFile not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(generateOnLoadFile)

        if generateOnSaveFile not in bpy.app.handlers.save_post:
            bpy.app.handlers.save_post.append(generateOnSaveFile)

        if dam_proc and psutil.pid_exists(dam_proc.pid):
            try :
                writeToProc("l")
                return {'FINISHED'}
            except:
                logger.info("DAM pid to be killed, " + str(dam_proc.pid))
                process = psutil.Process(dam_proc.pid)
                for proc in process.children(recursive=True):
                    proc.kill()
                process.kill()
                dam_proc = subprocess.Popen(
                                proc_cmd,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(os.path.dirname(__file__)))
                logger.info("DAM pid created, "+ str(dam_proc.pid))
                if platform.system() == "Windows" and not rThread:
                    readerThread = threading.Thread(target=openFileThread, args=())
                    readerThread.setDaemon(True)
                    readerThread.start()
                    rThread = readerThread
        else:
            dam_proc = subprocess.Popen(proc_cmd,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(os.path.dirname(__file__)))
            logger.info("DAM pid created, "+ str(dam_proc.pid))
            if platform.system() == "Windows" and not rThread:
                readerThread = threading.Thread(target=openFileThread, args=())
                readerThread.setDaemon(True)
                readerThread.start()
                rThread = readerThread

        logger.info("DAM process" + str(dam_proc))
        writeToProc("i" + str(os.getpid()) + ",")
        return {'FINISHED'}


class DamHelp(Operator):
    '''For help'''
    bl_idname = "helix_blender_plugin.damhelp"
    bl_label = "DAM Help"
    
    def execute(self, context):
        '''To be changed - Loads loads Maya User Guide'''
        bpy.ops.wm.url_open(url=bl_info["doc_url"])
        return {'FINISHED'}


class DamAbout(Operator):
    '''About Helix-Blender'''
    bl_idname = "helix_blender_plugin.damabout"
    bl_label = "About Helix Blender"
    
    def execute(self, context):
        return {'FINISHED'}
        
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=450)
    
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        split = layout.split(factor=0.65)
        
        #left split items
        col = split.column()
        col.label(text="Helix Blender version : " + ".".join([str(x) for x in bl_info["version"]]) + " - Build : " + Helix_Blender_build)
        col.label(text="Blender version : "+bpy.app.version_string)
        col.label(text="Platform : "+sysconfig.get_platform())
        col.label(text="Copyright (C) 2024 Perforce Software, Inc.")
        
        #right split items
        col = split.column()
        col.label(text="")
        col.operator("wm.url_open", text="Perforce", icon='URL',).url = "https://www.perforce.com/"
        col.operator("wm.url_open", text="Support", icon='URL',).url = "https://www.perforce.com/support"
        col.label(text="")
    

class TOPBAR_MT_DAM_menu(Menu):
    bl_label = "Perforce"

    def draw(self, context):
        layout = self.layout
        layout.menu("TOPBAR_MT_DAM_Editor_menus", text="Perforce")


class TOPBAR_MT_DAM_Editor_menus(Menu):
    bl_label = "Helix DAM"

    def draw(self, context):
        layout = self.layout
        layout.separator()
        layout.operator("helix_blender_plugin.damlogin", text="Helix DAM", icon="UV_SYNC_SELECT")
        layout.separator()
        layout.operator("helix_blender_plugin.damhelp", text="Help", icon = "HELP")
        layout.operator("helix_blender_plugin.damabout", text="About", icon = "INFO")
