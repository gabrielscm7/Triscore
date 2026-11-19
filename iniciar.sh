#!/usr/bin/env bash
set -u
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$APP_DIR/TriScore.sh" "$@"
