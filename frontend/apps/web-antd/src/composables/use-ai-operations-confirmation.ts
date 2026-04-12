import type { PageOperationResult } from '#/components/business/ai-slide-panel/page-operation-types';

import type { TrackableFormApi } from './use-form-state-tracker';

import { $t } from '#/locales';

import { getFormApi, isFormOpen } from './use-ai-operations-state';

export type FormOpenCheck =
  | { ok: true }
  | { ok: false; result: PageOperationResult };

export type FormApiCheck =
  | { ok: true; formApi: TrackableFormApi }
  | { ok: false; result: PageOperationResult };

export function requireOpenForm(pageKey: string): FormOpenCheck {
  if (!isFormOpen(pageKey)) {
    return {
      ok: false,
      result: {
        success: false,
        message: $t('shared.pageOperation.msg.formNotOpen'),
      },
    };
  }
  return { ok: true };
}

export function requireOpenFormApi(pageKey: string): FormApiCheck {
  const openCheck = requireOpenForm(pageKey);
  if (!openCheck.ok) {
    return openCheck;
  }

  const trackedApi = getFormApi(pageKey);
  if (!trackedApi) {
    return {
      ok: false,
      result: {
        success: false,
        message: $t('shared.pageOperation.msg.formApiNotAvailable'),
      },
    };
  }

  return { ok: true, formApi: trackedApi };
}
