# Copyright (C) 2020-2022 John Mille <john@ews-network.net>

"""
Module to get jobs from SQS and transfer files from S3 to a SFTP target
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tempfile import TemporaryDirectory

from json import JSONDecodeError, loads
from os import environ, path

from boto3.session import Session
from compose_x_common.aws.secrets_manager import SECRET_ARN_RE
from jsonschema import validate

from s3_to_sftp.logger import LOG

__author__ = """John Preston"""
__email__ = "john@compose-x.io"
__version__ = "1.0.0"


SFTP_DETAILS_ENV_NAME = "SFTP_TARGET"
PRIVATE_KEY_SECRET_ARN = "PRIVATE_KEY_SECRET_ARN"
PRIVATE_KEY_PASSPHRASE_SECRET_ARN = "PRIVATE_KEY_PASSPHRASE_SECRET_ARN"


SFTP_HOST = "host"
SFTP_PORT = "port"
SFTP_USER = "username"
SFTP_PASS = "password"
SFTP_PATH = "default_path"
SFTP_CLIENT_KEY_PATH = "private_key"
SFTP_CLIENT_KEY_PASSWORD = "private_key_pass"


def get_sftp_details_from_secrets_manager(secret_arn: str) -> dict:
    session = Session()
    client = session.client("secretsmanager")
    try:
        secret_r = client.get_secret_value(SecretId=secret_arn)
        return secret_r
    except (
        client.exceptions.ResourceNotFoundException,
        client.exceptions.DecryptionFailure,
    ):
        print("Failed to retrieve SFTP Secrets details")
        raise


def get_sftp_details_from_env(sftp_details: dict) -> None:
    keys = [
        SFTP_HOST,
        SFTP_USER,
        SFTP_USER,
        SFTP_PASS,
        SFTP_PATH,
        SFTP_CLIENT_KEY_PATH,
        SFTP_CLIENT_KEY_PASSWORD,
    ]
    for key in keys:
        value = environ.get(key, None)
        if value:
            sftp_details[key] = value
            if key in sftp_details:
                print(f"Override value for {key} from environment variable")


def get_sftp_ssh_key_details(
    sftp_connection_details: dict, temp_directory: TemporaryDirectory
) -> None:
    client_key = environ.get(PRIVATE_KEY_SECRET_ARN, None)
    if client_key and SECRET_ARN_RE.match(client_key):
        private_key = get_sftp_details_from_secrets_manager(client_key)
        temp_key_path = f"{temp_directory.name}/private_key"
        with open(temp_key_path, "w") as private_key_fd:
            private_key_fd.write(private_key["SecretString"])
            LOG.info(f"Pulled private key. Stored in {temp_key_path}")
        sftp_connection_details[SFTP_CLIENT_KEY_PATH] = temp_key_path
    client_key_passphrase = environ.get(PRIVATE_KEY_PASSPHRASE_SECRET_ARN, None)
    if client_key_passphrase and SECRET_ARN_RE.match(client_key_passphrase):
        sftp_connection_details[
            SFTP_CLIENT_KEY_PASSWORD
        ] = get_sftp_details_from_secrets_manager(client_key_passphrase)["SecretString"]
        LOG.info("Private key passphrase pulled from Secrets Manager")


def get_sftp_info(temp_directory: TemporaryDirectory) -> dict:
    """
    Function retrieving the SFTP target information from environment variable.

    :return: SFTP connection details
    :rtype: dict
    """
    sftp_connection_details: dict = {}
    get_sftp_ssh_key_details(sftp_connection_details, temp_directory)
    sftp_info = environ.get(SFTP_DETAILS_ENV_NAME, None)
    if sftp_info and isinstance(sftp_info, str) and SECRET_ARN_RE.match(sftp_info):
        try:
            sftp_details = loads(
                get_sftp_details_from_secrets_manager(sftp_info)["SecretString"]
            )
            LOG.info("Loaded sftp details from Secrets Manager")
        except JSONDecodeError:
            print("sftp_details in secrets manager are not in a valid JSON Format")
            raise
    elif sftp_info and isinstance(sftp_info, str):
        try:
            sftp_details = loads(sftp_info)
            LOG.info("Loaded sftp details from environment variable")
        except JSONDecodeError:
            print(
                "Secrets info from environment variable are not in a valid JSON Format"
            )
            raise
    else:
        raise ValueError(f"Unable to get secrets details from {SFTP_DETAILS_ENV_NAME}")
    sftp_connection_details.update(sftp_details)
    get_sftp_details_from_env(sftp_connection_details)
    with open(
        f"{path.abspath(path.dirname(__file__))}/secret-format.json"
    ) as secret_format_fd:
        secret_schema = json.loads(secret_format_fd.read())
    validate(sftp_connection_details, secret_schema)
    LOG.info("Successfully retrieved SFTP session details")
    LOG.info(
        "SFTP Connection: "
        f"{sftp_connection_details['username']}@"
        f"{sftp_connection_details['host']}:"
        f"{sftp_connection_details['port']}"
    )
    LOG.debug(sftp_connection_details.keys())
    return sftp_connection_details
