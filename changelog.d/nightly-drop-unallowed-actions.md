Fix the nightly workflow failing at startup: the org only allows selected actions, so the Docker (qemu, buildx, login) and GoReleaser actions are replaced by plain `run` steps.
