S3 to SFTP
===========

This repository stores the application worker, which will be pulling files out of S3 and sending them over SFTP
to a designated target.

The target information will be stored in AWS Secrets Manager and the value will be published to the microservice
directly via AWS ECS.

The name of the environment variable for the SFTP information must be: **SFTP_TARGET**


SFTP Secret format
-------------------

.. code-block:: json

    {
        "dstHost": "sftp.target.host",
        "dstPort": 22,
        "dstUsername": "username",
        "dstPassword": "password",
        "dstPath": "/path",
    }
