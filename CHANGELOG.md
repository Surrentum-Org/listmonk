# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Fix the nightly workflow failing at startup: the org only allows selected actions, so the Docker (qemu, buildx, login) and GoReleaser actions are replaced by plain `run` steps.
- Pin every action in the nightly workflow to a commit SHA; the org requires SHA-pinned actions, so the scheduled run failed at startup.
- Pin actions/stale to a commit SHA in the close-stale-issues-and-prs workflow; the org requires SHA-pinned actions, so the scheduled run failed at startup.

### Removed

- Removed upstream's nightly and tag release workflows (GitHub release assets nobody here uses); ci-ok now refuses workflows that store files on GitHub.

[Unreleased]: https://github.com/Surrentum-Org/listmonk/commits/main
