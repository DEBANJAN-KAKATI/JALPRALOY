# Image for the data pipelines + scheduler (heavy geo/ML stack via conda).
#   docker compose --profile live up -d scheduler
FROM condaforge/miniforge3:latest

WORKDIR /app
COPY environment.yml pyproject.toml ./
RUN mamba env create -f environment.yml && mamba clean -afy
SHELL ["conda", "run", "--no-capture-output", "-n", "jalproloi", "/bin/bash", "-c"]

COPY ml ./ml
COPY pipelines ./pipelines
RUN pip install --no-deps -e .

ENV JALPROLOI_DATA=/data
CMD ["conda", "run", "--no-capture-output", "-n", "jalproloi", "python", "-m", "pipelines.scheduler"]
