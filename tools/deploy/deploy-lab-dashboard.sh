#!/bin/bash
# Deploy the lab dashboard to IBM Code Engine from source. Idempotent.
# Needs an ibmcloud login (use IBMCLOUD_HOME to isolate). Env: CE_PROJECT, COS_INSTANCE, optional APP_NAME, COS_REGION.
set -euo pipefail
APP_NAME="${APP_NAME:-bob-sdlc-lab-dashboard}"
CE_PROJECT="${CE_PROJECT:?}"; COS_INSTANCE="${COS_INSTANCE:?}"
COS_REGION="${COS_REGION:-ca-tor}"; COS_ENDPOINT="https://s3.${COS_REGION}.cloud-object-storage.appdomain.cloud"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; SECRETS="$ROOT/.secrets/dashboard.env"
mkdir -p "$ROOT/.secrets"; touch "$SECRETS"; chmod 600 "$SECRETS"
get() { { grep -E "^$1=" "$SECRETS" || true; } | head -1 | cut -d= -f2-; }
put() { grep -qE "^$1=" "$SECRETS" && sed -i '' "s|^$1=.*|$1=$2|" "$SECRETS" || echo "$1=$2" >> "$SECRETS"; }
[ -n "$(get INGEST_TOKEN)" ] || put INGEST_TOKEN "$(openssl rand -hex 24)"
[ -n "$(get DASHBOARD_PASSWORD)" ] || put DASHBOARD_PASSWORD "$(openssl rand -base64 18 | tr -d '/+=\n')"
put DASHBOARD_USER governance
BUCKET="$(get COS_BUCKET)"; [ -n "$BUCKET" ] || { BUCKET="bob-sdlc-lab-$(openssl rand -hex 4)"; put COS_BUCKET "$BUCKET"; }

retry() { local n=0; until "$@"; do n=$((n+1)); [ $n -ge 3 ] && return 1; sleep 5; done; }
ibmcloud target -r "$COS_REGION" >/dev/null
retry ibmcloud ce project select --name "$CE_PROJECT" >/dev/null

COS_CRN="$(ibmcloud resource service-instance "$COS_INSTANCE" --output json | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')"
if ! ibmcloud cos buckets --ibm-service-instance-id "$COS_CRN" --output json | python3 -c "import sys,json; sys.exit(0 if any(b['Name']=='$BUCKET' for b in json.load(sys.stdin).get('Buckets',[])) else 1)"; then
  ibmcloud cos bucket-create --bucket "$BUCKET" --region "$COS_REGION" --ibm-service-instance-id "$COS_CRN" >/dev/null && echo "bucket created: $BUCKET"
fi
KEY="${APP_NAME}-cos-writer"
ibmcloud resource service-key "$KEY" >/dev/null 2>&1 || ibmcloud resource service-key-create "$KEY" Writer --instance-name "$COS_INSTANCE" >/dev/null
KJ="$(ibmcloud resource service-key "$KEY" --output json)"
COS_API_KEY="$(printf '%s' "$KJ" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["credentials"]["apikey"])')"
COS_RIID="$(printf '%s' "$KJ" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["credentials"]["resource_instance_id"])')"
sec() { local name="$1"; shift; if ibmcloud ce secret get --name "$name" >/dev/null 2>&1; then ibmcloud ce secret update --name "$name" "$@" >/dev/null; else ibmcloud ce secret create --name "$name" --format generic "$@" >/dev/null; fi; }
sec "${APP_NAME}-cos" --from-literal "COS_API_KEY=$COS_API_KEY" --from-literal "COS_RESOURCE_INSTANCE_ID=$COS_RIID"
sec "${APP_NAME}-env" --from-literal "INGEST_TOKEN=$(get INGEST_TOKEN)" --from-literal "DASHBOARD_USER=governance" --from-literal "DASHBOARD_PASSWORD=$(get DASHBOARD_PASSWORD)"

cd "$ROOT/dashboard"
# Code Engine source builds need IAM rights this account lacks, so build amd64 here and push to the account registry.
REGISTRY_SECRET="${REGISTRY_SECRET:-icr-ca}"; ICR_NAMESPACE="${ICR_NAMESPACE:-bobsdlc}"
IMAGE="ca.icr.io/${ICR_NAMESPACE}/${APP_NAME}:${IMAGE_TAG:-$(date -u +%Y%m%d%H%M%S)}"
ibmcloud cr region-set "$COS_REGION" >/dev/null; ibmcloud cr login >/dev/null
docker buildx build --platform linux/amd64 --load -t "$IMAGE" . && docker push "$IMAGE"
COMMON=(--image "$IMAGE" --registry-secret "$REGISTRY_SECRET" --port 8080 --min-scale 1 --max-scale 1 --cpu 0.5 --memory 1G
  --env-from-secret "${APP_NAME}-env" --env-from-secret "${APP_NAME}-cos"
  --env LAB_MODE=1 --env OBJECT_STORE_MODE=cos --env "COS_BUCKET=$BUCKET" --env "COS_ENDPOINT=$COS_ENDPOINT" --env COS_PREFIX=bob-sdlc-lab/v1 --wait --wait-timeout 600)
if ibmcloud ce app get --name "$APP_NAME" >/dev/null 2>&1; then ibmcloud ce app update --name "$APP_NAME" "${COMMON[@]}"; else ibmcloud ce app create --name "$APP_NAME" "${COMMON[@]}"; fi
URL="$(ibmcloud ce app get --name "$APP_NAME" --output url | tr -d '[:space:]')"; put DASHBOARD_URL "$URL"
curl -fsS --max-time 45 "$URL/healthz" && echo && curl -fsS --max-time 45 -u "governance:$(get DASHBOARD_PASSWORD)" "$URL/api/v1/storage/health"; echo
echo "Dashboard: $URL  (credentials in $SECRETS)"
