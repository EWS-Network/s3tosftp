#  -*- coding: utf-8 -*-
"""
Module to handle the SFTP files transfer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from boto3.session import Session

from os import path
from tempfile import TemporaryDirectory

import pysftp
from compose_x_common.aws import get_session

from .logger import LOG


class FileHandler(object):
    """
    Class to handle the SFTP file transfer from S3 to target.
    """

    file_path = None
    bucket_name = None
    connection = None

    def create_dir(self, sftp_fd):
        """
        Function to recursively create directory
        :return:
        """
        sub_folders = self.dir_path.split("/")
        paths = []
        for folder in sub_folders:
            paths.append(folder)
            dest_path = "/".join(paths)
            LOG.debug(f"Creating {dest_path}")
            if not sftp_fd.exists(dest_path):
                try:
                    sftp_fd.mkdir(dest_path)
                    LOG.info(f"Created {dest_path} successfully")
                except Exception as error:
                    LOG.error(f"Failed to create {dest_path}")
                    LOG.error(error)

    def push(self, sftp_fd) -> None:
        """
        Function to upload the file to SFTP target.
        """
        if not path.exists(self.local_file_path):
            raise FileNotFoundError(
                f"File {self.local_file_path} not found. Aborting transfer."
            )

        if not sftp_fd.exists(self.dir_path):
            self.create_dir(sftp_fd)
        LOG.debug(self.local_file_path)
        LOG.debug(self.remote_file_path)
        sftp_fd.put(self.local_file_path, self.remote_file_path)
        LOG.info(f"File {self.local_file_path} uploaded to SFTP")

    def pull(self):
        """
        Function to pull the file from s3 to local.
        """
        client = self.session.client("s3")
        LOG.info(
            f"Downloading {self.bucket_name}::{self.s3_path} to {self.local_file_path}"
        )
        with open(self.local_file_path, "wb") as file_fd:
            client.download_fileobj(self.bucket_name, self.s3_path, file_fd)
        LOG.info(f"Downloaded {self.bucket_name}::{self.s3_path} successfully")

    def __init__(
        self,
        bucket_name: str,
        file_path: str,
        temp_dir: TemporaryDirectory,
        session: Session = None,
    ):
        """
        Init function for file transfer.
        """
        self.session = get_session(session)
        self.bucket_name = bucket_name
        self.s3_path = file_path
        dir_path = path.dirname(file_path)
        file_name = path.basename(file_path)
        self.local_file_path = f"{temp_dir.name}/{file_name}"
        if dir_path:
            self.remote_file_path = path.normpath(f"{dir_path}/{file_name}")
            self.dir_path = dir_path
        else:
            self.remote_file_path = file_name
            self.dir_path = ""


def get_sftp_connection(sftp_connection_details: dict):
    cnopts = pysftp.CnOpts(knownhosts=None)
    cnopts.knownhosts = None
    cnopts.hostkeys = None

    connection = pysftp.Connection(cnopts=cnopts, **sftp_connection_details)
    return connection


def push_pull_file(
    file_info: dict, queue_url: str, message: dict, session: Session, sftp_fd
):
    temp_dir = TemporaryDirectory()
    file = FileHandler(
        file_info["bucket_name"],
        file_info["object"],
        temp_dir,
        session=session,
    )
    try:
        file.pull()
        file.push(sftp_fd)
        session.client("sqs").delete_message(
            QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"]
        )
    except Exception as error:
        LOG.exception(error)
        raise
    finally:
        temp_dir.cleanup()
