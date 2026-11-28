FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ARG VALIDATOR_ARTIFACT
LABEL io.detectbridge.p15b.validator.artifact=$VALIDATOR_ARTIFACT
LABEL io.detectbridge.p15b.validator.base="python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
COPY artifact.tar /opt/validator/artifact.tar
WORKDIR /opt/validator
RUN python -c "import tarfile; tarfile.open('artifact.tar').extractall('.', filter='data')" \
    && chmod 444 artifact.tar \
    && python -m pip install --disable-pip-version-check --no-cache-dir --no-compile --require-hashes --only-binary=:all: -r deploy/lifecycle-validator/requirements.txt
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 9999:9999
ENTRYPOINT ["python", "tools/lifecycle_worker_validator.py"]
