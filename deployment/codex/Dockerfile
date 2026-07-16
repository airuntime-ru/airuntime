# Long-lived runner container for the OpenAI Codex CLI.
#
# The `worker` service (the only backend process with Docker socket access - see
# backend/src/services/docker_control_queue.py) execs into this container for every coding-agent
# turn via `docker exec`, instead of the backend making raw HTTP calls to a model provider. This
# container itself gets the project-files volume and the Docker socket, so Codex can read/write
# a project's files and build/run Docker images directly through its own shell access.
#
# Auth: no key is baked into the image - the worker passes OPENAI_API_KEY per `docker exec` call
# (resolved the same way the old HTTP path did, via system_settings/config), so admin key
# rotation doesn't require restarting this container.
FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        docker.io \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @openai/codex

WORKDIR /data/airruntime-projects

# No fixed entrypoint command to run - this container just needs to stay up so `worker` can
# `docker exec` into it on demand.
CMD ["tail", "-f", "/dev/null"]
