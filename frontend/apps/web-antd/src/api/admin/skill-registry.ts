/**
 * Admin skill registry API / 平台管理端技能市场 API
 */

import { requestClient } from '#/utils/request';

const BASE_URL = '/admin/plugins/skill-registry';

export interface SkillRegistryPackageItem {
  author?: null | string;
  can_upgrade?: boolean;
  changelog?: null | string;
  description?: null | string;
  display_name?: null | string;
  docs_url?: null | string;
  download_url?: null | string;
  downloads?: number;
  homepage?: null | string;
  icon?: null | string;
  installed_version?: null | string;
  is_installed?: boolean;
  latest_version?: null | string;
  name?: null | string;
  rating?: null | number;
  readme?: null | string;
  repository_url?: null | string;
  slug: string;
  source_locked?: boolean | null;
  source_url?: null | string;
  tags?: string[];
  version?: null | string;
}

export function getSkillRegistryListApi(params?: Record<string, unknown>) {
  return requestClient.get<{ items: SkillRegistryPackageItem[]; total: number }>(
    BASE_URL,
    { params },
  );
}

export function getSkillRegistryDetailApi(slug: string) {
  return requestClient.get<SkillRegistryPackageItem>(`${BASE_URL}/${slug}`);
}

export function previewSkillRegistryInstallApi(slug: string) {
  return requestClient.post<SkillRegistryPackageItem>(
    `${BASE_URL}/${slug}/install-preview`,
  );
}

export function installSkillRegistryPackageApi(slug: string) {
  return requestClient.post<{
    package_id: number;
    package_name: string;
    registry_slug: string;
    skill_name: string;
    skill_version: string;
    status: string;
  }>(`${BASE_URL}/${slug}/install`);
}

export interface SkillRegistryUpdateItem {
  display_name: string;
  installed_version: null | string;
  latest_version: null | string;
  package_id: number;
  skill_id: number;
  slug: string;
  source_locked: boolean;
  source_url?: null | string;
}

export function getSkillRegistryUpdatesApi() {
  return requestClient.get<SkillRegistryUpdateItem[]>(`${BASE_URL}/updates`);
}

export function upgradeSkillRegistryPackageApi(slug: string) {
  return requestClient.post<{
    latest_version: null | string;
    package_id: number;
    package_name: string;
    previous_version: null | string;
    registry_slug: string;
    source_locked: boolean;
    source_url?: null | string;
    status: string;
  }>(`${BASE_URL}/${slug}/upgrade`);
}

export function previewSkillRegistryUpgradeApi(slug: string) {
  return requestClient.get<{
    can_upgrade: boolean;
    changelog?: null | string;
    display_name: string;
    download_url?: null | string;
    installed_version?: null | string;
    latest_version?: null | string;
    readme?: null | string;
    slug: string;
    source_locked: boolean;
    source_url?: null | string;
  }>(`${BASE_URL}/${slug}/upgrade-preview`);
}

export function batchUpgradeSkillRegistryPackagesApi(slugs?: string[]) {
  return requestClient.post<{
    failed: Array<{ error: string; slug: string }>;
    requested: number;
    upgraded: Array<{
      latest_version?: null | string;
      package_id: number;
      package_name: string;
      previous_version?: null | string;
      registry_slug: string;
      source_locked: boolean;
      source_url?: null | string;
      status: string;
    }>;
  }>(`${BASE_URL}/upgrade-batch`, null, {
    params: slugs && slugs.length > 0 ? { slugs } : undefined,
  });
}
