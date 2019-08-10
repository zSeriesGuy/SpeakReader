import threading
import re
from google.cloud import speech

import speakreader
from speakreader import logger
from speakreader.microphoneStream import MicrophoneStream

# Audio recording parameters
STREAMING_LIMIT = 50000
SAMPLE_RATE = 44100
CHUNK_SIZE = int(SAMPLE_RATE / 10)  # 100ms


class TranscribeEngine:

    _INITIALIZED = False
    _transcribeThread = None
    _ONLINE = False
    _censor_char = "*"
    OFFLINE_MESSAGE = {"event": "transcript", "final": False, "record": "Transcription Engine is Offline"}
    ONLINE_MESSAGE = {"event": "transcript", "final": False, "record": "Welcome to SpeakReader -- Listening"}

    def __init__(self, receiverQueue):
        if TranscribeEngine._INITIALIZED:
            logger.warn("Transcribe Engine already Initialized")
            return
        logger.info("Transcribe Engine Initializing")
        self.receiverQueue = receiverQueue
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
            self._ONLINE = False

    def run(self):
        if self._ONLINE:
            logger.warn("Transcribe Engine already Started")
            return

        logger.info("Transcribe Engine Starting")
        credentials_json = speakreader.CONFIG.CREDENTIALS_FILE

        client = speech.SpeechClient.from_service_account_json(credentials_json)

        config = speech.types.RecognitionConfig(
            encoding=speech.enums.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=SAMPLE_RATE,
            language_code='en-US',
            max_alternatives=1,
            enable_word_time_offsets=True,
            enable_automatic_punctuation=True,
            profanity_filter=speakreader.CONFIG.ENABLE_CENSORSHIP)

        streaming_config = speech.types.StreamingRecognitionConfig(
            config=config,
            interim_results=True)

        try:
            self.microphoneStream = MicrophoneStream(speakreader.CONFIG.INPUT_DEVICE, SAMPLE_RATE, CHUNK_SIZE, STREAMING_LIMIT)
            self._ONLINE = True
            self.receiverQueue.put_nowait(self.ONLINE_MESSAGE)
        except Exception as e:
            logger.debug("MicrophoneStream Exception: %s" % e)
            self.receiverQueue.put_nowait(self.OFFLINE_MESSAGE)
            return

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
