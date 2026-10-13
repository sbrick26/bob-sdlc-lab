#!/bin/bash

set -euo pipefail

PROJECT="${CE_PROJECT:?Set CE_PROJECT to the Code Engine project name}"
APP_NAME="${APP_NAME:-bob-governance}"
SECRET_NAME="${APP_SECRET:-bob-governance-env}"
EXPECTED_ACCOUNT="${EXPECTED_ACCOUNT:?Set EXPECTED_ACCOUNT to the IBM Cloud account id}"
KEYCHAIN_SERVICE="${INGEST_KEYCHAIN_SERVICE:-bob-governance-ingest-token}"
DASHBOARD_KEYCHAIN_SERVICE="${DASHBOARD_KEYCHAIN_SERVICE:-bob-governance-dashboard-password}"
SIMPLEMDM_KEYCHAIN_SERVICE="${SIMPLEMDM_KEYCHAIN_SERVICE:-bob-governance-simplemdm-api}"
DASHBOARD_USER="${DASHBOARD_USER:-governance}"
COS_INSTANCE="${COS_INSTANCE:?Set COS_INSTANCE to the COS service instance name}"
COS_BUCKET="${COS_BUCKET:?Set COS_BUCKET to a bucket name}"
ICR_NAMESPACE="${ICR_NAMESPACE:?Set ICR_NAMESPACE to the container registry namespace}"
REGISTRY_SECRET="${REGISTRY_SECRET:?Set REGISTRY_SECRET to the Code Engine registry secret}"
COS_REGION="${COS_REGION:-ca-tor}"
COS_ENDPOINT="${COS_ENDPOINT:-https://s3.ca-tor.cloud-object-storage.appdomain.cloud}"
COS_PREFIX="${COS_PREFIX:-bob-governance/v1}"
SIMPLEMDM_PROFILE_ID="${SIMPLEMDM_PROFILE_ID:-100001}"
SIMPLEMDM_GROUP_ID="${SIMPLEMDM_GROUP_ID:-200001}"

cd "$(dirname "$0")/.."

npm --prefix frontend ci
npm --prefix frontend run build

TARGET="$(ibmcloud target 2>/dev/null || true)"
printf '%s' "${TARGET}" | grep -q "${EXPECTED_ACCOUNT}" || {
  echo "Refusing to deploy: target IBM Cloud account is not ${EXPECTED_ACCOUNT}." >&2
  exit 1
}

ibmcloud ce project select --name "${PROJECT}" >/dev/null

if ! TOKEN="$(security find-generic-password -a "${USER}" -s "${KEYCHAIN_SERVICE}" -w 2>/dev/null)"; then
  TOKEN="$(openssl rand -hex 32)"
  security add-generic-password -U -a "${USER}" -s "${KEYCHAIN_SERVICE}" -w "${TOKEN}" >/dev/null
fi
trap 'unset TOKEN' EXIT

if ! DASHBOARD_PASSWORD="$(security find-generic-password -a "${USER}" -s "${DASHBOARD_KEYCHAIN_SERVICE}" -w 2>/dev/null)"; then
  DASHBOARD_PASSWORD="$(openssl rand -base64 30 | tr -d '\n')"
  security add-generic-password -U -a "${USER}" -s "${DASHBOARD_KEYCHAIN_SERVICE}" -w "${DASHBOARD_PASSWORD}" >/dev/null
fi
if ! SIMPLEMDM_API_KEY="$(security find-generic-password -a "${USER}" -s "${SIMPLEMDM_KEYCHAIN_SERVICE}" -w 2>/dev/null)"; then
  echo "Managed deployment credential is missing from Keychain service ${SIMPLEMDM_KEYCHAIN_SERVICE}." >&2
  exit 1
fi
trap 'unset TOKEN DASHBOARD_PASSWORD SIMPLEMDM_API_KEY' EXIT

if ibmcloud ce secret get --name "${SECRET_NAME}" >/dev/null 2>&1; then
  ibmcloud ce secret update --name "${SECRET_NAME}" --from-literal "INGEST_TOKEN=${TOKEN}" --from-literal "DASHBOARD_USER=${DASHBOARD_USER}" --from-literal "DASHBOARD_PASSWORD=${DASHBOARD_PASSWORD}" --from-literal "SIMPLEMDM_API_KEY=${SIMPLEMDM_API_KEY}" >/dev/null
else
  ibmcloud ce secret create --name "${SECRET_NAME}" --format generic --from-literal "INGEST_TOKEN=${TOKEN}" --from-literal "DASHBOARD_USER=${DASHBOARD_USER}" --from-literal "DASHBOARD_PASSWORD=${DASHBOARD_PASSWORD}" --from-literal "SIMPLEMDM_API_KEY=${SIMPLEMDM_API_KEY}" >/dev/null
fi

COS_CRN="$(ibmcloud resource service-instance "${COS_INSTANCE}" --output json | jq -er '.[0].id')"
# `bucket-head` does not accept --ibm-service-instance-id in current CLIs, so
# check existence through the instance-scoped bucket listing instead.
if ! ibmcloud cos buckets --ibm-service-instance-id "${COS_CRN}" --output json | jq -er --arg bucket "${COS_BUCKET}" '.Buckets[]? | select(.Name == $bucket)' >/dev/null; then
  ibmcloud cos bucket-create --bucket "${COS_BUCKET}" --region "${COS_REGION}" --ibm-service-instance-id "${COS_CRN}" >/dev/null
