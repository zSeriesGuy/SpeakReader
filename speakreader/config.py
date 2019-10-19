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

# This module is the manager for the configuration settings.

import re
from configobj import ConfigObj
from speakreader import logger


def bool_int(value):
    """
    Casts a config value into a 0 or 1
    """
    if isinstance(value, str):
        if value.lower() in ('', '0', 'false', 'f', 'no', 'n', 'off'):
            value = 0
    return int(bool(value))


FILENAME = "config.ini"

_CONFIG_DEFINITIONS = {
    'INPUT_DEVICE': (str, 'General', ''),
    'LAUNCH_BROWSER': (int, 'General', 1),
    'START_TRANSCRIBE_ON_STARTUP': (int, 'General', 1),
    'SHOW_INTERIM_RESULTS': (int, 'General', 1),
    'TRANSCRIPTS_FOLDER': (str, 'General', ''),
    'TRANSCRIPT_RETENTION_DAYS': (str, 'General', '30'),
    'ENABLE_CENSORSHIP': (int, 'General', 1),
    'CENSORED_WORDS': (list, 'General', ''),
    'LOG_DIR': (str, 'General', ''),
    'LOG_RETENTION_DAYS': (str, 'General', '30'),
    'ANON_REDIRECT': (str, 'General', 'http://www.nullrefer.com/?'),
    'SERVER_ENVIRONMENT': (str, 'Advanced', 'production'),
    'SAVE_RECORDINGS': (int, 'General', 1),
    'RECORDINGS_FOLDER': (str, 'General', ''),
    'RECORDING_RETENTION_DAYS': (str, 'General', '30'),
    'SPEECH_TO_TEXT_SERVICE': (str, 'General', 'google'),
    'GOOGLE_CREDENTIALS_FILE': (str, 'General', ''),
    'IBM_CREDENTIALS_FILE': (str, 'General', ''),
    'MICROSOFT_SERVICE_APIKEY': (str, 'General', ''),
    'MICROSOFT_SERVICE_REGION': (str, 'General', 'eastus'),

    'HTTP_PORT': (int, 'HTTP', 8880),
    'ENABLE_HTTPS': (int, 'HTTP', 0),
    'HTTPS_CERT': (str, 'HTTP', ''),
    'HTTPS_CERT_CHAIN': (str, 'HTTP', ''),
    'HTTPS_KEY': (str, 'HTTP', ''),
    'HTTP_HOST': (str, 'HTTP', '0.0.0.0'),
    'HTTP_PROXY': (int, 'HTTP', 0),
    'HTTP_ROOT': (str, 'HTTP', '/'),
    'HTTP_BASE_URL': (str, 'HTTP', ''),

    'HTTP_BASIC_AUTH': (int, 'HTTP', 0),
    'HTTP_USERNAME': (str, 'HTTP', ''),
    'HTTP_PASSWORD': (str, 'HTTP', ''),
    'HTTP_HASH_PASSWORD': (int, 'HTTP', 0),
    'JWT_SECRET': (str, 'HTTP', ''),

    'CHECK_GITHUB': (int, 'Update', 1),
    'GIT_TOKEN': (str, 'Update', ''),
    'GIT_REMOTE': (str, 'Update', 'origin'),
    'GIT_BRANCH': (str, 'Update', 'master'),
    'GIT_PATH': (str, 'Update', ''),
    'GIT_USER': (str, 'Update', 'zSeriesGuy'),
    'GIT_REPO': (str, 'Update', 'SpeakReader'),
    'DO_NOT_OVERRIDE_GIT_BRANCH': (int, 'Update', 0),

}


class Config(object):
    """ Wraps access to particular values in a config file """

    def __init__(self, config_file):
        """ Initialize the config with values from a file """
        self._config_file = config_file
        self._config = ConfigObj(self._config_file, encoding='utf-8')
        for key in _CONFIG_DEFINITIONS.keys():
            self.check_setting(key)

    @staticmethod
    def _define(name):
        key = name.upper()
        ini_key = name.lower()
        definition = _CONFIG_DEFINITIONS[key]
        if len(definition) == 3:
            definition_type, section, default = definition
        else:
            definition_type, section, _, default = definition
        return key, definition_type, section, ini_key, default

    def check_section(self, section):
        """ Check if INI section exists, if not create it """
        if section not in self._config:
            self._config[section] = {}
            return True
        else:
            return False

    def check_setting(self, key):
        """ Cast any value in the config to the right type or use the default """
        key, definition_type, section, ini_key, default = self._define(key)
        self.check_section(section)
        try:
            my_val = definition_type(self._config[section][ini_key])
        except Exception:
            my_val = definition_type(default)
            self._config[section][ini_key] = my_val
        return my_val

    def write(self):
        """ Make a copy of the stored config and write it to the configured file """
        new_config = ConfigObj(encoding="UTF-8")
        new_config.filename = self._config_file

        # first copy over everything from the old config, even if it is not
        # correctly defined to keep from losing data
        for key, subkeys in self._config.items():
            if key not in new_config:
                new_config[key] = {}
            for subkey, value in subkeys.items():
                new_config[key][subkey] = value

        # next make sure that everything we expect to have defined is so
        for key in _CONFIG_DEFINITIONS.keys():
            key, definition_type, section, ini_key, default = self._define(key)
            self.check_setting(key)
            if section not in new_config:
                new_config[section] = {}
            new_config[section][ini_key] = self._config[section][ini_key]

        # Write it to file
        logger.info("Config :: Writing configuration to file")

        try:
            new_config.write()
        except IOError as e:
            logger.error("Config :: Error writing configuration file: %s", e)

    def __getattr__(self, name):
        """
        Returns something from the ini unless it is a real property
        of the configuration object or is not all caps.
        """
        if not re.match(r'[A-Z_]+$', name):
            return super(Config, self).__getattr__(name)
        else:
            return self.check_setting(name)

    def __setattr__(self, name, value):
        """
        Maps all-caps properties to ini values unless they exist on the
        configuration object.
        """
        if not re.match(r'[A-Z_]+$', name):
            super(Config, self).__setattr__(name, value)
            return value
        else:
            key, definition_type, section, ini_key, default = self._define(name)
            self._config[section][ini_key] = definition_type(value)
            return self._config[section][ini_key]

    def process_kwargs(self, kwargs):
        """
        Given a big bunch of key value pairs, apply them to the ini.
        """
        for name, value in kwargs.items():
            key, definition_type, section, ini_key, default = self._define(name)
            self._config[section][ini_key] = definition_type(value)
