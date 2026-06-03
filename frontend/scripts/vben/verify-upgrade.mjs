import { execFileSync, spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, '../..');
const repoRoot = path.resolve(frontendRoot, '..');
const reportsDir = path.join(frontendRoot, 'docs', 'upgrade', 'reports');
const reportPath = path.join(reportsDir, 'vben-verify-v5.6.0.md');
const shellCommand =
  process.platform === 'win32' ? process.env.ComSpec || 'cmd.exe' : 'sh';

function parseVersion(raw) {
  return raw
    .replace(/^v/, '')
    .split('.')
    .map((value) => Number.parseInt(value, 10));
}

function compareVersions(leftRaw, rightRaw) {
  const left = parseVersion(leftRaw);
  const right = parseVersion(rightRaw);
  const length = Math.max(left.length, right.length);

  for (let index = 0; index < length; index += 1) {
    const leftPart = left[index] ?? 0;
    const rightPart = right[index] ?? 0;
    if (leftPart > rightPart) return 1;
    if (leftPart < rightPart) return -1;
  }

  return 0;
}

function createCommand(commandLine) {
  if (process.platform === 'win32') {
    return {
      args: ['/d', '/s', '/c', commandLine],
      command: shellCommand,
      printable: commandLine,
    };
  }

  return {
    args: ['-lc', commandLine],
    command: shellCommand,
    printable: commandLine,
  };
}

function run(commandLine, label) {
  const startedAt = Date.now();
  const wrapped = createCommand(commandLine);
  const result = spawnSync(wrapped.command, wrapped.args, {
    cwd: repoRoot,
    stdio: 'inherit',
  });
  const durationSeconds = ((Date.now() - startedAt) / 1000).toFixed(1);
  const status = result.status === 0 ? 'passed' : 'failed';
  return {
    command: wrapped.printable,
    duration_seconds: durationSeconds,
    label,
    status,
  };
}

const nodeVersion = process.version;
if (compareVersions(nodeVersion, '20.19.0') < 0) {
  throw new Error(
    `Node ${nodeVersion} is below the required >=20.19.0 for vben 5.6`,
  );
}

const versionCommand = createCommand('corepack pnpm -v');
const pnpmVersion = execFileSync(versionCommand.command, versionCommand.args, {
  cwd: repoRoot,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
}).trim();

if (compareVersions(pnpmVersion, '10.28.0') < 0) {
  throw new Error(
    `PnPM ${pnpmVersion} is below the required 10.28.x baseline for vben 5.6`,
  );
}

const checks = [
  ['Install dependencies', 'corepack pnpm -C frontend install'],
  ['Type check', 'corepack pnpm -C frontend run check:type'],
  ['Lint', 'corepack pnpm -C frontend run lint'],
  ['Build web-antd', 'corepack pnpm -C frontend run build:antd'],
  ['Unit tests', 'corepack pnpm -C frontend run test:unit'],
];

const results = [];
for (const [label, commandLine] of checks) {
  const result = run(commandLine, label);
  results.push(result);
}

mkdirSync(reportsDir, { recursive: true });
const markdown = [
  '# Vben 5.6 Verification',
  '',
  `- Generated at: ${new Date().toISOString()}`,
  `- Repo root: \`${repoRoot}\``,
  `- Frontend root: \`${frontendRoot}\``,
  `- Node version: \`${nodeVersion}\``,
  `- Corepack pnpm version: \`${pnpmVersion}\``,
  '',
  '## Automated Checks',
  '',
  '| Check | Status | Duration (s) | Command |',
  '| --- | --- | ---: | --- |',
  ...results.map(
    (result) =>
      `| ${result.label} | ${result.status} | ${result.duration_seconds} | \`${result.command}\` |`,
  ),
  '',
  '## Manual Smoke Checklist',
  '',
  '- Run `corepack pnpm -C frontend run dev:antd` with backend `8000` available.',
  '- Verify `/plugin-assets`, `/plugin-public-assets`, and `/plugin-icons` return plugin resources without 404.',
  '- Open at least one admin plugin page and one tenant plugin page.',
  '- Verify plugin page refresh, login redirect, dynamic route registration, and AI panel bridge behavior.',
  '- Verify branding text, About page, and playground title assertions did not regress.',
  '',
];

writeFileSync(reportPath, `${markdown.join('\n')}\n`);

console.log(`[vben-verify] Summary written: ${reportPath}`);

if (results.some((result) => result.status !== 'passed')) {
  process.exit(1);
}
