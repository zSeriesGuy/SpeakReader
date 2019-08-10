import time
import queue
import pyaudio


def get_current_time():
    return int(round(time.time() * 1000))


def duration_to_secs(duration):
    return duration.seconds + (duration.nanos / float(1e9))


class MicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, input_device, rate, chunk_size, streaming_limit):
        self._inputDevice = input_device
        self._rate = rate
        self._chunk_size = chunk_size
        self._streaming_limit = streaming_limit
        self._num_channels = 1
        self._max_replay_secs = 5

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True
        self.start_time = get_current_time()

        # 2 bytes in 16 bit samples
        self._bytes_per_sample = 2 * self._num_channels
        self._bytes_per_second = self._rate * self._bytes_per_sample

        self._bytes_per_chunk = (self._chunk_size * self._bytes_per_sample)
        self._chunks_per_second = (
                self._bytes_per_second // self._bytes_per_chunk)

    def __enter__(self):
        self.closed = False

        self._audio_interface = pyaudio.PyAudio()
        try:
            defaultHostAPIindex = self._audio_interface.get_default_host_api_info().get('index')
            numdevices = self._audio_interface.get_default_host_api_info().get('deviceCount')
            inputDeviceIndex = self._audio_interface.get_default_input_device_info().get('index')
            for i in range(0, numdevices):
                inputDevice = self._audio_interface.get_device_info_by_host_api_device_index(defaultHostAPIindex, i)
                if self._inputDevice == inputDevice.get('name'):
                    inputDeviceIndex = inputDevice.get('index')
                    break
            self._audio_stream = self._audio_interface.open(
                input_device_index=inputDeviceIndex,
                format=pyaudio.paInt16,
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

    def stop(self):
        self.__exit__(None, None, None)

    def _fill_buffer(self, in_data, *args, **kwargs):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # if speakreader._SHUTDOWN:
            #     self.closed = True
            #     return
            if get_current_time() - self.start_time > self._streaming_limit:
                self.start_time = get_current_time()
                break
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break
                except:
                    break

            yield b''.join(data)
