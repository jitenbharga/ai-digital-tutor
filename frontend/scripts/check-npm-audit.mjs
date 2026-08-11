#!/usr/bin/env node
/**
 * MF-1 — frontend dependency-audit gate.
 *
 * Fails CI on HIGH/CRITICAL advisories affecting shipped RUNTIME dependencies.
 * The audit is scoped with `--omit=dev`, so dev-only tooling advisories
 * (vitest / vite / esbuild transitive CVEs) — which never reach the browser —
 * do not block the build.
 *
 * ALLOWLIST: runtime advisories explicitly accepted, each with a justification
 * and an owner-visible reason. Keep this list SHORT and re-check every entry
 * whenever dependencies are upgraded.
 */
import { execSync } from 'node:child_process';

const ALLOWLIST = [
  {
    id: 'GHSA-qwww-vcr4-c8h2',
    pkg: 'react-router',
    reason:
      "RSC Mode CSRF Bypass (react-router 7.12.0-<8.3.0). This app is a Vite SPA " +
      'that uses declarative <BrowserRouter>/<Routes> only and does NOT use ' +
      "react-router's RSC / framework (server) mode, so the vulnerable code path " +
      'is unreachable. Remaining on 7.18.2 fixes the reachable open-redirect/XSS ' +
      'advisory (GHSA affecting <=7.17.0); no CSRF-patched version >=8.3.0 is ' +
      'published yet. Re-evaluate and remove this entry once one ships.',
  },
];

const allow = new Set(ALLOWLIST.map((a) => a.id));

function runAudit() {
  try {
    const out = execSync('npm audit --omit=dev --json', {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    });
    return JSON.parse(out);
  } catch (err) {
    // npm audit exits non-zero when advisories exist; the JSON is still on stdout.
    if (err.stdout) return JSON.parse(err.stdout.toString());
    throw err;
  }
}

const report = runAudit();
const vulns = report.vulnerabilities || {};
const blocking = [];

for (const [name, v] of Object.entries(vulns)) {
  if (v.severity !== 'high' && v.severity !== 'critical') continue;
  // GHSA ids attached directly to this advisory (object `via` entries). String
  // `via` entries are transitive references that carry no new GHSA of their own
  // and clear automatically once the upstream advisory is allowlisted.
  const ghsas = (v.via || [])
    .filter((x) => x && typeof x === 'object' && x.url)
    .map((x) => String(x.url).split('/').pop());
  if (ghsas.length === 0) continue;
  const unresolved = ghsas.filter((g) => !allow.has(g));
  if (unresolved.length) blocking.push({ name, severity: v.severity, ghsas: unresolved });
}

if (blocking.length) {
  console.error('❌ npm audit gate: unallowlisted high/critical runtime advisories:');
  for (const b of blocking) {
    console.error(`   - ${b.name} (${b.severity}): ${b.ghsas.join(', ')}`);
  }
  console.error(
    '\nRemediate by upgrading the dependency, or add an explicit, justified ' +
      'ALLOWLIST entry in frontend/scripts/check-npm-audit.mjs.',
  );
  process.exit(1);
}

console.log('✅ npm audit gate passed: no unallowlisted high/critical runtime advisories.');
for (const a of ALLOWLIST) console.log(`   (allowlisted) ${a.pkg} — ${a.id}`);
