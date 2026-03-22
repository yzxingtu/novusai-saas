<script lang="ts" setup>
import type { Recordable } from '@vben/types';

import { computed } from 'vue';
import { Button, Input, Tag, Tooltip } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

import { getComponent } from './field-utils';

defineOptions({ name: 'FieldCard' });

const ICON_MAP: Record<string, string> = {
  ApiSelect: 'lucide:link',
  ApiTreeSelect: 'lucide:git-branch',
  Cascader: 'lucide:map-pin',
  CodeEditor: 'lucide:code-2',
  ColorPicker: 'lucide:palette',
  DictSelect: 'lucide:book-open',
  FilePicker: 'lucide:file',
  ImageUpload: 'lucide:image',
  Rate: 'lucide:star',
  RichText: 'lucide:file-text',
  Slider: 'lucide:sliders-horizontal',
  TimePicker: 'lucide:clock',
  divider: 'lucide:minus',
  input: 'lucide:type',
  number: 'lucide:hash',
  password: 'lucide:lock',
  select: 'lucide:list',
  switch: 'lucide:toggle-left',
  textarea: 'lucide:align-left',
};

const props = defineProps<{
  field: Recordable;
  selected: boolean;
}>();

const emit = defineEmits<{
  (e: 'click'): void;
  (e: 'remove'): void;
  (e: 'update:dividerTitle', value: string): void;
}>();

const isDivider = computed(
  () => props.field?.type === '__divider__' || props.field?.divider,
);
const componentName = computed(() => getComponent(props.field));
const icon = computed(
  () => ICON_MAP[componentName.value as string] || 'lucide:circle-dot',
);
const capabilityBadges = computed(() => {
  if (isDivider.value) return [];
  const badges = [];
  if (props.field.required)
    badges.push($t('admin.system.codegen.property.required'));
  if (props.field.list_visible !== false) {
    badges.push($t('admin.system.codegen.property.listVisible'));
  }
  if (props.field.filterable)
    badges.push($t('admin.system.codegen.property.filterable'));
  if (props.field.editable !== false)
    badges.push($t('admin.system.codegen.property.editable'));
  return badges.slice(0, 4);
});
</script>

<template>
  <div
    v-if="isDivider"
    :data-field-key="String(field.__key || '')"
    class="group flex items-center gap-3 rounded-[22px] border border-dashed px-4 py-3 transition-colors"
    :class="
      selected
        ? 'bg-primary/8 border-primary shadow-sm'
        : 'border-border bg-background hover:border-primary/25 hover:bg-muted/25'
    "
    @click.stop="emit('click')"
  >
    <button
      type="button"
      class="drag-handle inline-flex size-9 cursor-grab items-center justify-center rounded-2xl border border-border/70 bg-muted/20 text-muted-foreground active:cursor-grabbing"
    >
      <IconifyIcon icon="lucide:grip-vertical" class="size-4" />
    </button>

    <div
      class="flex size-9 items-center justify-center rounded-2xl bg-background ring-1 ring-border/70"
    >
      <IconifyIcon icon="lucide:minus" class="size-4 text-muted-foreground" />
    </div>

    <div class="min-w-0 flex-1">
      <div
        class="text-[11px] uppercase tracking-[0.16em] text-muted-foreground"
      >
        {{ $t('admin.system.codegen.palette.divider') }}
      </div>
      <Input
        :model-value="field.divider_title || field.title || ''"
        :placeholder="
          $t('admin.system.codegen.palette.dividerTitlePlaceholder')
        "
        size="small"
        class="mt-1 !border-0 !bg-transparent !px-0"
        @click.stop
        @update:model-value="emit('update:dividerTitle', $event)"
      />
    </div>

    <Button
      type="text"
      size="small"
      danger
      class="!p-1 opacity-0 transition-opacity group-hover:opacity-100"
      @click.stop="emit('remove')"
    >
      <IconifyIcon icon="lucide:trash-2" class="size-4" />
    </Button>
  </div>

  <div
    v-else
    :data-field-key="String(field.__key || '')"
    class="group flex gap-4 rounded-[22px] border px-4 py-4 transition-all"
    :class="
      selected
        ? 'bg-primary/8 border-primary shadow-sm'
        : 'border-border bg-background hover:border-primary/30 hover:bg-muted/20'
    "
    @click="emit('click')"
  >
    <div class="flex items-start gap-3">
      <button
        type="button"
        class="drag-handle mt-0.5 inline-flex size-9 cursor-grab items-center justify-center rounded-2xl border border-border/70 bg-muted/20 text-muted-foreground active:cursor-grabbing"
      >
        <IconifyIcon icon="lucide:grip-vertical" class="size-4" />
      </button>

      <div
        class="flex size-10 items-center justify-center rounded-2xl bg-background shadow-sm ring-1 ring-border/70"
      >
        <IconifyIcon :icon="icon" class="size-5 text-foreground" />
      </div>
    </div>

    <div class="min-w-0 flex-1">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <span class="truncate text-sm font-semibold text-foreground">
              <span v-if="field.required" class="mr-0.5 text-destructive"
                >*</span
              >
              {{ field.name || $t('admin.system.codegen.property.unnamed') }}
            </span>
            <Tag v-if="field.type" class="!mr-0 !rounded-full">
              {{ field.type }}
            </Tag>
            <Tag
              v-if="field._auto_detected"
              color="success"
              class="!mr-0 !rounded-full"
            >
              {{ $t('admin.system.codegen.field.autoDetected') }}
            </Tag>
          </div>

          <div
            class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
          >
            <Tooltip v-if="field.display_name" :title="field.display_name">
              <span class="truncate">
                {{ field.display_name }}
              </span>
            </Tooltip>
            <span>{{ componentName }}</span>
          </div>
        </div>

        <Button
          type="text"
          size="small"
          danger
          class="!p-1 opacity-0 transition-opacity group-hover:opacity-100"
          @click.stop="emit('remove')"
        >
          <IconifyIcon icon="lucide:trash-2" class="size-4" />
        </Button>
      </div>

      <div class="mt-3 flex flex-wrap gap-2">
        <span
          v-for="badge in capabilityBadges"
          :key="badge"
          class="rounded-full border border-border/70 bg-muted/20 px-2 py-0.5 text-[11px] text-muted-foreground"
        >
          {{ badge }}
        </span>
      </div>
    </div>
  </div>
</template>
