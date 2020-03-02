# You need to install pyaudio to run this example
# pip install pyaudio

# When using a microphone, the AudioSource `input` parameter would be
# initialised as a queue. The pyaudio stream would be continuosly adding
# recordings to the queue, and the websocket client would be sending the
# recordings to the speech to text service

from threading import Thread
from queue import Queue

import speakreader
from speakreader import logger

try:
    from ibm_watson import SpeechToTextV1
    from ibm_watson.websocket import RecognizeCallback, AudioSource
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
    is_supported = True
except ImportError:
    is_supported = False


class ibmTranscribe:

    def __init__(self, audio_device):
        self.is_supported = is_supported
        if not self.is_supported:
            return

        self.audio_device = audio_device

        APIKEY = None
        URL = None
        with open(speakreader.CONFIG.IBM_CREDENTIALS_FILE) as f:
            for line in f.read().splitlines():
                parm = line.split('=')
                if parm[0] == 'SPEECH_TO_TEXT_APIKEY':
                    APIKEY = parm[1]
                if parm[0] == 'SPEECH_TO_TEXT_URL':
                    URL = parm[1]

        if APIKEY is None or URL is None:
            logger.warn('ibmTranscribe: APIKEY or URL not found in credentials file')

        # initialize speech to text service
        self.authenticator = IAMAuthenticator(APIKEY)
        self.speech_to_text = SpeechToTextV1(authenticator=self.authenticator)
        self.speech_to_text.set_service_url(URL)
        self.mycallback = ProcessResponses()

        self.audio_source = AudioSource(audio_device._streamBuff, is_recording=True, is_buffer=True)

    def transcribe(self):
        if not self.is_supported:
            return
        # Generator to return transcription results
        logger.debug('ibmTranscribe.transcribe ENTER')

        recognize_thread = Thread(target=self.recognize_using_websocket, args=())
        recognize_thread.start()

        while True:
            response = self.mycallback.responseQueue.get()
            if response is None:
                break
            yield response

        self.audio_source.completed_recording()
        recognize_thread.join()
        logger.debug('ibmTranscribe.transcribe EXIT')


    # this function will initiate the recognize service and pass in the AudioSource
    def recognize_using_websocket(self, *args):
        logger.debug("ibmTransribe.recognize_using_websocket ENTER")
        self.speech_to_text.recognize_using_websocket(
            audio=self.audio_source,
            content_type='audio/l16; rate=%s' % self.audio_device._outputSampleRate,
            recognize_callback=self.mycallback,
            interim_results=True,
            max_alternatives=1,
            inactivity_timeout=-1,
            smart_formatting=True,
            word_alternatives_threshold=0.75,
            profanity_filter=bool(speakreader.CONFIG.ENABLE_CENSORSHIP),
        )
        logger.debug("ibmTransribe.recognize_using_websocket EXIT")


# define callback for the speech to text service
class ProcessResponses(RecognizeCallback):
    def __init__(self):
        logger.debug("ibmTranscribe.ProcessResponse.Init ENTER")
        self.responseQueue = Queue(maxsize=100)
        RecognizeCallback.__init__(self)

    def on_connected(self):
        logger.debug('ibmTranscribe.ProcessResponses.Connection successful')

    def on_error(self, error):
        logger.warn('ibmTranscribe.ProcessResponses.Error Error received: {}'.format(error))

    def on_inactivity_timeout(self, error):
        logger.debug('ibmTranscribe.ProcessResponses.Inactivity timeout: {}'.format(error))

    def on_listening(self):
        logger.debug('ibmTranscribe.ProcessResponses.Listening Service is listening')

    def on_data(self, data):
        if 'results' not in data:
            return

        if 'alternatives' not in data['results'][0] or \
           'final' not in data['results'][0]:
            return

        if 'transcript' not in data['results'][0]['alternatives'][0]:
            return

        transcript = data['results'][0]['alternatives'][0]['transcript']
        final = data['results'][0]['final']

        if not final and not speakreader.CONFIG.SHOW_INTERIM_RESULTS:
            return

        # Temporary
        if '%HESITATION' in transcript:
            return

        response = {
            'transcript': transcript,
            'is_final': final,
        }

        self.responseQueue.put_nowait(response)

    def on_close(self):
        self.responseQueue.put_nowait(None)
        logger.debug("ibmTranscribe.ProcessResponses.Close Connection closed")
