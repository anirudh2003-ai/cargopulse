FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /opt/cargopulse

COPY requirements.txt requirements-airflow.txt ./

RUN pip install --upgrade pip \
    && pip install \
        -r requirements.txt \
        -r requirements-airflow.txt

COPY . .

RUN useradd \
    --create-home \
    --uid 10001 \
    cargopulse \
    && chown -R cargopulse:0 /opt/cargopulse \
    && chmod -R g=u /opt/cargopulse

USER cargopulse

ENTRYPOINT ["python", "-m", "pipeline"]
CMD ["--help"]
