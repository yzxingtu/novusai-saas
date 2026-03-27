import { createHash } from 'node:crypto';
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, '../..');
const vendorBase = path.join(frontendRoot, '.vendor', 'vue-vben-admin');
const reportsDir = path.join(frontendRoot, 'docs', 'upgrade', 'reports');

const TRACKED_TOP_LEVEL_DIRS = new Set([
  'apps',
  'internal',
  'packages',
  'playground',
  'scripts',
]);

const TRACKED_TOP_LEVEL_FILES = new Set([
  '.browserslistrc',
  '.commitlintrc.js',
  '.dockerignore',
  '.editorconfig',
  '.gitattributes',
  '.gitconfig',
  '.gitignore',
  '.gitpod.yml',
  '.node-version',
  '.npmrc',
  '.prettierignore',
  '.prettierrc.mjs',
  '.stylelintignore',
  'cspell.json',
  'eslint.config.mjs',
  'lefthook.yml',
  'LICENSE',
  'package.json',
  'pnpm-lock.yaml',
  'pnpm-workspace.yaml',
  'README.ja-JP.md',
  'README.md',
  'README.zh-CN.md',
  'stylelint.config.mjs',
  'turbo.json',
  'vitest.config.ts',
  'vitest.workspace.ts',
]);

const IGNORED_DIR_NAMES = new Set([
  '.git',
  '.turbo',
  '.vendor',
  'dist',
  'node_modules',
]);

function parseArgs(argv) {
  const parsed = {
    from: '',
    output: '',
    to: '',
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--from') {
      parsed.from = argv[index + 1] ?? '';
      index += 1;
      continue;
    }
    if (arg === '--output') {
      parsed.output = argv[index + 1] ?? '';
      index += 1;
      continue;
    }
    if (arg === '--to') {
      parsed.to = argv[index + 1] ?? '';
      index += 1;
      continue;
    }
    if (arg === '--help' || arg === '-h') {
      parsed.help = true;
    }
  }

  return parsed;
}

function usage() {
  console.log(
    'Usage: node ./scripts/vben/diff-upstream.mjs --from <old-tag> --to <new-tag> [--output <report.md>]',
  );
}

function normalizePath(filePath) {
  return filePath.split(path.sep).join('/');
}

function shouldTrack(relativePath) {
  const normalized = normalizePath(relativePath);
  const [firstSegment] = normalized.split('/');
  return (
    TRACKED_TOP_LEVEL_DIRS.has(firstSegment) ||
    TRACKED_TOP_LEVEL_FILES.has(normalized)
  );
}

function walkFiles(rootDir, currentDir = rootDir, files = []) {
  for (const entry of readdirSync(currentDir)) {
    const absolutePath = path.join(currentDir, entry);
    const relativePath = path.relative(rootDir, absolutePath);
    const stat = statSync(absolutePath);

    if (stat.isDirectory()) {
      if (IGNORED_DIR_NAMES.has(entry)) {
        continue;
      }
      walkFiles(rootDir, absolutePath, files);
      continue;
    }

    if (shouldTrack(relativePath)) {
      files.push(normalizePath(relativePath));
    }
  }

  return files;
}

function createFileMap(rootDir) {
  const map = new Map();
  const files = walkFiles(rootDir);

  for (const relativePath of files) {
    const absolutePath = path.join(rootDir, relativePath);
    const content = readFileSync(absolutePath);
    const hash = createHash('sha1').update(content).digest('hex');
    map.set(relativePath, hash);
  }

  return map;
}

function diffMaps(leftMap, rightMap) {
  const added = [];
  const changed = [];
  const removed = [];

  for (const [filePath, hash] of rightMap.entries()) {
    if (!leftMap.has(filePath)) {
      added.push(filePath);
      continue;
    }
    if (leftMap.get(filePath) !== hash) {
      changed.push(filePath);
    }
  }

  for (const filePath of leftMap.keys()) {
    if (!rightMap.has(filePath)) {
      removed.push(filePath);
    }
  }

  added.sort();
  changed.sort();
  removed.sort();

  return { added, changed, removed };
}

function classifyPath(filePath) {
  if (
    filePath === 'apps/web-antd/vite.config.mts' ||
    filePath === 'apps/web-antd/src/composables/use-plugin-frontend-init.ts' ||
    filePath.startsWith('apps/web-antd/build/') ||
    filePath.startsWith('apps/web-antd/src/utils/plugin-')
  ) {
    return 'novus_bridge_owned';
  }

  if (
    filePath.startsWith('apps/web-antd/src/components/business/') ||
    filePath.startsWith('apps/web-antd/src/views/') ||
    filePath.startsWith('apps/web-antd/src/api/') ||
    filePath.startsWith('apps/web-antd/src/store/') ||
    filePath.startsWith('apps/web-antd/src/locales/')
  ) {
    return 'product_owned';
  }

  if (
    filePath === 'apps/web-antd/package.json' ||
    filePath === 'apps/web-antd/vite.config.mts' ||
    filePath === 'packages/@core/preferences/src/config.ts' ||
    filePath === 'packages/@core/base/shared/src/constants/vben.ts' ||
    filePath === 'packages/effects/layouts/src/basic/copyright/copyright.vue' ||
    filePath === 'packages/effects/common-ui/src/ui/about/about.vue' ||
    filePath === 'playground/__tests__/e2e/auth-login.spec.ts' ||
    filePath === 'scripts/generate-lucide-subset.mjs'
  ) {
    return 'always_review';
  }

  return 'upstream_owned';
}

