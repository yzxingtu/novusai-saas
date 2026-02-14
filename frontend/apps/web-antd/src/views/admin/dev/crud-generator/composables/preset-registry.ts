/**
 * Preset Registry — 列渲染预设契约
 *
 * 单一数据源: ListPreview 渲染逻辑 与 代码生成模板 共用同一套 preset key。
 * 每个 preset 定义:
 *   - key: ListRenderPreset 枚举值
 *   - label: 显示名称
 *   - component: 主渲染组件名
 *   - props: 组件 props 映射（模板变量: value, record, field）
 *   - previewTemplate: ListPreview 中的 Vue template 片段
 *   - codegenTemplate: 代码生成时输出的 Vue template 片段
 *   - imports: 代码生成时需要导入的组件
 *   - fallback: 是否为兜底渲染
 */

import type { ListRenderPreset } from '../types';

export interface PresetDefinition {
  key: ListRenderPreset;
  label: string;
  component: string;
  props: Record<string, string>;
  previewTemplate: string;
  codegenTemplate: string;
  imports: string[];
  fallback?: boolean;
}

/**
 * 所有 preset 的注册表
 * ListPreview 和代码生成器 都从这里读取模板
 */
export const PRESET_REGISTRY: Record<ListRenderPreset, PresetDefinition> = {
  tag: {
    key: 'tag',
    label: 'Tag',
    component: 'Tag',
    props: { color: 'getEnumColor(record.{field}, "{field}")' },
    previewTemplate:
      '<Tag :color="getEnumColor(record.{field}, \'{field}\')">{{ getEnumLabel(record.{field}, \'{field}\') }}</Tag>',
    codegenTemplate:
      '<Tag :color="getEnumColor(record.{field})">{{ getEnumLabel(record.{field}) }}</Tag>',
    imports: ['Tag'],
  },

  badge: {
    key: 'badge',
    label: 'Badge',
    component: 'Badge',
    props: {
      color: 'getEnumColor(record.{field}, "{field}")',
      text: 'getEnumLabel(record.{field}, "{field}")',
    },
    previewTemplate:
      '<Badge :color="getEnumColor(record.{field}, \'{field}\')" :text="getEnumLabel(record.{field}, \'{field}\')" />',
    codegenTemplate:
      '<Badge :color="getEnumColor(record.{field})" :text="getEnumLabel(record.{field})" />',
    imports: ['Badge'],
  },

  switch: {
    key: 'switch',
    label: 'Switch',
    component: 'Switch',
    props: { checked: '!!record.{field}' },
    previewTemplate:
      '<Switch :checked="!!record.{field}" size="small" />',
    codegenTemplate:
      '<Switch :checked="!!record.{field}" size="small" @change="handleToggle(record, \'{field}\', $event)" />',
    imports: ['Switch'],
  },

  money: {
    key: 'money',
    label: 'Money (¥)',
    component: 'span',
    props: {},
    previewTemplate:
      '<span class="font-mono tabular-nums">¥ {{ Number(record.{field}).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</span>',
    codegenTemplate:
      '<span class="font-mono tabular-nums">¥ {{ formatMoney(record.{field}) }}</span>',
    imports: [],
  },

  percent: {
    key: 'percent',
    label: 'Percent (%)',
    component: 'span',
    props: {},
    previewTemplate:
      '<span class="tabular-nums">{{ Number(record.{field}).toFixed(1) }}%</span>',
    codegenTemplate:
      '<span class="tabular-nums">{{ Number(record.{field}).toFixed(1) }}%</span>',
    imports: [],
  },

  progress: {
    key: 'progress',
    label: 'Progress',
    component: 'Progress',
    props: { percent: 'Number(record.{field}) || 0' },
    previewTemplate:
      '<Progress :percent="Number(record.{field}) || 0" :show-info="false" size="small" style="width: 80px" />',
    codegenTemplate:
      '<Progress :percent="Number(record.{field}) || 0" :show-info="false" size="small" style="width: 80px" />',
    imports: ['Progress'],
  },

  relative_time: {
    key: 'relative_time',
    label: 'Relative Time',
    component: 'Tooltip',
    props: { title: 'record.{field}' },
    previewTemplate:
      '<Tooltip :title="record.{field}"><span class="text-muted-foreground text-xs">{{ formatRelativeTime(record.{field}) }}</span></Tooltip>',
    codegenTemplate:
      '<Tooltip :title="record.{field}"><span class="text-muted-foreground text-xs">{{ formatRelativeTime(record.{field}) }}</span></Tooltip>',
    imports: ['Tooltip'],
  },

  datetime: {
    key: 'datetime',
    label: 'Datetime',
    component: 'span',
    props: {},
    previewTemplate:
      '<span class="text-muted-foreground text-xs tabular-nums">{{ String(record.{field} || "").slice(0, 19) }}</span>',
    codegenTemplate:
      '<span class="text-muted-foreground text-xs tabular-nums">{{ formatDatetime(record.{field}) }}</span>',
    imports: [],
  },

  date: {
    key: 'date',
    label: 'Date',
    component: 'span',
    props: {},
    previewTemplate:
      '<span class="text-muted-foreground text-xs tabular-nums">{{ String(record.{field} || "").slice(0, 10) }}</span>',
    codegenTemplate:
      '<span class="text-muted-foreground text-xs tabular-nums">{{ formatDate(record.{field}) }}</span>',
    imports: [],
  },

  avatar: {
    key: 'avatar',
    label: 'Avatar',
    component: 'Avatar',
    props: { size: '24', src: 'record.{field}' },
    previewTemplate:
      '<Avatar :size="24" :src="record.{field}">{{ String(record.{field} || "?").charAt(0).toUpperCase() }}</Avatar>',
    codegenTemplate:
      '<Avatar :size="24" :src="record.{field}">{{ String(record.{field} || "?").charAt(0).toUpperCase() }}</Avatar>',
    imports: ['Avatar'],
  },

  image: {
    key: 'image',
    label: 'Image',
    component: 'img',
    props: { src: 'record.{field}' },
    previewTemplate:
      '<img :src="String(record.{field} || \'\')" alt="" class="h-8 w-8 rounded object-cover" />',
    codegenTemplate:
      '<img :src="record.{field}" alt="" class="h-8 w-8 rounded object-cover" @click="handlePreviewImage(record.{field})" />',
    imports: [],
  },

  link: {
    key: 'link',
    label: 'Link',
    component: 'a',
    props: { href: 'record.{field}', target: '"_blank"' },
    previewTemplate:
      '<a :href="String(record.{field} || \'#\')" class="text-primary truncate" target="_blank">{{ record.{field} }}</a>',
    codegenTemplate:
      '<a :href="record.{field}" class="text-primary truncate" target="_blank">{{ record.{field} }}</a>',
    imports: [],
  },

  copy: {
    key: 'copy',
    label: 'Copy',
    component: 'span',
    props: {},
    previewTemplate:
      '<span class="flex items-center gap-1"><span class="truncate">{{ record.{field} }}</span><span class="icon-[lucide--copy] text-muted-foreground size-3 cursor-pointer" /></span>',
    codegenTemplate:
      '<span class="flex items-center gap-1"><span class="truncate">{{ record.{field} }}</span><CopyButton :text="record.{field}" /></span>',
    imports: [],
  },

  icon: {
    key: 'icon',
    label: 'Icon',
    component: 'span',
    props: {},
    previewTemplate:
      '<span class="text-lg">{{ record.{field} }}</span>',
    codegenTemplate:
      '<IconifyIcon :icon="record.{field}" class="text-lg" />',
    imports: ['IconifyIcon'],
  },

  color: {
    key: 'color',
    label: 'Color',
    component: 'span',
    props: {},
    previewTemplate:
      '<span class="flex items-center gap-2"><span :style="{ backgroundColor: String(record.{field} || \'#ccc\') }" class="inline-block size-4 rounded border" /><span class="font-mono text-xs">{{ record.{field} }}</span></span>',
    codegenTemplate:
      '<span class="flex items-center gap-2"><span :style="{ backgroundColor: record.{field} || \'#ccc\' }" class="inline-block size-4 rounded border" /><span class="font-mono text-xs">{{ record.{field} }}</span></span>',
    imports: [],
  },

  ellipsis: {
    key: 'ellipsis',
    label: 'Ellipsis',
    component: 'span',
    props: {},
    previewTemplate:
      '<Tooltip :title="record.{field}"><span class="truncate">{{ record.{field} }}</span></Tooltip>',
    codegenTemplate:
      '<Tooltip :title="record.{field}"><span class="truncate">{{ record.{field} }}</span></Tooltip>',
    imports: ['Tooltip'],
    fallback: true,
  },
};

