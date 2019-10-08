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
import wave
import datetime
import numpy as np
import samplerate as sr
import speakreader

FILENAME_PREFIX = "Transcript-"
FILENAME_SUFFIX = "wav"
FILENAME_DATE_FORMAT = "%Y-%m-%d-%H%M"
FILENAME_DATESTRING = datetime.datetime.now().strftime(FILENAME_DATE_FORMAT)
FILENAME = FILENAME_PREFIX + FILENAME_DATESTRING + "." + FILENAME_SUFFIX

# Audio recording parameters
STREAMING_LIMIT = 50000


def get_current_time():
    return int(round(time.time() * 1000))


def duration_to_secs(duration):
    return duration.seconds + (duration.nanos / float(1e9))


class MicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, input_device, outputSampleRate):
        self._audio_interface = pyaudio.PyAudio()
        self._inputDevice = input_device
        self._num_channels = 1
        self._format = pyaudio.paInt16
        self._outputSampleRate = outputSampleRate
        self.receiverQueue = None

        defaultHostAPIindex = self._audio_interface.get_default_host_api_info().get('index')
        numdevices = self._audio_interface.get_default_host_api_info().get('deviceCount')
        self.inputDeviceIndex = self._audio_interface.get_default_input_device_info().get('index')
        for i in range(0, numdevices):
            inputDevice = self._audio_interface.get_device_info_by_host_api_device_index(defaultHostAPIindex, i)
            if self._inputDevice == inputDevice.get('name'):
                inputDeviceIndex = inputDevice.get('index')
                break

        deviceInfo = self._audio_interface.get_device_info_by_index(self.inputDeviceIndex)
        self._rate = int(deviceInfo.get('defaultSampleRate'))
        self._chunk_size = int(self._rate / 10)
        self._streaming_limit = STREAMING_LIMIT

        self._wavfile = None

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True
        self.start_time = get_current_time()

        # 2 bytes in 16 bit samples
        self._bytes_per_sample = 2 * self._num_channels
        self._bytes_per_second = self._rate * self._bytes_per_sample

        self._bytes_per_chunk = (self._chunk_size * self._bytes_per_sample)
        self._chunks_per_second = (self._bytes_per_second // self._bytes_per_chunk)

    def __enter__(self):
        self.closed = False
        try:
            self._audio_stream = self._audio_interface.open(
                input_device_index=self.inputDeviceIndex,
                format=self._format,
                channels=self._num_channels,
                rate=self._rate,
                input=True,
                frames_per_buffer=self._chunk_size,
                # Run the audio stream asynchronously to fill the buffer object.
                # This is necessary so that the input device's buffer doesn't
                # overflow while the calling thread makes network requests, etc.
                stream_callback=self._fill_buffer,
            )
        except OSError:
            print("microphone __enter__.OSError")
            self.closed = True
            raise Exception("Microphone Not Functioning")

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

        if self._wavfile is not None:
            self._wavfile.close()
            self._wavfile = None

    def initRecording(self, filename):
        if speakreader.CONFIG.SAVE_RECORDINGS:
            wavfile = os.path.join(speakreader.CONFIG.RECORDINGS_FOLDER, filename)
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

    def stop(self):
        self.__exit__(None, None, None)

    def _fill_buffer(self, in_data, *args, **kwargs):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        resampler = sr.Resampler()
        ratio = self._outputSampleRate / self._rate

        tps = 25        # times per second to compute RMS.
        peak_secs = 5   # seconds to accumulate for peak computation
        peak_np = np.empty(0, dtype=np.int16)
        time = float(0)

        while not self.closed:
            if get_current_time() - self.start_time > self._streaming_limit:
                self.start_time = get_current_time()
                break
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            audioData = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    audioData.append(chunk)
                except queue.Empty:
                    break
                except:
                    break

            audioData = b''.join(audioData)

            audioData_np = np.frombuffer(audioData, dtype=np.int16)
            audioData_np = resampler.process(audioData_np, ratio)
            audioData_np = audioData_np.astype(np.int16)
            audioData_resampled = audioData_np.tobytes()

            yield audioData_resampled

            if self._wavfile is not None:
                self._wavfile.writeframes(audioData_resampled)

            peak_np = np.concatenate((peak_np, audioData_np), axis=0)
            stop = peak_np.size - (peak_secs * self._outputSampleRate)
            if stop > 0:
                peak_np = np.delete(peak_np, np.s_[0:stop], axis=0)
            peak_rms = np.max(np.absolute(audioData_np / 32768))
            db_peak = int(round(20 * np.log10(peak_rms)))

            chunk_size = int(self._outputSampleRate / tps)
            for i in range(0, audioData_np.size, chunk_size):
                rms = np.sqrt(np.mean(np.absolute(audioData_np[i:i+chunk_size] / 32768) ** 2))
                db_rms = int(round(20 * np.log10(rms)))
                t = "{0:.2f}".format(time)
                try:
                    self.receiverQueue.put_nowait({'time': t, 'db_rms': db_rms, 'db_peak': db_peak})
                except:
                    pass
                time += 1 / tps
