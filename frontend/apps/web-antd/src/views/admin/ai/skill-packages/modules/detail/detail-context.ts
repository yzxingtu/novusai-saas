import type { InjectionKey } from 'vue';

import type { UseSkillPackageDetailPageReturn } from './use-skill-package-detail-page';

import { inject } from 'vue';

export const skillPackageDetailContextKey: InjectionKey<UseSkillPackageDetailPageReturn> =
  Symbol('SkillPackageDetailContext');

export function useSkillPackageDetailContext(): UseSkillPackageDetailPageReturn {
  const context = inject(skillPackageDetailContextKey);

  if (!context) {
    throw new Error('SkillPackageDetail context is not provided.');
  }

  return context;
}