fi

# Accounts without binding-operator IAM access (for example ITZ accounts) cannot
# use `ce app bind`; keep a Writer service credential mirrored into a Code
# Engine secret so the application can authenticate to COS directly.
COS_SECRET_NAME="${COS_SECRET_NAME:-bob-governance-cos}"
COS_KEY_NAME="${COS_KEY_NAME:-bob-governance-cos-writer}"
if ! ibmcloud resource service-key "${COS_KEY_NAME}" >/dev/null 2>&1; then
  ibmcloud resource service-key-create "${COS_KEY_NAME}" Writer --instance-name "${COS_INSTANCE}" >/dev/null
fi
COS_KEY_JSON="$(ibmcloud resource service-key "${COS_KEY_NAME}" --output json)"
COS_API_KEY_VALUE="$(printf '%s' "${COS_KEY_JSON}" | jq -er '.[0].credentials.apikey')"
COS_RIID_VALUE="$(printf '%s' "${COS_KEY_JSON}" | jq -er '.[0].credentials.resource_instance_id')"
trap 'unset TOKEN DASHBOARD_PASSWORD SIMPLEMDM_API_KEY COS_KEY_JSON COS_API_KEY_VALUE COS_RIID_VALUE' EXIT
if ibmcloud ce secret get --name "${COS_SECRET_NAME}" >/dev/null 2>&1; then
  ibmcloud ce secret update --name "${COS_SECRET_NAME}" --from-literal "COS_API_KEY=${COS_API_KEY_VALUE}" --from-literal "COS_RESOURCE_INSTANCE_ID=${COS_RIID_VALUE}" >/dev/null
else
  ibmcloud ce secret create --name "${COS_SECRET_NAME}" --format generic --from-literal "COS_API_KEY=${COS_API_KEY_VALUE}" --from-literal "COS_RESOURCE_INSTANCE_ID=${COS_RIID_VALUE}" >/dev/null
fi

ARGS=(
  --image "ca.icr.io/${ICR_NAMESPACE}/${APP_NAME}:${IMAGE_TAG:-$(date -u +%Y%m%d%H%M%S)}"
  --registry-secret "${REGISTRY_SECRET}"
  --port 8080
  --env-from-secret "${SECRET_NAME}"
  --min-scale 1
  --max-scale 1
  --cpu 0.5
  --memory 1G
  --env "OBJECT_STORE_MODE=cos"
  --env "COS_BUCKET=${COS_BUCKET}"
  --env "COS_ENDPOINT=${COS_ENDPOINT}"
  --env "COS_PREFIX=${COS_PREFIX}"
  --env "SIMPLEMDM_PROFILE_ID=${SIMPLEMDM_PROFILE_ID}"
  --env "SIMPLEMDM_GROUP_ID=${SIMPLEMDM_GROUP_ID}"
)

IMAGE="${ARGS[1]}"
ibmcloud cr login >/dev/null
docker buildx build --platform linux/amd64 --load --tag "${IMAGE}" .
docker push "${IMAGE}"

if ! ibmcloud ce app get --name "${APP_NAME}" >/dev/null 2>&1; then
  ibmcloud ce app create --name "${APP_NAME}" \
    --image "${IMAGE}" --registry-secret "${REGISTRY_SECRET}" --port 8080 \
    --env-from-secret "${SECRET_NAME}" --min-scale 1 --max-scale 1 --cpu 0.5 --memory 1G
fi

if ! BIND_OUTPUT="$(ibmcloud ce app bind --name "${APP_NAME}" --service-instance "${COS_INSTANCE}" --role Writer --wait --wait-timeout 180 2>&1)"; then
  if printf '%s' "${BIND_OUTPUT}" | grep -qiE 'already.*bound|binding.*exists'; then
    :
  elif printf '%s' "${BIND_OUTPUT}" | grep -qiE 'permission|not authorized|insufficient'; then
    echo "Service binding unavailable in this account; using credential secret ${COS_SECRET_NAME}." >&2
    ARGS+=(--env-from-secret "${COS_SECRET_NAME}")
  else
    printf '%s\n' "${BIND_OUTPUT}" >&2
    exit 1
  fi
fi

CURRENT_URL="$(ibmcloud ce app get --name "${APP_NAME}" --output url | tr -d '[:space:]')"
ARGS+=(--env "PUBLIC_BASE_URL=${CURRENT_URL}")
ibmcloud ce app update --name "${APP_NAME}" "${ARGS[@]}"

URL="$(ibmcloud ce app get --name "${APP_NAME}" --output url | tr -d '[:space:]')"
curl --silent --show-error --fail --max-time 45 "${URL}/healthz" >/dev/null
curl --silent --show-error --fail --max-time 45 --user "${DASHBOARD_USER}:${DASHBOARD_PASSWORD}" "${URL}/api/v1/storage/health" | jq -e '.status == "available" and .mode == "cos"' >/dev/null
printf 'Dashboard: %s\n' "${URL}"
printf 'Dashboard user: %s (password remains in Keychain service %s)\n' "${DASHBOARD_USER}" "${DASHBOARD_KEYCHAIN_SERVICE}"
printf 'Health check: PASS\n'
printf 'Durable object storage: PASS\n'
