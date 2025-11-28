#!/usr/bin/env bash
set -euo pipefail

if command -v apt-get >/dev/null 2>&1; then
  INSTALLER="apt-get"
else
  echo "apt-get not available; skipping chrome dependency install" >&2
  exit 0
fi

if command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  SUDO=""
fi

DISABLED_SOURCE=""
if [ -f /etc/apt/sources.list.d/mise.list ]; then
  DISABLED_SOURCE="/etc/apt/sources.list.d/mise.list"
  TEMP_DISABLED="/tmp/mise.list.disabled"
  mv "$DISABLED_SOURCE" "$TEMP_DISABLED"
  trap 'mv "$TEMP_DISABLED" "$DISABLED_SOURCE"' EXIT
fi

if command -v timeout >/dev/null 2>&1; then
  UPDATE_CMD=(timeout 30s $SUDO $INSTALLER update -y)
else
  UPDATE_CMD=($SUDO $INSTALLER update -y)
fi

"${UPDATE_CMD[@]}" || echo "apt-get update reported an error; continuing with available package lists" >&2

add_dep() {
  local primary="$1"
  local fallback="${2:-}"

  if apt-cache show "$primary" >/dev/null 2>&1; then
    DEPS+=("$primary")
    return
  fi

  if [ -n "$fallback" ] && apt-cache show "$fallback" >/dev/null 2>&1; then
    DEPS+=("$fallback")
  fi
}

DEPS=()
add_dep libatk1.0-0t64 libatk-1.0-0
add_dep libatk-bridge2.0-0t64 libatk-bridge2.0-0
add_dep libnss3
add_dep libxss1
add_dep libxcomposite1
add_dep libxrandr2
add_dep libxdamage1
add_dep libxfixes3
add_dep libxi6
add_dep libgbm1
add_dep libcups2t64 libcups2
add_dep libgtk-3-0
add_dep libgdk-pixbuf-2.0-0
add_dep libasound2t64 libasound2
add_dep libpangocairo-1.0-0
add_dep libpango-1.0-0
add_dep libcairo2
add_dep libdrm2
add_dep libxkbcommon0
add_dep xvfb

if [ ${#DEPS[@]} -eq 0 ]; then
  echo "No chrome dependencies were resolved; skipping installation" >&2
  exit 0
fi

echo "Installing chrome dependencies: ${DEPS[*]}" >&2
$SUDO $INSTALLER install -y "${DEPS[@]}"
