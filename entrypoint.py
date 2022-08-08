#!/usr/bin/env python
# Copyright (C) 2020-2022 John Mille <john@ews-network.net>

import logging
from argparse import ArgumentParser
from os import environ
from tempfile import TemporaryDirectory

from s3_to_sftp import get_sftp_info
from s3_to_sftp.logger import LOG
from s3_to_sftp.worker import Worker

MB: int = 1024**2
TRANSFER_RATE: int = int(environ.get("TRANSFER_RATE", 1))
ERROR_MARGIN: int = int(environ.get("TRANSFER_MARGIN_PERCENT", 15))
MAX_MESSAGES_BATCH = int(environ.get("SQS_MAX_MESSAGES", 10))


def get_queue_url() -> str:
    """
    Function to get the queue URL.
    """

    queue_url = environ.get("QUEUE_URL", None)
    if not queue_url:
        queue_name = environ.get("QUEUE_NAME", None)
        if queue_name and isinstance(queue_name, str):
            return Worker.get_queue_url_from_name(queue_name)
    return queue_url


def s3_to_sftp():
    parser = ArgumentParser("S3 to SFTP")
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode", required=False
    )
    parser.add_argument(
        "--max-messages-batch",
        required=False,
        type=int,
        default=2,
        help="Number of messages to receive max. Maximum 10.",
    )
    parser.add_argument(
        "--transfer-rate",
        type=int,
        help="Transfer rate, in MB/s, used to estimate message retention.",
        default=TRANSFER_RATE,
        required=False,
    )
    parser.add_argument(
        "--error-margin",
        type=int,
        required=False,
        help="In percent from 1 to 100, how much margin of error for transfer time to add.",
        default=ERROR_MARGIN,
    )
    args = parser.parse_args()
    if args.debug and LOG.hasHandlers():
        LOG.setLevel(logging.DEBUG)
        LOG.handlers[0].setLevel(logging.DEBUG)
    client_temp_dir = TemporaryDirectory()
    worker = Worker(get_queue_url(), get_sftp_info(client_temp_dir))
    worker.run(**vars(args))


if __name__ == "__main__":
    exit(s3_to_sftp())
