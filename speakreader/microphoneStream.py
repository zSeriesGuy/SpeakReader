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

# This module manages the microphone stream.

import time
import queue
import pyaudio
import os
from threading import Thread
import wave
import datetime
import numpy as np
import samplerate as sr

import speakreader
from speakreader import logger

FILENAME_PREFIX = "Transcript-"
FILENAME_SUFFIX = "wav"
FILENAME_DATE_FORMAT = "%Y-%m-%d-%H%M"
FILENAME_DATESTRING = datetime.datetime.now().strftime(FILENAME_DATE_FORMAT)
FILENAME = FILENAME_PREFIX + FILENAME_DATESTRING + "." + FILENAME_SUFFIX

# Audio recording parameters
SAMPLERATE = 16000


class MicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, input_device):
        logger.debug('MicrophoneStream INIT')
        self._audio_interface = pyaudio.PyAudio()
        self._inputDeviceName = input_device
        self._inputDeviceIndex = None
        self._num_channels = 1
        self._format = pyaudio.paInt16
        self._outputSampleRate = SAMPLERATE

        self.meterQueue = None
        self.meter_tps = 25        # times per second to compute RMS.
        self.meter_peak_secs = 3   # seconds to accumulate for peak computation
        self.meter_peak_np = np.empty(0, dtype=np.int16)
        self.meter_time = float(0)

        self.recordingFilename = None

        numdevices = self._audio_interface.get_default_host_api_info().get('deviceCount')
        defaultHostAPIindex = self._audio_interface.get_default_host_api_info().get('index')
        defaultInputDeviceIndex = self._audio_interface.get_default_input_device_info().get('index')
        defaultInputDeviceName = self._audio_interface.get_default_input_device_info().get('name')

        for i in range(0, numdevices):
            inputDevice = self._audio_interface.get_device_info_by_host_api_device_index(defaultHostAPIindex, i)
            if self._inputDeviceName == inputDevice.get('name'):
                self._inputDeviceIndex = inputDevice.get('index')
                break

        if self._inputDeviceIndex is None:
            self._inputDeviceName = defaultInputDeviceName
            self._inputDeviceIndex = defaultInputDeviceIndex

        deviceInfo = self._audio_interface.get_device_info_by_index(self._inputDeviceIndex)

        if self._audio_interface.is_format_supported(self._outputSampleRate, input_device=self._inputDeviceIndex,
                                                     input_channels=self._num_channels,
                                                     input_format=self._format):
            self._rate = self._outputSampleRate
        else:
            self._rate = int(deviceInfo.get('defaultSampleRate'))

        self.resampler = sr.Resampler()
        self.resampler_ratio = self._outputSampleRate / self._rate

        self._chunk_size = int(self._rate / 10)

        self._wavfile = None

        # Create a thread-safe buffer of audio data
        self._streamBuff = queue.Queue()
        self._recordingBuff = queue.Queue()
        self.closed = True

        # 2 bytes in 16 bit samples
        self._bytes_per_sample = 2 * self._num_channels
        self._bytes_per_second = self._rate * self._bytes_per_sample

        self._bytes_per_chunk = (self._chunk_size * self._bytes_per_sample)
        self._chunks_per_second = (self._bytes_per_second // self._bytes_per_chunk)

    def __enter__(self):
        logger.debug('MicrophoneStream.enter ENTER')
        self.closed = False
        try:
            self._audio_stream = self._audio_interface.open(
                input_device_index=self._inputDeviceIndex,
                format=self._format,
                channels=self._num_channels,
                rate=self._rate,
                input=True,
                frames_per_buffer=self._chunk_size,
                # Run the audio stream asynchronously to fill the buffer object.
                # This is necessary so that the input device's buffer doesn't
                # overflow while the calling thread makes network requests, etc.
                stream_callback=self._fill_buff,
            )
        except OSError:
            print("microphone __enter__.OSError")
            self.closed = True
            raise Exception("Microphone Not Functioning")

        self.initRecording()
        logger.debug('MicrophoneStream.enter EXIT')

        return self

    def __exit__(self, type, value, traceback):
        logger.debug('MicrophoneStream.exit ENTER')
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self._streamBuff.put(None)
        if speakreader.CONFIG.SAVE_RECORDINGS:
            self._recordingBuff.put(None)
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._audio_interface.terminate()

        if self._wavfile is not None:
            self._wavfile.close()
            self._wavfile = None

        logger.debug('MicrophoneStream.exit EXIT')

    def stop(self):
        self.__exit__(None, None, None)

    def _fill_buff(self, in_data, *args, **kwargs):
        """Continuously collect data from the audio stream, into the buffer."""
        audioData_np = np.frombuffer(in_data, dtype=np.int16)
        if self._rate != self._outputSampleRate:
            audioData_np = self.resampler.process(audioData_np, self.resampler_ratio)
            audioData_np = audioData_np.astype(np.int16)
            in_data = audioData_np.tobytes()

        self._streamBuff.put(in_data)

        if speakreader.CONFIG.SAVE_RECORDINGS:
            self._recordingBuff.put(in_data)

        # Compute db and put to meter queue
        self.meter_peak_np = np.concatenate((self.meter_peak_np, audioData_np), axis=0)
        stop = self.meter_peak_np.size - (self.meter_peak_secs * self._outputSampleRate)
        if stop > 0:
            self.meter_peak_np = np.delete(self.meter_peak_np, np.s_[0:stop], axis=0)
        peak_rms = np.max(np.absolute(audioData_np / 32768))
        db_peak = int(round(20 * np.log10(peak_rms)))

        chunk_size = int(round(self._outputSampleRate / self.meter_tps))
        for i in range(0, audioData_np.size, chunk_size):
            rms = np.sqrt(np.mean(np.absolute(audioData_np[i:i + chunk_size] / 32768) ** 2))
            db_rms = int(round(20 * np.log10(rms)))
            t = "{0:.2f}".format(self.meter_time)
            try:
                self.meterQueue.put_nowait({'time': t, 'db_rms': db_rms, 'db_peak': db_peak})
            except:
                pass
            self.meter_time += 1 / self.meter_tps

        return None, pyaudio.paContinue


    def initRecording(self):
        logger.debug("microphoneStream.initRecording Entering")
        if speakreader.CONFIG.SAVE_RECORDINGS:
            wavfile = os.path.join(speakreader.CONFIG.RECORDINGS_FOLDER, self.recordingFilename)
            try:
                w = wave.open(wavfile, 'rb')
                data = w.readframes(w.getnframes())
                self._wavfile = wave.open(wavfile, 'wb')
                self._wavfile.setparams(w.getparams())
                w.close()
                self._wavfile.writeframes(data)
            except FileNotFoundError:
                self._wavfile = wave.open(wavfile, 'wb')
                self._wavfile.setnchannels(self._num_channels)
                self._wavfile.setsampwidth(2)
                self._wavfile.setframerate(self._outputSampleRate)

            recordingThread = Thread(target=self.saveRecording, args=(), name='recordingThread')
            recordingThread.start()
        logger.debug("microphoneStream.initRecording Exiting")


    def saveRecording(self):
        logger.debug("microphoneStream.saveRecording entering")
        # Record the audio file
        if self._wavfile is not None:
            audioGenerator = self.recordingGenerator()
            for audioData in audioGenerator:
                self._wavfile.writeframes(audioData)
        logger.debug("microphoneStream.saveRecording exiting")

    def recordingGenerator(self):
        return self._generator(self._recordingBuff)

    def googleGenerator(self):
        return self._generator(self._streamBuff)

    def _generator(self, q):

        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = q.get()
            if chunk is None:
                return
            audioData = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = q.get(block=False)
                    if chunk is None:
                        return
                    audioData.append(chunk)
                except queue.Empty:
                    break
                except:
                    break

            audioData = b''.join(audioData)
            yield audioData

        logger.debug('microphone generator loop exited')
