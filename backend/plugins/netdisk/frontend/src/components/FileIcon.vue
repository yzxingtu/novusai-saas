<script lang="ts" setup>
/**
 * N-FileIcon: 通用文件类型 SVG 图标
 * 根据 nodeType / mimeType 渲染不同 SVG 路径，无需任何 emoji 或外部图标库
 */
interface NodeLike { nodeType: string; mimeType?: string | null; }

const props = defineProps<{ node: NodeLike; size?: number }>();

interface IconInfo { type: string; color: string; }

function info(): IconInfo {
  const mime = props.node.mimeType ?? '';
  if (props.node.nodeType === 'folder') return { type: 'folder', color: '#F59E0B' };
  if (mime.startsWith('image/'))   return { type: 'image',  color: '#8B5CF6' };
  if (mime.startsWith('video/'))   return { type: 'video',  color: '#EF4444' };
  if (mime.startsWith('audio/'))   return { type: 'audio',  color: '#10B981' };
  if (mime === 'application/pdf')  return { type: 'doc',    color: '#EF4444' };
  if (mime.includes('word') || mime.includes('document')) return { type: 'doc',   color: '#3B82F6' };
  if (mime.includes('sheet') || mime.includes('excel'))   return { type: 'excel', color: '#10B981' };
  if (mime.includes('ppt')  || mime.includes('presentation')) return { type: 'ppt', color: '#F59E0B' };
  if (mime.includes('zip')  || mime.includes('tar') || mime.includes('gzip')) return { type: 'zip', color: '#6B7280' };
  if (mime.startsWith('text/') || mime.includes('json') || mime.includes('xml')) return { type: 'text', color: '#64748B' };
  return { type: 'file', color: '#6B7280' };
}
</script>

<template>
  <svg
    :width="size ?? 24"
    :height="size ?? 24"
    viewBox="0 0 24 24"
    fill="none"
    :stroke="info().color"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <template v-if="info().type === 'folder'">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </template>
    <template v-else-if="info().type === 'image'">
      <rect x="3" y="3" width="18" height="18" rx="2"/>
      <circle cx="8.5" cy="8.5" r="1.5"/>
      <polyline points="21 15 16 10 5 21"/>
    </template>
    <template v-else-if="info().type === 'video'">
      <polygon points="23 7 16 12 23 17 23 7"/>
      <rect x="1" y="5" width="15" height="14" rx="2"/>
    </template>
    <template v-else-if="info().type === 'audio'">
      <path d="M9 18V5l12-2v13"/>
      <circle cx="6" cy="18" r="3"/>
      <circle cx="18" cy="16" r="3"/>
    </template>
    <template v-else-if="info().type === 'doc' || info().type === 'text'">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
    </template>
    <template v-else-if="info().type === 'excel'">
      <rect x="3" y="3" width="18" height="18" rx="2"/>
      <path d="M3 9h18M3 15h18M9 3v18"/>
    </template>
    <template v-else-if="info().type === 'ppt'">
      <rect x="2" y="3" width="20" height="14" rx="2"/>
      <line x1="8" y1="21" x2="16" y2="21"/>
      <line x1="12" y1="17" x2="12" y2="21"/>
    </template>
    <template v-else-if="info().type === 'zip'">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
      <polyline points="12 8 12 16"/>
      <line x1="9" y1="11" x2="15" y2="11"/>
    </template>
    <template v-else>
      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
      <polyline points="13 2 13 9 20 9"/>
    </template>
  </svg>
</template>
