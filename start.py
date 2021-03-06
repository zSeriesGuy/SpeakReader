#!/bin/sh
''''which python3   >/dev/null 2>&1 && exec python    "$0" "$@" # '''
''''exec echo "Error: Python3 not found!" # '''

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

#
# This file is the main startup module for SpeakReader.
#

import os
import sys
import subprocess
from platform import system, release, version, machine, processor

import argparse
import datetime
import locale
import pytz
import signal
import time
import tzlocal
import threading
import psutil

import speakreader
from speakreader import logger, config, SpeakReader

# Ensure lib added to path, before any other imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))


def main():
    """
    SpeakReader application entry point. Parses arguments, setups encoding and
    initializes the application.
    """

    DAEMON = False
    NOFORK = False

    QUIET = False
    VERBOSE = False
    NOLAUNCH = False
    HTTP_PORT = None

    PLATFORM = system()
    PLATFORM_RELEASE = release()
    PLATFORM_VERSION = version()
    PLATFORM_LINUX_DISTRO = None

    PLATFORM_PROCESSOR = processor()
    PLATFORM_MACHINE = machine()
    PLATFORM_IS_64BITS = sys.maxsize > 2**32
    SYS_PLATFORM = sys.platform

    # Fixed paths to application
    if hasattr(sys, 'frozen'):
        FULL_PATH = os.path.abspath(sys.executable)
    else:
        FULL_PATH = os.path.abspath(__file__)

    PROG_DIR = os.path.dirname(FULL_PATH)

    # Ensure only one instance of SpeakReader running.
    PIDFILE = os.path.join(PROG_DIR, 'pidfile')
    myPid = os.getpid()
    if os.path.exists(PIDFILE) and os.path.isfile(PIDFILE):
        for p in psutil.process_iter():
            if 'python' in p.name() and p.pid != myPid:
                for f in p.open_files():
                    if f.path == PIDFILE:
                        logger.error("SpeakReader is already Running. Exiting.")
                        sys.exit(0)

    myPidFile = open(PIDFILE, 'w+')
    myPidFile.write(str(myPid))
    myPidFile.flush()

    try:
        locale.setlocale(locale.LC_ALL, "")
    except (locale.Error, IOError):
        pass

    try:
        SYS_TIMEZONE = str(tzlocal.get_localzone())
        SYS_UTC_OFFSET = datetime.datetime.now(pytz.timezone(SYS_TIMEZONE)).strftime('%z')
    except (pytz.UnknownTimeZoneError, LookupError, ValueError) as e:
        logger.error("Could not determine system timezone: %s" % e)
        SYS_TIMEZONE = 'Unknown'
        SYS_UTC_OFFSET = '+0000'

    # Parse any passed startup arguments
    ARGS = sys.argv[1:]
    # Set up and gather command line arguments
    parser = argparse.ArgumentParser(description='A Python based monitoring and tracking tool for Plex Media Server.')

    parser.add_argument(
        '-v', '--verbose', action='store_true', help='Increase console logging verbosity')
    parser.add_argument(
        '-q', '--quiet', action='store_true', help='Turn off console logging')
    parser.add_argument(
        '-d', '--daemon', action='store_true', help='Run as a daemon')
    parser.add_argument(
        '-p', '--port', type=int, help='Force SpeakReader to run on a specified port')
    parser.add_argument(
        '--datadir', help='Specify a directory where to store your data files')
    parser.add_argument(
        '--config', help='Specify a config file to use')
    parser.add_argument(
        '--nolaunch', action='store_true', help='Prevent browser from launching on startup')
    parser.add_argument(
        '--nofork', action='store_true', help='Start SpeakReader as a service, do not fork when restarting')

    args = parser.parse_args()

    # Force the http port if necessary
    if args.port:
        HTTP_PORT = args.port
        logger.info('Using forced web server port: %i', HTTP_PORT)

    # Don't launch the browser
    if args.nolaunch:
        NOLAUNCH = True

    if args.verbose:
        VERBOSE = True
    if args.quiet:
        QUIET = True

    if args.daemon:
        if SYS_PLATFORM == 'win32':
            sys.stderr.write("Daemonizing not supported under Windows, starting normally\n")
        else:
            DAEMON = True
            QUIET = True

    if args.nofork:
        NOFORK = True
        logger.info("SpeakReader is running as a service, it will not fork when restarted.")

    # Determine which data directory and config file to use
    if args.datadir:
        DATA_DIR = args.datadir
    else:
        DATA_DIR = os.path.join(PROG_DIR, 'data')

    if args.config:
        CONFIG_FILE = args.config
    else:
        CONFIG_FILE = os.path.join(DATA_DIR, config.FILENAME)

    # Try to create the DATA_DIR if it doesn't exist
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
        except OSError:
            raise SystemExit('Could not create data directory: ' + DATA_DIR + '. Exiting....')

    # Make sure the DATA_DIR is writeable
    if not os.access(DATA_DIR, os.W_OK):
        raise SystemExit('Cannot write to the data directory: ' + DATA_DIR + '. Exiting...')

    # Do an initial setup of the logging.
    logger.initLogger(console=not QUIET, log_dir=False, verbose=VERBOSE)

    # Initialize the configuration from the config file
    CONFIG = config.Config(CONFIG_FILE)
    assert CONFIG is not None

    if CONFIG.SERVER_ENVIRONMENT.lower() != 'production':
        VERBOSE = True

    CONFIG.LOG_DIR, log_writable = check_folder_writable(
        CONFIG.LOG_DIR, os.path.join(DATA_DIR, 'logs'), 'logs')
    if not log_writable and not QUIET:
        sys.stderr.write("Unable to create the log directory. Logging to screen only.\n")

    # Start the logger, disable console if needed
    logger.initLogger(console=not QUIET, log_dir=CONFIG.LOG_DIR if log_writable else None, verbose=VERBOSE)

    logger.info("Initializing {} {}".format(speakreader.PRODUCT, speakreader.VERSION_RELEASE))
    logger.info("{} {} ({}{})".format(
        PLATFORM, PLATFORM_RELEASE, PLATFORM_VERSION,
        ' - {}'.format(PLATFORM_LINUX_DISTRO) if PLATFORM_LINUX_DISTRO else ''
    ))
    logger.info("{} ({} {})".format(
        PLATFORM_PROCESSOR, PLATFORM_MACHINE,
        '{}'.format('64-BIT') if PLATFORM_IS_64BITS else '32-BIT'
    ))
    logger.info("Python {}".format(
        sys.version
    ))
    logger.info("{} (UTC{})".format(
        SYS_TIMEZONE, SYS_UTC_OFFSET
    ))
    logger.info("Program Dir: {}".format(
        PROG_DIR
    ))
    logger.info("Config File: {}".format(
        CONFIG_FILE
    ))

    CONFIG.TRANSCRIPTS_FOLDER, _ = check_folder_writable(
        CONFIG.TRANSCRIPTS_FOLDER, os.path.join(DATA_DIR, 'transcripts'), 'transcripts')

    CONFIG.RECORDINGS_FOLDER, _ = check_folder_writable(
        CONFIG.RECORDINGS_FOLDER, os.path.join(DATA_DIR, 'recordings'), 'recordings')

    if DAEMON:
        daemonize(myPidFile)

    # Store the original umask
    UMASK = os.umask(0)
    os.umask(UMASK)

    initOptions = {
        'config': CONFIG,
        'http_port': HTTP_PORT,
        'nolaunch': NOLAUNCH,
        'prog_dir': PROG_DIR,
        'data_dir': DATA_DIR,
    }

    # Read config and start logging
    global SR
    SR = SpeakReader(initOptions)

    # Wait endlessly for a signal to happen
    restart = False
    checkout = False
    update = False
    while True:
        if not SR.SIGNAL:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                SR.SIGNAL = 'shutdown'
        else:
            logger.info('Received signal: %s', SR.SIGNAL)

            if SR.SIGNAL == 'shutdown':
                break
            elif SR.SIGNAL == 'restart':
                restart = True
                break
            elif SR.SIGNAL == 'update':
                restart = True
                update = True
                break
            elif SR.SIGNAL == 'checkout':
                restart = True
                checkout = True
                break
            else:
                SR.SIGNAL = None

    SR.shutdown(restart=restart, update=update, checkout=checkout)

    myPidFile.close()
    os.remove(PIDFILE)

    if restart:
        logger.info("SpeakReader is restarting...")

        exe = sys.executable
        args = [exe, FULL_PATH]
        args += ARGS
        if '--nolaunch' not in args:
            args += ['--nolaunch']

        # Separate out logger so we can shutdown logger after
        if NOFORK:
            logger.info('Running as service, not forking. Exiting...')
        elif os.name == 'nt':
            logger.info('Restarting SpeakReader with %s', args)
        else:
            logger.info('Restarting SpeakReader with %s', args)

        logger.shutdown()

        if NOFORK:
            pass
        elif os.name == 'nt':
            subprocess.Popen(args, cwd=os.getcwd())
        else:
            os.execv(exe, args)

    else:
        logger.info("SpeakReader Terminated")
        logger.shutdown()

    sys.exit(0)


