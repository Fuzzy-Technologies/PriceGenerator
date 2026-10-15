# -*- coding: utf-8 -*-
#
# Author: Timur Gilmullin

"""
This module init standard python logging system with some of pre-defined parameters,
e.g. debug level for log-file, info level for console, log-rotate and so on.

Current internal logger name for PriceGenerator module is `PriceGenerator-UniLogger`.
"""

# Copyright (c) 2022 Gilmillin Timur Mansurovich
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import sys
import logging.handlers


# initialize Main Parent Logger:
UniLogger = logging.getLogger("PriceGenerator-UniLogger")
formatString = "%(filename)-20sL:%(lineno)-5d%(levelname)-8s[%(asctime)s] %(message)s"
formatter = logging.Formatter(formatString)


def SetLevel(vLevel='ERROR'):
    """
    This procedure setting up UniLogger verbosity level.
    """
    UniLogger.level = logging.NOTSET

    if isinstance(vLevel, str):
        if vLevel == '5' or vLevel.upper() == 'CRITICAL':
            UniLogger.level = logging.CRITICAL

        elif vLevel == '4' or vLevel.upper() == 'ERROR':
            UniLogger.level = logging.ERROR

        elif vLevel == '3' or vLevel.upper() == 'WARNING':
            UniLogger.level = logging.WARNING

        elif vLevel == '2' or vLevel.upper() == 'INFO':
            UniLogger.level = logging.INFO

        elif vLevel == '1' or vLevel.upper() == 'DEBUG':
            UniLogger.level = logging.DEBUG


class LevelFilter(logging.Filter):
    """
    Class using to set up log level filtering.
    """

    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        return record.levelno >= self.level


def EnableLogger(logFile, parentHandler=UniLogger, useFormat=formatter):
    """
    Adding new file logger with rotation.
    """
    # logHandler = logging.FileHandler(logFile)
    maxSizeBytes = 50 * 1024 * 1024  # 5Mb log rotate by default
    logHandler = logging.handlers.RotatingFileHandler(logFile, encoding="UTF-8", maxBytes=maxSizeBytes, backupCount=4)
    logHandler.level = logging.DEBUG  # set up DEBUG verbosity level by default for file logging
    logHandler.addFilter(LevelFilter(logging.DEBUG))

    if useFormat:
        logHandler.setFormatter(useFormat)

    else:
        logHandler.setFormatter(formatter)

    parentHandler.addHandler(logHandler)

    return logHandler


def DisableLogger(handler, parentHandler=UniLogger):
    """
    Disable given file logger.
    """
    if handler:
        handler.flush()
        handler.close()

    if handler in parentHandler.handlers:
        parentHandler.removeHandler(handler)


# --- Main init:

SetLevel('DEBUG')  # set up DEBUG verbosity level by default for UniLogger

streamHandler = logging.StreamHandler(sys.stdout)  # keep CLI output on stdout without redirecting host stderr
streamHandler.setFormatter(formatter)  # set formatter for STDOUT UniLogger
streamHandler.level = logging.INFO  # set up INFO verbosity level by default for STDOUT UniLogger
UniLogger.addHandler(streamHandler)  # adding STDOUT UniLogger handler to Parent UniLogger

# fileLogHandler = EnableLogger(logFile='log.txt', parentHandler=UniLogger, useFormat=formatter)  # add logging to file

sepWide = '-' * 120  # long-long log separator
sepLong = '-' * 80  # long log separator
sepShort = '-' * 40  # short log separator
sepLine = '=--=' * 20  # log part separator
