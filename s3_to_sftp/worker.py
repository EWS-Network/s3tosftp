# Copyright (C) 2020-2022 John Mille <john@ews-network.net>

"""
Module to handle the queue jobs and execute the SFTP transfer.

"""
import signal
from time import sleep

from aws_embedded_metrics import metric_scope
from boto3.session import Session
from compose_x_common.aws import get_session
from compose_x_common.aws.sqs import SQS_QUEUE_ARN_RE
from compose_x_common.compose_x_common import set_else_none

from s3_to_sftp.transfer_handler import get_sftp_connection

from .logger import LOG
from .transfer_file import TransferFile

FOREVER = 42


class Worker:
    def __init__(self, queue_url: str, sftp_info: dict, session: Session = None):
        self.session = get_session(session)
        self.queue_url = queue_url
        self._sftp_info = sftp_info
        self.messages: list = []
        self.keep_running = FOREVER
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    @property
    def queue(self):
        return self.session.resource("sqs").Queue(self.queue_url)

    @property
    def queue_arn(self) -> str:
        return self.queue.attributes["QueueArn"]

    @property
    def queue_name(self) -> str:
        return SQS_QUEUE_ARN_RE.match(self.queue_arn).group("id")

    @property
    def sftp_info(self) -> dict:
        return self._sftp_info

    @property
    def sftp_host(self) -> str:
        return self.sftp_info["host"]

    @property
    def sftp_username(self) -> str:
        return self.sftp_info["username"]

    @property
    def sftp_port(self) -> int:
        return self.sftp_info["port"]

    @staticmethod
    def get_queue_url_from_name(queue_name: str, session: Session = None) -> str:
        session = get_session(session)
        return session.client("sqs").get_queue_url(QueueName=queue_name)["QueueUrl"]

    def run(self, **kwargs) -> None:
        global sftp_connection
        sftp_connection = get_sftp_connection(self.sftp_info)
        with sftp_connection as sftp_fd:
            LOG.info("Connected to SFTP")
            LOG.info(f"Waiting on messages from {self.queue_url}")
            while self.keep_running:
                try:
                    LOG.info(f"{self.queue_name} - Waiting for files_transfers")
                    queue_messages = self.queue.receive_messages(
                        MaxNumberOfMessages=min(
                            [
                                int(
                                    set_else_none(
                                        "max_messages_batch", kwargs, alt_value=2
                                    )
                                ),
                                10,
                            ]
                        ),
                        VisibilityTimeout=20,
                    )
                    if queue_messages:
                        files_transfers = [TransferFile(msg) for msg in queue_messages]
                        LOG.info(
                            f"{self.queue_name} - Processing S3 files to transfer from SQS files_transfers"
                        )
                        self.transfer_files_to_sftp(sftp_fd, files_transfers, **kwargs)
                except Exception as error:
                    LOG.error("Failed to retrieve jobs from queue")
                    LOG.exception(error)
                sleep(1)

    @metric_scope
    def transfer_files_to_sftp(
        self, sftp_fd, files_transfers: list[TransferFile], metrics, **kwargs
    ):
        from . import SFTP_HOST, SFTP_PORT, SFTP_USER

        metrics.set_namespace("S3ToSFTP")
        total_files_size = 0
        files_processed = 0
        files_failed = 0
        elapsed_time = 0
        transfer_rate = kwargs.pop("transfer_rate", 1)
        error_margin = kwargs.pop("error_margin", 15)

        for file_to_transfer in files_transfers:
            if not self.keep_running:
                LOG.warning("Worker instructed to stop")
                break

            LOG.info(f"Processing file {file_to_transfer.file_name}")
            transfer_time_estimate = file_to_transfer.file_transfer_duration_estimate(
                transfer_margin=error_margin, speed_in_mbytes=transfer_rate
            )
            LOG.info(
                f"Estimated transfer time for {file_to_transfer.file_name}: {transfer_time_estimate}s"
            )
            file_to_transfer.message.change_visibility(
                VisibilityTimeout=transfer_time_estimate
            )
            file_to_transfer.set_file_handler(self.sftp_info, self.session)
            try:
                file_to_transfer.file_handler.pull(file_to_transfer)
                file_to_transfer.file_handler.push(sftp_fd, file_to_transfer)
                if file_to_transfer.file_transfer_duration > 0:
                    elapsed_time += file_to_transfer.file_transfer_duration
                    total_files_size += file_to_transfer.file_size
                    file_to_transfer.message.delete()
                    LOG.info(
                        f"{file_to_transfer.file_name} - Transfer complete in: "
                        f"{file_to_transfer.file_transfer_duration}"
                        f" - Approximate transfer rate: {file_to_transfer.file_transfer_speed}MB/s"
                    )
            except Exception as error:
                LOG.error("Failed to push file to SFTP")
                LOG.exception(error)
                files_failed += 1
            finally:
                files_processed += 1

        metrics.put_metric("TotalFilesSize", float(total_files_size), "Bytes")
        if elapsed_time and elapsed_time > 0:
            metrics.put_metric(
                "TransferRate", float(total_files_size / elapsed_time), "Bytes/Second"
            )
        metrics.put_metric("FilesProcessed", float(files_processed), "None")
        metrics.put_metric("FilesFailed", float(files_failed), "None")
        metrics.put_dimensions({"Queue": self.queue_name})
        metrics.set_property(
            "SftpServer",
            {
                SFTP_HOST: self.sftp_host,
                SFTP_USER: self.sftp_username,
                SFTP_PORT: self.sftp_port,
            },
        )

    def exit_gracefully(self, signum: int, frame):
        """
        Handles gracious shutdown
        """
        LOG.warning(f"Received signal {signum}. Stopping process.")
        LOG.info("Stopping Worker")
        self.keep_running = 0
        sftp_connection.close()
        exit(0)
