#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_PATH="${1:-${REPO_DIR}/profiles/bob-enforced-hooks-canary.mobileconfig}"

PROFILE_UUID="$(/usr/bin/uuidgen)"
PAYLOAD_UUID="$(/usr/bin/uuidgen)"
# `&amp;&amp;` is decoded by the plist parser back to `&&` in the managed string.
# Keep the shell alive briefly after creating the marker so Bob can finish its
# asynchronous stdin write before the process exits.
HOOK_JSON='{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"/usr/bin/touch /tmp/bob-enforced-hooks-canary &amp;&amp; /bin/sleep 2","timeout":5}]}]}'

/bin/mkdir -p "$(dirname "${OUTPUT_PATH}")"

/bin/cat >"${OUTPUT_PATH}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadContent</key>
  <array>
    <dict>
      <key>PayloadContent</key>
      <dict>
        <key>com.ibm.bob</key>
        <dict>
          <key>Forced</key>
          <array>
            <dict>
              <key>mcx_preference_settings</key>
              <dict>
                <key>EnforcedHooks</key>
                <string>${HOOK_JSON}</string>
              </dict>
            </dict>
          </array>
        </dict>
      </dict>
      <key>PayloadDisplayName</key>
      <string>Bob Enforced Hooks Canary</string>
      <key>PayloadIdentifier</key>
      <string>com.ibm.bob.enforced-hooks.canary.preferences</string>
      <key>PayloadType</key>
      <string>com.apple.ManagedClient.preferences</string>
      <key>PayloadUUID</key>
      <string>${PAYLOAD_UUID}</string>
      <key>PayloadVersion</key>
      <integer>1</integer>
    </dict>
  </array>
  <key>PayloadDescription</key>
  <string>Harmless MDM canary for IBM Bob EnforcedHooks. On UserPromptSubmit it creates /tmp/bob-enforced-hooks-canary, briefly keeps the process open for Bob's stdin write, and transmits no data.</string>
  <key>PayloadDisplayName</key>
  <string>Bob Enforced Hooks Canary</string>
  <key>PayloadIdentifier</key>
  <string>com.ibm.bob.enforced-hooks.canary</string>
  <key>PayloadOrganization</key>
  <string>IBM Bob Enforced Hooks Lab</string>
  <key>PayloadRemovalDisallowed</key>
  <false/>
  <key>PayloadScope</key>
  <string>System</string>
  <key>PayloadType</key>
  <string>Configuration</string>
  <key>PayloadUUID</key>
  <string>${PROFILE_UUID}</string>
  <key>PayloadVersion</key>
  <integer>1</integer>
</dict>
</plist>
EOF

/usr/bin/plutil -lint "${OUTPUT_PATH}" >/dev/null
EMBEDDED_JSON="$(/usr/libexec/PlistBuddy -c 'Print :PayloadContent:0:PayloadContent:com.ibm.bob:Forced:0:mcx_preference_settings:EnforcedHooks' "${OUTPUT_PATH}")"
/usr/bin/osascript -l JavaScript \
  -e 'function run(argv) { JSON.parse(argv[0]); return "valid"; }' \
  "${EMBEDDED_JSON}" >/dev/null

/bin/echo "Generated and validated ${OUTPUT_PATH}"
