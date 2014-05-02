###
#
# WEIO Web Of Things Platform
# Copyright (C) 2013 Nodesign.net, Uros PETREVSKI, Drasko DRASKOVIC
# All rights reserved
#
#               ##      ## ######## ####  #######
#               ##  ##  ## ##        ##  ##     ##
#               ##  ##  ## ##        ##  ##     ##
#               ##  ##  ## ######    ##  ##     ##
#               ##  ##  ## ##        ##  ##     ##
#               ##  ##  ## ##        ##  ##     ##
#                ###  ###  ######## ####  #######
#
#                    Web Of Things Platform
#
# This file is part of WEIO
# WEIO is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# WEIO is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Authors :
# Uros PETREVSKI <uros@nodesign.net>
# Drasko DRASKOVIC <drasko.draskovic@gmail.com>
#
###

import os, signal, sys, platform, subprocess, datetime
from os.path import isfile, join

from tornado import web, ioloop, iostream, gen
sys.path.append(r'./');
from sockjs.tornado import SockJSRouter, SockJSConnection

import functools
import json
from weioLib import weioIpAddress
from weioLib import weioFiles

from shutil import copyfile, copytree

# IMPORT BASIC CONFIGURATION FILE
from weioLib import weio_config

# Import globals for main Tornado
from weioLib import weioIdeGlobals


