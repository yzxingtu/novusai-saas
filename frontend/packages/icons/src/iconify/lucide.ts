import { addCollection } from '@vben-core/icons';

import {
  LUCIDE_ICON_IDS,
  LUCIDE_ICON_NAMES,
  LUCIDE_ICON_SUBSET,
} from './lucide-subset.generated';

const LUCIDE_ICON_ID_PATTERN = /^lucide:[a-z0-9-]+$/;
const lucideSubsetIconIds = new Set<string>(LUCIDE_ICON_IDS);

let lucideCatalogIconIds: readonly string[] = LUCIDE_ICON_IDS;
let lucideCatalogIconIdsSet = new Set<string>(LUCIDE_ICON_IDS);
let lucideCatalogRegistered = false;
let lucideCatalogPromise: null | Promise<readonly string[]> = null;
let lucideSubsetRegistered = false;

function normalizeLucideIconId(icon: string): string {
  const raw = icon.trim();
  if (!raw) {
    return '';
  }

  const normalized = raw.startsWith('lucide:') ? raw.slice(7) : raw;
  return normalized ? `lucide:${normalized}` : '';
}

function isLucideIconId(icon: null | string | undefined): icon is string {
  return !!icon && LUCIDE_ICON_ID_PATTERN.test(icon.trim());
}

function isLucideSubsetIconId(icon: null | string | undefined): boolean {
  if (!icon) {
    return false;
  }

  return lucideSubsetIconIds.has(normalizeLucideIconId(icon));
}

function isLucideCatalogIconId(icon: null | string | undefined): boolean {
  if (!icon) {
    return false;
  }

  return lucideCatalogIconIdsSet.has(normalizeLucideIconId(icon));
}

function ensureLucideIconSubsetRegistered(): void {
  if (lucideSubsetRegistered) {
    return;
  }

  addCollection(LUCIDE_ICON_SUBSET);
  lucideSubsetRegistered = true;
}

async function ensureLucideIconCatalogRegistered(): Promise<readonly string[]> {
  ensureLucideIconSubsetRegistered();

  if (lucideCatalogRegistered) {
    return lucideCatalogIconIds;
  }

  if (!lucideCatalogPromise) {
    lucideCatalogPromise = import('./lucide-catalog.generated').then((module) => {
      addCollection(module.LUCIDE_ICON_CATALOG);
      lucideCatalogIconIds = module.LUCIDE_CATALOG_ICON_IDS;
      lucideCatalogIconIdsSet = new Set(module.LUCIDE_CATALOG_ICON_IDS);
      lucideCatalogRegistered = true;

      return lucideCatalogIconIds;
    });
  }

  return lucideCatalogPromise;
}

function getLucideSubsetIconIds(): readonly string[] {
  return LUCIDE_ICON_IDS;
}

function getLucideSubsetIconNames(): readonly string[] {
  return LUCIDE_ICON_NAMES;
}

export {
  ensureLucideIconCatalogRegistered,
  ensureLucideIconSubsetRegistered,
  isLucideCatalogIconId,
  isLucideIconId,
  isLucideSubsetIconId,
  getLucideSubsetIconIds,
  getLucideSubsetIconNames,
  normalizeLucideIconId,
};
