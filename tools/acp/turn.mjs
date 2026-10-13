#!/usr/bin/env node
/**
 * turn.mjs - one Bob turn over ACP, steerable from outside while it runs.
 *
 * The lab harness launches this as a background job, then:
 *   - tails  tools/acp/run[/<lane>]/live.log        human-readable event stream (timestamped)
 *   - tails  tools/acp/run[/<lane>]/agent-text.log  Bob's streaming prose/thoughts
 *   - reads  tools/acp/run[/<lane>]/state.json      machine state incl. pending permission
 *   - writes tools/acp/run[/<lane>]/control.jsonl   commands, one JSON per line:
 *         {"cmd":"cancel"}                        stop the turn now (session survives)
 *         {"cmd":"kill"}                          hard kill
 *         {"cmd":"answer","optionId":"..."}       answer the pending permission
 *         {"cmd":"allow"} / {"cmd":"allow_always"} / {"cmd":"reject"} / {"cmd":"reject_always"}
 *
 * Usage:
 *   node tools/acp/turn.mjs [--resume <id>] [--mode <id>] [--auto-approve] [--cwd <dir>]
 *        [--lane <name>] [--mcp] [--disable-subagents] [--user <name>] [--env KEY=VAL]...
 *        [--image <path>] "<prompt>"
 *
 * Exit: prints one final JSON summary line on stdout:
 *   {sessionId, stopReason, errorClass, seconds, mode, permissions:{...}, toolCalls, cost}
 * Steering = write cancel, then run a new turn.mjs --resume <sessionId> with the corrected
 * prompt: session context persists in Bob's store across processes.
 */
import { spawn, execFileSync } from 'node:child_process';
import { appendFileSync, writeFileSync, readFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';

// The driver lives in tools/acp/; run state lives in tools/acp/run/; default workspace = repo root.
const LAB = resolve(dirname(fileURLToPath(import.meta.url)));
const REPO_ROOT = resolve(LAB, '..', '..');
const lanePre = process.argv.indexOf('--lane');
const LANE = lanePre >= 0 ? process.argv[lanePre + 1] : null;
const RUN = LANE ? join(LAB, 'run', LANE) : join(LAB, 'run');
mkdirSync(RUN, { recursive: true });
const LIVE = join(RUN, 'live.log');
const TEXT = join(RUN, 'agent-text.log');
const EVENTS = join(RUN, 'events.jsonl');
const STATE = join(RUN, 'state.json');
const CONTROL = join(RUN, 'control.jsonl');
const BOB_DB = process.env.BOB_DB || join(homedir(), '.bob', 'db', 'bob.db');

// ---- args ----
const USAGE = 'usage: turn.mjs [--resume id] [--mode id] [--auto-approve] [--cwd dir] [--lane name] [--mcp] [--disable-subagents] [--user name] [--env KEY=VAL]... [--image path] "<prompt>"';
const argv = process.argv.slice(2);
let resumeId = null, modeId = 'agent', modeExplicit = false, autoApprove = false, cwd = REPO_ROOT,
  promptText = null, imagePath = null, withMcp = false, noSubagents = false, labUser = null;
const extraEnv = {};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--lane') i++; // consumed in pre-scan above
  else if (a === '--resume') resumeId = argv[++i];
  else if (a === '--mode') { modeId = argv[++i]; modeExplicit = true; }
  else if (a === '--auto-approve') autoApprove = true;
  else if (a === '--image') imagePath = resolve(argv[++i]);
  else if (a === '--mcp') withMcp = true;
  else if (a === '--disable-subagents') noSubagents = true;
  else if (a === '--cwd') cwd = resolve(argv[++i]);
  else if (a === '--user') labUser = argv[++i];
  else if (a === '--env') {
    const kv = argv[++i] || ''; const eq = kv.indexOf('=');
    if (eq <= 0) { console.error(`bad --env "${kv}" (want KEY=VAL)`); process.exit(2); }
    extraEnv[kv.slice(0, eq)] = kv.slice(eq + 1);
  } else if (a.startsWith('--')) { console.error(`unknown flag ${a}\n${USAGE}`); process.exit(2); }
  else promptText = a;
}
if (!promptText) { console.error(USAGE); process.exit(2); }
if (labUser) extraEnv.LAB_USER = labUser;

