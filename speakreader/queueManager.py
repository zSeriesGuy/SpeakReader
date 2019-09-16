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

# This module manages the queues.

import threading
import queue
from queue import Queue

from speakreader import logger
import logging
from logging import handlers


class QueueManager(object):

    _INITIALIZED = False

    def __init__(self):
        if self._INITIALIZED:
            logger.warn('Queue Manager already Initialized')
            return
        logger.info('Queue Manager Initializing')
        self.transcriptHandler = TranscriptHandler("TranscriptQueueHandler")
        self.logHandler = LogHandler("LogQueueHandler")
        self.meterHandler = MeterHandler("SoundMeterQueueHandler")
        self._INITIALIZED = True

    @property
    def is_initialized(self):
        return self._INITIALIZED

    def shutdown(self):
        self._INITIALIZED = False
        self.transcriptHandler.shutdown()
        self.logHandler.shutdown()
        self.meterHandler.shutdown()
        logger.info("Queue Manager terminated")

    def closeAllListeners(self):
        self.transcriptHandler.closeAllListeners()
        self.logHandler.closeAllListeners()

    def addListener(self, type=None, sessionID=None, remoteIP=None):
        if type == "log":
            return self.logHandler.addListener(type=type, sessionID=sessionID, remoteIP=remoteIP)
        elif type == "transcript":
            return self.transcriptHandler.addListener(type=type, sessionID=sessionID, remoteIP=remoteIP)
        elif type == "meter":
            return self.meterHandler.addListener(type=type, sessionID=sessionID, remoteIP=remoteIP)
        return None

    def removeListener(self, type=None, sessionID=None, remoteIP=None):
        if type == "log":
            self.logHandler.removeListener(sessionID=sessionID)
        elif type == "transcript":
            self.transcriptHandler.removeListener(sessionID=sessionID)
        elif type == "meter":
            self.meterHandler.removeListener(sessionID=sessionID)

    def getUsage(self):
        usage = {}
        usage['transcript'] = self.transcriptHandler.getUsage()
        usage['log'] = self.logHandler.getUsage()
        return usage


class QueueHandler(object):

    def __init__(self, name):
        self._STARTED = False
        self.fileLock = threading.Lock()
        self._listenerQueues = {}
        self.fileName = None
        self.threadName = name

        # Initialize the Handler queue manager
        self._receiverQueue = Queue(maxsize=-1)
        self._queueHandlerThread = threading.Thread(name=self.threadName, target=self.runHandler)
        self._queueHandlerThread.start()

    def setFileName(self, filename):
        self.fileName = filename

    def getReceiverQueue(self):
        return self._receiverQueue

    def setReceiverQueue(self, queue):
        self._receiverQueue = queue

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

        if type == 'meter':
            maxsize = 100
        else:
            maxsize = 10

        queueElement = QueueElement(type=type, remoteIP=remoteIP, sessionID=sessionID, maxsize=maxsize)
        self._listenerQueues[sessionID] = queueElement

        data = {"event": "open",
                "sessionID": sessionID,
                }
        queueElement.put_nowait(data)

        data = None
        if type == "log":
            if self.fileName:
                with open(self.fileName) as f:
                    records = '<p>' + f.read().replace("\n", "</p><p>") + '</p>'
                data = {"event": "logrecord",
                        "final": "reload",
                        "record": records,
                        }
        elif type == "transcript":
            if self.fileName:
                with open(self.fileName, 'r') as f:
                    records = "<p>" + f.read().rstrip("\n\n").replace("\n\n", "</p><p>") + "</p>"
                data = {"event": "transcript",
                        "final": "reload",
                        "record": records,
                        }

        if data:
            queueElement.put_nowait(data)

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

    def runHandler(self):
        if self._STARTED:
            logger.warn('Transcript Queue Handler already started')
            return

        logger.info('Transcript Queue Handler starting')
        self._STARTED = True

        while self._STARTED:
            try:
                transcript = self._receiverQueue.get(timeout=2)
                if transcript is None:
                    break

            except queue.Empty:
                if self._STARTED:
                    transcript = {"event": "ping"}
                else:
                    break

            for queueElement in list(self._listenerQueues.values()):
                try:
                    queueElement.put_nowait(transcript)
                except queue.Full:
                    self.removeListener(sessionID=queueElement.sessionID)

        self._STARTED = False
        self.closeAllListeners()
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
                self.fileName = handler.baseFilename
                break

        while self._STARTED:
            try:
                logRecord = self._receiverQueue.get(timeout=2)
                if logRecord is None:
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

            except queue.Empty:
                if self._STARTED:
                    data = {"event": "ping"}
                else:
                    break

            for queueElement in list(self._listenerQueues.values()):
                try:
                    queueElement.put_nowait(data)
                except queue.Full:
                    self.removeListener(sessionID=queueElement.sessionID)

        self._STARTED = False
        self.closeAllListeners()
        logger.info('Log Queue Handler terminated')


class MeterHandler(QueueHandler):

    def runHandler(self):
        if self._STARTED:
            logger.warn('Sound Meter Queue Handler already started')
            return

        logger.info('Sound Meter Queue Handler starting')
        self._STARTED = True

        while self._STARTED:
            try:
                meterRecord = self._receiverQueue.get(timeout=2)
                if meterRecord is None:
                    break

                data = {"event": "meterrecord",
                        "final": True,
                        "record": meterRecord,
                        }

            except queue.Empty:
                if self._STARTED:
                    data = {"event": "ping"}
                else:
                    break

            for queueElement in list(self._listenerQueues.values()):
                try:
                    queueElement.put_nowait(data)
                except queue.Full:
                    self.removeListener(sessionID=queueElement.sessionID)

        self._STARTED = False
        self.closeAllListeners()
        logger.info('Sound Meter Queue Handler terminated')


class QueueElement(object):
    type = None
    sessionID = None
    remoteIP = None
    listenerQueue = None

    def __init__(self, type, remoteIP, sessionID, maxsize=10):
        self.listenerQueue = Queue(maxsize=maxsize)
        self.type = type.lower()
        self.remoteIP = remoteIP
        self.sessionID = sessionID

    def put_nowait(self, data):
        self.listenerQueue.put_nowait(data)

    def put(self, data):
        self.listenerQueue.put(data)

    def clear(self):
        self.listenerQueue.queue.clear()
