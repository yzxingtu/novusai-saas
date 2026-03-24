import { createRequire } from 'node:module';
import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(SCRIPT_DIR, '..');
const REPO_ROOT = resolve(FRONTEND_ROOT, '..');
const APP_REQUIRE = createRequire(
  resolve(FRONTEND_ROOT, 'apps/web-antd/package.json'),
);
const SUBSET_OUTPUT_FILE = resolve(
  FRONTEND_ROOT,
  'packages/icons/src/iconify/lucide-subset.generated.ts',
);
const CATALOG_OUTPUT_FILE = resolve(
  FRONTEND_ROOT,
  'packages/icons/src/iconify/lucide-catalog.generated.ts',
);

const SCAN_ROOTS = [
  resolve(FRONTEND_ROOT, 'apps/web-antd/src'),
  resolve(FRONTEND_ROOT, 'playground/src'),
  resolve(FRONTEND_ROOT, 'packages'),
  resolve(REPO_ROOT, 'backend/app'),
  resolve(REPO_ROOT, 'backend/plugins'),
];

const EXCLUDED_SEGMENTS = new Set([
  '.backups',
  '.git',
  '.idea',
  '.turbo',
  '__pycache__',
  '__tests__',
  'dist',
  'docs',
  'migrations',
  'node_modules',
  'playground',
  'test',
  'tests',
]);

const ALLOWED_EXTENSIONS = new Set([
  '.py',
  '.ts',
  '.tsx',
  '.vue',
  '.yaml',
  '.yml',
]);

const LUCIDE_ICON_ID_PATTERN = /lucide:([a-z0-9-]+)/g;
const EXCLUDED_FILE_NAMES = new Set([
  'lucide-catalog.generated.ts',
  'lucide-subset.generated.ts',
]);

const BARE_ICON_RULES = [
  {
    file: resolve(REPO_ROOT, 'backend/plugins/weather-widget/frontend/src/weather-codes.ts'),
    pattern: /\b(?:icon|nightIcon)\s*:\s*'([a-z0-9-]+)'/g,
  },
];

function shouldSkipPath(pathname) {
  return pathname
    .split(/[\\/]+/)
    .some((segment) => EXCLUDED_SEGMENTS.has(segment));
}

function walkFiles(rootDir) {
  if (shouldSkipPath(rootDir)) {
    return [];
  }

  const queue = [rootDir];
  const files = [];

  while (queue.length > 0) {
    const currentDir = queue.pop();
    const entries = readdirSync(currentDir, { withFileTypes: true });

    for (const entry of entries) {
      const absolutePath = join(currentDir, entry.name);
      if (shouldSkipPath(absolutePath)) {
        continue;
      }

      if (EXCLUDED_FILE_NAMES.has(entry.name)) {
        continue;
      }

      if (entry.isDirectory()) {
        queue.push(absolutePath);
        continue;
      }

      if (!ALLOWED_EXTENSIONS.has(extname(entry.name))) {
        continue;
      }

      files.push(absolutePath);
    }
  }

  return files;
}

function collectMatches(text, pattern, names) {
  for (const match of text.matchAll(pattern)) {
    const iconName = match[1]?.trim();
    if (iconName) {
      names.add(iconName);
    }
  }
}

function sortObjectEntries(record) {
  return Object.fromEntries(
    Object.entries(record).sort(([left], [right]) => left.localeCompare(right)),
  );
}

function resolveLucideIconsJsonPath() {
  const resolvers = [
    () => require.resolve('@iconify-json/lucide/icons.json'),
    () => APP_REQUIRE.resolve('@iconify-json/lucide/icons.json'),
    () =>
      resolve(
        FRONTEND_ROOT,
        'apps/web-antd/node_modules/@iconify-json/lucide/icons.json',
      ),
  ];

  for (const resolver of resolvers) {
    try {
      const candidate = resolver();
      if (candidate) {
        return candidate;
      }
    } catch {
      // Try the next resolver / 尝试下一个解析路径
    }
  }

  throw new Error(
    'Cannot resolve @iconify-json/lucide/icons.json from frontend root or apps/web-antd workspace',
  );
}

