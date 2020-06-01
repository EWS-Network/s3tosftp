#  -*- coding: utf-8 -*-
"""
Module to handle the SFTP files transfer.
"""

from os import path, remove, makedirs
import boto3
import pysftp

from s3sftp import SFTP_PATH, SFTP_PORT, SFTP_HOST, SFTP_USER, SFTP_PASS, LOG, keyisset


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

    def push(self):
        """
        Function to upload the file to SFTP target.
        """
        if not path.exists(self.local_file_path):
            raise FileNotFoundError(
                f"File {self.local_file_path} not found. Aborting transfer."
            )
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        cnopts.knownhosts = None

        connection = pysftp.Connection(
            host=self.sftp_info[SFTP_HOST],
            username=self.sftp_info[SFTP_USER],
            password=self.sftp_info[SFTP_PASS],
            port=self.sftp_info[SFTP_PORT],
            cnopts=cnopts,
        )
        with connection as sftp_fd:
            if not sftp_fd.exists(self.dir_path):
                self.create_dir(sftp_fd)
            LOG.debug(self.local_file_path)
            LOG.debug(self.remote_file_path)
            sftp_fd.put(self.local_file_path, self.remote_file_path)
        connection.close()

    def pull(self):
        """
        Function to pull the file from s3 to local.
        """
        if not path.exists(self.local_dir_path) or not path.isdir(self.local_dir_path):
            makedirs(path.abspath(self.local_dir_path))
        with open(self.local_file_path, "wb") as file_fd:
            self.client.download_fileobj(self.bucket_name, self.s3_path, file_fd)

    def clean(self):
        """
        Function to delete file from system
        """
        if path.exists(self.local_file_path):
            remove(self.local_file_path)

    def __init__(
        self, sftp_info, bucket_name, file_path, session=None, client=None,
    ):
        """
        Init function for file transfer.
        """
        if not client:
            if not session:
                self.client = boto3.client("s3")
            else:
                self.client = session.client("s3")
        else:
            self.client = client

        self.sftp_info = sftp_info
        self.bucket_name = bucket_name
        self.s3_path = file_path
        dir_path = path.split(file_path)[0]
        file_name = path.split(file_path)[1]

        if keyisset(SFTP_PATH, sftp_info) and (
            sftp_info[SFTP_PATH] != "" or sftp_info[SFTP_PATH] != "/"
        ):
            self.dir_path = f"{sftp_info[SFTP_PATH]}/{dir_path}"
        else:
            self.dir_path = dir_path

        self.local_dir_path = path.abspath(f"/tmp/{dir_path}")
        self.local_file_path = path.abspath(f"{self.local_dir_path}/{file_name}")
        self.remote_file_path = path.abspath(f"{self.dir_path}/{file_name}")