def daemonize(myPidFile):

    if threading.activeCount() != 1:
        logger.warn(
            "There are %r active threads. Daemonizing may cause"
            " strange behavior.",
            threading.enumerate())

    sys.stdout.flush()
    sys.stderr.flush()

    # Do first fork
    try:
        pid = os.fork()  # @UndefinedVariable - only available in UNIX
        if pid != 0:
            sys.exit(0)
    except OSError as e:
        raise RuntimeError("1st fork failed: %s [%d]", e.strerror, e.errno)

    os.setsid()

    # Make sure I can read my own files and shut out others
    prev = os.umask(0)  # @UndefinedVariable - only available in UNIX
    os.umask(prev and int('077', 8))

    # Make the child a session-leader by detaching from the terminal
    try:
        pid = os.fork()  # @UndefinedVariable - only available in UNIX
        if pid != 0:
            sys.exit(0)
    except OSError as e:
        raise RuntimeError("2nd fork failed: %s [%d]", e.strerror, e.errno)

    dev_null = open('/dev/null', 'r')
    os.dup2(dev_null.fileno(), sys.stdin.fileno())

    si = open('/dev/null', "r")
    so = open('/dev/null', "a+")
    se = open('/dev/null', "a+")

    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    pid = os.getpid()
    myPidFile.seek(0)
    myPidFile.write(str(pid))
    myPidFile.flush()
    logger.info("Daemonized to PID: %d", pid)


def check_folder_writable(folder, fallback, name):
    if not folder:
        folder = fallback

    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except OSError as e:
            logger.error("Could not create %s dir '%s': %s" % (name, folder, e))
            if folder != fallback:
                logger.warn("Falling back to %s dir '%s'" % (name, fallback))
                return check_folder_writable(None, fallback, name)
            else:
                return folder, None

    if not os.access(folder, os.W_OK):
        logger.error("Cannot write to %s dir '%s'" % (name, folder))
        if folder != fallback:
            logger.warn("Falling back to %s dir '%s'" % (name, fallback))
            return check_folder_writable(None, fallback, name)
        else:
            return folder, False

    return folder, True


def sig_handler(signum=None, frame=None):
    global SR
    if signum is not None:
        logger.info("sig_handler: Signal %i caught, Shutting Down SpeakReader...", signum)
        SR.SIGNAL = 'shutdown'


# Register signals, such as CTRL + C
signal.signal(signal.SIGINT, sig_handler)
signal.signal(signal.SIGTERM, sig_handler)


# Call main()
if __name__ == "__main__":
    main()
