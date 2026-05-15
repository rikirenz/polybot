# Polybot Docker Quickstart

This project runs the Polymarket MVP pipeline in Docker using Docker Compose.

## Prerequisites

- Docker
- Docker Compose plugin (`docker compose` command)

## Build and Run

From the project root:

```bash
docker compose -f polymarket_mvp/docker-compose.yml up --build
```

This will:
- Build the image from `polymarket_mvp/Dockerfile`
- Start the `strategy` service
- Run the pipeline end-to-end

## Run in Background

```bash
docker compose -f polymarket_mvp/docker-compose.yml up --build -d
```

## View Logs

```bash
docker compose -f polymarket_mvp/docker-compose.yml logs -f
```

## Stop Containers

```bash
docker compose -f polymarket_mvp/docker-compose.yml down
```

## Output Files

Generated artifacts (for example, the dashboard image) are written to:

- `polymarket_mvp/output/`
