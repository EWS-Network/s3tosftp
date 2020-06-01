#!/usr/bin/env python
#  -*- coding: utf-8 -*-
from json import dumps
from s3sftp import get_sftp_info, get_queue_name, LOG
from s3sftp.worker import listen_for_jobs

if __name__ == "__main__":
    SFTP_TARGET = get_sftp_info()
    QUEUE_NAME = get_queue_name()
    LOG.debug(dumps(SFTP_TARGET))
    LOG.info(QUEUE_NAME)
    listen_for_jobs(QUEUE_NAME, SFTP_TARGET)
