#!/bin/sh
''''which python3   >/dev/null 2>&1 && exec python    "$0" "$@" # '''
''''exec echo "Error: Python3 not found!" # '''

#
# This file is the main startup module for SpeakReader.
#

import os
import sys
import subprocess
from platform import node, system, release, version

import argparse
import datetime
import locale
import pytz
import signal
import time
import tzlocal
import threading

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
    CREATEPID = False
    PIDFILE = None

    QUIET = False
    VERBOSE = True
    NOLAUNCH = False
    HTTP_PORT = None

    PLATFORM = system()
    PLATFORM_RELEASE = release()
    PLATFORM_VERSION = version()
    PLATFORM_LINUX_DISTRO = None
    PLATFORM_DEVICE_NAME = node()

    # Fixed paths to application
    if hasattr(sys, 'frozen'):
        FULL_PATH = os.path.abspath(sys.executable)
    else:
        FULL_PATH = os.path.abspath(__file__)

    PROG_DIR = os.path.dirname(FULL_PATH)

    # From sickbeard
    SYS_PLATFORM = sys.platform
    SYS_ENCODING = None

    try:
        locale.setlocale(locale.LC_ALL, "")
        SYS_LANGUAGE, SYS_ENCODING = locale.getdefaultlocale()
    except (locale.Error, IOError):
        pass

    # for OSes that are poorly configured I'll just force UTF-8
    if not SYS_ENCODING or SYS_ENCODING in ('ANSI_X3.4-1968', 'US-ASCII', 'ASCII'):
        SYS_ENCODING = 'UTF-8'

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
        '--pidfile', help='Create a pid file (only relevant when running as a daemon)')
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
        if sys.platform == 'win32':
            sys.stderr.write("Daemonizing not supported under Windows, starting normally\n")
        else:
            DAEMON = True
            QUIET = True

    if args.nofork:
        NOFORK = True
        logger.info("SpeakReader is running as a service, it will not fork when restarted.")

    if args.pidfile:
        PIDFILE = str(args.pidfile)

        # If the pidfile already exists, SpeakReader may still be running, so EXIT
        if os.path.exists(PIDFILE):
            try:
                with open(PIDFILE, 'r') as fp:
                    pid = int(fp.read())
                os.kill(pid, 0)
            except IOError as e:
                raise SystemExit("Unable to read PID file: %s", e)
            except OSError:
                logger.warn("PID file '%s' already exists, but PID %d is not running. Ignoring PID file." %
                            (PIDFILE, pid))
            else:
                # The pidfile exists and points to a live PID. SpeakReader may still be running, so exit.
                raise SystemExit("PID file '%s' already exists. Exiting." % PIDFILE)

        # The pidfile is only useful in daemon mode, make sure we can write the file properly
        if DAEMON:
            CREATEPID = True
            try:
                with open(PIDFILE, 'w') as fp:
                    fp.write("pid\n")
            except IOError as e:
                raise SystemExit("Unable to write PID file: %s", e)
        else:
            logger.warn("Not running in daemon mode. PID file creation disabled.")

    # Determine which data directory and config file to use
    if args.datadir:
        DATA_DIR = args.datadir
    else:
        DATA_DIR = PROG_DIR

    if args.config:
        CONFIG_FILE = args.config
    else:
        CONFIG_FILE = os.path.join(DATA_DIR, config.FILENAME)

    # Do an initial setup of the logging.
    logger.initLogger(console=not QUIET, log_dir=False, verbose=VERBOSE)

    # Initialize the configuration from the config file
    CONFIG = config.Config(CONFIG_FILE)
    assert CONFIG is not None

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
    logger.info("{} (UTC{})".format(
        SYS_TIMEZONE, SYS_UTC_OFFSET
    ))
    logger.info(u"Python {}".format(
        sys.version
    ))
    logger.info(u"Program Dir: {}".format(
        PROG_DIR
    ))
    logger.info(u"Config File: {}".format(
        CONFIG_FILE
    ))

    CONFIG.TRANSCRIPTS_FOLDER, _ = check_folder_writable(
        CONFIG.TRANSCRIPTS_FOLDER, os.path.join(DATA_DIR, 'transcripts'), 'transcripts')

    # Try to create the DATA_DIR if it doesn't exist
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
        except OSError:
            raise SystemExit('Could not create data directory: ' + DATA_DIR + '. Exiting....')

    # Make sure the DATA_DIR is writeable
    if not os.access(DATA_DIR, os.W_OK):
        raise SystemExit('Cannot write to the data directory: ' + DATA_DIR + '. Exiting...')

    if DAEMON:
        daemonize(CREATEPID, PIDFILE)

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
            else:
                SR.SIGNAL = None

    SR.shutdown()

    if CREATEPID:
        logger.info("Removing pidfile %s", PIDFILE)
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


def daemonize(CREATEPID, PIDFILE):

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
    logger.info(u"Daemonized to PID: %d", pid)

    if CREATEPID:
        logger.info(u"Writing PID %d to %s", pid, PIDFILE)
        with open(PIDFILE, 'w') as fp:
            fp.write("%s\n" % pid)


def check_folder_writable(folder, fallback, name):
    if not folder:
        folder = fallback

    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except OSError as e:
            logger.error(u"Could not create %s dir '%s': %s" % (name, folder, e))
            if folder != fallback:
                logger.warn(u"Falling back to %s dir '%s'" % (name, fallback))
                return check_folder_writable(None, fallback, name)
            else:
                return folder, None

    if not os.access(folder, os.W_OK):
        logger.error(u"Cannot write to %s dir '%s'" % (name, folder))
        if folder != fallback:
            logger.warn(u"Falling back to %s dir '%s'" % (name, fallback))
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
