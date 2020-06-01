#  -*- coding: utf-8 -*-

"""
Module to handle the queue jobs and execute the SFTP transfer.

"""

import boto3
from json import loads
from s3sftp import LOG, keyisset
from s3sftp.transfer import FileHandler

FOREVER = 42


def validate_attributes(message):
    """
    Function to validate SQS message attributes.

    :param message: sqs message
    :return: True/False
    :rtype: bool
    """
    return True


def get_file_information(message):
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
            }
    return


def listen_for_jobs(queue_name, sftp_info, session=None, client=None):
    """
    Function to listen to the jobs coming through AWS SQS queue and dispatching to execute.

    :param str queue_name: Name of the queue
    :param dict sftp_info: Information about the SFTP target
    :param boto3.session.Session session: Boto3 session to override client.
    :param boto3.client client: Client to use for SQS queries.
    """
    if not client:
        if session:
            client = session.client("sqs")
        else:
            client = boto3.client("sqs")
    try:
        queue_url = client.get_queue_url(QueueName=queue_name)["QueueUrl"]
    except Exception as error:
        LOG.debug(f"QueueName is {queue_name}")
        LOG.error(error)
        exit(1)
    while FOREVER:
        messages_r = client.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=2, VisibilityTimeout=20
        )
        messages = messages_r["Messages"] if keyisset("Messages", messages_r) else []
        for message in messages:
            validate_attributes(message)
            file_info = get_file_information(loads(message["Body"]))
            LOG.debug(file_info)
            if not file_info:
                continue
            try:
                file = FileHandler(
                    sftp_info,
                    file_info["bucket_name"],
                    file_info["object"],
                    session=session,
                )
                file.pull()
                file.push()
                file.clean()
                client.delete_message(
                    QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"]
                )
            except Exception as error:
                LOG.error(error)
                pass
