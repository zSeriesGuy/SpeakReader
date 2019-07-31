# List input devices

import pyaudio
p = pyaudio.PyAudio()

defaultHostAPIindex = p.get_default_host_api_info().get('index')
numdevices = p.get_default_host_api_info().get('deviceCount')
defaultInputDeviceIndex = p.get_default_input_device_info().get('index')

for i in range(0, numdevices):
    if (p.get_device_info_by_host_api_device_index(defaultHostAPIindex, i).get('maxInputChannels')) > 0:
        print("Input Device id ", str(i) + "* - " if i == defaultInputDeviceIndex else str(i) + "  - ",
              p.get_device_info_by_host_api_device_index(defaultHostAPIindex, i).get('name'))

