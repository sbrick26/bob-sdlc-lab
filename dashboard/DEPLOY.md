# Deploy the lab dashboard to IBM Code Engine

> **Status: untested.** These commands follow the Code Engine CLI but have not
> been run against this folder. Check each one before you use it.

## Local mode (no cloud)

```bash
./run-local.sh                         # http://localhost:8080, user governance, password lab
.venv/bin/python scripts/seed-lab.py   # optional: four-person demo run
```

`run-local.sh` sets `LAB_MODE=1`, `OBJECT_STORE_MODE=local`, `DATA_DIR=./data`,
`INGEST_TOKEN=lab-ingest-token`, `DASHBOARD_USER=governance`,
`DASHBOARD_PASSWORD=lab`. These are demo values. Do not use them on a public URL.

## Environment variables

| Variable | Required | Value |
| --- | --- | --- |
| `INGEST_TOKEN` | yes | Bearer token for `/api/v1/hooks` and `/api/v1/lab/events`. Put it in a secret. |
| `DASHBOARD_USER` | no | Basic-auth user for the console and read APIs. Default `governance`. |
| `DASHBOARD_PASSWORD` | yes | Basic-auth password. Put it in a secret. |
| `LAB_MODE` | lab | `1`: policy publish activates the policy in the object store, no MDM. |
| `LAB_PACKAGE_ALLOWLIST` | no | Approved Python packages for GOV-PKG-001. Default `flask,pytest,mcp,pyyaml`. Read when the default policy is first written; after that, edit the policy in the console. |
| `OBJECT_STORE_MODE` | yes | `local` (container disk, lost on restart) or `cos`. |
| `DATA_DIR` | local | Directory for the local object store. Image default `/app/data`. |
| `COS_BUCKET`, `COS_ENDPOINT`, `COS_PREFIX` | cos | IBM Cloud Object Storage target. |
| `COS_API_KEY`, `COS_RESOURCE_INSTANCE_ID` | cos | COS credentials, from a secret (or a service binding). |
| `PORT` | no | Set by Code Engine. The image listens on `${PORT:-8080}`. |
| `SIMPLEMDM_API_KEY` | no | Only when `LAB_MODE` is off and policy publish must reach MDM. |

## Commands

Set your names first. Nothing below is specific to one account.

```bash
export REGION=us-south
export CE_PROJECT=<code-engine-project>
export ICR_NAMESPACE=<registry-namespace>
export IMAGE=us.icr.io/${ICR_NAMESPACE}/bob-sdlc-lab-dashboard:$(date -u +%Y%m%d%H%M%S)

ibmcloud target -r "${REGION}"
ibmcloud ce project select --name "${CE_PROJECT}"

# 1. Build the image (the Dockerfile builds the frontend) and push it.
ibmcloud cr login
docker buildx build --platform linux/amd64 --load --tag "${IMAGE}" .
docker push "${IMAGE}"

# 2. Secret with the credentials. Generate fresh values; do not reuse the demo ones.
ibmcloud ce secret create --name bob-sdlc-lab-dashboard-env --format generic \
  --from-literal "INGEST_TOKEN=$(openssl rand -hex 32)" \
  --from-literal "DASHBOARD_USER=governance" \
  --from-literal "DASHBOARD_PASSWORD=$(openssl rand -base64 24)"

# 3. Registry access for the image pull.
ibmcloud ce registry create --name icr-lab --server us.icr.io --username iamapikey --password "<api-key>"

# 4. First deploy (local object store inside the container; one instance only).
ibmcloud ce application create --name bob-sdlc-lab-dashboard \
  --image "${IMAGE}" --registry-secret icr-lab --port 8080 \
  --env-from-secret bob-sdlc-lab-dashboard-env \
  --env LAB_MODE=1 --env OBJECT_STORE_MODE=local --env DATA_DIR=/app/data \
  --min-scale 1 --max-scale 1 --cpu 0.5 --memory 1G

# 5. Later deploys.
ibmcloud ce application update --name bob-sdlc-lab-dashboard --image "${IMAGE}"

# 6. Optional: durable storage in COS instead of container disk.
ibmcloud ce application update --name bob-sdlc-lab-dashboard \
  --env OBJECT_STORE_MODE=cos --env COS_BUCKET=<bucket> \
  --env COS_ENDPOINT=https://s3.us-south.cloud-object-storage.appdomain.cloud \
  --env COS_PREFIX=bob-sdlc-lab/v1 --env-from-secret <cos-credentials-secret>

# 7. Check it.
URL=$(ibmcloud ce application get --name bob-sdlc-lab-dashboard --output url)
curl -fsS "${URL}/healthz"
```

Notes:

- Keep `--max-scale 1`. The query index is in process memory; with
  `OBJECT_STORE_MODE=local` each instance would also have its own disk.
- With `OBJECT_STORE_MODE=local`, data is lost when the instance restarts.
  Use COS for a run you must keep.
- Lab hook clients send `Authorization: Bearer <INGEST_TOKEN>` to
  `${URL}/api/v1/hooks`, and CI sends lab events to `${URL}/api/v1/lab/events`.
- `scripts/deploy-code-engine.sh` is the original MDM-mode deploy script. It
  needs `CE_PROJECT`, `EXPECTED_ACCOUNT`, `COS_INSTANCE`, `COS_BUCKET`,
  `ICR_NAMESPACE` and `REGISTRY_SECRET`, and reads credentials from macOS Keychain.
