import { execFileSync, spawn } from 'node:child_process';
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, '../..');
const repoRoot = path.resolve(frontendRoot, '..');
const vendorBase = path.join(frontendRoot, '.vendor', 'vue-vben-admin');

function parseArgs(argv) {
  const parsed = {
    force: false,
    tag: '',
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--force') {
      parsed.force = true;
      continue;
    }
    if (arg === '--tag') {
      parsed.tag = argv[index + 1] ?? '';
      index += 1;
      continue;
    }
    if (arg === '--help' || arg === '-h') {
      parsed.help = true;
      continue;
    }
  }

  return parsed;
}

function runGit(args, options = {}) {
  return execFileSync('git', args, {
    cwd: repoRoot,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    ...options,
  }).trim();
}

function ensureTag(tag) {
  try {
    return runGit(['rev-parse', '--verify', `${tag}^{commit}`]);
  } catch {
    try {
      runGit(['remote', 'get-url', 'upstream']);
    } catch {
      throw new Error(
        "Missing 'upstream' remote. Add it before syncing snapshots.",
      );
    }

    runGit(['fetch', 'upstream', `refs/tags/${tag}:refs/tags/${tag}`]);
    return runGit(['rev-parse', '--verify', `${tag}^{commit}`]);
  }
}

function usage() {
  console.log(
    'Usage: node ./scripts/vben/sync-upstream.mjs --tag <tag> [--force]',
  );
}

async function archiveTagToDir(tag, targetDir) {
  const archiveProc = spawn('git', ['archive', '--format=tar', tag], {
    cwd: repoRoot,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const tarProc = spawn('tar', ['-xf', '-', '-C', targetDir], {
    cwd: repoRoot,
    stdio: ['pipe', 'ignore', 'pipe'],
  });

  archiveProc.stdout.pipe(tarProc.stdin);

  let archiveStderr = '';
  let tarStderr = '';

  archiveProc.stderr.on('data', (chunk) => {
    archiveStderr += chunk.toString();
  });
  tarProc.stderr.on('data', (chunk) => {
    tarStderr += chunk.toString();
  });

  const waitForExit = (proc, label) =>
    new Promise((resolve, reject) => {
      proc.on('error', reject);
      proc.on('close', (code) => {
        if (code === 0) {
          resolve();
          return;
        }
        reject(
          new Error(
            `${label} exited with code ${code}: ${
              label === 'git archive' ? archiveStderr.trim() : tarStderr.trim()
            }`,
          ),
        );
      });
    });

  await Promise.all([
    waitForExit(archiveProc, 'git archive'),
    waitForExit(tarProc, 'tar extract'),
  ]);
}

const args = parseArgs(process.argv.slice(2));
if (args.help || !args.tag) {
  usage();
  process.exit(args.help ? 0 : 1);
}

const commit = ensureTag(args.tag);
const targetDir = path.join(vendorBase, args.tag);

if (existsSync(targetDir)) {
  if (!args.force) {
    console.log(`[vben-sync] Snapshot already exists: ${targetDir}`);
    process.exit(0);
  }
  rmSync(targetDir, { force: true, recursive: true });
}

mkdirSync(targetDir, { recursive: true });

await archiveTagToDir(args.tag, targetDir);

writeFileSync(
  path.join(targetDir, '.snapshot-meta.json'),
  JSON.stringify(
    {
      commit,
      generated_at: new Date().toISOString(),
      source_remote: 'upstream',
      tag: args.tag,
    },
    null,
    2,
  ),
);

console.log(`[vben-sync] Snapshot ready: ${targetDir}`);
