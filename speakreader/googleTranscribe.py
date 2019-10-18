from google.cloud import speech
from queue import Queue

import speakreader
from speakreader import logger


class googleTranscribe:

    def __init__(self, audio_device):

        self.audio_device = audio_device

        self.responseQueue = Queue(maxsize=100)

        self.credentials_json = speakreader.CONFIG.GOOGLE_CREDENTIALS_FILE

        self.client = speech.SpeechClient.from_service_account_json(self.credentials_json)

        self.config = speech.types.RecognitionConfig(
            encoding=speech.enums.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=audio_device._outputSampleRate,
            language_code='en-US',
            max_alternatives=1,
            enable_word_time_offsets=False,
            enable_automatic_punctuation=True,
            profanity_filter=bool(speakreader.CONFIG.ENABLE_CENSORSHIP),
        )

        self.streaming_config = speech.types.StreamingRecognitionConfig(
            config=self.config,
            interim_results=True)

    def transcribe(self):
        # Generator to return transcription results
        logger.debug("googleTranscribe.transcribe Entering")
        audio_generator = self.audio_device.streamGenerator()

        requests = (speech.types.StreamingRecognizeRequest(
            audio_content=content)
            for content in audio_generator)

        responses = self.client.streaming_recognize(self.streaming_config, requests)

        for response in responses:
            if not response.results:
                continue

            result = response.results[0]

            if not result.is_final and not speakreader.CONFIG.SHOW_INTERIM_RESULTS:
                continue

            if not result.alternatives:
                continue

            if not result.is_final and result.stability < 0.75:
                continue

            transcript = {
                'transcript': result.alternatives[0].transcript,
                'is_final': result.is_final,
            }

            yield transcript

        logger.debug("googleTranscribe.transcribe Exiting")
