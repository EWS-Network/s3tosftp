ARG PYTHON_VERSION=3.10
ARG BASE_IMAGE=public.ecr.aws/docker/library/python:3.10.13-slim
FROM $BASE_IMAGE as builder

WORKDIR /temp
RUN pip install pip poetry -U
COPY . /temp
RUN poetry build


FROM $BASE_IMAGE
WORKDIR /app
#RUN yum upgrade -y; yum install -y shadow-utils ;\
#    groupadd -r app -g 1042 && \
#    useradd -u 1042 -r -g app -M -d /app -s /sbin/nologin -c "App user" app && chown -R app:app /app;\
#    yum erase shadow-utils -y
#USER app
COPY --from=builder /temp/dist/*.whl .
COPY ["LICENSE", "README.rst", "/app/"]

ENV PATH=/app:/app/.local/bin:$PATH
RUN pip install --no-cache-dir pip -U; pip install --no-cache-dir *whl --user
COPY --chown=app:app entrypoint.py entrypoint.py
COPY --chown=app:app entrypoint.sh entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
