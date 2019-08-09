# This file is part of SpeakReader.
#

import os
from stat import ST_CTIME
import json
import datetime
import time
import queue

import cherrypy
from cherrypy.lib.static import serve_download

from mako.lookup import TemplateLookup
from mako import exceptions
from passlib.hash import pbkdf2_sha256

import speakreader
from speakreader import logger
from speakreader.session import get_session_info, get_session_user_id
from speakreader.webauth import AuthController, requireAuth, is_admin


def checked(variable):
    if variable:
        return 'checked'
    else:
        return ''


def serve_template(templatename, **kwargs):
    http_root = speakreader.CONFIG.HTTP_ROOT
    server_name = speakreader.PRODUCT
    # TODO: Remove timestamp from cache_param when done.
    cache_param = '?v=' + speakreader.VERSION_RELEASE + '-' + datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")

    template_dir = os.path.join(str(speakreader.PROG_DIR), 'html')

    _hplookup = TemplateLookup(directories=[template_dir], default_filters=['unicode', 'h'])

    _session = get_session_info()

    try:
        template = _hplookup.get_template(templatename)
        return template.render(http_root=http_root, server_name=server_name, cache_param=cache_param,
                               _session=_session, **kwargs)
    except:
        return exceptions.html_error_template().render()


class WebInterface(object):

    auth = AuthController()
    SR = None

    def __init__(self):
        pass


    ###################################################################################################
    #  Home Page
    ###################################################################################################
    @cherrypy.expose
    def index(self, **kwargs):
        return self.listen()

    @cherrypy.expose
    def listen(self, **kwargs):
        return serve_template(templatename="listen.html", title="Listen")


    ###################################################################################################
    #  Manage the Service
    ###################################################################################################
    @cherrypy.expose
    @requireAuth()
    def manage(self, **kwargs):
        productInfo = {
            "product": speakreader.PRODUCT,
            "current_version": self.SR.versionInfo.INSTALLED_RELEASE,
        }
        settings = self.getSettings()
        return serve_template(templatename="manage.html", title="Management Console", productInfo=productInfo, config=settings['config'])

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @requireAuth(is_admin())
    def getSettings(self, **kwargs):

        config = {
            "start_transcribe_on_startup": speakreader.CONFIG.START_TRANSCRIBE_ON_STARTUP,
            "launch_browser": speakreader.CONFIG.LAUNCH_BROWSER,
            "transcripts_folder": speakreader.CONFIG.TRANSCRIPTS_FOLDER,
            "log_dir": speakreader.CONFIG.LOG_DIR,
            "http_port": speakreader.CONFIG.HTTP_PORT,
            "enable_https": speakreader.CONFIG.ENABLE_HTTPS,
            "https_cert": speakreader.CONFIG.HTTPS_CERT,
            "https_cert_chain": speakreader.CONFIG.HTTPS_CERT_CHAIN,
            "https_key": speakreader.CONFIG.HTTPS_KEY,
            "credentials_file": speakreader.CONFIG.CREDENTIALS_FILE,
            "show_interim_results": speakreader.CONFIG.SHOW_INTERIM_RESULTS,
            "enable_censorship": speakreader.CONFIG.ENABLE_CENSORSHIP,
            "censored_words": '\r\n'.join(speakreader.CONFIG.CENSORED_WORDS),
            "http_basic_auth": speakreader.CONFIG.HTTP_BASIC_AUTH,
            "http_username": speakreader.CONFIG.HTTP_USERNAME,
            "http_hash_password": speakreader.CONFIG.HTTP_HASH_PASSWORD,
            "hashed_password": speakreader.CONFIG.HTTP_HASH_PASSWORD,
            "check_github": speakreader.CONFIG.CHECK_GITHUB,
            "git_token": speakreader.CONFIG.GIT_TOKEN,
            "git_remote": speakreader.CONFIG.GIT_REMOTE,
            "git_branch": speakreader.CONFIG.GIT_BRANCH,
            "git_path": speakreader.CONFIG.GIT_PATH,
            "install_type": self.SR.versionInfo.INSTALL_TYPE,
        }

        return {"result": "success", "config": config}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @requireAuth(is_admin())
    def configUpdate(self, **kwargs):
        logger.info("Processing configUpdate.")

        restartTranscribeEngine = False
        restartSpeakReader = False
        logout = False

        checked_configs = [
            "start_transcribe_on_startup",
            "launch_browser",
            "enable_https",
            "show_interim_results",
            "enable_censorship",
            "http_hash_password",
            "http_basic_auth",
            "check_github",
        ]
        for checked_config in checked_configs:
            if checked_config not in kwargs:
                # checked items should be zero or one. if they were not sent then the item was not checked
                kwargs[checked_config] = 0
            else:
                kwargs[checked_config] = 1

        upload_credentials_file = kwargs.pop('upload_credentials_file')
        if upload_credentials_file.file != None:
            self.upload_credentials_file(upload_credentials_file)
            kwargs['credentials_file'] = os.path.join(speakreader.DATA_DIR, upload_credentials_file.filename)

        if kwargs.get('credentials_file') != speakreader.CONFIG.CREDENTIALS_FILE \
        or kwargs.get('enable_censorship') != speakreader.CONFIG.ENABLE_CENSORSHIP \
        or kwargs.get('input_device') != speakreader.CONFIG.INPUT_DEVICE:
            restartTranscribeEngine = True

        if kwargs.get('http_port') != str(speakreader.CONFIG.HTTP_PORT) \
        or kwargs.get('enable_https') != speakreader.CONFIG.ENABLE_HTTPS \
        or kwargs.get('https_cert') != speakreader.CONFIG.HTTPS_CERT \
        or kwargs.get('https_cert_chain') != speakreader.CONFIG.HTTPS_CERT_CHAIN \
        or kwargs.get('https_key') != speakreader.CONFIG.HTTPS_KEY \
        or kwargs.get('transcripts_folder') != speakreader.CONFIG.TRANSCRIPTS_FOLDER \
        or kwargs.get('log_dir') != speakreader.CONFIG.LOG_DIR:
            restartSpeakReader = True

        kwargs['censored_words'] = kwargs['censored_words'].rstrip('\r\n').replace('\r\n', ',').split(',')
        while ("" in kwargs['censored_words']):
            kwargs['censored_words'].remove("")

        set_http_password = int(kwargs.pop('set_http_password', 0))
        if kwargs.get('http_username') == "":
            kwargs['http_password'] = ""
        else:
            if set_http_password:
                if kwargs.get('http_hash_password'):
                    kwargs['http_password'] = pbkdf2_sha256.hash(kwargs['http_password'])
            else:
                kwargs.pop('http_password', 0)
                if kwargs.get('http_hash_password') != speakreader.CONFIG.HTTP_HASH_PASSWORD:
                    if kwargs.get('http_hash_password') and speakreader.CONFIG.HTTP_PASSWORD != "":
                        kwargs['http_password'] = pbkdf2_sha256.hash(speakreader.CONFIG.HTTP_PASSWORD)

        if kwargs['http_username'] != speakreader.CONFIG.HTTP_USERNAME or set_http_password:
            logout = True

        speakreader.CONFIG.process_kwargs(kwargs)
        speakreader.CONFIG.write()

        if restartSpeakReader:
            self.restart()
            return {'portchanged': True}

        if restartTranscribeEngine and self.SR.transcribeEngine.is_online:
            self.SR.stopTranscribeEngine()
            self.SR.startTranscribeEngine()

        return {'result': 'success', 'credentials_file': kwargs['credentials_file'], 'logout': logout, 'portchanged': False}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @requireAuth(is_admin())
    def startTranscribe(self, **kwargs):
        self.SR.startTranscribeEngine()
        return {'result': 'success'}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @requireAuth(is_admin())
    def stopTranscribe(self, **kwargs):
        self.SR.stopTranscribeEngine()
        return {'result': 'success'}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @requireAuth(is_admin())
    def checkForUpdate(self, **kwargs):
        logger.info("Checking for Updates")
        self.SR.versionInfo.checkForUpdate()
        versionInfo = {
            "latest_release": self.SR.versionInfo.LATEST_RELEASE,
            "latest_release_url": self.SR.versionInfo.LATEST_RELEASE_URL,
            "update_available": int(bool(self.SR.versionInfo.UPDATE_AVAILABLE)),
        }
        return versionInfo

    @cherrypy.expose
    @requireAuth(is_admin())
    def update(self, **kwargs):
        if self.SR.versionInfo.UPDATE_AVAILABLE:
            return self.do_state_change('update', 'Updating', 60)
        else:
            logger.info("No Updates Available")
            return self.manage()

    @cherrypy.expose
    @requireAuth(is_admin())
    def shutdown(self, **kwargs):
        self.SR.queueManager.closeAllListeners()
        return self.do_state_change('shutdown', 'Shutting Down', 15)

    @cherrypy.expose
    @requireAuth(is_admin())
    def restart(self, **kwargs):
        self.SR.queueManager.closeAllListeners()
        return self.do_state_change('restart', 'Restarting', 30)

    @cherrypy.expose
    @requireAuth(is_admin())
    def checkout_git_branch(self, git_remote=None, git_branch=None, **kwargs):
        if git_branch == speakreader.CONFIG.GIT_BRANCH:
            logger.error(u"Already on the %s branch" % git_branch)
            raise cherrypy.HTTPRedirect(speakreader.CONFIG.HTTP_ROOT + "manage")

        # Set the new git remote and branch
        speakreader.CONFIG.__setattr__('GIT_REMOTE', git_remote)
        speakreader.CONFIG.__setattr__('GIT_BRANCH', git_branch)
        speakreader.CONFIG.write()
        return self.do_state_change('checkout', 'Switching Git Branches', 120)

    def do_state_change(self, signal, title, timer, **kwargs):
        message = title
        self.SR.SIGNAL = signal

        if speakreader.CONFIG.HTTP_ROOT.strip('/'):
            new_http_root = '/' + speakreader.CONFIG.HTTP_ROOT.strip('/') + '/'
        else:
            new_http_root = '/'

        return serve_template(templatename="confirm.html", signal=signal, title=title,
                              new_http_root=new_http_root, message=message, timer=timer)

    ###################################################################################################
    #  Event Sources
    ###################################################################################################

    @cherrypy.expose
    def removeListener(self, **kwargs):
        cl = cherrypy.request.headers['Content-Length']
        data = json.loads(cherrypy.request.body.read(int(cl)))
        self.SR.queueManager.removeListener(type=data['type'], sessionID=data['sessionID'])

    @cherrypy.expose
    def addListener(self, **kwargs):
        cherrypy.response.headers["Content-Type"] = "text/event-stream;charset=utf-8"
        type = kwargs.get('type', None)
        sessionID = kwargs.get('sessionID', None)
        remoteIP = cherrypy.request.remote.ip
        def eventSource(type, listenerQueue, remoteIP, sessionID):
            while self.SR.queueManager.is_initialized:
                try:
                    data = listenerQueue.get(timeout=5)
                except queue.Empty:
                    continue
                if data == None:
                    close_event = json.dumps({"event": "close"})
                    yield 'data: {}\n\n'.format(close_event)
                    break
                yield 'data: {}\n\n'.format(data)
            logger.debug("Exiting " + type.capitalize() + " Listener loop for IP: " + remoteIP + " with sessionID: " + sessionID)

        listenerQueue = self.SR.queueManager.addListener(type=type, remoteIP=remoteIP, sessionID=sessionID)

        if type == 'transcript':
            if self.SR.transcribeEngine.is_online:
                listenerQueue.put_nowait(json.dumps(self.SR.transcribeEngine.ONLINE_MESSAGE))
            else:
                listenerQueue.put_nowait(json.dumps(self.SR.transcribeEngine.OFFLINE_MESSAGE))

        return eventSource(type, listenerQueue, remoteIP, sessionID)
    addListener._cp_config = {'response.stream': True}

    @cherrypy.expose
    @requireAuth(is_admin())
    def transcribeEngineStatus(self, **kwargs):
        cherrypy.response.headers["Content-Type"] = "text/event-stream;charset=utf-8"

        def eventSource():
            while self.SR.is_initialized:
                yield 'data: {}\n\n'.format(self.SR.transcribeEngine.is_online)
                time.sleep(1.0)
            yield 'data: {}\n\n'.format('Close')

        return eventSource()
    transcribeEngineStatus._cp_config = {'response.stream': True}


    ###################################################################################################
    #  Helper Routines
    ###################################################################################################
    def upload_credentials_file(self, ufile):
        # Either save the file to the directory where server.py is
        # or save the file to a given path:
        # upload_path = '/path/to/project/data/'
        upload_path = speakreader.DATA_DIR

        # Save the file to a predefined filename
        # or use the filename sent by the client:
        # upload_filename = ufile.filename
        upload_filename = ufile.filename

        upload_file = os.path.normpath(
            os.path.join(upload_path, upload_filename))
        size = 0
        with open(upload_file, 'wb') as out:
            while True:
                data = ufile.file.read(8192)
                if not data:
                    break
                out.write(data)
                size += len(data)
        return


    ###################################################################################################
    #  AJAX calls
    ###################################################################################################
    @cherrypy.expose
    @requireAuth(is_admin())
    def get_input_device_list(self, **kwargs):
        inputDeviceList = self.SR.get_input_device_list()
        data = json.dumps(inputDeviceList)
        return data

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @requireAuth(is_admin())
    def get_files_list(self, **kwargs):
        if kwargs.get('list') == 'logs':
            path = speakreader.CONFIG.LOG_DIR
        elif kwargs.get('list') == 'transcripts':
            path = speakreader.CONFIG.TRANSCRIPTS_FOLDER
        else:
            return {"result": "error"}

        fileList = []
        with os.scandir(path=path) as files:
            for file in files:
                file_info = file.stat()
                fileList.append({"name": file.name,
                                 "created": datetime.datetime.fromtimestamp(file_info.st_ctime).strftime('%b %d, %Y %I:%M %p')})
        return {"data": fileList}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @requireAuth(is_admin())
    def view_file(self, **kwargs):
        if kwargs.get('log'):
            file = os.path.join(speakreader.CONFIG.LOG_DIR, kwargs['log'])
            with open(file) as f:
                data = '<p>' + f.read().replace("\n", "</p><p>") + '</p>'

        elif kwargs.get('transcript'):
            file = os.path.join(speakreader.CONFIG.TRANSCRIPTS_FOLDER, kwargs['transcript'])
            with open(file) as f:
                data = "<p>" + f.read().rstrip("\n\n").replace("\n\n", "</p><p>") + "</p>"
        else:
            return {"result": "error"}

        return {"result": "success", "data": data}


    @cherrypy.expose
    @cherrypy.tools.json_out()
    @requireAuth(is_admin())
    def delete_file(self, **kwargs):
        if kwargs.get('log'):
            file = os.path.join(speakreader.CONFIG.LOG_DIR, kwargs['log'])
        elif kwargs.get('transcript'):
            file = os.path.join(speakreader.CONFIG.TRANSCRIPTS_FOLDER, kwargs['transcript'])
        else:
            return {"result": "error"}

        if os.path.exists(file):
            os.remove(file)
        return {"result": "success"}

    @cherrypy.expose
    @requireAuth(is_admin())
    def download_file(self, **kwargs):
        """ Download the file. """

        if kwargs.get('log'):
            path = speakreader.CONFIG.LOG_DIR
            file = kwargs['log']
        elif kwargs.get('transcript'):
            path = speakreader.CONFIG.TRANSCRIPTS_FOLDER
            file = kwargs['transcript']
        else:
            return

        return serve_download(os.path.join(path, file), name=file)
