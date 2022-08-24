# duckietown_project

## Running with docker
- If run before, remove all files in `fifos` folder. e.g. `rm ./fifos/*`
- *Optional* Run `docker compose build` to recreate the image
- Run `docker compose up` (or `docker-compose up` if on older version) (`--force-recreate` to force creating new containers from the images if ego doesn't behave)

## Running natively
Dependencies require python 3.9, for ubuntu this requires the deadsnakes ppa:

```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.9-distutils
```

Package management with [poetry](https://python-poetry.org/). See Dockerfile for required OS dependencies. Example command `poetry run python -m duckietown_project automated --scoring-root ./scoring_root --scenario-path ./generated.yaml`. See `./duckietown_project/__main__.py` for available commands.