function main() {
  const lucideJsonPath = resolveLucideIconsJsonPath();
  const lucideJson = JSON.parse(readFileSync(lucideJsonPath, 'utf8'));
  const iconNames = new Set();

  for (const scanRoot of SCAN_ROOTS) {
    if (!statSync(scanRoot).isDirectory()) {
      continue;
    }

    for (const filePath of walkFiles(scanRoot)) {
      const text = readFileSync(filePath, 'utf8');
      collectMatches(text, LUCIDE_ICON_ID_PATTERN, iconNames);
    }
  }

  for (const rule of BARE_ICON_RULES) {
    const text = readFileSync(rule.file, 'utf8');
    collectMatches(text, rule.pattern, iconNames);
  }

  const requestedIconNames = [...iconNames].sort((left, right) =>
    left.localeCompare(right),
  );
  const catalogIconNames = [
    ...new Set([
      ...Object.keys(lucideJson.aliases ?? {}),
      ...Object.keys(lucideJson.icons ?? {}),
    ]),
  ].sort((left, right) => left.localeCompare(right));

  const resolvedIcons = {};
  const resolvedAliases = {};
  const missingNames = [];
  const resolving = new Set();

  function resolveIcon(name) {
    if (resolvedIcons[name] || resolvedAliases[name]) {
      return;
    }
    if (resolving.has(name)) {
      return;
    }

    resolving.add(name);

    if (lucideJson.icons?.[name]) {
      resolvedIcons[name] = lucideJson.icons[name];
      resolving.delete(name);
      return;
    }

    if (lucideJson.aliases?.[name]) {
      const alias = lucideJson.aliases[name];
      resolvedAliases[name] = alias;
      if (alias.parent) {
        resolveIcon(alias.parent);
      }
      resolving.delete(name);
      return;
    }

    missingNames.push(name);
    resolving.delete(name);
  }

  for (const iconName of requestedIconNames) {
    resolveIcon(iconName);
  }

  if (missingNames.length > 0) {
    throw new Error(
      `Unknown lucide icon names: ${missingNames.join(', ')}`,
    );
  }

  const subsetOutput = `/* eslint-disable */
// Generated by frontend/scripts/generate-lucide-subset.mjs / 脚本生成
// Do not edit manually. / 请勿手改

export const LUCIDE_ICON_NAMES = ${JSON.stringify(requestedIconNames, null, 2)} as const;

export const LUCIDE_ICON_IDS = ${JSON.stringify(
    requestedIconNames.map((name) => `lucide:${name}`),
    null,
    2,
  )} as const;

export const LUCIDE_ICON_SUBSET = ${JSON.stringify(
    {
      aliases: sortObjectEntries(resolvedAliases),
      height: lucideJson.height,
      icons: sortObjectEntries(resolvedIcons),
      prefix: 'lucide',
      width: lucideJson.width,
    },
    null,
    2,
  )} as const;
`;

  const catalogOutput = `/* eslint-disable */
// Generated by frontend/scripts/generate-lucide-subset.mjs / 脚本生成
// Do not edit manually. / 请勿手改

export const LUCIDE_CATALOG_ICON_NAMES = ${JSON.stringify(catalogIconNames, null, 2)} as const;

export const LUCIDE_CATALOG_ICON_IDS = ${JSON.stringify(
    catalogIconNames.map((name) => `lucide:${name}`),
    null,
    2,
  )} as const;

export const LUCIDE_ICON_CATALOG = ${JSON.stringify(
    {
      aliases: sortObjectEntries(lucideJson.aliases ?? {}),
      height: lucideJson.height,
      icons: sortObjectEntries(lucideJson.icons ?? {}),
      prefix: 'lucide',
      width: lucideJson.width,
    },
    null,
    2,
  )} as const;
`;

  mkdirSync(dirname(SUBSET_OUTPUT_FILE), { recursive: true });
  writeFileSync(SUBSET_OUTPUT_FILE, subsetOutput, 'utf8');
  writeFileSync(CATALOG_OUTPUT_FILE, catalogOutput, 'utf8');

  console.log(
    `Generated lucide subset with ${requestedIconNames.length} icon ids -> ${SUBSET_OUTPUT_FILE}`,
  );
  console.log(
    `Generated lucide catalog with ${catalogIconNames.length} icon ids -> ${CATALOG_OUTPUT_FILE}`,
  );
}

main();
