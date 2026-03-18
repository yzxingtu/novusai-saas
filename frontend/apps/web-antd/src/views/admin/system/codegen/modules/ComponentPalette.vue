<script lang="ts" setup>
/**
 * 组件面板 / Component Palette
 *
 * 左侧 200px 宽，可折叠分组 + 搜索 + 色条 / Left 200px, collapsible groups + search + color bar
 */
import { useDebounceFn } from '@vueuse/core';
import { computed, ref } from 'vue';
import { Collapse, CollapsePanel, Input } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { $t } from '#/locales';

defineOptions({ name: 'ComponentPalette' });

export interface PaletteItem {
  type: string;
  component: string;
  icon: string;
  label: string;
  defaultName: string;
  multiple?: boolean;
}

const PALETTE_GROUPS: { title: string; items: PaletteItem[] }[] = [
  {
    title: 'admin.system.codegen.palette.basicInput',
    items: [
      { type: 'String', component: 'input', icon: 'lucide:type', label: 'admin.system.codegen.palette.input', defaultName: 'name' },
      { type: 'String', component: 'input', icon: 'lucide:barcode', label: 'admin.system.codegen.palette.code', defaultName: 'code' },
      { type: 'Text', component: 'textarea', icon: 'lucide:align-left', label: 'admin.system.codegen.palette.textarea', defaultName: 'description' },
      { type: 'Integer', component: 'number', icon: 'lucide:list-ordered', label: 'admin.system.codegen.palette.number', defaultName: 'sort_order' },
      { type: 'Decimal', component: 'number', icon: 'lucide:circle-dollar-sign', label: 'admin.system.codegen.palette.amount', defaultName: 'price' },
      { type: 'String', component: 'password', icon: 'lucide:lock', label: 'admin.system.codegen.palette.password', defaultName: 'password' },
    ],
  },
  {
    title: 'admin.system.codegen.palette.selectors',
    items: [
      { type: 'Enum', component: 'select', icon: 'lucide:list', label: 'admin.system.codegen.palette.select', defaultName: 'status' },
      { type: 'Boolean', component: 'switch', icon: 'lucide:toggle-left', label: 'admin.system.codegen.palette.switch', defaultName: 'is_active' },
      { type: 'Date', component: 'date', icon: 'lucide:calendar', label: 'admin.system.codegen.palette.date', defaultName: 'birthday' },
      { type: 'DateTime', component: 'date', icon: 'lucide:clock', label: 'admin.system.codegen.palette.datetime', defaultName: 'created_at' },
      { type: 'String', component: 'TimePicker', icon: 'lucide:clock', label: 'admin.system.codegen.palette.timePicker', defaultName: 'start_time' },
      { type: 'String', component: 'DictSelect', icon: 'lucide:book-open', label: 'admin.system.codegen.palette.dictSelect', defaultName: 'type' },
      { type: 'Integer', component: 'Rate', icon: 'lucide:star', label: 'admin.system.codegen.palette.rate', defaultName: 'rating' },
      { type: 'Integer', component: 'Slider', icon: 'lucide:sliders-horizontal', label: 'admin.system.codegen.palette.slider', defaultName: 'score' },
    ],
  },
  {
    title: 'admin.system.codegen.palette.upload',
    items: [
      { type: 'ImageUpload', component: 'ImageUpload', icon: 'lucide:image', label: 'admin.system.codegen.palette.singleImage', defaultName: 'avatar' },
      { type: 'Images', component: 'ImageUpload', icon: 'lucide:images', label: 'admin.system.codegen.palette.multiImage', defaultName: 'images', multiple: true },
      { type: 'File', component: 'FilePicker', icon: 'lucide:file', label: 'admin.system.codegen.palette.singleFile', defaultName: 'attachment' },
      { type: 'Files', component: 'FilePicker', icon: 'lucide:files', label: 'admin.system.codegen.palette.multiFile', defaultName: 'attachments', multiple: true },
    ],
  },
  {
    title: 'admin.system.codegen.palette.relation',
    items: [
      { type: 'ForeignKey', component: 'ApiSelect', icon: 'lucide:link', label: 'admin.system.codegen.palette.fkSingle', defaultName: 'category_id' },
      { type: 'ForeignKey', component: 'ApiSelect', icon: 'lucide:links', label: 'admin.system.codegen.palette.fkMulti', defaultName: 'tag_ids', multiple: true },
      { type: 'TreeSelect', component: 'ApiTreeSelect', icon: 'lucide:git-branch', label: 'admin.system.codegen.palette.treeSelect', defaultName: 'parent_id' },
      { type: 'UserSelect', component: 'ApiSelect', icon: 'lucide:user', label: 'admin.system.codegen.palette.userSelect', defaultName: 'created_by' },
      { type: 'DeptSelect', component: 'ApiTreeSelect', icon: 'lucide:building-2', label: 'admin.system.codegen.palette.deptSelect', defaultName: 'dept_id' },
      { type: 'Cascader', component: 'Cascader', icon: 'lucide:map-pin', label: 'admin.system.codegen.palette.cascader', defaultName: 'region' },
    ],
  },
  {
    title: 'admin.system.codegen.palette.advanced',
    items: [
      { type: 'RichText', component: 'RichText', icon: 'lucide:file-text', label: 'admin.system.codegen.palette.richText', defaultName: 'content' },
      { type: 'IconPicker', component: 'IconPicker', icon: 'lucide:sparkles', label: 'admin.system.codegen.palette.icon', defaultName: 'icon' },
      { type: 'JSON', component: 'CodeEditor', icon: 'lucide:code-2', label: 'admin.system.codegen.palette.json', defaultName: 'config' },
      { type: 'String', component: 'ColorPicker', icon: 'lucide:palette', label: 'admin.system.codegen.palette.color', defaultName: 'theme_color' },
    ],
  },
  {
    title: 'admin.system.codegen.palette.layout',
    items: [
      { type: '__divider__', component: 'divider', icon: 'lucide:minus', label: 'admin.system.codegen.palette.divider', defaultName: '' },
    ],
  },
];

