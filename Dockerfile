FROM python:3.8-slim
RUN groupadd -r app -g 1042 && useradd -u 1042 -r -g app -m -d /app -s /sbin/nologin -c "App user" app && chmod 755 /app
USER app
ENV PATH=$PATH:/app/.local/bin
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt --user
COPY s3sftp s3sftp
COPY transfer.py transfer.py
CMD ["python", "transfer.py"]
