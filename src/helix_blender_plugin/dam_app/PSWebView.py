import os
import logging
import platform
import subprocess
from select import select
import sys
from logging.handlers import TimedRotatingFileHandler
from logging import Formatter
from xml.dom import minidom

# Import PyQt modules
if platform.system() != "Windows":
    sys.path.insert(0, str(os.path.dirname(__file__)) + "/site_packages/")
import PyQt5
import psutil
from PyQt5.QtCore import QSize, QUrl, Qt, QTimer, pyqtSignal, pyqtSlot, pyqtProperty, QObject, QThread
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QSplitter, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtGui import QDesktopServices, QIcon

# Import resource files (compiled js, html and css files taken from Maya plugin)
from resources import photoshop_plugin_rc
from resources import pswebview_rc
from resources import spectrum_components_rc

if platform.system() == 'Windows':
    import win32gui
    import win32process
    config_path = str(os.path.abspath(".")) + "\\logs\\config.xml"
    logpath = str(os.path.abspath(".")) + '\\logs\\run.log'
    iconpath = str(os.path.abspath(".")) + '\\icon\\plugin_402x.png'
else:
    config_path = str(os.path.abspath(".")) + "/logs/config.xml"
    logpath = str(os.path.abspath(".")) + '/logs/run.log'
    iconpath = str(os.path.abspath(".")) + '/icon/plugin_402x.png'

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
logger.info("DAM seesion launched")
logger.info("Log level " + log_level)

# Import bridge class and script injection function
from ObjectInjection import objectInjectionScripts
from PSWebViewBridge import PSWebViewBridge

host_pid = None


class Worker(QObject):
    finished = pyqtSignal()
    result = pyqtSignal(str)

    def run(self):
        logger.info("In worker thread")
        while True:
            logger.info(host_pid)
            if host_pid and not psutil.pid_exists(host_pid):
                dam_pid = os.getpid()
                logger.info("DAM pid to be killed, ", dam_pid)
                process = psutil.Process(dam_pid)
                for proc in process.children(recursive=True):
                    proc.kill()
                process.kill()
                self.finished.emit()
                break
            logger.info("Waiting for input")
            output = str(sys.stdin.readline())
            logger.info(output)
            sys.stdin.flush()
            logger.info("Event recieved")
            logger.info("DAM input type " + output[0])

            self.result.emit(output)


class OpenLinksExternallyWebEnginePage(QWebEnginePage):
    ''' This class is called to open the url in default browser of the system.
        For example, an error message might have a link to a page in our docs.
        We don't want that link to load in our QWebEngineView,
        so we need to be able to ask the system webbrowser to load it.'''

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        if _type == QWebEnginePage.NavigationTypeLinkClicked:
            QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, _type, isMainFrame)


