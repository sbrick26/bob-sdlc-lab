#!/bin/sh
# lab-check.sh - headless rehearsal of the Bob SDLC lab. See tools/acp/lanes.md.
exec python3 "$(dirname "$0")/lab-check.py" "$@"
