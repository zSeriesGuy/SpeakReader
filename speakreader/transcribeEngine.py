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

# This module is the transcribe engine. It takes input from the microphone
# and invokes the API to convert the audio to text and sends the transcript
# to the queue manager.

import threading
import re
import os
import datetime
from google.cloud import speech

import speakreader
from speakreader import logger
from speakreader.microphoneStream import MicrophoneStream
from speakreader.queueManager import QueueManager

FILENAME_PREFIX = "Transcript-"
FILENAME_DATE_FORMAT = "%Y-%m-%d-%H%M"
TRANSCRIPT_FILENAME_SUFFIX = "txt"
RECORDING_FILENAME_SUFFIX = "wav"

SAMPLERATE = 16000


class TranscribeEngine:

    _INITIALIZED = False
    _transcribeThread = None
    _ONLINE = False
    _censor_char = "*"
    OFFLINE_MESSAGE = {"event": "transcript", "final": False, "record": "Transcription Engine is Offline"}
    ONLINE_MESSAGE = {"event": "transcript", "final": False, "record": "Welcome to SpeakReader -- Listening"}

    def __init__(self):
        if TranscribeEngine._INITIALIZED:
            logger.warn("Transcribe Engine already Initialized")
            return

        logger.info("Transcribe Engine Initializing")
        ###################################################################################################
        #  Initialize the Queue Manager
        ###################################################################################################
        self.queueManager = QueueManager()
        self.receiverQueue = self.queueManager.transcriptHandler.getReceiverQueue()

        TranscribeEngine._INITIALIZED = True

    @property
    def is_online(self):
        if self._transcribeThread is None or not self._transcribeThread.is_alive():
            self._ONLINE = False
        return self._ONLINE

    def start(self):
        self._transcribeThread = threading.Thread(name='TranscribeEngine', target=self.run)
        self._transcribeThread.start()

    def stop(self):
        if self._ONLINE:
            self.microphoneStream.stop()
            self.receiverQueue.put_nowait(self.OFFLINE_MESSAGE)
            self._transcribeThread.join()
            self.queueManager.transcriptHandler.setFileName(None)
            self._ONLINE = False

    def shutdown(self):
        self.stop()
        self.queueManager.shutdown()

    def run(self):
        if self._ONLINE:
            logger.warn("Transcribe Engine already Started")
            return

        logger.info("Transcribe Engine Starting")

        FILENAME_DATESTRING = datetime.datetime.now().strftime(FILENAME_DATE_FORMAT)
        TRANSCRIPT_FILENAME = FILENAME_PREFIX + FILENAME_DATESTRING + "." + TRANSCRIPT_FILENAME_SUFFIX
        RECORDING_FILENAME = FILENAME_PREFIX + FILENAME_DATESTRING + "." + RECORDING_FILENAME_SUFFIX

        tf = os.path.join(speakreader.CONFIG.TRANSCRIPTS_FOLDER, TRANSCRIPT_FILENAME)
        self.queueManager.transcriptHandler.setFileName(tf)
        self.transcriptFile = open(tf, "a+")

        try:
            self.microphoneStream = MicrophoneStream(speakreader.CONFIG.INPUT_DEVICE, SAMPLERATE)
            rf = os.path.join(speakreader.CONFIG.RECORDINGS_FOLDER, RECORDING_FILENAME)
            self.microphoneStream.initRecording(RECORDING_FILENAME)
            self.microphoneStream.receiverQueue = self.queueManager.meterHandler.getReceiverQueue()

        except Exception as e:
            logger.debug("MicrophoneStream Exception: %s" % e)
            self.receiverQueue.put_nowait(self.OFFLINE_MESSAGE)
            return

        credentials_json = speakreader.CONFIG.CREDENTIALS_FILE

        client = speech.SpeechClient.from_service_account_json(credentials_json)

        config = speech.types.RecognitionConfig(
            encoding=speech.enums.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=SAMPLERATE,
            language_code='en-US',
            max_alternatives=1,
            enable_word_time_offsets=True,
            enable_automatic_punctuation=True,
            profanity_filter=speakreader.CONFIG.ENABLE_CENSORSHIP)

        streaming_config = speech.types.StreamingRecognitionConfig(
            config=config,
            interim_results=True)

        self._ONLINE = True
        self.receiverQueue.put_nowait(self.ONLINE_MESSAGE)

        try:
            with self.microphoneStream as stream:

                while not stream.closed:
                    audio_generator = stream.generator()

                    requests = (speech.types.StreamingRecognizeRequest(
                        audio_content=content)
                        for content in audio_generator)

                    responses = client.streaming_recognize(streaming_config, requests)

                    # Now, put the transcription responses to use.
                    try:
                        self.process_responses(responses)
                    except Exception as e:
                        logger.debug("a: %s" % e)

                logger.debug("Microphone Stream Closed")

        except Exception as e:
            logger.error("b: %s" % e)

        self.transcriptFile.close()
        self.receiverQueue.put_nowait(self.OFFLINE_MESSAGE)
        self._ONLINE = False
        logger.info("Transcribe Engine Terminated")

    def process_responses(self, responses):

        """Iterates through server responses and prints them.
        The responses passed is a generator that will block until a response
        is provided by the server.
        Each response may contain multiple results, and each result may contain
        multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
        print only the transcription for the top alternative of the top result.
        In this case, responses are provided for interim results as well. If the
        response is an interim one, print a line feed at the end of it, to allow
        the next result to overwrite it, until the response is a final one. For the
        final one, print a newline to preserve the finalized transcription.
        """

        responses = (r for r in responses if (
                r.results and r.results[0].alternatives))

        for response in responses:

            if not response.results:
                continue

            result = response.results[0]

            if not result.is_final and not speakreader.CONFIG.SHOW_INTERIM_RESULTS:
                continue

            if not result.alternatives:
                continue

            if not result.is_final and result.stability < 0.80:
                continue

            transcript = result.alternatives[0].transcript

            """ If there are any additionally defined censor words, censor the transcript """
            if speakreader.CONFIG.ENABLE_CENSORSHIP and speakreader.CONFIG.CENSORED_WORDS:
                transcript = self.censor(transcript)

            transcription = {
                'event': 'transcript',
                'final': result.is_final,
                'record': transcript,
            }

            self.receiverQueue.put(transcription)

            if result.is_final:
                self.transcriptFile.write(transcript.strip() + "\n\n")
                self.transcriptFile.flush()

    def censor(self, input_text):
        """Returns input_text with any defined words censored."""
        res = input_text

        for word in speakreader.CONFIG.CENSORED_WORDS:
            if len(word) > 1:
                regex_string = r'\b{0}\b'
                regex_string = regex_string.format("(" + word[0] + ")" + word[1:len(word)])
                regex = re.compile(regex_string, re.IGNORECASE)
                res = regex.sub(r"\1" + self._censor_char * (len(word)-1), res)

        return res
