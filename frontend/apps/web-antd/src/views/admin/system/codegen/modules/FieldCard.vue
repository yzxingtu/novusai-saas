<script lang="ts" setup>
/**
 * 单字段卡片 / Field Card
 *
 * 拖拽手柄 + 图标 + 字段名 + 类型标签 + 删除按钮
 * __divider__ 类型渲染分隔线 + 标题输入框
 */
import type { Recordable } from '@vben/types';

import { computed } from 'vue';
import { Button, Input, Tooltip } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { $t } from '#/locales';

import { getComponent } from './field-utils';

defineOptions({ name: 'FieldCard' });

const ICON_MAP: Record<string, string> = {
  input: 'lucide:type',
  textarea: 'lucide:align-left',
  number: 'lucide:hash',
  select: 'lucide:list',
  switch: 'lucide:toggle-left',
  date: 'lucide:calendar',
  ImageUpload: 'lucide:image',
  FilePicker: 'lucide:file',
  ApiSelect: 'lucide:link',
  ApiTreeSelect: 'lucide:git-branch',
  DictSelect: 'lucide:book-open',
  Cascader: 'lucide:map-pin',
  RichText: 'lucide:file-text',
  IconPicker: 'lucide:sparkles',
  CodeEditor: 'lucide:code-2',
  ColorPicker: 'lucide:palette',
  Rate: 'lucide:star',
  Slider: 'lucide:sliders-horizontal',
  password: 'lucide:lock',
  divider: 'lucide:minus',
  TimePicker: 'lucide:clock',
};

const TYPE_ABBREV: Record<string, string> = {
  ForeignKey: 'FK',
  ImageUpload: 'Img',
  Images: 'Imgs',
  File: 'File',
  Files: 'Files',
  DateTime: 'DT',
  RichText: 'RT',
};

const props = defineProps<{
  field: Recordable;
  selected: boolean;
}>();

const emit = defineEmits<{ (e: 'click'): void; (e: 'remove'): void; (e: 'update:dividerTitle', v: string): void }>();

const isDivider = computed(() => props.field?.type === '__divider__' || props.field?.divider);
const componentName = computed(() => getComponent(props.field));
const icon = computed(() => ICON_MAP[(componentName.value as string) || ''] || 'lucide:circle-dot');
const typeLabel = computed(() => {
  const t = (props.field?.type as string) || '';
  return TYPE_ABBREV[t] || t;
});
</script>

<template>
  <!-- 分隔线类型 -->
  <div
    v-if="isDivider"
    class="group flex cursor-pointer items-center gap-2 rounded border border-dashed px-3 py-2 transition-colors"
    :class="selected ? 'border-primary bg-primary/10' : 'border-border bg-muted/30 hover:border-primary/50 hover:bg-muted/50'"
    @click.stop="emit('click')"
  >
    <span class="drag-handle cursor-grab shrink-0 text-muted-foreground active:cursor-grabbing">
      <IconifyIcon icon="lucide:grip-vertical" class="size-4" />
    </span>
    <IconifyIcon icon="lucide:minus" class="size-4 shrink-0 text-muted-foreground" />
    <Input
      :model-value="field.divider_title || field.title || ''"
      :placeholder="$t('admin.system.codegen.palette.dividerTitlePlaceholder')"
      size="small"
      class="flex-1 !border-0 !bg-transparent"
      @click.stop
      @update:model-value="emit('update:dividerTitle', $event)"
    />
    <Button
      type="text"
      size="small"
      danger
      class="opacity-0 shrink-0 !p-1 group-hover:opacity-100"
      @click.stop="emit('remove')"
    >
      <IconifyIcon icon="lucide:trash-2" class="size-4" />
    </Button>
  </div>
  <!-- 普通字段 -->
  <div
    v-else
    class="group flex cursor-pointer items-center gap-2 rounded border px-2 py-2 text-sm transition-colors"
    :class="selected ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/50 hover:bg-muted/50'"
    @click="emit('click')"
  >
    <span class="drag-handle cursor-grab shrink-0 text-muted-foreground active:cursor-grabbing">
      <IconifyIcon icon="lucide:grip-vertical" class="size-4" />
    </span>
    <IconifyIcon :icon="icon" class="size-4 shrink-0 text-muted-foreground" />
    <Tooltip v-if="field.display_name" :title="field.display_name">
      <div class="min-w-0 flex-1 truncate">
        <span class="font-medium">
          <span v-if="field.required" class="mr-0.5 text-destructive">*</span>
          {{ field.name || $t('admin.system.codegen.property.unnamed') }}
        </span>
        <span v-if="field.display_name" class="ml-1 text-muted-foreground">({{ field.display_name }})</span>
      </div>
    </Tooltip>
    <div v-else class="min-w-0 flex-1 truncate">
      <span class="font-medium">
        <span v-if="field.required" class="mr-0.5 text-destructive">*</span>
        {{ field.name || $t('admin.system.codegen.property.unnamed') }}
      </span>
    </div>
    <span
      v-if="field.type"
      class="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
    >
      {{ typeLabel }}
    </span>
    <span
      v-if="field._auto_detected"
      class="shrink-0 rounded bg-green-100 px-1 text-xs text-green-700 dark:bg-green-900/30 dark:text-green-400"
    >
      {{ $t('admin.system.codegen.field.autoDetected') }}
    </span>
    <Button
      type="text"
      size="small"
      danger
      class="opacity-0 shrink-0 !p-1 group-hover:opacity-100"
      @click.stop="emit('remove')"
    >
      <IconifyIcon icon="lucide:trash-2" class="size-4" />
    </Button>
  </div>
</template>
