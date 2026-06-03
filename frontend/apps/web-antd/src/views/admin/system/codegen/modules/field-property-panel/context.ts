import type { InjectionKey } from 'vue';

import type { UseFieldPropertyPanelReturn } from './use-field-property-panel';

import { inject } from 'vue';

export const fieldPropertyPanelContextKey: InjectionKey<UseFieldPropertyPanelReturn> =
  Symbol('fieldPropertyPanelContext');

export function useFieldPropertyPanelContext(): UseFieldPropertyPanelReturn {
  const context = inject(fieldPropertyPanelContextKey);
  if (!context) {
    throw new Error('FieldPropertyPanel context is not provided.');
  }
  return context;
}
