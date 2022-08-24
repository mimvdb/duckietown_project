FROM python:3.9-bullseye as base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

WORKDIR /app

FROM base as builder

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.1.14

#RUN apk add --no-cache gcc g++ libffi-dev musl-dev
RUN pip install "poetry==$POETRY_VERSION"
RUN python -m venv /venv

COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt --without-hashes | /venv/bin/pip install -r /dev/stdin

COPY . .
RUN poetry build && /venv/bin/pip install dist/*.whl

FROM base as final

#RUN apk add --no-cache libffi libpq
# opencv-python dependencies (cannot be opencv-python-headless as it is imported by other libraries)
# freeglut3-dev for pyglet, mencoder mplayer for procgraph-z6
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6 freeglut3-dev mencoder mplayer -y
COPY --from=builder /venv /venv
COPY --from=builder /app/generated.yaml /app/generated.yaml
RUN mkdir scoring_root
CMD ["/venv/bin/python", "-m", "duckietown_project", "automated", "--scoring-root", "/app/scoring_root", "--scenario-path", "/app/generated.yaml"]