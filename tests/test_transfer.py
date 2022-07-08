#  -*- coding: utf-8 -*-

import sys
from os import path, environ
import pytest
from json import dumps, loads

here = path.abspath(path.dirname(__file__))
there = path.abspath(f"{here}/..")
sys.path.insert(0, there)

from s3_to_sftp import get_queue_url, get_sftp_info


@pytest.fixture()
def test_target(monkeypatch):
    """
    Function to import valid target
    """
    monkeypatch.setenv(
        "SFTP_TARGET",
        dumps(
            {
                "host": "localhost",
                "port": 2200,
                "username": "foo",
                "password": "pass",
                "path": "upload",
            }
        ),
    )


@pytest.fixture()
def test_invalid_target(monkeypatch):
    """
    Function to validate input
    """
    monkeypatch.setenv(
        "SFTP_TARGET",
        dumps(
            {
                "host": "localhost",
                "port": "2200",
                "username": "foo",
                "password": "pass",
                "path": "upload",
            }
        ),
    )


def test_valid_sftp_input(test_target):
    """
    Function checking the validation process works.
    """
    sftp_info = get_sftp_info()


def test_invalid_sftp_input(test_invalid_target):
    """
    Function checking the validation process works.
    """
    with pytest.raises(TypeError):
        sftp_info = get_sftp_info()
