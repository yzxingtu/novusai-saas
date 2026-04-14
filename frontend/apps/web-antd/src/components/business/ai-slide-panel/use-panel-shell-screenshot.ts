import type { ComputedRef, Ref } from 'vue';

import type { ChatAttachment } from '#/types/ai-chat';

import {
  DEFAULT_PAGE_SCREENSHOT_EXCLUDE_SELECTORS,
  usePageScreenshot,
} from '#/composables/use-page-screenshot';

interface UsePanelShellScreenshotOptions {
  apiPrefix: Ref<string>;
  pendingAttachments: Ref<ChatAttachment[]>;
  supportsVision: ComputedRef<boolean>;
  uploadUrl: Ref<string>;
}

export function usePanelShellScreenshot(
  options: UsePanelShellScreenshotOptions,
) {
  const { capturing, captureAndUpload } = usePageScreenshot();

  async function handleScreenshot() {
    if (capturing.value || !options.supportsVision.value) return;

    const result = await captureAndUpload({
      uploadUrl: options.uploadUrl.value,
      extraData: options.apiPrefix.value.includes('/admin')
        ? { tenant_id: '0' }
        : undefined,
      excludeSelectors: [...DEFAULT_PAGE_SCREENSHOT_EXCLUDE_SELECTORS],
    });

    if (result) {
      options.pendingAttachments.value.push(result.attachment);
    }
  }

  return {
    capturing,
    handleScreenshot,
  };
}
