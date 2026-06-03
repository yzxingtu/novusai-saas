import type { InjectionKey } from 'vue';

import type { WysiwygFormPreviewState } from './useWysiwygFormPreview';

import { inject } from 'vue';

export const wysiwygFormContextKey: InjectionKey<WysiwygFormPreviewState> =
  Symbol('WysiwygFormPreviewContext');

export function useWysiwygFormContext(): WysiwygFormPreviewState {
  const context = inject(wysiwygFormContextKey);
  if (!context) {
    throw new Error('WysiwygFormPreview context is not provided.');
  }
  return context;
}