const t0 = Date.now();
const ts = () => new Date().toISOString().slice(11, 19) + ' +' + ((Date.now() - t0) / 1000).toFixed(1).padStart(6) + 's';
const say = (s) => appendFileSync(LIVE, `[${ts()}] ${s}\n`);
const state = {
  phase: 'starting', sessionId: resumeId, lane: LANE, cwd, turn: promptText.slice(0, 120), startedAt: new Date().toISOString(),
  requestedMode: modeId, currentMode: null, modeSetVia: null,
  lastEventAt: null, pendingPermission: null, permissionsAsked: [], toolCalls: [], filesTouched: [], stopReason: null, pid: process.pid,
};
const perm = { auto_allow: 0, auto_reject: 0, manual_allow: 0, manual_reject: 0 };
const saveState = () => { state.permissionCounts = perm; writeFileSync(STATE, JSON.stringify(state, null, 1)); };
writeFileSync(CONTROL, ''); // fresh control channel per turn
saveState();
appendFileSync(LIVE, `\n===== TURN start ${new Date().toISOString()} | lane=${LANE || '-'} | resume=${resumeId || '-'} | mode=${modeId} | auto=${autoApprove} | env=${Object.keys(extraEnv).join(',') || '-'} =====\n>> ${promptText}\n`);
appendFileSync(TEXT, `\n===== TURN ${new Date().toISOString()} =====\n`);

// ---- spawn bob ----
const flags = ['acp', '--accept-license', '--trust', '--log-level', 'warn'];
if (!withMcp) flags.push('--disable-mcp');
if (noSubagents) flags.push('--disable-subagents');
if (autoApprove) flags.push('--auto-approve');
const p = spawn('bob', flags, { cwd, stdio: ['pipe', 'pipe', 'pipe'], env: { ...process.env, ...extraEnv } });
const stderrTail = [];
p.stderr.on('data', (d) => {
  const s = d.toString();
  stderrTail.push(s); if (stderrTail.length > 50) stderrTail.shift();
  appendFileSync(EVENTS, JSON.stringify({ ts: ts(), stderr: s }) + '\n');
});
p.stdin.on('error', () => {}); // bob gone: the exit handler reports it
const send = (o) => { try { p.stdin.write(JSON.stringify(o) + '\n'); } catch {} };