# Wifi detection route handler
class WeioDashBoardHandler(SockJSConnection):
    global callbacks

    # Handler sanity, True alive, False dead
    global stdoutHandlerIsLive
    global stderrHandlerIsLive

    stdoutHandlerIsLive = None
    stderrHandlerIsLive = None

    def __init__(self, *args, **kwargs):
        SockJSConnection.__init__(self, *args, **kwargs)
        self.errObject = []
        self.errReason = ""

    def setEditor(editor):
        self.editor = editor

    # DEFINE CALLBACKS HERE
    # First, define callback that will be called from websocket
    def sendIp(self,rq):

        # get configuration from file
        config = weio_config.getConfiguration()

        data = {}
        ip = weioIpAddress.getLocalIpAddress()
        #publicIp = weioIpAddress.getPublicIpAddress()
        data['requested'] = rq['request']
        data['status'] = config["dns_name"] + " on " + ip
        # Send connection information to the client
        self.send(json.dumps(data))

    def sendLastProjectName(self,rq):

        # get configuration from file
        config = weio_config.getConfiguration()

        data = {}
        data['requested'] = rq['request']
        lp = config["last_opened_project"].split("/")

        #print "USER PRJ NAME",lp

        if (weioFiles.checkIfDirectoryExists(config["user_projects_path"]+config["last_opened_project"])):
            print "PROJ NAME", config["user_projects_path"]+config["last_opened_project"]
            data['data'] = lp[2]
        else :
            data['data'] = "Select project here"
        # Send connection information to the client
        self.send(json.dumps(data))

    def play(self, rq):
        weioIdeGlobals.PLAYER.play(rq)

    def stop(self, rq):
        """Stop running application"""
        weioIdeGlobals.PLAYER.stop(rq)

    def sendPlatformDetails(self, rq):
        # get configuration from file
        config = weio_config.getConfiguration()

        data = {}

        platformS = ""

        platformS += "WeIO version " + config["weio_version"] + " with Python " + platform.python_version() + " on " + platform.system() + "<br>"
        platformS += "GPL 3, Nodesign.net 2013 Uros Petrevski & Drasko Draskovic <br>"

        data['serverPush'] = 'sysConsole'
        data['data'] = platformS
        weioIdeGlobals.CONSOLE.send(json.dumps(data))

    def getUserProjectsList(self, rq):

        # get configuration from file
        config = weio_config.getConfiguration()

        data = {}
        data['requested'] = rq['request']
        #data['data'] = weioFiles.listOnlyFolders(config["user_projects_path"]+"examples/userProjects")

        userDirs = weioFiles.listUserDirectories(config["user_projects_path"])

        #print "PROJECTS ", userDirs
        allUserProjects = []
        for d in userDirs:
            prj = weioFiles.listOnlyFolders(d+"/userProjects")
            a = {"projects": prj, "path":d, "storageName":os.path.basename(d)}
            if (len(prj)>0):
                allUserProjects.append(a)

        data['data'] = allUserProjects

        #TODO add listing for examples, flash & sd card storage
        self.send(json.dumps(data))

    def changeProject(self,rq):
        #print "CHANGE PROJECT", rq
        # get configuration from file
        print "TO CHANGE ", rq
        config = weio_config.getConfiguration()
        # TODO add directories logic for examples, flash & sd card
        config["last_opened_project"] = rq['data']+"/"
        weio_config.saveConfiguration(config);

        data = {}
        data['requested'] = rq['request']
        self.send(json.dumps(data))

        rqlist = ["stop", "getLastProjectName", "getUserProjetsFolderList"]

        for i in range(0,len(rqlist)):
            rq['request'] = rqlist[i]
            callbacks[rq['request']](self, rq)


    def sendUserData(self,rq):
        data = {}
        # get configuration from file
        config = weio_config.getConfiguration()
        data['requested'] = rq['request']

        data['name'] = config["user"]
        self.send(json.dumps(data))

    def newProject(self, rq):
        config = weio_config.getConfiguration()
        #print "NEW PROJECT", rq
        data = {}
        data['requested'] = rq['request']
        path = rq['storageUnit'] + "/userProjects/" + rq['path']

        weioFiles.createDirectory(config["user_projects_path"] + path)
        # ADD HERE SOME DEFAULT FILES
        # adding __init__.py
        weioFiles.saveRawContentToFile(config["user_projects_path"] + path + "/__init__.py", "")

        # copy all files from directory boilerplate to destination
        mypath = "www/libs/weio/boilerPlate/"
        onlyfiles = [ f for f in os.listdir(mypath) if isfile(join(mypath,f)) ]
        for f in onlyfiles:
            copyfile(mypath+f, config["user_projects_path"] + path +"/"+f)

        data['status'] = "New project created"
        data['path'] = path
        self.send(json.dumps(data))

    def duplicateProject(self, rq):
        config = weio_config.getConfiguration()

        path = rq['storageUnit'] + "/userProjects/" + rq['path']

        # destroy symlinks before
        # os.unlink(config["user_projects_path"]+config["last_opened_project"]+"weioLibs")
        copytree(config["user_projects_path"]+config["last_opened_project"],config["user_projects_path"]+path)

        data = {}
        data['requested'] = "status"
        data['status'] = "Project duplicated"
        self.send(json.dumps(data))

        # now go to newely duplicated project

        data['request'] = "changeProject"
        data['data'] = path

        self.changeProject(data)

    def deleteCurrentProject(self, rq):

        data = {}
        data['requested'] = rq['request']

        config = weio_config.getConfiguration()
        projectToKill = config["last_opened_project"]

        print "PROJECT TO KILL ", projectToKill

        weioFiles.removeDirectory(config["user_projects_path"]+projectToKill)

        folders = weioFiles.listOnlyFolders(config["user_projects_path"]+ "examples/userProjects")

        if len(folders) > 0 :
         config["last_opened_project"] = folders[0]
         weio_config.saveConfiguration(config)

         data['data'] = "reload page"
        else :
         data['data'] = "ask to create new project"

        self.send(json.dumps(data))

    def iteratePacketRequests(self, rq) :

        requests = rq["packets"]

        for uniqueRq in requests:
            request = uniqueRq['request']
            if request in callbacks:
                callbacks[request](self, uniqueRq)
            else :
                print "unrecognised request ", uniqueRq['request']

    def sendPlayerStatus(self, rq):
        data = {}
        data['requested'] = rq['request']
        data['status'] = weioIdeGlobals.PLAYER.playing

        self.send(json.dumps(data))

    def createTarForProject(self, rq):
        # TEST IF NAME IS OK FIRST
        # get configuration from file
        config = weio_config.getConfiguration()
        data = {}
        data['requested'] = "status"
        data['status'] = "Making archive..."
        self.send(json.dumps(data))

        data['requested'] = rq['request']

        splitted = config["last_opened_project"].split("/")
        lp = splitted[2]
        storage = splitted[0]

        if (weioFiles.checkIfDirectoryExists(config["user_projects_path"]+config["last_opened_project"])):
            weioFiles.createTarfile(config["user_projects_path"]+config["last_opened_project"]+lp+".tar", config["user_projects_path"]+config["last_opened_project"])
            data['status'] = "Project archived"
            print "project archived"
        else :
            data['status'] = "Error archiving project"

        self.send(json.dumps(data))

    def decompressNewProject(self, rq):
        print "decompress"
        f = rq['data']
        name = f['name']
        contents = f['data']
        storageUnit = rq['storageUnit'] +"/"
        #print contents

        # get configuration from file
        confFile = weio_config.getConfiguration()
        pathCurrentProject = confFile["user_projects_path"] + storageUnit

        projectName = name.split(".tar")[0]
        data = {}

        if (weioFiles.checkIfDirectoryExists(pathCurrentProject+projectName) is False) :
            #decode from base64, file is binary
            bin = contents
            bin = bin.split(",")[1] # split header, for example: "data:image/jpeg;base64,"
            weioFiles.saveRawContentToFile(pathCurrentProject+name, bin.decode("base64"))
            #print "save to ", pathCurrentProject+name
            weioFiles.createDirectory(pathCurrentProject+"userProjects/"+projectName)
            #print "mkdir ", pathCurrentProject+"userProjects/"+projectName
            weioFiles.unTarFile(pathCurrentProject+name, pathCurrentProject+"userProjects/"+projectName)
            #print "untar ", pathCurrentProject+"userProjects/"+projectName

            data['request'] = "changeProject"
            data['data'] = storageUnit+"userProjects/"+projectName

            self.changeProject(data)
        else :
            data['requested'] = 'status'
            data['status'] = "Error this projet already exists"
            self.send(json.dumps(data))


