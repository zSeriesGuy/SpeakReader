import threading
import queue
import json
import os
import datetime

import speakreader
from speakreader import logger


class QueueManager(object):
    _listenerQueues = []
    _INITIALIZED = False
    _STARTED = False
    _OFFLINE = True
    _offline_message = {"event": "transcript", "final": False, "transcript": "Transcription Engine is Offline"}
    _online_message = {"event": "transcript", "final": False, "transcript": "Welcome to SpeakReader -- Listening"}
    _close_event = {"event": "close"}

    FILENAME_PREFIX = "Transcript-"
    FILENAME_SUFFIX = "txt"
    FILENAME_DATE_FORMAT = "%Y-%m-%d-%H%M"
    FILENAME_DATESTRING = datetime.datetime.now().strftime(FILENAME_DATE_FORMAT)
    FILENAME = FILENAME_PREFIX + FILENAME_DATESTRING + "." + FILENAME_SUFFIX

    def __init__(self):
        if QueueManager._INITIALIZED:
            logger.warn('Queue Manager already Initialized')
            return
        logger.info('Queue Manager Initializing')
        self.fileLock = threading.Lock()

        self._transcribeQueue = queue.Queue(maxsize=-1)
        self._queueManagerThread = threading.Thread(name='QueueManager', target=self.run)
        self._queueManagerThread.start()
        QueueManager._INITIALIZED = True


    @property
    def is_started(self):
        if self._queueManagerThread is None or not self._queueManagerThread.is_alive():
            self._STARTED = False
        return self._STARTED


    def shutdown(self):
        self._OFFLINE = True
        for listenerQueue in self._listenerQueues:
            self.removeListener(listenerQueue=listenerQueue)
        self._transcribeQueue.put(None)
        self._queueManagerThread.join()


    def offline(self):
        self._OFFLINE = True
        self._transcribeQueue.put(self._offline_message)


    def online(self):
        self._OFFLINE = False
        self._transcribeQueue.put(self._online_message)


    def put(self, data):
        self._transcribeQueue.put(data)


    def run(self):
        if self._STARTED:
            logger.warn('Queue Manager already Started')
            return

        logger.info('Queue Manager Starting')
        self._STARTED = True
        self.transcriptFileName = os.path.join(speakreader.CONFIG.TRANSCRIPTS_FOLDER, self.FILENAME)
        self.transcriptFile = open(self.transcriptFileName, "a+")

        while True:
            try:
                transcript = self._transcribeQueue.get(timeout=2)
            except queue.Empty:
                if self._OFFLINE:
                    transcript = self._offline_message
                else:
                    continue

            if transcript is None:
                break

            if transcript['event'] == 'transcript' and transcript['final']:
                with self.fileLock:
                    self.transcriptFile.write(transcript['transcript'].strip() + "\n\n")
                    self.transcriptFile.flush()

            transcript = json.dumps(transcript)

            for q in self._listenerQueues:
                try:
                    q.put_nowait(transcript)
                except queue.Full:
                    self.removeListener(listenerQueue=q)

        self.transcriptFile.close()
        QueueManager._INITIALIZED = False
        self._STARTED = False
        self._OFFLINE = True
        logger.info('Queue Manager Terminated')


    def addListener(self, sessionID):
        if not self._STARTED:
            return None

        logger.debug("Adding Transcript Listener Queue: " + sessionID)
        listenerQueue = queue.Queue(maxsize=10)
        listenerQueue.sessionID = sessionID
        self._listenerQueues.append(listenerQueue)

        with self.fileLock:
            self.transcriptFile.flush()
            os.fsync(self.transcriptFile.fileno())
            self.transcriptFile.seek(0)
            data = "<p>" + self.transcriptFile.read().rstrip("\n\n").replace("\n\n", "</p><p>") + "</p>"

        transcript = {"event": "transcript",
                      "final": "refresh",
                      "transcript": data,
        }
        listenerQueue.put(json.dumps(transcript))

        if self._OFFLINE:
            listenerQueue.put(json.dumps(self._offline_message))
        else:
            listenerQueue.put(json.dumps(self._online_message))

        return listenerQueue


    def removeListener(self, sessionID=None, listenerQueue=None):
        if listenerQueue is None and sessionID is not None:
            for q in self._listenerQueues:
                if q.sessionID == sessionID:
                    listenerQueue = q
                    break
        if listenerQueue is not None:
            logger.debug("Removing Transcript Listener Queue: " + listenerQueue.sessionID)
            listenerQueue.queue.clear()
            listenerQueue.put(json.dumps(self._close_event))
            listenerQueue.put(None)
            QueueManager._listenerQueues.remove(listenerQueue)
