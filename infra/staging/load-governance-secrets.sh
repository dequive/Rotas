#!/bin/sh
set -eu

load_secret() {
  name="$1"
  file_variable="${name}_FILE"
  file_path="$(printenv "${file_variable}" 2>/dev/null || true)"
  if [ -n "${file_path}" ]; then
    if [ ! -r "${file_path}" ]; then
      echo "Secret file for ${name} is not readable." >&2
      exit 78
    fi
    value="$(cat "${file_path}")"
    if [ -z "${value}" ]; then
      echo "Secret file for ${name} is empty." >&2
      exit 78
    fi
    export "${name}=${value}"
  fi
}

for secret_name in \
  GOVERNANCE_DATABASE_URL \
  JWT_SECRET_KEY \
  PLATFORM_ADMIN_KEY
do
  load_secret "${secret_name}"
done

exec "$@"
