# **************************************************************************************
# * This file is part of SpeakReader.
# *
# *  SpeakReader is free software: you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License V3 as published by
# *  the Free Software Foundation.
# *
# *  SpeakReader is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with SpeakReader.  If not, see <http://www.gnu.org/licenses/gpl-3.0.html>.
# **************************************************************************************

# This module is the main initialization module for the SpeakReader functions.

import os
import threading
import uuid
import pyaudio
import cherrypy
import json
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger


try:
    import webbrowser
    no_browser = False
except ImportError:
    no_browser = True

from speakreader import webstart, logger, config, version
from speakreader.versionMgmt import Version
from speakreader.transcribeEngine import TranscribeEngine

PROG_DIR = None
DATA_DIR = None
CONFIG = None
INIT_LOCK = threading.Lock()

# Identify Our Application
PRODUCT = version.PRODUCT
VERSION_RELEASE = version.VERSION_RELEASE
GITHUB_BRANCH = version.GITHUB_BRANCH


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
            #  Initialize the Transcribe Engine
            ###################################################################################################
            self.transcribeEngine = TranscribeEngine()

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

            ###################################################################################################
            #  Run cleanup of old logs, transcripts, and recordings and start a scheduler to run every 24 hours
            ###################################################################################################
            self.cleanup_files()
            self.scheduler = BackgroundScheduler()
            self.scheduler.add_job(self.cleanup_files, 'interval', hours=24)
            self.scheduler.start()

            SpeakReader._INITIALIZED = True

    @property
    def is_initialized(self):
        return self._INITIALIZED

    ###################################################################################################
    #  Start the Transcribe Engine
    ###################################################################################################
    def startTranscribeEngine(self):
        if self.transcribeEngine.is_online:
            logger.info("Transcribe Engine already started.")
            return

        if self.get_input_device() is None:
            logger.warn("No Input Devices Available. Can't start Transcribe Engine.")
            return

        if CONFIG.SPEECH_TO_TEXT_SERVICE == 'google':
            if CONFIG.GOOGLE_CREDENTIALS_FILE == "":
                logger.warn("API Credentials not available. Can't start Transcribe Engine.")
                return
            try:
                with open(CONFIG.GOOGLE_CREDENTIALS_FILE) as f:
                    json.loads(f.read())
            except json.decoder.JSONDecodeError:
                logger.warn("API Credentials does not appear to be a valid JSON file. Can't start Transcribe Engine.")
                return

        elif CONFIG.SPEECH_TO_TEXT_SERVICE == 'IBM':
            if CONFIG.IBM_CREDENTIALS_FILE == "":
                logger.warn("API Credentials not available. Can't start Transcribe Engine.")
                return

            APIKEY = None
            URL = None
            try:
                with open(CONFIG.IBM_CREDENTIALS_FILE) as f:
                    for line in f.read().splitlines():
                        parm = line.split('=')
                        if parm[0] == 'SPEECH_TO_TEXT_APIKEY':
                            APIKEY = parm[1]
                        if parm[0] == 'SPEECH_TO_TEXT_URL':
                            URL = parm[1]
            except:
                pass
            if APIKEY is None or URL is None:
                logger.warn("APIKEY or URL not found in IBM credentials file. Can't start Transcribe Engine.")
                return

        elif CONFIG.SPEECH_TO_TEXT_SERVICE == 'microsoft':
            if CONFIG.MICROSOFT_SERVICE_APIKEY == "" or CONFIG.MICROSOFT_SERVICE_REGION == "":
                logger.warn("Microsoft Azure APIKEY and Region are required. Can't start Transcribe Engine.")
                return

        else:
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
        SpeakReader._INITIALIZED = False
        self.transcribeEngine.shutdown()
        self.scheduler.shutdown()
        CONFIG.write()

        if not restart and not update and not checkout:
            logger.info("Shutting Down SpeakReader")

        if update:
            logger.info("********************************")
            logger.info("*  SpeakReader is updating...  *")
            logger.info("********************************")
            try:
                self.versionInfo.update()
            except Exception as e:
                logger.warn("SpeakReader failed to update: %s. Restarting." % e)

        logger.info('WebServer Terminating')
        cherrypy.engine.exit()

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


    ###################################################################################################
    #  Delete any files over the retention days
    ###################################################################################################
    def cleanup_files(self):
        logger.info("Running File Cleanup")
        def delete(path, days):
            try:
                days = int(days)
            except ValueError:
                return
            delete_date = datetime.datetime.now() - datetime.timedelta(days=days)
            with os.scandir(path=path) as files:
                for file in files:
                    file_info = file.stat()
                    if datetime.datetime.fromtimestamp(file_info.st_ctime) < delete_date:
                        filename = os.path.join(path, file.name)
                        logger.debug("Deleting: %s" % filename)
                        os.remove(filename)

        if CONFIG.LOG_RETENTION_DAYS != "":
            delete(CONFIG.LOG_DIR, CONFIG.LOG_RETENTION_DAYS)

        if CONFIG.TRANSCRIPT_RETENTION_DAYS != "":
            delete(CONFIG.TRANSCRIPTS_FOLDER, CONFIG.TRANSCRIPT_RETENTION_DAYS)

        if CONFIG.RECORDING_RETENTION_DAYS != "":
            delete(CONFIG.RECORDINGS_FOLDER, CONFIG.RECORDING_RETENTION_DAYS)


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
