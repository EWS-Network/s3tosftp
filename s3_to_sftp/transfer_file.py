# Copyright (C) 2020-2022 John Mille <john@ews-network.net>

import json
from tempfile import TemporaryDirectory

from boto3 import Session
from compose_x_common.compose_x_common import set_else_none

from s3_to_sftp import LOG
from s3_to_sftp.transfer_handler import FileHandler

MB: int = 1024**2


class TransferFile:
    def __init__(self, message):
        self.message = message
        self.file_info = self.get_file_information()
        self.file_name = self.file_info["object"]
        self.file_size = self.file_info["size"]
        self.s3_bucket = self.file_info["bucket_name"]
        self.file_transfer_start_time = None
        self.file_transfer_end_time = None
        self.file_transfer_status = "PENDING"
        self.temp_dir = TemporaryDirectory()
        self.file_handler = None

    @property
    def file_transfer_duration(self) -> float:
        if self.file_transfer_start_time and self.file_transfer_end_time:
            return (
                self.file_transfer_end_time - self.file_transfer_start_time
            ).total_seconds()
        return -1

    @property
    def file_transfer_speed(self) -> int:
        if self.file_transfer_duration > 0:
            return int((self.file_size / MB) / self.file_transfer_duration)
        return -1

    def set_file_handler(self, sftp_info: dict, session: Session):
        self.file_handler = FileHandler(
            self.s3_bucket,
            self.file_name,
            self.temp_dir,
            sftp_info,
            session=session,
        )

    def file_transfer_duration_estimate(
        self,
        double_for_s3: bool = True,
        penalty_factor: int = 1,
        transfer_margin: int = 15,
        speed_in_mbytes: int = 1,
    ) -> int:
        LOG.debug(
            f"{self.file_name} - {self.file_size} - 1MB={MB}B - Rate: {speed_in_mbytes}MB/s"
        )
        wait_time = int((self.file_size / MB) / speed_in_mbytes)
        LOG.debug(f"Initial wait_time: {wait_time}")
        if not wait_time:
            wait_time = 1
        transfer_margin = min([transfer_margin, 100])
        wait_time += transfer_margin / (100 * wait_time)
        estimated_duration = (
            int(wait_time * penalty_factor)
            if not double_for_s3
            else int((wait_time * penalty_factor) * 2)
        )
        LOG.debug(estimated_duration)
        return estimated_duration if estimated_duration > 20 else 20

    def get_file_information(self) -> dict:
        """
        Function to return the file information from the event
        """
        records = set_else_none("Records", json.loads(self.message.body), alt_value=[])
        if not isinstance(records, list):
            raise TypeError("Records must be a list. Got", type(records))
        for record in records:
            return {
                "bucket_name": record["s3"]["bucket"]["name"],
                "object": record["s3"]["object"]["key"],
                "size": int(record["s3"]["object"]["size"]),
            }