function summarizeByArea(diff) {
  const summary = new Map([
    ['always_review', 0],
    ['novus_bridge_owned', 0],
    ['product_owned', 0],
    ['upstream_owned', 0],
  ]);

  for (const filePath of [...diff.added, ...diff.changed, ...diff.removed]) {
    const area = classifyPath(filePath);
    summary.set(area, (summary.get(area) ?? 0) + 1);
  }

  return summary;
}

function formatSummaryTable(summary) {
  return [
    '| Area | Changed Files |',
    '| --- | ---: |',
    ...[...summary.entries()].map(([area, count]) => `| ${area} | ${count} |`),
  ].join('\n');
}

function formatSampleList(title, items, limit = 40) {
  if (items.length === 0) {
    return `### ${title}\n\n- none\n`;
  }

  const visible = items.slice(0, limit).map((item) => `- \`${item}\``);
  const remainder =
    items.length > limit ? [`- ... and ${items.length - limit} more`] : [];

  return `### ${title}\n\n${[...visible, ...remainder].join('\n')}\n`;
}

function existsOrThrow(targetPath, label) {
  if (!existsSync(targetPath)) {
    throw new Error(`Missing ${label}: ${targetPath}`);
  }
}

const args = parseArgs(process.argv.slice(2));
if (args.help || !args.from || !args.to) {
  usage();
  process.exit(args.help ? 0 : 1);
}

const fromSnapshot = path.join(vendorBase, args.from);
const toSnapshot = path.join(vendorBase, args.to);
existsOrThrow(fromSnapshot, `snapshot ${args.from}`);
existsOrThrow(toSnapshot, `snapshot ${args.to}`);

const outputPath =
  args.output || path.join(reportsDir, `vben-${args.from}-to-${args.to}.md`);

mkdirSync(path.dirname(outputPath), { recursive: true });

const fromMap = createFileMap(fromSnapshot);
const toMap = createFileMap(toSnapshot);
const localMap = createFileMap(frontendRoot);

const upstreamDelta = diffMaps(fromMap, toMap);
const localVsBase = diffMaps(fromMap, localMap);
const localVsTarget = diffMaps(toMap, localMap);

const p0Paths = [
  'package.json',
  'pnpm-workspace.yaml',
  'pnpm-lock.yaml',
  'apps/web-antd/package.json',
  'apps/web-antd/vite.config.mts',
  'apps/web-antd/build/vite-plugin-novus-plugins.ts',
  'apps/web-antd/src/utils/plugin-loader.ts',
  'apps/web-antd/src/utils/plugin-shared.ts',
  'apps/web-antd/src/composables/use-plugin-frontend-init.ts',
];

const reportLines = [
  '# Vben Upgrade Diff Report',
  '',
  `- Generated at: ${new Date().toISOString()}`,
  `- Tracking base tag: \`${args.from}\``,
  `- Target upstream tag: \`${args.to}\``,
  `- Local frontend root: \`${frontendRoot}\``,
  `- Base snapshot: \`${fromSnapshot}\``,
  `- Target snapshot: \`${toSnapshot}\``,
  '',
  '## Upstream Delta',
  '',
  formatSummaryTable(summarizeByArea(upstreamDelta)),
  '',
  formatSampleList('Upstream Added', upstreamDelta.added),
  formatSampleList('Upstream Changed', upstreamDelta.changed),
  formatSampleList('Upstream Removed', upstreamDelta.removed),
  '## Local Divergence From Tracking Base',
  '',
  formatSummaryTable(summarizeByArea(localVsBase)),
  '',
  formatSampleList('Local Added Vs Base', localVsBase.added),
  formatSampleList('Local Changed Vs Base', localVsBase.changed),
  formatSampleList('Local Missing Vs Base', localVsBase.removed),
  '## Local Divergence From Target',
  '',
  formatSummaryTable(summarizeByArea(localVsTarget)),
  '',
  formatSampleList('Local Added Vs Target', localVsTarget.added),
  formatSampleList('Local Changed Vs Target', localVsTarget.changed),
  formatSampleList('Local Missing Vs Target', localVsTarget.removed),
  '## P0 Focus Paths',
  '',
  ...p0Paths.map((filePath) => {
    const changedUpstream =
      upstreamDelta.added.includes(filePath) ||
      upstreamDelta.changed.includes(filePath) ||
      upstreamDelta.removed.includes(filePath);
    const divergesFromTarget =
      localVsTarget.added.includes(filePath) ||
      localVsTarget.changed.includes(filePath) ||
      localVsTarget.removed.includes(filePath);
    return `- \`${filePath}\`: upstream_changed=${changedUpstream}, local_diverges_from_target=${divergesFromTarget}`;
  }),
  '',
];

writeFileSync(outputPath, `${reportLines.join('\n').trim()}\n`);

console.log(`[vben-diff] Report written: ${outputPath}`);