/**
 * 获取指定 preset 的定义，未知 preset 返回 ellipsis 兜底
 */
export function getPresetDefinition(
  preset: ListRenderPreset | null | undefined,
): PresetDefinition | null {
  if (!preset) return null;
  return PRESET_REGISTRY[preset] ?? PRESET_REGISTRY.ellipsis;
}

/**
 * 将 preset 模板中的 {field} 占位符替换为实际字段名
 */
export function renderPresetTemplate(
  template: string,
  fieldName: string,
): string {
  return template.replaceAll('{field}', fieldName);
}

/**
 * 获取代码生成时需要导入的所有组件 (去重)
 */
export function collectPresetImports(
  presets: (ListRenderPreset | null | undefined)[],
): string[] {
  const imports = new Set<string>();
  for (const preset of presets) {
    const def = getPresetDefinition(preset);
    if (def) {
      for (const imp of def.imports) {
        imports.add(imp);
      }
    }
  }
  return [...imports].sort();
}

/**
 * 所有可用 preset 列表 (用于 Select 选项)
 */
export const PRESET_OPTIONS: { label: string; value: ListRenderPreset | '' }[] = [
  { label: 'None', value: '' },
  ...Object.values(PRESET_REGISTRY)
    .filter((d) => !d.fallback)
    .map((d) => ({ label: d.label, value: d.key })),
];
