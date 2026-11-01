#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
read -r -p 'Is this the remote side or main side? [remote/main]: ' side
case "$side" in remote|main) ;; *) echo 'Please enter remote or main.' >&2; exit 1;; esac
umask 077
printf 'PETER_SIDE=%s\nCOMPOSE_PROFILES=%s\nROS_DOMAIN_ID=0\n' "$side" "$side" > "$ROOT/.env"
printf 'Configured %s side in %s/.env\n' "$side" "$ROOT"
