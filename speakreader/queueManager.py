import threading
import queue
from queue import Queue
import json
import os
import datetime

import speakreader
from speakreader import logger
import logging
from logging import handlers

FILENAME_PREFIX = "Transcript-"
FILENAME_SUFFIX = "txt"
FILENAME_DATE_FORMAT = "%Y-%m-%d-%H%M"
FILENAME_DATESTRING = datetime.datetime.now().strftime(FILENAME_DATE_FORMAT)
FILENAME = FILENAME_PREFIX + FILENAME_DATESTRING + "." + FILENAME_SUFFIX


class QueueManager(object):

    _INITIALIZED = False

    def __init__(self):
        if self._INITIALIZED:
            logger.warn('Queue Manager already Initialized')
            return
        logger.info('Queue Manager Initializing')
        self.transcriptHandler = TranscriptHandler("TranscriptQueueHandler")
        self.logHandler = LogHandler("LogQueueHandler")
        self._INITIALIZED = True

    @property
    def is_initialized(self):
        return self._INITIALIZED

    def shutdown(self):
        self._INITIALIZED = False
        self.transcriptHandler.shutdown()
        self.logHandler.shutdown()
        logger.info("Queue Manager terminated")

    def closeAllListeners(self):
        self.transcriptHandler.closeAllListeners()
        self.logHandler.closeAllListeners()

    def addListener(self, type=None, sessionID=None, remoteIP=None):
        if type == "log":
            return self.logHandler.addListener(type=type, sessionID=sessionID, remoteIP=remoteIP)
        elif type == "transcript":
            return self.transcriptHandler.addListener(type=type, sessionID=sessionID, remoteIP=remoteIP)
        return None

    def removeListener(self, type=None, sessionID=None, remoteIP=None):
        if type == "log":
            self.logHandler.removeListener(sessionID=sessionID)
        elif type == "transcript":
            self.transcriptHandler.removeListener(sessionID=sessionID)

    def getUsage(self):
        usage = {}
        usage['transcript'] = self.transcriptHandler.getUsage()
        usage['log'] = self.logHandler.getUsage()
        return usage

class QueueHandler(object):

    def __init__(self, name):
        self._STARTED = False
        self.fileLock = threading.Lock()
        self._receiverQueue = None
        self._listenerQueues = {}
        self._queueHandlerThread = None
        self.logFileName = None
        self.transcriptFile = None
        self.threadName = name

        # Initialize the Handler queue manager
        self._receiverQueue = Queue(maxsize=-1)
        self._queueHandlerThread = threading.Thread(name=self.threadName, target=self.runHandler)
        self._queueHandlerThread.start()

    def getReceiverQueue(self):
        return self._receiverQueue

    @property
    def is_started(self):
        if self._queueHandlerThread is None or not self._queueHandlerThread.is_alive():
            self._STARTED = False
        return self._STARTED

    def runHandler(self):
        pass


    def addListener(self, type=None, remoteIP=None, sessionID=None):
        if not self._STARTED or  not remoteIP or not sessionID:
            return None

        logger.info("Adding " + type.capitalize() + " Listener Queue for IP: " + remoteIP + " with SessionID: " + sessionID)

        queueElement = QueueElement(type=type, remoteIP=remoteIP, sessionID=sessionID)
        self._listenerQueues[sessionID] = queueElement

        data = {"event": "open",
                "sessionID": sessionID,
                }
        queueElement.put_nowait(json.dumps(data))

        data = None
        if type == "log":
            if self.logFileName:
                with open(self.logFileName) as f:
                    records = '<p>' + f.read().replace("\n", "</p><p>") + '</p>'
                data = {"event": "logrecord",
                        "final": "reload",
                        "record": records,
                        }
        elif type == "transcript":
            if self.transcriptFile:
                with self.fileLock:
                    self.transcriptFile.flush()
                    os.fsync(self.transcriptFile.fileno())
                    self.transcriptFile.seek(0)
                    records = "<p>" + self.transcriptFile.read().rstrip("\n\n").replace("\n\n", "</p><p>") + "</p>"
                data = {"event": "transcript",
                        "final": "reload",
                        "record": records,
                        }

        if data:
            queueElement.put_nowait(json.dumps(data))

        return queueElement.listenerQueue


    def removeListener(self, sessionID=None, listenerQueue=None):

        queueElement = None
        if sessionID is not None:
            queueElement = self._listenerQueues[sessionID]

        elif listenerQueue is not None:
            for sessionID, queueElement in self._listenerQueues.items():
                if queueElement.listenerQueue == listenerQueue:
                    break

        if queueElement is not None:
            logger.info("Removing " + queueElement.type.capitalize() + " Listener Queue for IP: " + queueElement.remoteIP + " with SessionID: " + sessionID)
            queueElement.clear()
            queueElement.put_nowait(None)
            self._listenerQueues.pop(sessionID)

    def closeAllListeners(self):
        for sessionID in list(self._listenerQueues.keys()):
            self.removeListener(sessionID=sessionID)

    def shutdown(self):
        self.closeAllListeners()
        self._receiverQueue.put(None)
        self._queueHandlerThread.join()
        self._STARTED = False

    def getUsage(self):
        count = len(self._listenerQueues)
        list = []
        for q in self._listenerQueues.values():
            list.append({'remoteIP': q.remoteIP, 'sessionID': q.sessionID})
        return {'count': count, 'list': list}

