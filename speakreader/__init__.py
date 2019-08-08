# SpeakReader

import os
import threading
import uuid
import pyaudio
import cherrypy

# Some cut down versions of Python may not include this module and it's not critical for us
try:
    import webbrowser
    no_browser = False
except ImportError:
    no_browser = True

from speakreader import webstart, logger, config, version
from speakreader.version import Version
from speakreader.transcribeEngine import TranscribeEngine
from speakreader.queueManager import QueueManager

PROG_DIR = None
DATA_DIR = None
CONFIG = None
INIT_LOCK = threading.Lock()

# Identify Our Application
PRODUCT = 'SpeakReader'
VERSION_RELEASE = "V1.1.6"
GITHUB_BRANCH = "Master"

# TODO: Update checks and auto update from GITHUB
# TODO: Do something about certgen. Do you need it?

class SpeakReader(object):
    _INITIALIZED = False
    SIGNAL = None
    transcribeEngine = None
    HTTP_PORT = None
    _INPUT_DEVICE = None

    ###################################################################################################
    #  Initialize SpeakReader
    ###################################################################################################
    def __init__(self, initOptions):
        if SpeakReader._INITIALIZED:
            return

        with INIT_LOCK:

            global PROG_DIR
            PROG_DIR = initOptions['prog_dir']

            global DATA_DIR
            DATA_DIR = initOptions['data_dir']

            global CONFIG
            CONFIG = initOptions['config']
            assert CONFIG is not None

            if isinstance(initOptions['http_port'], int):
                self.HTTP_PORT = initOptions['http_port']
            else:
                self.HTTP_PORT = int(CONFIG.HTTP_PORT)

            if self.HTTP_PORT < 21 or self.HTTP_PORT > 65535:
                logger.warn("HTTP_PORT out of bounds: 21 < %s < 65535", self.HTTP_PORT)
                self.HTTP_PORT = 8880

            # Check if pyOpenSSL is installed. It is required for certificate generation
            # and for CherryPy.
            if CONFIG.ENABLE_HTTPS:
                try:
                    import OpenSSL
                except ImportError:
                    logger.warn("The pyOpenSSL module is missing. Install this "
                                "module to enable HTTPS. HTTPS will be disabled.")
                    CONFIG.ENABLE_HTTPS = False

                if not CONFIG.HTTPS_CERT:
                    CONFIG.HTTPS_CERT = os.path.join(DATA_DIR, 'server.crt')
                if not CONFIG.HTTPS_KEY:
                    CONFIG.HTTPS_KEY = os.path.join(DATA_DIR, 'server.key')

                if not (os.path.exists(CONFIG.HTTPS_CERT) and os.path.exists(CONFIG.HTTPS_KEY)):
                    logger.warn("Disabled HTTPS because of missing certificate and key.")
                    CONFIG.ENABLE_HTTPS = False

            # Check if we has a jwt_secret
            if CONFIG.JWT_SECRET == '' or not CONFIG.JWT_SECRET:
                logger.debug("Generating JWT secret...")
                CONFIG.JWT_SECRET = generate_uuid()
                CONFIG.write()

            ###################################################################################################
            #  Get Version Information and check for updates
            ###################################################################################################
            self.versionInfo = Version()

            ###################################################################################################
            #  Get the Input Device
            ###################################################################################################
            self.get_input_device()

            ###################################################################################################
            #  Initialize the Queue Manager
            ###################################################################################################
            self.queueManager = QueueManager()

            ###################################################################################################
            #  Initialize the Transcribe Engine
            ###################################################################################################
            self.transcribeEngine = TranscribeEngine(self.queueManager.transcriptHandler.getReceiverQueue())

            if CONFIG.START_TRANSCRIBE_ON_STARTUP :
                self.startTranscribeEngine()

            ###################################################################################################
            #  Initialize the webserver
            ###################################################################################################
            logger.info('WebServer Initializing')
            webServerOptions = {
                'config': CONFIG,
                'prog_dir': PROG_DIR,
                'data_dir': DATA_DIR,
                'http_port': self.HTTP_PORT,
            }
            self.webServer = webstart.initialize(webServerOptions)
            self.webServer.root.SR = self
            cherrypy.server.start()

            # Launch the WebBrowser
            if CONFIG.LAUNCH_BROWSER and not initOptions['nolaunch']:
                launch_browser(CONFIG.HTTP_HOST, self.HTTP_PORT, CONFIG.HTTP_ROOT + 'manage')

            SpeakReader._INITIALIZED = True

    @property
    def is_initialized(self):
        return self._INITIALIZED

    ###################################################################################################
    #  Start the Transcribe Engine
    ###################################################################################################
    def startTranscribeEngine(self):
        if CONFIG.CREDENTIALS_FILE == "":
            logger.warn("API Credentials not available. Can't start Transcribe Engine.")
            return

        if self.transcribeEngine.is_online:
            logger.info("Transcribe Engine already started.")
            return

        if self.get_input_device() is None:
            logger.warn("No Input Devices Available. Can't start Transcribe Engine.")
            return

        self.transcribeEngine.start()

    ###################################################################################################
    #  Stop the Transcribe Engine
    ###################################################################################################
    def stopTranscribeEngine(self):
        if self.transcribeEngine.is_online:
            self.transcribeEngine.stop()

    ###################################################################################################
    #  Shutdown SpeakReader
    ###################################################################################################
    def shutdown(self, restart=False, update=False, checkout=False):
        import time
        SpeakReader._INITIALIZED = False
        self.stopTranscribeEngine()
        self.queueManager.shutdown()
        logger.info('WebServer Terminating')
        cherrypy.engine.exit()

        CONFIG.write()

        if not restart and not update and not checkout:
            logger.info("Shutting Down SpeakReader")

        if update:
            logger.info("SpeakReader is updating...")
            try:
                self.versionInfo.update()
            except Exception as e:
                logger.warn("SpeakReader failed to update: %s. Restarting." % e)

        if checkout:
            logger.info("SpeakReader is switching the git branch...")
            try:
                self.versionInfo.checkout_git_branch()
            except Exception as e:
                logger.warn("SpeakReader failed to switch git branch: %s. Restarting." % e)


    ###################################################################################################
    #  Get Input Device
    ###################################################################################################
    def get_input_device(self):
        self._INPUT_DEVICE = CONFIG.INPUT_DEVICE
        try:
            p = pyaudio.PyAudio()
            defaultInputDevice = p.get_default_input_device_info()

            if self._INPUT_DEVICE not in list(d['name'] for d in self.get_input_device_list()):
                CONFIG.INPUT_DEVICE = self._INPUT_DEVICE = defaultInputDevice.get('name')
                CONFIG.write()
        except:
            self._INPUT_DEVICE = None

        return self._INPUT_DEVICE

    ###################################################################################################
    #  Get Input Device List
    ###################################################################################################
    def get_input_device_list(self):
        deviceList = []
        try:
            p = pyaudio.PyAudio()
            defaultHostAPIindex = p.get_default_host_api_info().get('index')
            numdevices = p.get_default_host_api_info().get('deviceCount')
            for i in range(0, numdevices):
                inputDevice = p.get_device_info_by_host_api_device_index(defaultHostAPIindex, i)
                if inputDevice.get('maxInputChannels') > 0:
                    device = {
                        'index':    inputDevice.get('index'),
                        'name':     inputDevice.get('name'),
                        'selected': True if inputDevice.get('name') == self._INPUT_DEVICE else False,
                    }
                    deviceList.append(device)
        except Exception:
            pass

        return deviceList


def generate_uuid():
    return uuid.uuid4().hex


def launch_browser(host, port, root):
    if not no_browser:
        if host == '0.0.0.0':
            host = 'localhost'

        if CONFIG.ENABLE_HTTPS:
            protocol = 'https'
        else:
            protocol = 'http'

        try:
            webbrowser.open('%s://%s:%i%s' % (protocol, host, port, root))
        except Exception as e:
            logger.error("Could not launch browser: %s" % e)