// ---- cost from Bob's local store (sessionId == tasks.id). Read-only, never throws. ----
function readCost(sessionId) {
  if (!sessionId || !existsSync(BOB_DB)) return null;
  const q = `SELECT costs FROM tasks WHERE id='${String(sessionId).replace(/'/g, "''")}' LIMIT 1;`;
  let raw = null;
  try {
    raw = execFileSync('sqlite3', ['-readonly', BOB_DB, q], { encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    try { // fallback: node:sqlite (Node >= 22.5)
      const req = process.getBuiltinModule?.('node:sqlite');
      if (req) {
        const db = new req.DatabaseSync(BOB_DB, { readOnly: true });
        raw = db.prepare('SELECT costs FROM tasks WHERE id = ?').get(String(sessionId))?.costs ?? null;
        db.close();
      }
    } catch {}
  }
  if (!raw) return null;
  try {
    const c = JSON.parse(raw);
    const n = (k) => (typeof c[k] === 'number' ? c[k] : null);
    // `cost` is Bob credits, not dollars.
    // Bob 2.0.6 writes only {cost, contextTokens}; token fields appear when Bob records them.
    const out = { credits: n('cost') };
    for (const k of ['input', 'output', 'cacheRead', 'cacheWrite', 'contextTokens']) if (n(k) !== null) out[k] = n(k);
    return out;
  } catch { return { raw: String(raw).slice(0, 200) }; }
}
const sleepMs = (ms) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);

// -32603 / provider / 5xx / connection blips are platform faults, not a verdict on the agent.
const INFRA_RE = /-32600|-32603|not trusted|internal error|provider ?error|request failed|connection (reset|aborted|refused)|broken pipe|econnreset|socket hang up|bob acp exited|(?:http|status|code)\D{0,12}5\d\d\b/i;
function classify(stopReason, errText) {
  if (['end_turn', 'max_tokens', 'max_turn_requests', 'refusal'].includes(stopReason)) return null;
  if (stopReason === 'cancelled' || stopReason === 'killed') return 'cancelled';
  if (stopReason === 'timeout') return 'timeout';
  if (stopReason === 'backend_error' || stopReason === 'process_exit' || INFRA_RE.test(errText || '')) return 'infra';
  return 'error';
}

let done = false, lastError = '';
function finish(stopReason, code = 0) {
  if (done) return; done = true;
  // Flag question-shaped endings so the harness can answer within seconds (a --resume turn).
  const tail = finalText.trim().slice(-600);
  state.endedWithQuestion = /\?\s*$|\?[\s*_`)"']*$|let me know|which (one|of|option|approach)|would you (like|prefer)|should i\b|option\s*[1aA][):.]/im.test(tail);
  state.finalText = tail;
  state.phase = 'done'; state.stopReason = stopReason;
  state.errorClass = classify(stopReason, lastError + '\n' + stderrTail.join(''));
  saveState();
  try { p.kill(); } catch {}
  // costs lands in bob.db within ms of the turn ending; retry briefly.
  let cost = null;
  for (let i = 0; i < 4 && !cost; i++) { cost = readCost(state.sessionId); if (!cost) sleepMs(400); }
  state.cost = cost; saveState();
  const seconds = +((Date.now() - t0) / 1000).toFixed(1);
  say(`===== TURN end: ${stopReason}${state.errorClass ? ' [' + state.errorClass + ']' : ''} (${seconds}s) cost=${cost?.credits ?? 'null'} =====`);
  console.log(JSON.stringify({
    sessionId: state.sessionId, stopReason, errorClass: state.errorClass, seconds,
    mode: state.currentMode, modeSetVia: state.modeSetVia, lane: LANE,
    permissions: { asked: state.permissionsAsked.length, ...perm, pending: permQueue.length },
    toolCalls: state.toolCalls.length, filesTouched: state.filesTouched.length,
    endedWithQuestion: state.endedWithQuestion, cost,
  }));
  process.exit(code);
}

// ---- control channel: poll for harness commands ----
let ctlOffset = 0;
setInterval(() => {
  if (done || !existsSync(CONTROL)) return;
  let raw; try { raw = readFileSync(CONTROL, 'utf8'); } catch { return; }
  if (raw.length <= ctlOffset) return;
  const fresh = raw.slice(ctlOffset); ctlOffset = raw.length;
  for (const line of fresh.split('\n')) {
    if (!line.trim()) continue;
    let c; try { c = JSON.parse(line); } catch { say(`!! bad control line: ${line.slice(0, 80)}`); continue; }
    if (c.cmd === 'cancel') {
      say('CONTROL: cancel -> session/cancel');
      send({ jsonrpc: '2.0', method: 'session/cancel', params: { sessionId: state.sessionId } });
    } else if (c.cmd === 'kill') {
      say('CONTROL: hard kill'); finish('killed', 1);
    } else if (['answer', 'allow', 'allow_always', 'reject', 'reject_always'].includes(c.cmd)) {
      answerPermission(c);
    } else say(`!! unknown control cmd: ${c.cmd}`);
  }
}, 300);

// ---- policy ----
// policy.json: [{"match":"substring-or-*","decision":"allow"|"allow_always"|"reject"|"reject_always"}]
// FIRST MATCH WINS, case-insensitive substring. Effective order for a lane:
//   1. the default policy's reject_always rules (a hard floor no lane can lift)
//   2. run/<lane>/policy.json rules (task-scoped allows such as one `git push origin x`)
//   3. the rest of the default policy (reject `git push`, then the `*` catch-all)
// No match (only possible if `*` was removed) -> queued for a human via control.jsonl.
function loadPolicy() {
  const read = (f) => { try { const r = JSON.parse(readFileSync(f, 'utf8')); return Array.isArray(r) ? r : []; } catch { return []; } };
  const base = read(join(LAB, 'policy.json'));
  const lane = existsSync(join(RUN, 'policy.json')) ? read(join(RUN, 'policy.json')) : [];
  return [...base.filter((r) => r.decision === 'reject_always'), ...lane, ...base.filter((r) => r.decision !== 'reject_always')];
}
const lc = (s) => String(s ?? '').toLowerCase();
const EXEC_NAME = /execute|bash|shell|terminal|run_command/;
const EDIT_NAME = /edit|write|apply_diff|insert_content|search_and_replace|create_|notebook/;
function toolInfo(tc) {
  const kind = lc(tc.kind), name = lc(tc.name || tc.toolName), title = String(tc.title || tc.kind || 'unknown tool');
  const raw = tc.rawInput ?? tc.raw_input ?? tc.input ?? null;
  const isMcp = name.startsWith('mcp__') || kind === 'mcp';
  const isEdit = !isMcp && (kind === 'edit' || kind === 'write' || EDIT_NAME.test(name));
  const isExec = !isMcp && !isEdit && (kind === 'execute' || EXEC_NAME.test(name) || /^run(:| |ning)/i.test(title) || (raw && typeof raw === 'object' && 'command' in raw));
  return { kind, name, title, raw, isMcp, isEdit, isExec };
}
// What a rule is matched against: the COMMAND for shell tools (not just the title, which
// can truncate), MCP arguments for MCP tools, the title otherwise. Edit/write tools only
// ever match the `*` catch-all: a file whose body mentions `curl ` does not run curl.
function haystack(ti) {
  const parts = [ti.title];
  const r = ti.raw;
  if (ti.isExec) {
    if (typeof r === 'string') parts.push(r);
    else if (r && typeof r === 'object') for (const k of ['command', 'cmd', 'commands', 'args', 'argv', 'script']) if (r[k] != null) parts.push(typeof r[k] === 'string' ? r[k] : JSON.stringify(r[k]));
  } else if (ti.isMcp) {
    parts.push(ti.name || ti.kind);
    try { parts.push(JSON.stringify(r).slice(0, 2048)); } catch {}
  }
  return lc(parts.join(' '));
}
function decide(rules, ti) {
  const hay = haystack(ti);
  for (const r of rules) {
    const m = String(r.match ?? '');
    if (m === '*' || (!ti.isEdit && m && hay.includes(lc(m)))) return r;
  }
  return null;
}
function pickOption(options, decision, ti) {
  // ACP "always" is keyed by tool NAME and the shell is one generic tool: allow_always on a
  // command would blanket-approve every later command, rejects included. Downgrade it.
  if (decision === 'allow_always' && ti.isExec) { say(`policy: allow_always downgraded to allow for shell tool`); decision = 'allow'; }
  const want = { allow: 'allow_once', allow_always: 'allow_always', reject: 'reject_once', reject_always: 'reject_always' }[decision] || 'reject_once';
  const side = want.startsWith('allow') ? 'allow' : 'reject';
  return options.find((o) => o.kind === want) || options.find((o) => (o.kind || '').startsWith(side)) || null;
}

// ---- permissions (FIFO queue: Bob can fire several requests back-to-back) ----
const permQueue = []; // [{rpcId, title, options, ti}]
function syncPermState() {
  const head = permQueue[0];
  state.pendingPermission = head
    ? { title: head.title, queued: permQueue.length, options: head.options.map((o) => ({ optionId: o.optionId, kind: o.kind, name: o.name })) }
    : null;
  saveState();
}
function answerPermission(c) {
  if (!permQueue.length) { say('!! control answer but no pending permission'); return; }
  const { rpcId, title, options, ti } = permQueue[0];
  let opt = null;
  if (c.cmd === 'answer') opt = options.find((o) => o.optionId === c.optionId);
  else opt = pickOption(options, c.cmd, ti);
  if (!opt) { say(`!! no matching option for ${JSON.stringify(c)} among ${options.map((o) => o.kind + ':' + o.optionId).join(', ')}`); return; }
  say(`PERMISSION answered [${title.slice(0, 60)}]: ${opt.kind || opt.optionId}`);
  if ((opt.kind || '').startsWith('allow')) perm.manual_allow++; else perm.manual_reject++;
  send({ jsonrpc: '2.0', id: rpcId, result: { outcome: { outcome: 'selected', optionId: opt.optionId } } });
  permQueue.shift(); syncPermState();
  if (permQueue.length) say(`PERMISSION pending (next of ${permQueue.length}): ${permQueue[0].title} | options: ${permQueue[0].options.map((o) => o.kind || o.optionId).join(', ')}`);
}
function onPermissionRequest(m) {
  const tc = m.params?.toolCall || m.params?.tool_call || {};
  const ti = toolInfo(tc);
  const title = ti.title.slice(0, 160);
  const options = m.params?.options || [];
  const rule = decide(loadPolicy(), ti);
  if (rule && permQueue.length === 0) { // keep strict FIFO: never answer past a queued human request
    const opt = pickOption(options, rule.decision, ti);
    if (opt) {
      const allowed = (opt.kind || '').startsWith('allow');
      if (allowed) perm.auto_allow++; else perm.auto_reject++;
      say(`PERMISSION auto (policy "${rule.match}"${ti.isEdit ? ', edit tool' : ''}): ${title} -> ${opt.kind}`);
      state.permissionsAsked.push(`[auto:${opt.kind}] ${title}`); saveState();
      send({ jsonrpc: '2.0', id: m.id, result: { outcome: { outcome: 'selected', optionId: opt.optionId } } });
      return;
    }
    say(`!! policy "${rule.match}" matched but no usable option among ${options.map((o) => o.kind).join(',')}`);
  }
  permQueue.push({ rpcId: m.id, title, options, ti });
  state.permissionsAsked.push(title); syncPermState();
  say(`PERMISSION pending (${permQueue.length} queued): ${title} | options: ${options.map((o) => o.kind || o.optionId).join(', ')} | answer via control.jsonl`);
}

// ---- protocol ----
// ids: 1 initialize, 2 session/new, 3 session/resume, 4 session/set_mode, 5 session/prompt
const isUntrusted = (e) => /-32600|not trusted/i.test(JSON.stringify(e || ''));
let trustRetried = false;
let buf = '', textCol = 0, finalText = '';
function sendNew() {
  // Bob Shell >= 2.0.6: _meta["bob/mode"] sets the starting mode on session/new.
  send({ jsonrpc: '2.0', id: 2, method: 'session/new', params: { cwd, mcpServers: [], _meta: { 'bob/mode': modeId } } });
}
p.stdout.on('data', (d) => {
  buf += d.toString(); let i;
  while ((i = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, i); buf = buf.slice(i + 1);
    if (!line.trim()) continue;
    appendFileSync(EVENTS, line + '\n');
    let m; try { m = JSON.parse(line); } catch { continue; }
    state.lastEventAt = new Date().toISOString();

    // server -> client requests
    if (m.method && m.id !== undefined) {
      if (m.method === 'session/request_permission') onPermissionRequest(m);
      else send({ jsonrpc: '2.0', id: m.id, error: { code: -32601, message: `${m.method} not supported by turn.mjs` } });
      continue;
    }

    // notifications
    if (m.method === 'session/update') {
      const u = m.params?.update || {}; const k = u.sessionUpdate;
      if (k === 'agent_message_chunk' || k === 'agent_thought_chunk') {
        const t = u.content?.text || '';
        appendFileSync(TEXT, (k === 'agent_thought_chunk' && textCol === 0 ? '[thought] ' : '') + t);
        if (k === 'agent_message_chunk') finalText = (finalText + t).slice(-2000);
        textCol = t.endsWith('\n') ? 0 : 1;
      } else if (k === 'tool_call') {
        const title = (u.title || u.kind || '').slice(0, 140);
        state.toolCalls.push(title);
        for (const loc of u.locations || []) {
          if (loc.path && !state.filesTouched.includes(loc.path)) state.filesTouched.push(loc.path);
        }
        saveState();
        say(`tool: ${title}`);
      } else if (k === 'tool_call_update') {
        if (u.status === 'failed') say(`!! tool FAILED: ${(u.title || '').slice(0, 120)}`);
      } else if (k === 'plan') {
        const es = u.entries || [];
        say(`plan: ${es.map((e) => `[${e.status === 'completed' ? 'x' : e.status === 'in_progress' ? '>' : ' '}] ${(e.content || '').slice(0, 60)}`).join(' | ')}`);
      } else if (k === 'current_mode_update') { state.currentMode = u.currentModeId; saveState(); say(`mode -> ${u.currentModeId}`); }
      continue;
    }

    // responses to our requests
    if (m.id === 1) { // initialize
      if (m.error) { lastError = JSON.stringify(m.error); say(`!! initialize error: ${lastError.slice(0, 300)}`); finish('init_error', 1); continue; }
      state.phase = 'initialized'; saveState();
      if (resumeId) send({ jsonrpc: '2.0', id: 3, method: 'session/resume', params: { sessionId: resumeId, cwd, mcpServers: [] } });
      else sendNew();
      continue;
    }
    if (m.id === 2) { // session/new
      if (m.error) {
        // `--trust` writes the trust store async; the first session/new can beat it (-32600).
        if (isUntrusted(m.error) && !trustRetried) {
          trustRetried = true; say(`session/new untrusted race (${JSON.stringify(m.error).slice(0, 120)}) -- retrying once in 1s`);
          setTimeout(sendNew, 1000); continue;
        }
        lastError = JSON.stringify(m.error); say(`!! session/new error: ${lastError.slice(0, 300)}`); finish('session_error', 1); continue;
      }
      if (trustRetried) say('session/new retry succeeded');
      state.sessionId = m.result.sessionId;
      const modes = m.result.modes?.availableModes || [];
      const cur = m.result.modes?.currentModeId || null;
      state.currentMode = cur; saveState();
      say(`session ${state.sessionId} | currentMode=${cur} | modes: ${modes.map((x) => x.id).join(',')}`);
      const target = modes.find((x) => x.id === modeId); // EXACT id only (contains-match trap)
      if (cur === modeId) { state.modeSetVia = '_meta'; saveState(); say(`mode ${modeId} set via _meta`); startPrompt(); }
      else if (target) {
        state.modeSetVia = 'set_mode'; saveState();
        say(`_meta bob/mode ignored (current=${cur}) -- falling back to session/set_mode ${modeId}`);
        send({ jsonrpc: '2.0', id: 4, method: 'session/set_mode', params: { sessionId: state.sessionId, modeId } });
      } else { say(`!! mode '${modeId}' not found, using ${cur}`); startPrompt(); }
      continue;
    }
    if (m.id === 3) { // session/resume
      if (m.error) { lastError = JSON.stringify(m.error); say(`!! resume failed: ${lastError.slice(0, 200)}`); finish('resume_error', 1); }
      else if (modeExplicit) { // mode switch on resumed sessions too
        state.modeSetVia = 'set_mode'; saveState();
        say(`resumed ${state.sessionId}, switching mode -> ${modeId}`);
        send({ jsonrpc: '2.0', id: 4, method: 'session/set_mode', params: { sessionId: state.sessionId, modeId } });
      } else { state.currentMode = m.result?.modes?.currentModeId || null; saveState(); say(`resumed ${state.sessionId}`); startPrompt(); }
      continue;
    }
    if (m.id === 4) { // session/set_mode
      if (m.error) say(`!! set_mode failed: ${JSON.stringify(m.error).slice(0, 200)}`);
      else { state.currentMode = modeId; saveState(); say('mode set'); }
      startPrompt(); continue;
    }
    if (m.id === 5) { // prompt turn finished
      if (m.error) {
        lastError = JSON.stringify(m.error);
        say(`!! prompt error: ${lastError.slice(0, 300)}`);
        // -32603 blip: check whether the work landed, then --resume; do not redo landed work.
        finish(m.error.code === -32603 ? 'backend_error' : 'error', 0);
      } else finish(m.result?.stopReason || 'end_turn');
      continue;
    }
  }
});
function startPrompt() {
  state.phase = 'running'; saveState();
  const content = [{ type: 'text', text: promptText }];
  if (imagePath) {
    const ext = imagePath.split('.').pop().toLowerCase();
    const mime = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp' }[ext] || 'image/png';
    content.push({ type: 'image', mimeType: mime, data: readFileSync(imagePath).toString('base64') });
    say(`image attached: ${imagePath} (${mime})`);
  }
  send({ jsonrpc: '2.0', id: 5, method: 'session/prompt', params: { sessionId: state.sessionId, prompt: content } });
}
p.on('error', (e) => { lastError = String(e); say(`!! cannot start bob: ${e.message}`); finish('process_exit', 1); });
p.on('exit', (c) => { if (!done) { lastError = `bob acp exited ${c}`; say(`!! bob acp exited ${c}`); finish('process_exit', 1); } });
send({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: 1, clientCapabilities: { fs: { readTextFile: false, writeTextFile: false } } } });
setTimeout(() => { if (!done) { say('!! HARD TIMEOUT 45min'); finish('timeout', 1); } }, 2700000);
