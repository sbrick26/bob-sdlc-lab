from __future__ import annotations

import base64
import json
import plistlib
import shlex
import uuid
from typing import Any


def _rule_config(config: dict[str, Any], rule_id: str) -> dict[str, Any]:
    for entry in config.get("rules", []):
        if isinstance(entry, dict) and entry.get("rule_id") == rule_id:
            return entry
    return {}


def _enabled(config: dict[str, Any], rule_id: str) -> bool:
    entry = _rule_config(config, rule_id)
    return bool(entry and entry.get("enabled", True))


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _local_checker(config: dict[str, Any]) -> str:
    package_rule = _rule_config(config, "GOV-PKG-001")
    allowlist = package_rule.get("configuration", {}).get("allowlist", {})
    python = json.dumps(
        [str(value).lower().replace("_", "-") for value in allowlist.get("python", [])],
        separators=(",", ":"),
    )
    node = json.dumps(
        [str(value).lower() for value in allowlist.get("node", [])],
        separators=(",", ":"),
    )
    enabled = {
        rule_id: _enabled(config, rule_id)
        for rule_id in ("GOV-PROMPT-001", "GOV-PROMPT-002", "GOV-TOOL-001", "GOV-PKG-001")
    }
    enabled_json = json.dumps(enabled, separators=(",", ":"))
    return rf'''ObjC.import("Foundation");
function read(path) {{
  return ObjC.unwrap($.NSString.stringWithContentsOfFileEncodingError($(path), $.NSUTF8StringEncoding, null));
}}
function normalize(value, ecosystem) {{
  value = String(value || "").replace(/^["']|["']$/g, "");
  if (ecosystem === "python") return value.split(";")[0].split("[")[0].split(/[<>=!~]/)[0].toLowerCase().replace(/_/g, "-");
  if (value[0] === "@") {{ var slash=value.indexOf("/"); var at=value.indexOf("@", slash+1); return (at >= 0 ? value.slice(0,at) : value).toLowerCase(); }}
  return value.split("@")[0].toLowerCase();
}}
function tokenize(segment) {{
  var tokens=[];
  var pattern=/"(?:\\.|[^"\\])*"|'[^']*'|[^\s]+/g;
  var match;
  while ((match=pattern.exec(segment)) !== null) tokens.push(match[0].replace(/^["']|["']$/g, ""));
  return tokens;
}}
function packageFindings(command, allowlists) {{
  var findings={{python:{{}},node:{{}}}}, detected={{}};
  String(command || "").split(/&&|\|\||[;|\n]/).forEach(function(segment) {{
    var tokens=tokenize(segment.trim());
    for (var i=0;i<tokens.length;i++) {{
      var base=tokens[i].split("/").pop().toLowerCase(), ecosystem="", start=-1;
      if ((base === "pip" || base === "pip3") && tokens[i+1] === "install") {{ ecosystem="python"; start=i+2; }}
      else if ((base === "python" || base === "python3") && tokens.slice(i+1,i+4).join(" ") === "-m pip install") {{ ecosystem="python"; start=i+4; }}
      else if ((base === "npm" || base === "pnpm") && ["install","i","add"].indexOf(tokens[i+1]) >= 0) {{ ecosystem="node"; start=i+2; }}
      else if (base === "yarn" && ["add","install"].indexOf(tokens[i+1]) >= 0) {{ ecosystem="node"; start=i+2; }}
      if (!ecosystem) continue;
      detected[ecosystem]=true;
      var requested=[], skip=false, args=tokens.slice(start);
      for (var j=0;j<args.length;j++) {{
        var arg=args[j];
        if (skip) {{ skip=false; continue; }}
        if (arg === "-r" || arg === "--requirement" || /^-r.+/.test(arg) || /^--requirement=/.test(arg)) {{
          findings[ecosystem]["dependency-manifest"]=true;
          if (arg === "-r" || arg === "--requirement") skip=true;
          continue;
        }}
        if (["--index-url","--extra-index-url","--registry"].indexOf(arg) >= 0) {{ skip=true; continue; }}
        if (arg[0] === "-") continue;
        var name=normalize(arg,ecosystem);
        if (/^(\.|\/|git\+|https?:\/\/)/.test(name)) findings[ecosystem]["local-or-remote-source"]=true;
        else if (name) requested.push(name);
      }}
      if (!requested.length && !Object.keys(findings[ecosystem]).length) findings[ecosystem]["dependency-manifest"]=true;
      requested.forEach(function(name) {{ if (allowlists[ecosystem].indexOf(name) < 0) findings[ecosystem][name]=true; }});
    }}
  }});
  var denied=[];
  Object.keys(detected).sort().forEach(function(ecosystem) {{ denied=denied.concat(Object.keys(findings[ecosystem])); }});
  return denied.filter(function(value,index,array) {{ return array.indexOf(value) === index; }}).sort();
}}
var enabled={enabled_json};
var payload={{}};
try {{ payload=JSON.parse(read($.NSProcessInfo.processInfo.arguments.objectAtIndex(4).js)); }} catch (_) {{}}
var event=String(payload.hook_event_name || "");
var scan=event === "UserPromptSubmit" ? String(payload.prompt || "") : JSON.stringify(payload.tool_input || "");
var withoutRefs=scan.replace(/\$\{{[A-Z_][A-Z0-9_]*\}}|\$[A-Z_][A-Z0-9_]*|process\.env\.[A-Z_][A-Z0-9_]*|os\.environ\[[^\]]+\]|os\.getenv\([^)]*\)|(?:vault|secret):\/\/[^\s"']+|(?:environment|env)\s+(?:variable|var)\s+[A-Z_][A-Z0-9_]*/gi, "<managed-reference>");
var known=/\bsk-[A-Za-z0-9_-]{{20,}}\b|\bgh[pousr]_[A-Za-z0-9]{{20,}}\b|\bgithub_pat_[A-Za-z0-9_]{{20,}}\b|\bAKIA[0-9A-Z]{{12,}}\b|\bxox[abprs]-[A-Za-z0-9-]{{10,}}\b|\bsk_(?:live|test)_[A-Za-z0-9]{{16,}}\b|\beyJ[A-Za-z0-9_-]{{10,}}\.[A-Za-z0-9_-]{{10,}}\.[A-Za-z0-9_-]{{5,}}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----/;
var labeledAssignment=/(?:api[_ -]?key|token|secret|password|client[_ -]?secret)\s*[:=]\s*["']?(?!REDACTED|example|changeme|<managed-reference>)[A-Za-z0-9._~+\/=\-]{{16,}}/i;
var labeledNatural=/(?:api[_ -]?key|token|secret|password|client[_ -]?secret)(?:[^\n]{{0,80}}?)(?=[A-Za-z0-9]{{24,}}\b)(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*[a-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{{24,}}/i;
var result={{decision:"allowed",rule_id:"",outcome:"completed"}};
if (event === "UserPromptSubmit") {{
  if (known.test(withoutRefs) && enabled["GOV-PROMPT-001"]) result={{decision:"blocked",rule_id:"GOV-PROMPT-001",outcome:"prevented_before_model"}};
  else if ((labeledAssignment.test(withoutRefs) || labeledNatural.test(withoutRefs)) && enabled["GOV-PROMPT-002"]) result={{decision:"blocked",rule_id:"GOV-PROMPT-002",outcome:"prevented_before_model"}};
}} else if (event === "PreToolUse") {{
  if ((known.test(withoutRefs) || labeledAssignment.test(withoutRefs) || labeledNatural.test(withoutRefs)) && enabled["GOV-TOOL-001"]) result={{decision:"blocked",rule_id:"GOV-TOOL-001",outcome:"prevented_before_tool"}};
  else if (enabled["GOV-PKG-001"]) {{
    var command=payload.tool_input && (payload.tool_input.command || payload.tool_input.cmd || payload.tool_input.script) || "";
    var denied=packageFindings(command,{{python:{python},node:{node}}});
    if (denied.length) result={{decision:"blocked",rule_id:"GOV-PKG-001",outcome:"prevented_before_tool",detail:denied.join(",")}};
  }}
}}
JSON.stringify(result);'''


