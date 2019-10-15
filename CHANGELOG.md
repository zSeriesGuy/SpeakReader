# Changelog

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
