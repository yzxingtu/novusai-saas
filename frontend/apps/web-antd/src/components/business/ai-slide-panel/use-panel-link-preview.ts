import { ref } from 'vue';

import { toAbsoluteApiUrl } from '#/utils/image';

export function usePanelLinkPreview() {
  const previewImageUrl = ref('');
  const previewImageVisible = ref(false);

  function openImagePreview(url: string) {
    previewImageUrl.value = url;
    previewImageVisible.value = true;
  }

  function isLikelyImageUrl(url: string) {
    const normalized = (url || '').trim().toLowerCase();
    if (!normalized) return false;
    if (normalized.startsWith('data:image/')) return true;
    if (normalized.startsWith('blob:')) return true;
    if (/\/api\/public\/attachments\/\d+\/image(?:[?#]|$)/.test(normalized)) {
      return true;
    }
    const withoutQuery = normalized.split('?')[0]?.split('#')[0] || normalized;
    return /\.(?:avif|bmp|gif|ico|jpe?g|png|svg|webp)$/i.test(withoutQuery);
  }

  function handleOpenUrl(url: string) {
    const normalizedUrl = toAbsoluteApiUrl(url) || url;
    if (!normalizedUrl) return;
    if (isLikelyImageUrl(normalizedUrl)) {
      openImagePreview(normalizedUrl);
      return;
    }
    window.open(normalizedUrl, '_blank', 'noopener,noreferrer');
  }

  return {
    handleOpenUrl,
    previewImageUrl,
    previewImageVisible,
  };
}