const searchText = ref('');
const defaultActiveKeys = PALETTE_GROUPS.slice(0, 3).map((g) => g.title);

const filteredGroups = computed(() => {
  const q = (searchText.value || '').trim().toLowerCase();
  if (!q) return PALETTE_GROUPS;
  return PALETTE_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter(
      (it) =>
        ($t(it.label) as string).toLowerCase().includes(q) ||
        (it.defaultName || '').toLowerCase().includes(q),
    ),
  })).filter((g) => g.items.length > 0);
});

const GROUP_COLORS = ['#3b82f6', '#22c55e', '#eab308', '#ef4444', '#8b5cf6', '#6366f1'];

const emit = defineEmits<{ (e: 'add', item: PaletteItem): void }>();

function onDragStart(e: DragEvent, item: PaletteItem) {
  if (!e.dataTransfer) return;
  e.dataTransfer.effectAllowed = 'copy';
  const payload = JSON.stringify(item);
  e.dataTransfer.setData('application/json', payload);
  e.dataTransfer.setData('text/plain', payload);
}

const debouncedEmitAdd = useDebounceFn((item: PaletteItem) => {
  emit('add', item);
}, 200);

function onClick(item: PaletteItem) {
  debouncedEmitAdd(item);
}
</script>

<template>
  <div class="flex w-56 min-w-[14rem] shrink-0 flex-col overflow-y-auto border-r border-border bg-muted/30 p-3">
    <Input
      v-model:value="searchText"
      :placeholder="$t('admin.system.codegen.palette.searchPlaceholder')"
      allow-clear
      size="small"
      class="mb-2"
    >
      <template #prefix>
        <IconifyIcon icon="lucide:search" class="size-4 text-muted-foreground" />
      </template>
    </Input>
    <Collapse :default-active-key="defaultActiveKeys" :bordered="false" expand-icon-position="end" class="!gap-0">
      <CollapsePanel
        v-for="(group, gi) in filteredGroups"
        :key="group.title"
        class="!border-0"
      >
        <template #header>
          <span class="flex items-center gap-2">
            <span
              class="h-4 w-0.5 shrink-0 rounded-full"
              :style="{ backgroundColor: GROUP_COLORS[gi % GROUP_COLORS.length] }"
            />
            {{ $t(group.title) }}
          </span>
        </template>
        <div class="flex flex-col gap-1.5">
          <div
            v-for="(item, ii) in group.items"
            :key="`${item.type}-${item.defaultName || ii}`"
            class="flex cursor-grab items-center gap-2 rounded border border-border bg-background px-2 py-1.5 text-sm transition-colors hover:border-primary/50 hover:bg-primary/5 active:cursor-grabbing"
            draggable="true"
            @click="onClick(item)"
            @dragstart="onDragStart($event, item)"
          >
            <IconifyIcon :icon="item.icon" class="size-4 shrink-0 text-muted-foreground" />
            <span class="truncate">{{ $t(item.label) }}</span>
          </div>
        </div>
      </CollapsePanel>
    </Collapse>
  </div>
</template>
