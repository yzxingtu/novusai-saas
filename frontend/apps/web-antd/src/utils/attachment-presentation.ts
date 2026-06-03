import type { AttachmentCategory } from '#/types/attachment';

export type AttachmentPresentationColor =
  | 'blue'
  | 'cyan'
  | 'default'
  | 'green'
  | 'orange'
  | 'purple'
  | 'red';

export function getAttachmentCategoryColor(
  category: AttachmentCategory | null | undefined,
): AttachmentPresentationColor {
  if (!category) return 'default';
  const colorMap: Record<AttachmentCategory, AttachmentPresentationColor> = {
    archive: 'orange',
    audio: 'cyan',
    document: 'blue',
    image: 'green',
    other: 'default',
    video: 'purple',
  };
  return colorMap[category] ?? 'default';
}

export function getAttachmentVisibilityColor(
  visibility: 'private' | 'public' | undefined,
): 'green' | 'orange' {
  return visibility === 'public' ? 'green' : 'orange';
}

export function getAttachmentMimeCategoryFilterValues(): [
  string,
  string,
  string,
  string,
] {
  return ['image/', 'application/', 'video/', 'audio/'];
}
