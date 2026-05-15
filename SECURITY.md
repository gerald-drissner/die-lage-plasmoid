# Security Policy

## Supported versions

This is a personal KDE Plasma widget. The current public release line is supported on a best-effort basis.

## Reporting a vulnerability

Please open a private security advisory on GitHub if available, or contact the maintainer via the project website.

## Local helper service

Die Lage uses a local helper service bound to `127.0.0.1:8765`. It is intended for local access by the Plasma widget. The service does not listen on external interfaces.

Do not expose the helper port to a network. That would be a creative way to invent problems nobody asked for.
