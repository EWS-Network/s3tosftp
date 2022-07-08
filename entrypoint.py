#!/usr/bin/env python
#  -*- coding: utf-8 -*-

from tempfile import TemporaryDirectory
from s3_to_sftp import get_sftp_info, get_queue_url
from s3_to_sftp.worker import listen_for_jobs


def s3_to_sftp():
    client_temp_dir = TemporaryDirectory()
    sftp_target = get_sftp_info(client_temp_dir)
    queue_url = get_queue_url()
    listen_for_jobs(queue_url, sftp_target)


if __name__ == "__main__":
    s3_to_sftp()
