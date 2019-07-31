# SpeakReader for the Hearing Impaired

## What is SpeakReader
There is someone that attends my [church](https://www.ladoniabaptist.org) that is hearing impaired. We no longer have someone to sign for her. That was the inspiration for the development of this application.

There seems to be many speech-to-text applications out there. But they all seem to be designed for input and output on the same device. I wanted something that could output the transcription to many.

SpeakReader is an application that takes microphone or line-in input and transcribes it to text in realtime. It then sends the transcription text to a web page. As a speech is being given, anyone with a smart device (smart phone, tablet, laptop) can connect to the web server and read what is being spoken.
 
SpeakReader can be used anywhere that spoken words need to be transcribed to text and shared. Churches, conferences, meetings, etc.
It is written in Python and can run on any platform that supports Python. As a very low cost solution, I am running SpeakReader in production at my church on a Raspberry Pi 3. SpeakReader's system requirements and demands are very low.

SpeakReader is currently written to call the [Google Speech-To-Text](https://cloud.google.com/speech-to-text/) service. But I plan to add support in the future for [IBM Watson](https://www.ibm.com/watson/services/speech-to-text/) and [AWS](https://aws.amazon.com/transcribe/).

If you find value in this project, please consider making a [donation via PayPal](https://paypal.me/jerryleenance). 75% of your donation will go to the [Ladonia Baptist Church](https://www.ladoniabaptist.org) building fund. 
You may also make a [donation](https://onrealm.org/LadoniaBaptist/Give/EAVLVGBZJN) directly to the church building fund.


## Installation
Installation instructions can be found here.
 

## Usage

The default port for SpeakReader at installation is 8880. This can be changed in the configuration on the configuration page or by editing the config.ini file.

Connect a microphone or line-in to the server that you are running SpeakReader on and start SpeakReader.
The recommendation is to have a good clean input feed. For my production server, I use a line feed directly off of the church sound board. The cleaner the input feed, the more accurate the transcription results will be.

The transcription services do not have to be "trained" to the speaker. It gets the majority of the words correct. But due to differences in speaking style, clarity, accents, the transcription services may not get every word correct.

Profanity filters have been turned on in the transcription services to mask any intentional or unintentional profanity. 


#### User Interface
Access the web server. Be sure to include the port if you are not using the standard 80 or 443 (*`http://speakreaderURL:8880`*).

The home page on the SpeakReader web server is the transcription text.
The web page automatically scrolls to bottom. To pause auto scroll, just scroll back in the transcription text. A bottom button will appear in the upper right that, when clicked, will resume auto scrolling at the bottom position in the transcript.

To adjust the font, tap or click on the transcription. A tab will slide up from the bottom allowing font adjustment.

#### Management 
To manage SpeakReader, access the web server's **`/manage`** page.

There are three tabs on the management page: **Status**, **Configuration**, and **Transcripts**.

##### Status Page
The Status page:
* Shows the current status of the transcription engine.
* Shows the current input device.
* Allows for starting and stopping the transcription engine.
* Allows for restarting and shutting down the SpeakReader server.

##### Configuration Page
The Configuration page allows you to make and save changes to the configuration which are stored in the config.ini.

Settings include:
* Select the microphone or line-in input device.
* Upload your GoogleAPI credentials file.
* Whether or not to start the transcribe engine on server start up.
* Whether or not to launch a web browser to the server on server start up.
* Set the folder where to store transcripts.
* Set the port the server will listen on.
* Enable HTTPS for secure communications.
* Enable/disable censorship and add additional words to the censored words list.

##### Transcripts Page
The Transcripts page shows a list of all transcript files in the Transcripts folder. From the list, you can view or delete the transcript.
