#  This file is part of SpeakReader.
#

import contextlib
import errno
import json
from queue import Queue
import logging, logging.handlers
from logging import handlers
import multiprocessing
import os
#import re
import sys
import threading
import traceback
import datetime

# These settings are for file logging only
FILENAME_PREFIX = "speakreader-"
FILENAME_SUFFIX = "log"
FILENAME_DATE_FORMAT = "%Y-%m-%d-%H%M"
FILENAME_DATESTRING = datetime.datetime.now().strftime(FILENAME_DATE_FORMAT)
FILENAME = FILENAME_PREFIX + FILENAME_DATESTRING + "." + FILENAME_SUFFIX
MAX_SIZE = 5000000  # 5 MB
MAX_FILES = 5

# SpeakReader logger
logger = logging.getLogger("SpeakReader")
log_level = logging.DEBUG
log_format = logging.Formatter('%(asctime)s - %(levelname)s :: %(threadName)s : %(message)s', '%Y-%m-%d %H:%M:%S')
listenerQueues = []

# Global queue for multiprocessing logging
queue = None


def initLogger(console=False, log_dir=False, verbose=False):
    """
    Setup logging for SpeakReader. It uses the logger instance with the name
    'SpeakReader'. Three log handlers are added:

    * RotatingFileHandler: for the file speakreader.log
    * LogListHandler: for Web UI
    * StreamHandler: for console (if console)

    Console logging is only enabled if console is set to True. This method can
    be invoked multiple times, during different stages of SpeakReader.
    """

    # Close and remove old handlers. This is required to reinit the loggers
    # at runtime
    global log_level
    log_level = logging.DEBUG if verbose else logging.INFO

    for handler in logger.handlers[:]:
        # Just make sure it is cleaned up.
        if isinstance(handler, handlers.RotatingFileHandler):
            handler.close()
        elif isinstance(handler, logging.StreamHandler):
            handler.flush()

        logger.removeHandler(handler)

    # Configure the logger to accept all messages
    logger.propagate = False
    logger.setLevel(log_level)

    # Setup file logger
    if log_dir:
        # Main SpeakReader logger
        filename = os.path.join(str(log_dir), FILENAME)
        file_handler = handlers.RotatingFileHandler(filename, maxBytes=MAX_SIZE, backupCount=MAX_FILES)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(log_format)

        logger.addHandler(file_handler)

    # Setup console logger
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_format)
        console_handler.setLevel(log_level)

        logger.addHandler(console_handler)

    # Install exception hooks
    initHooks(thread_exceptions=False)


def initHooks(global_exceptions=True, thread_exceptions=True, pass_original=True):
    """
    This method installs exception catching mechanisms. Any exception caught
    will pass through the exception hook, and will be logged to the logger as
    an error. Additionally, a traceback is provided.

    This is very useful for crashing threads and any other bugs, that may not
    be exposed when running as daemon.

    The default exception hook is still considered, if pass_original is True.
    """

    def excepthook(*exception_info):
        # We should always catch this to prevent loops!
        try:
            message = "".join(traceback.format_exception(*exception_info))
            logger.error("Uncaught exception: %s", message)
        except:
            pass

        # Original excepthook
        if pass_original:
            sys.__excepthook__(*exception_info)

    # Global exception hook
    if global_exceptions:
        sys.excepthook = excepthook

    # Thread exception hook
    if thread_exceptions:
        old_init = threading.Thread.__init__

        def new_init(self, *args, **kwargs):
            old_init(self, *args, **kwargs)
            old_run = self.run

            def new_run(*args, **kwargs):
                try:
                    old_run(*args, **kwargs)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception:
                    sys.excepthook(*sys.exc_info())
            self.run = new_run

        # Monkey patch the run() by monkey patching the __init__ method
        threading.Thread.__init__ = new_init


def shutdown():
    logging.shutdown()


# Expose logger methods
info = logger.info
warn = logger.warn
error = logger.error
debug = logger.debug
warning = logger.warning
exception = logger.exception
