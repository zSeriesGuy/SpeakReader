from queue import Queue, Empty

import azure.cognitiveservices.speech as speechsdk

import speakreader
from speakreader import logger

RAW = 2
MASKED = 0


class microsoftTranscribe(object):

    def __init__(self, audio_device):

        self.audio_device = audio_device

        self.eventProcessor = ProcessEvents()

        # Creates an instance of a speech config with specified subscription key and service region.
        self.speech_config = speechsdk.SpeechConfig(subscription=speakreader.CONFIG.MICROSOFT_SERVICE_APIKEY,
                                                    region=speakreader.CONFIG.MICROSOFT_SERVICE_REGION)
        self.speech_config.enable_dictation()
        if speakreader.CONFIG.ENABLE_CENSORSHIP:
            profanityOption = speechsdk.ProfanityOption(MASKED)
        else:
            profanityOption = speechsdk.ProfanityOption(RAW)
        self.speech_config.set_profanity(profanityOption)


    def transcribe(self):
        # Generator to return transcription results
        logger.debug("microsoftTranscribe.transcribe Enter")

        audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=16000,
                                                         bits_per_sample=16,
                                                         channels=1)

        audio_stream_callback = AudioStreamCallback(self.audio_device._streamBuff)

        audio_stream = speechsdk.audio.PullAudioInputStream(audio_stream_callback, audio_format)
        self.audio_config = speechsdk.audio.AudioConfig(stream=audio_stream)

        self.speech_recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=self.audio_config)

        # Connect callbacks to the events fired by the speech recognizer
        self.speech_recognizer.recognizing.connect(self.eventProcessor.recognizing)
        self.speech_recognizer.recognized.connect(self.eventProcessor.recognized)
        self.speech_recognizer.session_started.connect(self.eventProcessor.session_started)
        self.speech_recognizer.session_stopped.connect(self.eventProcessor.session_stopped)
        self.speech_recognizer.canceled.connect(self.eventProcessor.canceled)

        # Start continuous speech recognition
        self.speech_recognizer.start_continuous_recognition()

        while True:
            response = self.eventProcessor.responseQueue.get()
            if response is None:
                self.speech_recognizer.stop_continuous_recognition()
                self.audio_device.closed = True
                break
            if response == 'canceled':
                self.audio_device.closed = True
                break

            yield response

        logger.debug("microsoftTranscribe.transcribe Exit")


class ProcessEvents(object):
    """ Class to process events returned from the Speech Service """
    def __init__(self):
        logger.debug("microsoftTranscribe.ProcessEvents.Init")
        self.responseQueue = Queue(maxsize=100)

    def recognizing(self, evt):
        #logger.debug('microsoftTranscribe.ProcessEvents.RECOGNIZING: {}'.format(evt))
        if not speakreader.CONFIG.SHOW_INTERIM_RESULTS:
            return

        if evt.result.text == "":
            return

        response = {
            'transcript': evt.result.text,
            'is_final': False,
        }

        self.responseQueue.put_nowait(response)

    def recognized(self, evt):
        #logger.debug('microsoftTranscribe.ProcessEvents.RECOGNIZED: {}'.format(evt))
        if evt.result.text == "":
            return

        response = {
            'transcript': evt.result.text,
            'is_final': True,
        }

        self.responseQueue.put_nowait(response)

    def session_started(self, evt):
        logger.debug('microsoftTranscribe.ProcessEvents.SESSION_STARTED: {}'.format(evt))

    def session_stopped(self, evt):
        logger.debug('microsoftTranscribe.ProcessEvents.SESSION_STOPPED {}'.format(evt))
        self.responseQueue.put(None)

    def canceled(self, evt):
        logger.debug('microsoftTranscribe.ProcessEvents.CANCELED: {}'.format(evt))
        logger.error('microsoftTranscribe terminated. Ensure you have the correct API Key and service region.')
        self.responseQueue.put('canceled')


class AudioStreamCallback(speechsdk.audio.PullAudioInputStreamCallback):
    """ Class that implements the Pull Audio Stream interface to return the audio stream """
    def __init__(self, q: Queue):
        super().__init__()
        self.q = q
        self.closed = False

    def read(self, buffer: memoryview) -> int:
        """read callback function"""
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self.q.get()
            if chunk is None:
                return 0
            audioData = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self.q.get(block=False)
                    if chunk is None:
                        return 0
                    audioData.append(chunk)
                except Empty:
                    break

            audioData = b''.join(audioData)

            buffer[:len(audioData)] = audioData

            return len(audioData)

    def close(self):
        """close callback function"""
        self.closed = True
