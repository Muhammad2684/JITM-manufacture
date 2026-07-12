#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
xdg-open http://localhost:5000 2>/dev/null
exec ./JITM "$@"