##############################################################################################################################
    # DEFINE CALLBACKS IN DICTIONARY
    # Second, associate key with right function to be called
    # key is comming from socket and call associated function
    callbacks = {
        'getIp' : sendIp,
        'getLastProjectName' : sendLastProjectName,
        #'getFileTreeHtml' : getTreeInHTML,
        #'getFile': sendFileContent,
        'play' : play,
        'stop' : stop,
        'getUserProjetsFolderList': getUserProjectsList,
        'changeProject': changeProject,
        #'saveFile': saveFile,
        #'createNewFile': createNewFile,
        #'deleteFile': deleteFile,
        'getUser': sendUserData,
        'createNewProject': newProject,
        'deleteProject' : deleteCurrentProject,
        'packetRequests': iteratePacketRequests,
        'getPlayerStatus': sendPlayerStatus,
        'archiveProject' : createTarForProject,
        'addNewProjectFromArchive' : decompressNewProject,
        'duplicateProject': duplicateProject

    }

    def on_open(self, info) :
        # Store instance of the ConsoleConnection class
        # in the global variable that will be used
        # by the MainProgram thread
        weioIdeGlobals.CONSOLE = self
        # connect interfaces to player object
        weioIdeGlobals.PLAYER.setConnectionObject(self)


    def on_message(self, data):
        """Parsing JSON data that is comming from browser into python object"""
        req = json.loads(data)
        self.serve(req)

    def serve(self, rq):
        """Parsed input from browser ready to be served"""
        # Call callback by key directly from socket
        global callbacks
        request = rq['request']

        if request in callbacks :
            callbacks[request](self, rq)
        else :
            print "unrecognised request ", rq['request']
