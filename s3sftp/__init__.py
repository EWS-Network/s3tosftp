#  -*- coding: utf-8 -*-
"""
Module to get jobs from SQS and transfer files from S3 to a SFTP target
"""

import sys
from os import environ
import logging as logthings
from json import loads, dumps

SFTP_ENV_NAME = "SFTP_TARGET"
QUEUE_KEY = "QUEUE_NAME"

SFTP_HOST = "dstHost"
SFTP_PORT = "dstPort"
SFTP_USER = "dstUsername"
SFTP_PASS = "dstPassword"
SFTP_PATH = "dstPath"


def keyisset(x, y):
    """Macro to figure if the the dictionary contains a key and that the key is not empty

    :param x: The key to check presence in the dictionary
    :type x: str
    :param y: The dictionary to check for
    :type y: dict

    :returns: True/False
    :rtype: bool
    """
    if isinstance(y, dict) and x in y.keys() and y[x]:
        return True
    return False


def setup_logging():
    """Function to setup logging for ECS ComposeX.
    In case this is used in a Lambda function, removes the AWS Lambda default log handler

    :returns: the_logger
    :rtype: Logger
    """
    level = environ.get("LOGLEVEL")
    default_level = True
    formats = {
        "INFO": logthings.Formatter(
            "%(asctime)s [%(levelname)s], %(message)s", "%Y-%m-%d %H:%M:%S",
        ),
        "DEBUG": logthings.Formatter(
            "%(asctime)s [%(levelname)s], %(filename)s.%(lineno)d , %(funcName)s, %(message)s",
            "%Y-%m-%d %H:%M:%S",
        ),
    }

    if level is not None and isinstance(level, str):
        print("SETTING TO", level.upper())
        logthings.basicConfig(level=level.upper())
        default_level = False
    else:
        logthings.basicConfig(level="INFO")

    root_logger = logthings.getLogger()
    for h in root_logger.handlers:
        root_logger.removeHandler(h)
    the_logger = logthings.getLogger("EcsComposeX")

    if not the_logger.handlers:
        if default_level:
            formatter = formats["INFO"]
        elif keyisset(level.upper(), formats):
            formatter = formats[level.upper()]
        else:
            formatter = formats["DEBUG"]
        handler = logthings.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        the_logger.addHandler(handler)
    return the_logger


def get_sftp_info():
    """
    Function retrieving the SFTP target information from environment variable.

    :return: SFTP connection details
    :rtype: dict
    """
    secret_required_keys = [
        (SFTP_HOST, str),
        (SFTP_USER, str),
        (SFTP_PATH, str),
        (SFTP_PORT, int),
    ]
    stfp_info = environ.get(SFTP_ENV_NAME)
    if stfp_info is not None and isinstance(stfp_info, str):
        try:
            secret = loads(stfp_info)
        except Exception as error:
            raise ValueError(error)
        for attr in secret_required_keys:
            if attr[0] not in secret.keys():
                raise KeyError(f"{attr[0]} missing in secret. Got", secret.keys())
            elif not isinstance(secret[attr[0]], attr[1]):
                raise TypeError(
                    f"{attr[0]} must be of type",
                    type(attr[1]),
                    "Got",
                    type(secret[attr[0]]),
                )
        return secret
    else:
        raise ValueError(
            f"{SFTP_ENV_NAME} not set or invalid", environ.get(SFTP_ENV_NAME)
        )


def get_queue_name():
    """
    Function to get the queue name from environ.

    :return: queue name
    :rtype: str
    """
    queue = environ.get(QUEUE_KEY)
    if queue is not None and isinstance(queue, str):
        return queue
    else:
        raise ValueError("QUEUE_NAME not set or invalid", environ.get(QUEUE_KEY))


LOG = setup_logging()
