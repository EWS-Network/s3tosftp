# Copyright (C) 2020-2022 John Mille <john@ews-network.net>

"""
Module to handle the SFTP files transfer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from boto3.session import Session
    from s3_to_sftp.transfer_file import TransferFile

from datetime import datetime as dt
from os import path
from tempfile import TemporaryDirectory

from compose_x_common.aws import get_session
from compose_x_common.compose_x_common import keyisset, set_else_none
from paramiko import AutoAddPolicy, SFTPClient, SSHClient, Transport
from paramiko.ssh_exception import AuthenticationException

from s3_to_sftp.logger import LOG


def recursive_mkdir(sftp, remote_directory):
    if remote_directory == "/":
        sftp.chdir("/")
        return
    if remote_directory == "":
        return
    try:
        sftp.chdir(remote_directory)
    except IOError:
        dirname, basename = path.split(remote_directory.rstrip("/"))
        recursive_mkdir(sftp, dirname)
        sftp.mkdir(basename)
        sftp.chdir(basename)
        return True


class FileHandler(object):
    """
    Class to handle the SFTP file transfer from S3 to target.
    """

    file_path = None
    bucket_name = None
    connection = None

    def push(self, sftp_fd, transfer_file: TransferFile) -> None:
        """
        Function to upload the file to SFTP target.
        """
        if not path.exists(self.local_file_path):
            transfer_file.file_transfer_status = "SFTP_FAILED"
            transfer_file.file_transfer_start_time = None
            raise FileNotFoundError(
                f"File {self.local_file_path} not found. Aborting transfer."
            )
        recursive_mkdir(sftp_fd, path.dirname(self.remote_file_path))

        LOG.debug(self.local_file_path)
        LOG.debug(self.remote_file_path)
        transfer_file.file_transfer_start_time = dt.utcnow()
        try:
            sftp_fd.put(self.local_file_path, self.remote_file_path, confirm=True)
            LOG.info(f"File {self.local_file_path} uploaded to SFTP")
            transfer_file.file_transfer_end_time = dt.utcnow()
            transfer_file.file_transfer_status = "SFTP_COMPLETE"
        except Exception as error:
            LOG.error("Failed to transfer via SFTP")
            LOG.exception(error)
            transfer_file.file_transfer_status = "SFTP_FAILED"
            transfer_file.file_transfer_start_time = None

    def pull(self, transfer_file: TransferFile):
        """
        Function to pull the file from s3 to local.
        """
        client = self.session.client("s3")
        LOG.info(
            f"Downloading {self.bucket_name}::{self.s3_path} to {self.local_file_path}"
        )
        try:
            with open(self.local_file_path, "wb") as file_fd:
                client.download_fileobj(self.bucket_name, self.s3_path, file_fd)
                LOG.info(f"Downloaded {self.local_file_path} successfully")
                transfer_file.file_status = "S3_COMPLETE"
        except Exception as error:
            LOG.error(f"Failed to pull {transfer_file.file_name} from S3")
            LOG.exception(error)
            transfer_file.file_transfer_status = "S3_FAILED"

    def __init__(
        self,
        bucket_name: str,
        file_path: str,
        temp_dir: TemporaryDirectory,
        sftp_info: dict,
        session: Session = None,
    ):
        """
        Init function for file transfer.
        """
        self.session = get_session(session)
        self.bucket_name = bucket_name
        self.s3_path = file_path
        prefix_path = set_else_none("default_path", sftp_info, alt_value="")
        if prefix_path and not prefix_path.startswith(r"/"):
            prefix_path = "/" + prefix_path
        if prefix_path and not prefix_path.endswith(r"/"):
            prefix_path += r"/"
        dir_path = path.dirname(file_path)
        file_name = path.basename(file_path)
        self.local_file_path = f"{temp_dir.name}/{file_name}"
        if dir_path:
            self.remote_file_path = path.normpath(
                f"{prefix_path}{dir_path}/{file_name}"
            )
            self.dir_path = dir_path
        else:
            self.remote_file_path = prefix_path + file_name
            self.dir_path = ""


def paramiko_auth_interactive_adaptive_best_effort(
    title, instructions, fields
) -> Union[list, tuple]:
    print("T", title, "INST", instructions, "FIELDS", fields)
    if not fields or TEMP_PASS is None:
        return []
    return tuple([TEMP_PASS for _ in fields])


def get_sftp_connection(
    sftp_connection_details: dict,
    alternative_function=None,
    attempt_interactive_auth_with_password: bool = False,
) -> SFTPClient:

    try:
        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        client.connect(
            hostname=sftp_connection_details["host"],
            username=sftp_connection_details["username"],
            password=set_else_none("password", sftp_connection_details),
            port=int(set_else_none("port", sftp_connection_details, alt_value=22)),
            key_filename=set_else_none("private_key", sftp_connection_details),
            passphrase=set_else_none("private_key_pass", sftp_connection_details),
        )
        return client.open_sftp()
    except AuthenticationException:
        if attempt_interactive_auth_with_password and keyisset(
            "password", sftp_connection_details
        ):
            try:
                transport = Transport(sftp_connection_details["host"])
                transport.connect(username=sftp_connection_details["username"])
                global TEMP_PASS
                TEMP_PASS = sftp_connection_details["password"]
                transport.auth_interactive(
                    sftp_connection_details["username"],
                    paramiko_auth_interactive_adaptive_best_effort,
                )
                return transport.open_sftp_client()
            except Exception as error:
                LOG.error("Failure in attempt to use Transport connectivity")
                LOG.exception(error)

    if alternative_function:
        return alternative_function(sftp_connection_details)