def build_profile(
    *, config: dict[str, Any], version: str, api_url: str, ingest_token: str,
    profile_id: str,
) -> bytes:
    offline = config.get("offline", {})
    queue_max_events = _bounded_int(
        offline.get("queue_max_events"), default=500, minimum=1, maximum=10_000
    )
    queue_max_bytes = _bounded_int(
        offline.get("queue_max_bytes"), default=10_485_760, minimum=4_096, maximum=1_073_741_824
    )
    retry_max_seconds = _bounded_int(
        offline.get("retry_max_seconds"), default=300, minimum=1, maximum=3_600
    )
    checker = base64.b64encode(_local_checker(config).encode()).decode()
    quoted_url = shlex.quote(api_url.rstrip("/") + "/api/v1/hooks")
    quoted_token = shlex.quote(ingest_token)
    command = rf'''GOV_ROOT="$HOME/Library/Application Support/IBM Bob/Governance"
GOV_QUEUE="$GOV_ROOT/queue"
GOV_CHECKER="$GOV_ROOT/local-check.js"
/bin/mkdir -p "$GOV_QUEUE" || exit 0
/bin/chmod 700 "$GOV_ROOT" "$GOV_QUEUE" 2>/dev/null || true
/usr/bin/printf '%s' '{checker}' | /usr/bin/base64 -D > "$GOV_CHECKER"
/bin/chmod 600 "$GOV_CHECKER" 2>/dev/null || true
GOV_EVENT_ID=$(/usr/bin/uuidgen | /usr/bin/tr '[:upper:]' '[:lower:]')
GOV_OCCURRED_AT=$(/bin/date -u '+%Y-%m-%dT%H:%M:%SZ')
GOV_SEQUENCE_FILE="$GOV_ROOT/sequence"
GOV_SEQUENCE=0
[ -f "$GOV_SEQUENCE_FILE" ] && GOV_SEQUENCE=$(/bin/cat "$GOV_SEQUENCE_FILE" 2>/dev/null || /usr/bin/printf 0)
case "$GOV_SEQUENCE" in ''|*[!0-9]*) GOV_SEQUENCE=0 ;; esac
GOV_SEQUENCE=$((GOV_SEQUENCE + 1))
/usr/bin/printf '%s' "$GOV_SEQUENCE" > "$GOV_SEQUENCE_FILE"
/bin/chmod 600 "$GOV_SEQUENCE_FILE" 2>/dev/null || true
GOV_ORDER=$(/usr/bin/printf '%020d' "$GOV_SEQUENCE")
GOV_DIR="$GOV_QUEUE/event.$GOV_ORDER.$GOV_EVENT_ID"
GOV_BODY="$GOV_DIR/body.json"
GOV_META="$GOV_DIR/metadata.plist"
/bin/mkdir -m 700 "$GOV_DIR" || exit 0
: > "$GOV_BODY" || exit 0
/bin/cat > "$GOV_BODY"
/bin/chmod 600 "$GOV_BODY" 2>/dev/null || true
GOV_LOCAL_JSON=$(/usr/bin/osascript -l JavaScript "$GOV_CHECKER" "$GOV_BODY" 2>/dev/null || /usr/bin/printf '{{"decision":"allowed","rule_id":"","outcome":"completed"}}')
GOV_LOCAL_DECISION=$(/usr/bin/printf '%s' "$GOV_LOCAL_JSON" | /usr/bin/plutil -extract decision raw -o - - 2>/dev/null || /usr/bin/printf allowed)
GOV_LOCAL_RULE=$(/usr/bin/printf '%s' "$GOV_LOCAL_JSON" | /usr/bin/plutil -extract rule_id raw -o - - 2>/dev/null || true)
GOV_LOCAL_OUTCOME=$(/usr/bin/printf '%s' "$GOV_LOCAL_JSON" | /usr/bin/plutil -extract outcome raw -o - - 2>/dev/null || /usr/bin/printf completed)
GOV_LOCAL_DETAIL=$(/usr/bin/printf '%s' "$GOV_LOCAL_JSON" | /usr/bin/plutil -extract detail raw -o - - 2>/dev/null || true)
GOV_USER=$(/usr/bin/id -un)
GOV_DEVICE=$(/usr/sbin/scutil --get ComputerName 2>/dev/null || /bin/hostname)
GOV_DEVICE_ID=$(/usr/sbin/ioreg -rd1 -c IOPlatformExpertDevice 2>/dev/null | /usr/bin/awk -F '"' '/IOPlatformUUID/{{print $(NF-1);exit}}')
/usr/bin/plutil -create xml1 "$GOV_META"
/usr/bin/plutil -insert event_id -string "$GOV_EVENT_ID" "$GOV_META"
/usr/bin/plutil -insert occurred_at -string "$GOV_OCCURRED_AT" "$GOV_META"
/usr/bin/plutil -insert policy_version -string {shlex.quote(version)} "$GOV_META"
/usr/bin/plutil -insert local_decision -string "$GOV_LOCAL_DECISION" "$GOV_META"
/usr/bin/plutil -insert local_rule -string "$GOV_LOCAL_RULE" "$GOV_META"
/usr/bin/plutil -insert local_outcome -string "$GOV_LOCAL_OUTCOME" "$GOV_META"
/usr/bin/plutil -insert user -string "$GOV_USER" "$GOV_META"
/usr/bin/plutil -insert device -string "$GOV_DEVICE" "$GOV_META"
/usr/bin/plutil -insert device_id -string "$GOV_DEVICE_ID" "$GOV_META"
/usr/bin/plutil -insert profile -string 'Bob Governance' "$GOV_META"
/usr/bin/plutil -insert profile_id -string {shlex.quote(profile_id)} "$GOV_META"
/usr/bin/plutil -insert bob_version -string '2.1.0' "$GOV_META"
/usr/bin/plutil -insert bob_channel -string 'insiders' "$GOV_META"
/bin/chmod 600 "$GOV_META" 2>/dev/null || true
gov_meta() {{ /usr/bin/plutil -extract "$1" raw -o - "$2" 2>/dev/null || true; }}
gov_send() {{
  GOV_SEND_DIR="$1"
  GOV_SEND_TIMEOUT="$2"
  GOV_SEND_DELIVERY="$3"
  GOV_SEND_META="$GOV_SEND_DIR/metadata.plist"
  GOV_SEND_BODY="$GOV_SEND_DIR/body.json"
  /usr/bin/curl --fail-with-body --silent --show-error --max-time "$GOV_SEND_TIMEOUT" --request POST \
    --header 'Authorization: Bearer {quoted_token}' \
    --header 'Content-Type: application/json' \
    --header "X-Governance-Delivery: $GOV_SEND_DELIVERY" \
    --header "X-Governance-Event-ID: $(gov_meta event_id "$GOV_SEND_META")" \
    --header "X-Governance-Occurred-At: $(gov_meta occurred_at "$GOV_SEND_META")" \
    --header "X-Governance-Policy-Version: $(gov_meta policy_version "$GOV_SEND_META")" \
    --header "X-Governance-Local-Decision: $(gov_meta local_decision "$GOV_SEND_META")" \
    --header "X-Governance-Local-Rule: $(gov_meta local_rule "$GOV_SEND_META")" \
    --header "X-Governance-Local-Outcome: $(gov_meta local_outcome "$GOV_SEND_META")" \
    --header "X-Governance-User: $(gov_meta user "$GOV_SEND_META")" \
    --header "X-Governance-Device: $(gov_meta device "$GOV_SEND_META")" \
    --header "X-Governance-Device-ID: $(gov_meta device_id "$GOV_SEND_META")" \
    --header "X-Governance-Profile: $(gov_meta profile "$GOV_SEND_META")" \
    --header "X-Governance-Profile-ID: $(gov_meta profile_id "$GOV_SEND_META")" \
    --header "X-Bob-Version: $(gov_meta bob_version "$GOV_SEND_META")" \
    --header "X-Bob-Channel: $(gov_meta bob_channel "$GOV_SEND_META")" \
    --data-binary @"$GOV_SEND_BODY" {quoted_url}
}}
gov_drop_oldest() {{
  GOV_DROP=$(/usr/bin/find "$GOV_QUEUE" -mindepth 1 -maxdepth 1 -type d -name 'event.*' -print | /usr/bin/sort | /usr/bin/head -1)
  [ -n "$GOV_DROP" ] || return 1
  /bin/rm -rf "$GOV_DROP"
  GOV_DROPPED=0
  [ -f "$GOV_ROOT/dead-letter-count" ] && GOV_DROPPED=$(/bin/cat "$GOV_ROOT/dead-letter-count" 2>/dev/null || /usr/bin/printf 0)
  case "$GOV_DROPPED" in ''|*[!0-9]*) GOV_DROPPED=0 ;; esac
  /usr/bin/printf '%s' "$((GOV_DROPPED + 1))" > "$GOV_ROOT/dead-letter-count"
  /bin/chmod 600 "$GOV_ROOT/dead-letter-count" 2>/dev/null || true
}}
while :; do
  GOV_COUNT=$(/usr/bin/find "$GOV_QUEUE" -mindepth 1 -maxdepth 1 -type d -name 'event.*' -print | /usr/bin/wc -l | /usr/bin/tr -d ' ')
  GOV_BYTES=$(/usr/bin/find "$GOV_QUEUE" -type f \( -name 'body.json' -o -name 'metadata.plist' \) -exec /usr/bin/stat -f '%z' {{}} + 2>/dev/null | /usr/bin/awk '{{sum += $1}} END {{print sum + 0}}')
  [ "${{GOV_COUNT:-0}}" -le {queue_max_events} ] && [ "${{GOV_BYTES:-0}}" -le {queue_max_bytes} ] && break
  gov_drop_oldest || break
done
GOV_NOW=$(/bin/date +%s)
GOV_NEXT=0
[ -f "$GOV_ROOT/next-retry" ] && GOV_NEXT=$(/bin/cat "$GOV_ROOT/next-retry" 2>/dev/null || /usr/bin/printf 0)
case "$GOV_NEXT" in ''|*[!0-9]*) GOV_NEXT=0 ;; esac
GOV_RESPONSE=''
GOV_SENT=0
GOV_ATTEMPTED=0
if [ "$GOV_NOW" -ge "$GOV_NEXT" ] && [ -d "$GOV_DIR" ]; then
  GOV_ATTEMPTED=1
  GOV_RESPONSE=$(gov_send "$GOV_DIR" 3 foreground 2>/dev/null) && GOV_SENT=1
fi
if [ "$GOV_SENT" -eq 1 ]; then
  /bin/rm -rf "$GOV_DIR"
  /bin/rm -f "$GOV_ROOT/next-retry" "$GOV_ROOT/retry-attempt"
  GOV_DECISION=$(/usr/bin/printf '%s' "$GOV_RESPONSE" | /usr/bin/plutil -extract decision raw -o - - 2>/dev/null || true)
  GOV_REASON=$(/usr/bin/printf '%s' "$GOV_RESPONSE" | /usr/bin/plutil -extract reason raw -o - - 2>/dev/null || true)
  GOV_CONTEXT=$(/usr/bin/printf '%s' "$GOV_RESPONSE" | /usr/bin/plutil -extract context raw -o - - 2>/dev/null || true)
  GOV_OLD=$(/usr/bin/find "$GOV_QUEUE" -mindepth 1 -maxdepth 1 -type d -name 'event.*' -print | /usr/bin/sort | /usr/bin/head -1)
  if [ -n "$GOV_OLD" ]; then gov_send "$GOV_OLD" 1 deferred >/dev/null 2>&1 && /bin/rm -rf "$GOV_OLD"; fi
  if [ "$GOV_DECISION" = blocked ]; then /usr/bin/printf '%s\n' "${{GOV_REASON:-Blocked by managed Governance policy.}}" >&2; exit 2; fi
  [ -n "$GOV_CONTEXT" ] && /usr/bin/printf '%s\n' "$GOV_CONTEXT"
  exit 0
fi
if [ "$GOV_ATTEMPTED" -eq 1 ]; then
  GOV_ATTEMPT=0
  [ -f "$GOV_ROOT/retry-attempt" ] && GOV_ATTEMPT=$(/bin/cat "$GOV_ROOT/retry-attempt" 2>/dev/null || /usr/bin/printf 0)
  case "$GOV_ATTEMPT" in ''|*[!0-9]*) GOV_ATTEMPT=0 ;; esac
  GOV_ATTEMPT=$((GOV_ATTEMPT + 1))
  GOV_DELAY=5
  GOV_STEP=1
  while [ "$GOV_STEP" -lt "$GOV_ATTEMPT" ] && [ "$GOV_DELAY" -lt {retry_max_seconds} ]; do GOV_DELAY=$((GOV_DELAY * 2)); GOV_STEP=$((GOV_STEP + 1)); done
  [ "$GOV_DELAY" -gt {retry_max_seconds} ] && GOV_DELAY={retry_max_seconds}
  /usr/bin/printf '%s' "$GOV_ATTEMPT" > "$GOV_ROOT/retry-attempt"
  /usr/bin/printf '%s' "$((GOV_NOW + GOV_DELAY))" > "$GOV_ROOT/next-retry"
  /bin/chmod 600 "$GOV_ROOT/retry-attempt" "$GOV_ROOT/next-retry" 2>/dev/null || true
fi
case "$GOV_LOCAL_DECISION:$GOV_LOCAL_RULE" in
  blocked:GOV-PROMPT-001|blocked:GOV-PROMPT-002|blocked:GOV-TOOL-001) /usr/bin/printf '%s\n' "Blocked by offline Governance policy ($GOV_LOCAL_RULE): credential-shaped content must use a managed secret reference." >&2; exit 2 ;;
  blocked:GOV-PKG-001) /usr/bin/printf '%s\n' "Blocked by offline Governance policy (GOV-PKG-001): unapproved package $GOV_LOCAL_DETAIL." >&2; exit 2 ;;
esac
exit 0'''

    hook = {"type": "command", "command": command, "timeout": 10}
    enforced = {
        "SessionStart": [{"hooks": [hook]}],
        "UserPromptSubmit": [{"hooks": [hook]}],
        "PreToolUse": [{"matcher": ".*", "hooks": [hook]}],
        "PostToolUse": [{"matcher": ".*", "hooks": [hook]}],
        "Stop": [{"hooks": [hook]}],
    }
    payload_uuid = str(uuid.uuid4()).upper()
    profile_uuid = str(uuid.uuid4()).upper()
    profile = {
        "PayloadContent": [{
            "PayloadContent": {"com.ibm.bob": {"Forced": [{"mcx_preference_settings": {
                "EnforcedHooks": json.dumps(enforced, separators=(",", ":"))
            }}]}},
            "PayloadDisplayName": "Bob Governance",
            "PayloadIdentifier": "com.ibm.bob.governance.preferences",
            "PayloadType": "com.apple.ManagedClient.preferences",
            "PayloadUUID": payload_uuid,
            "PayloadVersion": 1,
        }],
        "PayloadDescription": "Managed IBM Bob governance policy.",
        "PayloadDisplayName": "Bob Governance",
        "PayloadIdentifier": "com.ibm.bob.governance",
        "PayloadOrganization": "Governance",
        "PayloadRemovalDisallowed": True,
        "PayloadScope": "System",
        "PayloadType": "Configuration",
        "PayloadUUID": profile_uuid,
        "PayloadVersion": 1,
    }
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML, sort_keys=False)
