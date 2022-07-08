#  -*- coding: utf-8 -*-

"""
Module to handle the queue jobs and execute the SFTP transfer.

"""
import re
from datetime import datetime as dt
from datetime import timedelta as td
from json import loads
from os import environ

import boto3
from aws_embedded_metrics import metric_scope
from boto3.session import Session
from botocore.exceptions import ClientError
from compose_x_common.aws import get_session
from compose_x_common.aws.sqs import SQS_QUEUE_ARN_RE
from compose_x_common.compose_x_common import keyisset, set_else_none

from s3_to_sftp.transfer import get_sftp_connection, push_pull_file

from .logger import LOG

FOREVER = 42
""" Considering Speed is 1MB/s """
MB = 1024**2
SPEED = MB * int(environ.get("TRANSFER_SPEED", 1))
DEFAULT_HIDE_TIMEOUT = int(environ.get("DEFAULT_HIDE_TIMEOUT", 60))


def get_file_information(message: dict) -> dict:
    """
    Function to return the file information from the event

    :param dict message: the message payload
    :return: message_info
    :rtype dict:
    """
    if keyisset("Records", message) and isinstance(message["Records"], list):
        records = message["Records"]
        for record in records:
            return {
                "bucket_name": record["s3"]["bucket"]["name"],
                "object": record["s3"]["object"]["key"],
                "size": int(record["s3"]["object"]["size"]),
            }


def change_message_visibility(
    file_info: dict, queue_url: str, message_handle: str, session: Session
) -> None:
    """
    Based on the file size and transfer rate, updates the visibility timeout in order to ensure we get
    enough time to complete the file transfer

    :param file_info:
    :param queue_url:
    :param message_handle:
    """
    client = session.client("sqs")
    size = set_else_none("size", file_info, alt_value=0)
    if not size:
        return
    wait_time = int((size / MB) / SPEED)
    if not wait_time:
        return
    transfer_margin = int(environ.get("TRANSFER_MARGIN_PERCENT", 15))
    wait_time += transfer_margin / 100 * wait_time
    if wait_time < DEFAULT_HIDE_TIMEOUT:
        try:
            LOG.info(
                f"Message is {size}B, transfer at speed {SPEED}, "
                f"therefore waiting {wait_time} with {transfer_margin}% margin"
            )
            client.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=message_handle,
                VisibilityTimeout=int(wait_time),
            )
        except ClientError as error:
            try:
                LOG.warning(
                    f"Failed to Change message visibility, because {error.response['Message']}"
                )
            except KeyError:
                LOG.warning(f"Failed to Change message visibility")


def get_queue_name(queue_url: str, session: Session = None) -> str:
    session = get_session(session)
    client = session.client("sqs")
    try:
        queue_arn = client.get_queue_attributes(
            QueueUrl=queue_url, AttributeNames=["QueueArn"]
        )["Attributes"]["QueueArn"]
        queue_name = SQS_QUEUE_ARN_RE.match(queue_arn).group("id")
    except ClientError as error:
        LOG.exception(error)
        LOG.error("Failed to get QueueArn from attributes. Deducing QueueName from URL")
        queue_name = re.match(r"\d{12}/(?P<queue_name>\S+$)", queue_url).group(
            "queue_name"
        )
    return queue_name


@metric_scope
def transfer_files_to_sftp(
    sftp_info: dict, queue_url: str, messages: list, session: Session, metrics
):
    from . import SFTP_HOST, SFTP_PORT, SFTP_USER

    sftp_connection = get_sftp_connection(sftp_info)
    queue_name = get_queue_name(queue_url, session)
    metrics.set_namespace("S3ToSFTP")
    now = dt.utcnow()
    total_files_size = 0
    files_processed = 0
    files_failed = 0
    with sftp_connection as sftp_fd:
        for message in messages:
            file_info = get_file_information(loads(message["Body"]))
            LOG.debug(file_info)
            if not file_info:
                continue
            LOG.info(f"Processing file {file_info['object']}")
            size = set_else_none("size", file_info, alt_value=0)
            if size:
                total_files_size += int(file_info["size"])
                change_message_visibility(
                    file_info, queue_url, message["ReceiptHandle"], session
                )
            try:
                push_pull_file(file_info, queue_url, message, session, sftp_fd)
            except Exception as error:
                files_failed += 1
                LOG.exception(error)
            finally:
                files_processed += 1
    then = dt.utcnow()
    diff = (then - now).total_seconds()
    metrics.put_metric("TotalFilesSize", float(total_files_size), "Bytes")
    metrics.put_metric("TransferRate", float(total_files_size / diff), "Bytes/Second")
    metrics.put_metric("FilesProcessed", float(files_processed), "None")
    metrics.put_metric("FilesFailed", float(files_failed), "None")
    metrics.put_dimensions({"Queue": queue_name})
    metrics.set_property(
        "SftpServer",
        {
            SFTP_HOST: sftp_info[SFTP_HOST],
            SFTP_USER: sftp_info[SFTP_USER],
            SFTP_PORT: sftp_info[SFTP_PORT],
        },
    )


def listen_for_jobs(queue_url: str, sftp_info, session: Session = None):
    """
    Function to listen to the jobs coming through AWS SQS queue and dispatching to execute.
    """
    session = get_session(session)
    client = session.client("sqs")
    LOG.info(f"Pulling messages from {queue_url}")
    while FOREVER:
        messages_r = client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=int(environ.get("SQS_MAX_MESSAGES", 10)),
            VisibilityTimeout=20,
        )
        messages = set_else_none("Messages", messages_r, alt_value=[])
        if messages:
            transfer_files_to_sftp(sftp_info, queue_url, messages, session)
