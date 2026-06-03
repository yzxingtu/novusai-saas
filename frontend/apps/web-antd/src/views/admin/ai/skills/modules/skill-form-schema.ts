import type { SkillFormSharedState } from './skill-form-types';

import {
  buildSkillFormCoreSchema,
  buildSkillFormToolkitSchema,
} from './skill-form-schema-core';
import { buildSkillFormServiceSchema } from './skill-form-schema-services';

export type {
  BuiltinToolInfo,
  SkillFormSharedState,
  SkillFormValues,
} from './skill-form-types';

export function createSkillFormSchema(state: SkillFormSharedState) {
  return () => [
    ...buildSkillFormCoreSchema(state),
    ...buildSkillFormToolkitSchema(state),
    ...buildSkillFormServiceSchema(),
  ];
}
