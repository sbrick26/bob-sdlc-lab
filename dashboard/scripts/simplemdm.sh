#!/bin/bash

set -euo pipefail

API_BASE="${SIMPLEMDM_API_BASE:-https://a.simplemdm.com/api/v1}"
KEYCHAIN_SERVICE="${SIMPLEMDM_KEYCHAIN_SERVICE:-bob-governance-simplemdm-api}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CANARY_PROFILE="${REPO_DIR}/profiles/bob-enforced-hooks-canary.mobileconfig"
CANARY_NAME="Bob Enforced Hooks Canary"
GOVERNANCE_PROFILE="${REPO_DIR}/tmp/bob-governance.mobileconfig"
GOVERNANCE_NAME="Bob Governance"

for dependency in curl jq; do
  command -v "${dependency}" >/dev/null || {
    echo "Missing required command: ${dependency}" >&2
    exit 1
  }
done

load_api_key() {
  if [[ -n "${SIMPLEMDM_API_KEY:-}" ]]; then
    printf '%s' "${SIMPLEMDM_API_KEY}"
    return
  fi

  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Set SIMPLEMDM_API_KEY when macOS Keychain is unavailable." >&2
    exit 1
  fi

  security find-generic-password \
    -a "${USER}" \
    -s "${KEYCHAIN_SERVICE}" \
    -w 2>/dev/null || {
      echo "SimpleMDM API key not found in macOS Keychain service ${KEYCHAIN_SERVICE}." >&2
      exit 1
    }
}

API_KEY_VALUE="$(load_api_key)"
trap 'unset API_KEY_VALUE' EXIT

api_get() {
  curl --fail-with-body --silent --show-error \
    --user "${API_KEY_VALUE}:" \
    "${API_BASE}$1"
}

find_profile_id() {
  api_get "/custom_configuration_profiles?limit=100" |
    jq -er --arg name "${CANARY_NAME}" \
      '[.data[] | select(.attributes.name == $name)] | if length == 1 then .[0].id else error("expected exactly one matching canary profile") end'
}

find_governance_profile_id() {
  api_get "/custom_configuration_profiles?limit=100" |
    jq -er --arg governance "${GOVERNANCE_NAME}" --arg canary "${CANARY_NAME}" '
      [.data[] | select(.attributes.name == $governance or .attributes.name == $canary)] |
      if length == 1 then .[0].id else error("expected exactly one governance/canary profile") end'
}

find_group_id() {
  local group_name="$1"
  api_get "/assignment_groups?limit=100" |
    jq -er --arg name "${group_name}" \
      '[.data[] | select(.attributes.name == $name)] | if length == 1 then .[0].id else error("expected exactly one matching assignment group") end'
}

update_canary() {
  local group_name="${1:-Default}"
  local profile_id group_id update_status sync_status

  [[ -f "${CANARY_PROFILE}" ]] || {
    echo "Canary profile is missing: ${CANARY_PROFILE}" >&2
    exit 1
  }
  /usr/bin/plutil -lint "${CANARY_PROFILE}" >/dev/null

  profile_id="$(find_profile_id)"
  group_id="$(find_group_id "${group_name}")"

  update_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --user "${API_KEY_VALUE}:" \
    --request PATCH \
    --form "mobileconfig=@${CANARY_PROFILE}" \
    --form 'declarative=false' \
    --form 'user_scope=false' \
    --form 'allowed_platforms[]=macos' \
    "${API_BASE}/custom_configuration_profiles/${profile_id}")"
  [[ "${update_status}" == "200" ]] || {
    echo "Profile update failed with HTTP ${update_status}." >&2
    exit 1
  }

  sync_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --user "${API_KEY_VALUE}:" \
    --request POST \
    "${API_BASE}/assignment_groups/${group_id}/sync_profiles")"
  [[ "${sync_status}" == "204" ]] || {
    echo "Group sync failed with HTTP ${sync_status}. It may be rate-limited for 30 seconds." >&2
    exit 1
  }

  printf 'Updated profile %s and synced assignment group %s (%s).\n' \
    "${profile_id}" "${group_id}" "${group_name}"
}

update_governance() {
  local group_name="${1:-Default}"
  local profile_id group_id update_status sync_status

  [[ -f "${GOVERNANCE_PROFILE}" ]] || {
    echo "Governance profile is missing; run scripts/generate-governance-profile.py first." >&2
    exit 1
  }
  /usr/bin/plutil -lint "${GOVERNANCE_PROFILE}" >/dev/null

  profile_id="$(find_governance_profile_id)"
  group_id="$(find_group_id "${group_name}")"

  update_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --user "${API_KEY_VALUE}:" \
    --request PATCH \
    --form "name=${GOVERNANCE_NAME}" \
    --form "mobileconfig=@${GOVERNANCE_PROFILE}" \
    --form 'declarative=false' \
    --form 'user_scope=false' \
    --form 'allowed_platforms[]=macos' \
    "${API_BASE}/custom_configuration_profiles/${profile_id}")"
  [[ "${update_status}" == "200" ]] || {
    echo "Governance profile update failed with HTTP ${update_status}." >&2
    exit 1
  }

  sync_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --user "${API_KEY_VALUE}:" \
    --request POST \
    "${API_BASE}/assignment_groups/${group_id}/sync_profiles")"
  [[ "${sync_status}" == "204" ]] || {
    echo "Group sync failed with HTTP ${sync_status}. It may be rate-limited for 30 seconds." >&2
    exit 1
  }

  printf 'Updated Governance profile %s and synced assignment group %s (%s).\n' \
    "${profile_id}" "${group_id}" "${group_name}"
}

usage() {
  cat <<'EOF'
Usage: scripts/simplemdm.sh COMMAND [ARG]

Read-only commands:
  account                 Verify API access and print the account name.
  devices                 List device IDs, names, and enrollment status.
  profiles                List custom profile IDs and deployment state.
  groups                  List assignment-group IDs and names.
  device-profiles ID      List profiles and installation status for a device.

Managed canary command:
  update-canary [GROUP]   Upload the local canary with declarative=false and
                          immediately sync GROUP (default: Default).

Managed Governance command:
  update-governance [GROUP]
                          Replace the assigned canary with the generated
                          five-event Governance profile and sync GROUP.

The API key is read from macOS Keychain service
"bob-governance-simplemdm-api" for the current user. SIMPLEMDM_API_KEY is
accepted only as an explicit environment override for CI.
EOF
}

case "${1:-}" in
  account)
    api_get /account | jq -r '.data.attributes.name'
    ;;
  devices)
    api_get '/devices?limit=100' |
      jq -r '.data[] | [.id, .attributes.name, .attributes.status] | @tsv'
    ;;
  profiles)
    api_get '/custom_configuration_profiles?limit=100' |
      jq -r '.data[] | [.id, .attributes.name, .attributes.declarative, .attributes.group_count, .attributes.device_count] | @tsv'
    ;;
  groups)
    api_get '/assignment_groups?limit=100' |
      jq -r '.data[] | [.id, .attributes.name, .attributes.group_type] | @tsv'
    ;;
  device-profiles)
    [[ -n "${2:-}" ]] || { usage >&2; exit 2; }
    api_get "/devices/$2/profiles" |
      jq -r '.data[] | [.id, .attributes.name, .attributes.declarative, .attributes.user_scope] | @tsv'
    ;;
  update-canary)
    update_canary "${2:-Default}"
    ;;
  update-governance)
    update_governance "${2:-Default}"
    ;;
  -h|--help|help|'')
    usage
    ;;
  *)
    echo "Unknown command: $1" >&2
    usage >&2
    exit 2
    ;;
esac
