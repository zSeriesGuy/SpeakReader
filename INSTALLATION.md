# Installation Instructions
SpeakReader has been installed and tested on Windows 10 and Ubuntu 18.04 using Python 3.7.3.

### Windows

Install the latest version of [Python 3](https://www.python.org/downloads/windows/). Download the Windows installer and complete the installation with all the default options.

##### Method 1 (easy):
* Download SpeakReader from GitHub: [https://github.com/zSeriesGuy/SpeakReader/zipball/master](https://github.com/zSeriesGuy/SpeakReader/zipball/master)
* Extract the ZIP file.
* Open a CMD window.
* CD to the directory where you unzipped SpeakReader.
* Type: `python -m venv .\`
* Type: `.\scripts\activate`
* Type: `python -m pip install --upgrade pip setuptools`
* Type: `python -m pip install wheel pip-tools`
* Install the appropriate PyAudio wheel package for your release of Windows and Python. Several are provided in the PyAudioWheels folder. For example, to install the 32-bit version for Python V3.7: 
    * Type: `pip3 install .\PyAudioWheels\PyAudio-0.2.11-cp37-cp37m-win32.whl`
* Type: `pip3 install -r requirements.txt`
* Type: `.\scripts\python start.py` to start SpeakReader.
* SpeakReader will be loaded in your browser or listening on http://localhost:8880
* You can change the port in the Settings tab of the management page or by editing config.ini.

##### Method 2 (preferred):
> NOTE: This method is preferred because it adds the support to Windows to be able to more reliably update SpeakReader. This will install extra shell extensions and make adjustments to your path environment. 

* Go to [https://gitforwindows.org/](https://gitforwindows.org/) and download git.
* Run the installation with the default options.
* Right click on your desktop and select "Git Gui".
* Select "Clone Existing Repository".
* In the "Source Location" enter: https://github.com/zSeriesGuy/SpeakReader.git
* In the "Target Directory" enter a new folder where you want to install SpeakReader to (e.g. C:\SpeakReader).
* Click "Clone".
* When it's finished a Git Gui windows will appear, just close this window.
* Go to Method 1 and continue at the "Open a CMD Window".


### Linux
SpeakReader will be installed to `/opt/SpeakReader`.

* Open a terminal
* Install Git
    * Ubuntu/Debian: `sudo apt-get install git-core`
* Install prerequisites:
    * Ubuntu/Debian:
        * `sudo apt-get install build-essential libffi-dev libssl-dev libxml2-dev libxslt1-dev libjpeg8-dev zlib1g-dev alsa-utils portaudio19-dev`
        * `sudo apt-get install python3 python3-venv python3-all-dev`
* Type: `cd /opt`
* Type: `sudo git clone https://github.com/zSeriesGuy/SpeakReader.git`
* Type: `cd SpeakReader`
* Type: `python3 -m venv /opt/SpeakReader`
* Type: `source /opt/SpeakReader/bin/activate`
* Type: `python -m pip install --upgrade pip setuptools wheel pip-tools`
* Type: `pip3 install -r /opt/SpeakReader/requirements.txt`
* Type: `sudo usermod -aG audio userid` where userid is the user that you signed in to the terminal with.   
* Type: `/opt/SpeakReader/bin/python3 /opt/SpeakReader/start.py` to start SpeakReader
* SpeakReader will be loaded in your browser or listening on http://localhost:8880

To run SpeakReader in the background as a Daemon on startup:

* Ubuntu/Debian:
    * `sudo cp /opt/SpeakReader/init-scripts/speakreader.service /lib/systemd/system`
    * `sudo systemctl daemon-reload`
    * `sudo addgroup speakreader && sudo adduser --system --no-create-home speakreader --ingroup speakreader`
    * `sudo usermod -aG audio speakreader`  
    * `sudo chown -R speakreader:speakreader /opt/SpeakReader`
    * `sudo systemctl enable speakreader`
    * `sudo systemctl start speakreader`
    
    If you configure SpeakReader to listen on port 80 or 443 (or any port below 1024), you will need to run SpeakReader as **root** user.
    
    * Edit `/lib/systemd/system/speakreader/service` and change user and group to *root*.
    * `sudo systemctl daemon-reload`
    * `sudo systemctl restart speakreader`


## Choose a Transcription Service
Google API and IBM Watson are supported.


# Google API Services

You won't be able to start the transcribe engine until you have provided a valid Google API credentials JSON file.

> NOTE: The [Google Speech-To-Text](https://cloud.google.com/speech-to-text/) API service is not free. But it is not very expensive, less than $1 US per hour. See the [pricing](https://cloud.google.com/speech-to-text/pricing).

#### Setting Up API Access

* Go to the [Google API Console](https://console.cloud.google.com). Sign in with your Google Account if you have one or create one.
* Create a billing account by clicking on Billing and set up your payment method.
* Return to the Home page. 
* At the top of the screen next to Google Cloud Platform, click the Select Project.
* In the popped up window, click NEW PROJECT in the upper right.
* Give the project a name or take the default and click CREATE.
* Back on the Home page, if the selected project is not your newly created project, select it from the top of the screen next to Google Cloud Platform.
* Select APIs & Services.
* Click on the ENABLE APIS AND SERVICES at the top of the screen.
* Search for Speech and click on Cloud Speech-to-Text API.
* Click on ENABLE to enable this API for your project.
* On the APIs & Services screen, click Credentials.
* Click CREATE CREDENTIALS at the top of the screen and choose Service account key.
* Create a Service Account with a Role of Service Usage Consumer. The Key Type should be JSON.
* After you click the Create button, a json file will be downloaded to your computer. 
* Go to the SpeakReader management console Settings page and upload this json file.
* You should now be able to start the transcribe engine.
> HINT: When you go to the Google API Console, there may be at the very top of the screen something about Free Trial. You can activate that to get $300 credit good for one year. This will allow you to test and use SpeakReader at no cost for one year or $300 worth, whichever comes first.


# IBM Cloud API Services

You won't be able to start the transcribe engine until you have provided a valid IBM Cloud API credentials ENV file.

> NOTE: The [IBM Cloud Speech-To-Text](https://www.ibm.com/watson/services/speech-to-text/) API service is not free. But it is not very expensive, less than $1 US per hour. See the [pricing](hhttps://www.ibm.com/cloud/watson-speech-to-text/pricing). There is a Lite level that includes 500 minutes per month FREE.

#### Setting Up API Access

* Go to the [IBM Cloud API Dashboard](https://cloud.ibm.com/login). Sign in with your IBM Cloud Account if you have one or create one.
* Set up your billing method by clicking on Manage->Billing and Usage. Then click on Payments.
* Next, set up your resource by clicking on Resource List. Then click Create Resource (upper right).
* Search for speech to text. It should find AI Speech to Text. Click on it. The free Lite plan is a good start.
* Once you have completed creating the resource, click Resource List at the top. Then choose Manage on the menu at the left.
* It should be showing you a screen with the API Key. Click Download to save the credentials ENV file to your computer.
* Go to the SpeakReader management console Settings page and upload this ENV file.
* You should now be able to start the transcribe engine.


# Microsoft Azure Speech API Services

You won't be able to start the transcribe engine until you have provided a valid Microsoft Azure APIKEY and Region setting.

> NOTE: The [Microsoft Azure Speech-To-Text](https://azure.microsoft.com/en-us/services/cognitive-services/speech-to-text/) API service is not free. But it is not very expensive and includes a free tier. See the [pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/). There is a Free tier that allows for 5 audio hours per month.

#### Setting Up API Access

* Check out the [Getting Started](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/get-started) page for more instruction detail.
* Go to the [Azure Portal Dashboard](https://portal.azure.com/#home). Sign in to your Azure Account.
* Click the **Create a resource** in the top of the left menu.
* Search for Speech and click on Speech.
* Click **Create**
* Once you have completed creating the resource, you can click on **All resources** in the left menu, then select your resource.
* In the resource page, you will find the APIKEY in **Quick start**
* Copy and paste the APIKEY into the SpeakReader management console settings page after choosing the Microsoft transcription service.
* Set the Service Region that you chose when you created the Azure resource.
* You should now be able to start the transcribe engine.
 