class PSWebView(QWidget):
    ''' This class provides the public Qt-based interface to a Photoshop plugin'''
    logger.info("In PSWebView Class")

    # Signal to notify when active document path changed or new file loaded in host application
    activeDocumentPathChanged = pyqtSignal(str)

    def __init__(self, mPanelID="helixdam", mDevToolsVisible=False):
        super(PSWebView, self).__init__()
        self.mPanelID = mPanelID  # Panel ID attribute to show from the manifest.json
        self.mDevToolsVisible = mDevToolsVisible  # Attribute to enable/disbale developer tool in a splitter window
        self.host_pid = None  # Host application process ID requires to check whether host process running or not
        self.rendering_label = None

        # Create a bridge object with all the required parameters obtained from manifest.json
        logger.info("Creating bridge object")
        self.mBridge = PSWebViewBridge(self.mPanelID)

        # Set up the UI
        logger.info("Setting up the UI")
        self.layout = QVBoxLayout(self)
        self.mSplitter = QSplitter(self)
        self.mSplitter.setOrientation(Qt.Vertical)
        self.layout.addWidget(self.mSplitter)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.mMainview = QWebEngineView(self.mSplitter)  # Create an instance of QWebEngineView
        self.mMainview.setPage(OpenLinksExternallyWebEnginePage(self))

        if self.mDevToolsVisible:
            self.mDevTools = QWebEngineView(self.mSplitter)

        self.mainPage = self.mMainview.page()  # Create an instance of QWebEnginePage
        self.mainPage.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        if self.mDevToolsVisible:
            self.mainPage.setDevToolsPage(self.mDevTools.page())
        self.mSplitter.addWidget(self.mMainview)

        if self.mDevToolsVisible:
            self.mSplitter.addWidget(self.mDevTools)
            self.mDevTools.setVisible(self.mDevToolsVisible)

        # Load size preferences
        logger.info("Loading size preferences")
        minimumSize = self.mBridge.panelManifest()['minimumSize']
        self.mMinimumSize = QSize(minimumSize['width'] - 1, minimumSize['height'] - 1)
        maximumSize = self.mBridge.panelManifest()['maximumSize']
        max = QSize(maximumSize['width'] - 1, maximumSize['height'] - 1)

        if max.isValid():
            self.setMaximumSize(max)

        size = self.mBridge.panelManifest()['preferredFloatingSize']

        if size:
            size = self.mBridge.panelManifest()['preferredDockedSize']

        self.mPreferredSize = QSize(size['width'] - 1, size['height'] - 1)
        self.setWindowTitle(self.mBridge.panelManifest()['label']['default'])
        self.mMainview.setContextMenuPolicy(Qt.NoContextMenu)

        # BOOTSTRAP THE PLUGIN ENVIRONMENT
        logger.info("Bootstrap plugin env")

        # Propagate signals for this property to the public interface.
        self.mBridge.activeDocumentPathChanged.connect(self.activeDocumentPathChanged)

        # Inject all the scripts needed to inject the PSWebViewBridge
        logger.info("Injecting scripts")
        self.mainPage.scripts().insert(objectInjectionScripts())

        # Create a webchannel and register the bridge object to it
        webchannel = QWebChannel(self.mainPage)
        webchannel.registerObject("PSWebViewBridge", self.mBridge)
        self.mainPage.setWebChannel(webchannel)

        # Load the index, which boots up the plugin
        logger.info("Loading index.html")
        self.mainPage.setUrl(QUrl("qrc:/pswebview/custom-index.html"))

        # Track the url load progress
        try:
            self.mainPage.loadProgress.connect(self.on_load_progress)
            self.mainPage.loadFinished.connect(self.on_load_finished)
        except Exception as e:
            logging.error("Exception in loading:\n" + str(e))

    @pyqtSlot(bool)
    def on_load_finished(self):
        ''' Show QApplication and start QTimer on URL load finished '''
        logger.info("URL load successful")
        if host_pid:
            return
        self.show()
        self.initialStdin()
        if platform.system() == "Windows":
            try:
                self.worker_thread = QThread()
                logger.info("Worker thread " + str(self.worker_thread.currentThreadId()))
                logger.info("Main app thread after setting worker" + str(self.thread))
                self.worker = Worker()  # Create a worker object
                self.worker.moveToThread(self.worker_thread)  # Move worker to the thread
                self.worker_thread.started.connect(self.worker.run)  # Connect signals and slots
                self.worker.finished.connect(self.worker_thread.quit)
                self.worker.finished.connect(self.worker.deleteLater)
                self.worker_thread.finished.connect(self.worker_thread.deleteLater)
                self.worker.result.connect(self.readStdinFromThread)
                self.worker_thread.start()  # Start the thread
            except Exception as e:
                logger.info("Thread exception " + str(e))

        self.startTimer()

    @pyqtSlot(int)
    def on_load_progress(self, prog):
        logger.info("URL load progress " + str(prog))

    def setActiveDocumentPath(self, path):
        logger.info("Calling bridge object to set path")
        return self.mBridge.setActiveDocumentPath(path)

    @pyqtProperty(str, notify=activeDocumentPathChanged)
    def activeDocumentPath(self):
        logger.info("Notifying bridge object about path")
        return self.mBridge.activeDocumentPath()

    @pyqtProperty(bool)
    def setDevToolsVisible(self, visible):
        if self.mDevToolsVisible == visible:
            return
        if not self.mDevTools:
            self.mDevTools = QWebEngineView(self.mSplitter)
            self.mMainview.page().setDevToolsPage(self.mDevTools.page())
            self.mSplitter.addWidget(self.mDevTools)

        self.mDevToolsVisible = visible
        self.mDevTools.setVisible(visible)

    def areDevToolsVisible(self):
        self.mDevToolsVisible

    def notifyActiveDocumentWasSaved(self, path):
        '''Set the active document just in case the calling code didn't do it first'''
        logger.info("Notifying bridge object about save")
        self.setActiveDocumentPath(path)
        self.mBridge.activeDocumentWasSaved.emit(path)

    def minimumSizeHint(self):
        if self.mMinimumSize.isValid():
            return self.mMinimumSize
        return QWidget.minimumSizeHint()

    def sizeHint(self):
        if self.mPreferredSize.isValid():
            return self.mPreferredSize
        return QWidget.sizeHint()

    def startTimer(self):
        ''' This is a QTimer which calls "isHostRunning" function every seconds '''
        if self.host_pid and psutil.pid_exists(self.host_pid):
            self.timer_obj = QTimer()
            if platform.system() == "Windows":
                self.timer_obj.timeout.connect(self.isWinHostRunning)
            else:
                self.timer_obj.timeout.connect(self.isHostRunning)
            self.timer_obj.start(1000)
            
    def isWinHostRunning(self):
        ''' This method checks whether the windows Host app is running or not.'''
        logger.debug("Host app is active")
        if not self.host_pid:
            return
        title = getWinTitle(self.host_pid)
        if len(title) == 0 or title == "no title":
            self.endDamProc()

    def isHostRunning(self):
        ''' This method checks whether the Host app is running or not. '''
        logger.debug("Host app is active")
        if self.host_pid and not psutil.pid_exists(self.host_pid):
            self.endDamProc()
        self.checkStdin()
            
    def endDamProc(self):
        '''This method will stop the QTimer and kill the dam process'''
        self.timer_obj.stop()
        dam_pid = os.getpid()
        logger.info("Killing DAM pid" + str(dam_pid))
        process = psutil.Process(dam_pid)
        for proc in process.children(recursive=True):
            proc.kill()
        process.kill()

    def checkStdin(self):
        # Reading stdin puts a deadlock until it receives an input.
        # To avoid it, python's "select" module provides a way to
        # check if anything is there in stdin or not within a time limit (0.001 sec in our case)
        # "select" does not work in case of Windows
        rlist, _, _ = select([sys.stdin], [], [], 0.001)
        if rlist:
            self.initialStdin()

    def readStdinFromThread(self, output):
        logger.info("Output " + output)
        self.readStdin(output)

    def initialStdin(self):
        logger.info("Event recieved")
        output = str(sys.stdin.readline())
        logger.info("DAM input type " + output[0])
        sys.stdin.flush()
        self.readStdin(output)

    def readStdin(self, output):
        ''' This is the other end of IPC which reads stdin data (in string format) written by the Host.
            Classify which kind of input received and perform different operations. '''

        global host_pid
        path = None

        # Event "l" stands for "Launch" the app again (or bring it to foreground) with the active session
        # Work in two conditions 1. when user close the DAM window
        #                        2. when app is in background
        # Doesn't work when app is minimized
        if output[0] == "l":
            self.show()
            bringToFront(os.getpid())
            return

        if self.rendering_label:
            self.rendering_label.deleteLater()
            self.rendering_label = None

        # Event "i" stands for "Initials" require to send active file path to bridge object and get the Host ID
        if output[0] == "i":
            res = output[1:].split(",")
            logger.info(res)
            self.host_pid = int(res[0])
            host_pid = self.host_pid
            logger.info("Host PID " + str(self.host_pid))
            path = res[1][:-1]
            logger.info("Initial filepath " + path)

        # Event "f" stands for "File Changed" require to send active file path to bridge object
        if output[0] == "f":
            path = output[1:][:-1]
            logger.info("Loaded filepath " + path)

        # Event "s" stands for "File Saved" require to send file saved notification to bridge object
        if output[0] == "s":
            path = output[1:][:-1]
            logger.info("Saved filepath " + path)

        # Event "r" stands for "Rendering is started" and require to show 'rendering in progress' message in DAM window
        if output[0] == "r":
            path = output[1:][:-1]
            if path and self.mBridge.mActiveFileInDAM == path:
                self.rendering_label = QLabel("   Please wait rendering is in progress...")
                logger.info("active docu while rendering " + self.mBridge.mActiveDocumentPath)
                self.rendering_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.layout.addWidget(self.rendering_label)

        logger.info("Current document path " + str(path))

        if path and len(path) > 1:
            if output[0] in ["i", "f"]:
                self.setActiveDocumentPath(path)
            elif output[0] == "s":
                self.notifyActiveDocumentWasSaved(path)

    def closeEvent(self, event):
        ''' This is a close event (inbuilt method of a QApplication) called when a user close the app.
            Once a user clicks on close button, dam window doesn't quit.
            It hides the window and keeps the session alive. '''
        event.ignore()
        self.hide()

def getWinTitle(pid):
    '''This function checks whether the windows Blender is active or not'''
    def callbacks(hwnd, hwnds):
        if str(win32process.GetWindowThreadProcessId(hwnd)[1])==str(pid):
            hwnds.append(hwnd)
        return True
    hwnds = []
    win32gui.EnumWindows(callbacks, hwnds)

    if len(hwnds) > 0:
        title = str(win32gui.GetWindowText(hwnds[0]))
        return title
    else:
        return ""

def bringToFront(procID):
    ''' This function brings a process ID to foreground by executing an osascript'''
    proc_to_fg = "/usr/bin/osascript -e \'set processID to {id} \ntell application \"System Events\" to set frontmost of every process whose unix id is processID to true\' "
    proc_to_fg = proc_to_fg.format(id=str(procID))
    os.system(proc_to_fg)


if __name__ == "__main__":
    ''' Main function calls the PSWebView class and launch a QApplication '''
    try:
        app = QApplication(sys.argv)
        logger.info("Main app thread " + str(app.instance().thread()))
        window = PSWebView()
        window.setMinimumSize(600, 400)
        app.setWindowIcon(QIcon(iconpath))
        app.exec_()

    except Exception as e:
        logging.error("Exception in main :\n" + str(e))