class TranscriptHandler(QueueHandler):
    def __init__(self, name):
        super().__init__(name)
        

    def runHandler(self):
        if self._STARTED:
            logger.warn('Transcript Queue Handler already started')
            return

        logger.info('Transcript Queue Handler starting')
        self._STARTED = True
        self.filename = os.path.join(speakreader.CONFIG.TRANSCRIPTS_FOLDER, FILENAME)
        self.transcriptFile = open(self.filename, "a+")

        while True:
            try:
                transcript = self._receiverQueue.get(timeout=2)
            except queue.Empty:
                if self._STARTED:
                    continue
                else:
                    break

            if transcript is None or not self._STARTED:
                break

            if transcript['event'] == 'transcript' and transcript['final']:
                with self.fileLock:
                    self.transcriptFile.write(transcript['record'].strip() + "\n\n")
                    self.transcriptFile.flush()

            transcript = json.dumps(transcript)

            for queueElement in list(self._listenerQueues.values()):
                try:
                    queueElement.put_nowait(transcript)
                except queue.Full:
                    self.removeListener(sessionID=queueElement.sessionID)

        self.transcriptFile.close()
        self._STARTED = False
        logger.info('Transcript Queue Handler terminated')


class LogHandler(QueueHandler):

    def runHandler(self):
        if self._STARTED:
            logger.warn('Log Queue Handler already started')
            return

        logger.info('Log Queue Handler starting')
        self._STARTED = True

        mainLogger = logging.getLogger("SpeakReader")
        self.queueHandler = handlers.QueueHandler(self._receiverQueue)
        self.queueHandler.setFormatter(logger.log_format)
        self.queueHandler.setLevel(logger.log_level)
        mainLogger.addHandler(self.queueHandler)

        for handler in mainLogger.handlers[:]:
            if isinstance(handler, handlers.RotatingFileHandler):
                self.logFileName = handler.baseFilename
                break

        while True:
            try:
                logRecord = self._receiverQueue.get(timeout=2)
            except queue.Empty:
                if self._STARTED:
                    continue
                else:
                    break

            if logRecord is None or not self._STARTED:
                break


            # Python 3.6.8 doesn't seem to return a formatted message while 3.7.3 does.
            logMessage = logRecord.getMessage()
            formatted_logMessage = self.queueHandler.format(logRecord)
            logRecord.msg = ""
            formatted_header = self.queueHandler.format(logRecord)

            if formatted_header not in logMessage:
               logMessage = formatted_logMessage

            data = {"event": "logrecord",
                    "final": True,
                    "record": logMessage,
                    }

            data = json.dumps(data)

            for queueElement in list(self._listenerQueues.values()):
                try:
                    queueElement.put_nowait(data)
                except queue.Full:
                    self.removeListener(sessionID=queueElement.sessionID)

        self._STARTED = False
        logger.info('Log Queue Handler terminated')


class QueueElement(object):
    type = None
    sessionID = None
    remoteIP = None
    listenerQueue = None

    def __init__(self, type, remoteIP, sessionID):
        self.listenerQueue = Queue(maxsize=10)
        self.type = type.lower()
        self.remoteIP = remoteIP
        self.sessionID = sessionID

    def put_nowait(self, data):
        self.listenerQueue.put_nowait(data)

    def put(self, data):
        self.listenerQueue.put(data)

    def clear(self, data):
        self.listenerQueue.queue.clear()
