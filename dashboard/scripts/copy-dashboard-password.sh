#!/bin/bash

set -euo pipefail

SERVICE="${DASHBOARD_KEYCHAIN_SERVICE:-bob-governance-dashboard-password}"
PASSWORD="$(security find-generic-password -a "${USER}" -s "${SERVICE}" -w)"
trap 'unset PASSWORD' EXIT
printf '%s' "${PASSWORD}" | pbcopy
printf 'Governance dashboard password copied to the clipboard. Username: governance\n'
