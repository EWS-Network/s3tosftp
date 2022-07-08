============
S3 to SFTP
============

Simple application that listens on a SQS Queue and transfers files from S3
to a SFTP Server.

The authentication can be done via username/password or username/private key.
Private key should be stored "as-is" in AWS Secrets Manager.

The container must have an environment variable ``SFTP_TARGET``, that follows the format below.
You can set an enviroment variable for each of the below, using the property name as environment variable name.

The value in environment variables overrides the values otherwise set.

Build
======

You can build the docker image with the following commands

.. code-block::

    docker build . -t s3-to-sftp

Alternatively, using docker-compose

.. code-block::

    docker-compose build

Deploy with ECS Compose-X
===========================

We highly recommend that you store the value for ``SFTP_TARGET`` in AWS Secrets Manager.

Install compose-x
------------------

.. code-block::

    python3 -m venv compose-x
    source compose-x/bin/activate
    pip install pip -U; pip install ecs-composex

Deploy
--------

You might need to update the settings in the aws.yaml file to meet your environment settings.
On start, the connection to the SFTP server is not established, so the deployment won't fail
because of that. However, it requires to have the ``SFTP_TARGET`` details setup in before it
starts listening on the SQS queue jobs.

.. code-block::

    ecs-compose-x up -d templates -f docker-compose.yaml -f aws.yaml -p s3-to-sftp-testing

Monitoring
-----------

In AWS CloudWatch, you will see new metrics in a Namespace called ``S3ToSFTP`` which is going to have
some metrics, here for statistics.

These metrics are published using `EMF`_.

.. _EMF: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html


SFTP_TARGET format
===================

.. code-block::

    {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "id": "sftp-secret-format",
        "type": "object",
        "additionalProperties": false,
        "properties": {
            "host": {
                "type": "string",
                "format": "idn-hostname"
            },
            "port": {
                "type": "number",
                "minimum": 1,
                "maximum": 65535
            },
            "username": {
                "type": "string"
            },
            "password": {
                "type": "string"
            },
            "default_path": {
                "type": "string"
            },
            "private_key": {
                "type": "string"
            },
            "private_key_pass": {
                "type": "string"
            }
        },
        "required": [
            "host",
            "port",
            "username"
        ]
    }
