ARG PYTHON_VERSION=3.9
ARG BASE_IMAGE=public.ecr.aws/ews-network/python:${PYTHON_VERSION}
FROM $BASE_IMAGE as builder

WORKDIR /temp
COPY pyproject.toml /temp/pyproject.toml
COPY poetry.lock /temp/poetry.lock
RUN pip install pip -U; pip install poetry
RUN poetry export --without-hashes -o /temp/requirements.txt


FROM $BASE_IMAGE
WORKDIR /app
RUN yum upgrade -y; yum install -y shadow-utils ;\
    groupadd -r app -g 1042 && \
    useradd -u 1042 -r -g app -M -d /app -s /sbin/nologin -c "App user" app && chown -R app:app /app;\
    yum erase shadow-utils -y
USER app
COPY --from=builder /temp/requirements.txt /app/requirements.txt

ENV PATH=/app:/app/.local/bin:$PATH
RUN pip install --no-cache-dir -r requirements.txt --user
COPY --chown=app:app s3_to_sftp s3_to_sftp
COPY --chown=app:app entrypoint.py entrypoint.py
COPY --chown=app:app entrypoint.sh entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "entrypoint.py"]
