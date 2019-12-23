# Changelog

## v1.2.5 (2019-12-10)
* Upgrade packages, specifically grpcio, to fix an issue on Raspbian.
* Modify pip_sync to output messages from process in realtime.
* Modify loop to handle Google Cloud time limits on content.
* Set GIT remote and branch based on what's installed.

## v1.2.4 (2019-12-09)
* Fix favicon handling.
* Run pip install requirements before pip-sync.
* Update installation instructions and init scripts

## v1.2.3 (2019-10-21)
* Add support to ensure only one instance of SpeakReader is running.
* Add exception handler for Google OutOfRange exception. Streaming limit is 5 minutes.
* Run file cleanup if days changes in management console settings.
* Upgrade packages.

## v1.2.2 (2019-10-19)
* Add settings and process for deleting logs, transcripts, and recordings after a specified number of days.

## v1.2.1 (2019-10-19)
* Microsoft Azure Speech-to-Text Cloud service is not available on some platforms. Added support for detecting failure to load service.

## v1.2.0 (2019-10-15)
* Add support for Microsoft Azure Speech-to-Text Cloud service.
* Remove Nightly as a selectable git branch.

## v1.1.0 (2019-10-15)
**Changes:**
* Modifications to support different transcription services.
* Update packages.

**New:**
* Add support for IBM Watson Speech-to-Text Cloud service.

> **NOTE:** Due to the modifications to support multiple transcription services, if you are upgrading from a previous release, you will need to re-upload your Google API JSON file or edit the config.ini file and change credentials_file to google_credentials_file.

## v1.0.5 (2019-10-15)
* Run pip-sync on git branch change.

## v1.0.4 (2019-10-08)
* Increase max size of transcript font setting.
* Correct issues using IOS Safari browser.

## v1.0.3 (2019-09-15)
* Added db sound meter.

## v1.0.2 (2019-09-01)
* Resample input device stream to 16kHz.
* Added saving the sound recording to a wav file.

## v1.0.1 (2019-08-31)
* Change to use input device's default sample rate.

## v1.0.0 (2019-08-15)
* Initial Release
