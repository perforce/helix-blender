import json
import os
import logging
import platform
import sys
import ast
from pathlib import Path

# Import PyQt modules
if platform.system() != "Windows":
    sys.path.insert(0, str(os.path.dirname(__file__)) + "/site_packages/")
import PyQt5
import psutil
from PyQt5.QtCore import QOperatingSystemVersion, QSysInfo, QDir, QUrl, QObject, pyqtSlot, pyqtSignal, QVariant, \
    pyqtProperty, QFile
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtGui import QDesktopServices

# Import resource files (compiled js, html and css files taken from Maya plugin)
from resources import pswebview_rc

logger = logging.getLogger("__main__")


class PSWebViewBridge(QObject):
    ''' The PSWebViewBridge class is the QObject that is injected into
        the Javascript environment of the plugin. It provides a bridge for
        Javascript to communicate with the Qt side and vice-versa.
        It provides the public interface of the host application to Javascript.'''

    logger.info("In PSWebViewBridge Class")

    # Siganls accessible to JavaScript
    activeDocumentPathChanged = pyqtSignal(str)
    activeDocumentWasSaved = pyqtSignal(str)

    def __init__(self, mPanelID):
        super().__init__()
        self.mPanelID = mPanelID
        self.mActiveDocumentPath = None
        self.mActiveFileInDAM = None

        # Load manifest.json file and convert the data in dictionary format
        file_handle = QFile("://pswebview/manifest.json")
        file_handle.open(QFile.ReadOnly)
        data = bytes(file_handle.readAll()).decode('utf-8')
        self.mManifest = ast.literal_eval(data)

        # Fetch the panel manifest through the entrypoints in manifest.json
        self.mPanelManifest = None
        for entrypoint in self.mManifest['entrypoints']:
            if entrypoint["id"] == self.mPanelID:
                self.mPanelManifest = entrypoint
                break
        self.mOpenURLHandler = QDesktopServices.openUrl

    @pyqtProperty(str, constant=True)
    def panelID(self):
        ''' The ID of the desired panel to show'''
        return self.mPanelID

    @pyqtProperty(QVariant, constant=True)
    def manifest(self):
        ''' The manifest.json of the plugin'''
        return self.mManifest

    def panelManifest(self):
        '''The section of the manifest.json file pertaining to the current
            panelID. This is for PSWebView to use as a convenience.'''
        return self.mPanelManifest

    @pyqtProperty(bool, constant=True)
    def debug(self):
        ''' Whether or not this is a debug version '''
        return True

    @pyqtProperty(str, constant=True)
    def platform(self):
        ''' The platform name (ex: macOS)'''
        return QOperatingSystemVersion.current().name()

    @pyqtProperty(str, constant=True)
    def release(self):
        ''' The version string'''
        return QSysInfo.productVersion()

    def setActiveDocumentPath(self, path):
        ''' Sets the path to the active document. Set by PSWebView.'''
        if self.mActiveDocumentPath == path:
            return
        self.mActiveDocumentPath = path
        logger.info("Emitting path changed signal")
        self.activeDocumentPathChanged.emit(path)

    @pyqtProperty(str, notify=activeDocumentPathChanged)
    def activeDocumentPath(self):
        logger.info("Returns activeDocumentPath to JS")
        return self.mActiveDocumentPath

    @pyqtSlot(str)
    def openExternal(self, url):
        ''' Called to request the host application open a URL'''
        logger.info("Open external " + str(url))
        if platform.system() == "Windows":
            return True
        else:
            return self.mOpenURLHandler(url)

    @pyqtSlot(str)
    def openPath(self, path):
        ''' Called to request the host application open a file.
            Calls through to openExternal() with a file:/// url.'''
        logger.info("Open path " + str(path))
        self.mActiveFileInDAM = str(path)
        if str(path).split(".")[-1] == "blend":
            try:
                if platform.system() == "Windows":
                    val = str(path) + "\n"
                    sys.stdout.write(val)
                    sys.stdout.flush()
                    logger.info("Open file command sent")
                return self.openExternal(QUrl.fromLocalFile(path))
            except Exception as e:
                logger.info("Open path error " + e)

    @pyqtSlot(result=str)
    def getFolder(self):
        ''' Opens a folder choosing dialog
            return what the user chose or a null QString'''
        path = QFileDialog.getExistingDirectory()
        nativePath = QDir.toNativeSeparators(path)
        logger.info("Native path " + str(nativePath))
        return nativePath

    def setOpenURLHandler(self, handler):
        ''' Users of this class can override the behavior of the call to
             openExternal() for custom handling. By default, it asks the
             host OS to handle it.'''
        self.mOpenURLHandler = handler
