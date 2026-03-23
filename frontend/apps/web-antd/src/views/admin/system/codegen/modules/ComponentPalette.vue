<script lang="ts" setup>
import { computed, ref } from 'vue';
import { Input } from 'ant-design-vue';
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

type PaletteGroup = {
  key: string;
  title: string;
  items: PaletteItem[];
};

type PaletteViewItem = PaletteItem & {
  groupKey: string;
  groupTitle: string;
  signature: string;
};

const PALETTE_GROUPS: PaletteGroup[] = [
  {
    key: 'basic',
    title: 'admin.system.codegen.palette.basicInput',
    items: [
      {
        type: 'String',
        component: 'input',
        icon: 'lucide:type',
        label: 'admin.system.codegen.palette.titleField',
        defaultName: 'title',
      },
      {
        type: 'String',
        component: 'input',
        icon: 'lucide:type',
        label: 'admin.system.codegen.palette.input',
        defaultName: 'name',
      },
      {
        type: 'String',
        component: 'input',
        icon: 'lucide:barcode',
        label: 'admin.system.codegen.palette.code',
        defaultName: 'code',
      },
      {
        type: 'String',
        component: 'input',
        icon: 'lucide:mail',
        label: 'admin.system.codegen.palette.email',
        defaultName: 'email',
      },
      {
        type: 'String',
        component: 'input',
        icon: 'lucide:phone',
        label: 'admin.system.codegen.palette.phone',
        defaultName: 'phone',
      },
      {
        type: 'String',
        component: 'input',
        icon: 'lucide:link',
        label: 'admin.system.codegen.palette.url',
        defaultName: 'website',
      },
      {
        type: 'Text',
        component: 'textarea',
        icon: 'lucide:align-left',
        label: 'admin.system.codegen.palette.textarea',
        defaultName: 'description',
      },
      {
        type: 'Integer',
        component: 'number',
        icon: 'lucide:list-ordered',
        label: 'admin.system.codegen.palette.number',
        defaultName: 'sort_order',
      },
      {
        type: 'Decimal',
        component: 'number',
        icon: 'lucide:wallet',
        label: 'admin.system.codegen.palette.amount',
        defaultName: 'price',
      },
      {
        type: 'String',
        component: 'password',
        icon: 'lucide:lock',
        label: 'admin.system.codegen.palette.password',
        defaultName: 'password',
      },
    ],
  },
  {
    key: 'selector',
    title: 'admin.system.codegen.palette.selectors',
    items: [
      {
        type: 'Enum',
        component: 'select',
        icon: 'lucide:list',
        label: 'admin.system.codegen.palette.select',
        defaultName: 'status',
      },
      {
        type: 'Enum',
        component: 'radio',
        icon: 'lucide:circle',
        label: 'admin.system.codegen.palette.radioGroup',
        defaultName: 'status',
      },
      {
        type: 'Enum',
        component: 'checkbox',
        icon: 'lucide:check',
        label: 'admin.system.codegen.palette.checkboxGroup',
        defaultName: 'tags',
        multiple: true,
      },
      {
        type: 'Boolean',
        component: 'switch',
        icon: 'lucide:toggle-left',
        label: 'admin.system.codegen.palette.switch',
        defaultName: 'is_active',
      },
      {
        type: 'Date',
        component: 'date',
        icon: 'lucide:calendar',
        label: 'admin.system.codegen.palette.date',
        defaultName: 'birthday',
      },
      {
        type: 'DateTime',
        component: 'date',
        icon: 'lucide:clock',
        label: 'admin.system.codegen.palette.datetime',
        defaultName: 'created_at',
      },
      {
        type: 'DateTime',
        component: 'date',
        icon: 'lucide:clock-3',
        label: 'admin.system.codegen.palette.updatedAt',
        defaultName: 'updated_at',
      },
      {
        type: 'String',
        component: 'TimePicker',
        icon: 'lucide:clock',
        label: 'admin.system.codegen.palette.timePicker',
        defaultName: 'start_time',
      },
      {
        type: 'String',
        component: 'DictSelect',
        icon: 'lucide:book-open',
        label: 'admin.system.codegen.palette.dictSelect',
        defaultName: 'type',
      },
      {
        type: 'Integer',
        component: 'Rate',
        icon: 'lucide:star',
        label: 'admin.system.codegen.palette.rate',
        defaultName: 'rating',
      },
      {
        type: 'Integer',
        component: 'Slider',
        icon: 'lucide:sliders-horizontal',
        label: 'admin.system.codegen.palette.slider',
        defaultName: 'score',
      },
    ],
  },
  {
    key: 'upload',
    title: 'admin.system.codegen.palette.upload',
    items: [
      {
        type: 'ImageUpload',
        component: 'ImageUpload',
        icon: 'lucide:image',
        label: 'admin.system.codegen.palette.singleImage',
        defaultName: 'avatar',
      },
      {
        type: 'ImageUpload',
        component: 'ImageUpload',
        icon: 'lucide:image-up',
        label: 'admin.system.codegen.palette.coverImage',
        defaultName: 'cover_image',
      },
      {
        type: 'Images',
        component: 'ImageUpload',
        icon: 'lucide:images',
        label: 'admin.system.codegen.palette.multiImage',
        defaultName: 'images',
        multiple: true,
      },
      {
        type: 'File',
        component: 'FilePicker',
        icon: 'lucide:file',
        label: 'admin.system.codegen.palette.singleFile',
        defaultName: 'attachment',
      },
      {
        type: 'Files',
        component: 'FilePicker',
        icon: 'lucide:files',
        label: 'admin.system.codegen.palette.multiFile',
        defaultName: 'attachments',
        multiple: true,
      },
    ],
  },
  {
    key: 'relation',
    title: 'admin.system.codegen.palette.relation',
    items: [
      {
        type: 'ForeignKey',
        component: 'ApiSelect',
        icon: 'lucide:link',
        label: 'admin.system.codegen.palette.fkSingle',
        defaultName: 'category_id',
      },
      {
        type: 'ForeignKey',
        component: 'ApiSelect',
        icon: 'lucide:link-2',
        label: 'admin.system.codegen.palette.fkMulti',
        defaultName: 'tag_ids',
        multiple: true,
      },
      {
        type: 'TreeSelect',
        component: 'ApiTreeSelect',
        icon: 'lucide:git-branch',
        label: 'admin.system.codegen.palette.treeSelect',
        defaultName: 'parent_id',
      },
      {
        type: 'UserSelect',
        component: 'ApiSelect',
        icon: 'lucide:user',
        label: 'admin.system.codegen.palette.userSelect',
        defaultName: 'created_by',
      },
      {
        type: 'DeptSelect',
        component: 'ApiTreeSelect',
        icon: 'lucide:building-2',
        label: 'admin.system.codegen.palette.deptSelect',
        defaultName: 'dept_id',
      },
      {
        type: 'Cascader',
        component: 'Cascader',
        icon: 'lucide:map-pin',
        label: 'admin.system.codegen.palette.cascader',
        defaultName: 'region',
      },
    ],
  },
  {
    key: 'advanced',
    title: 'admin.system.codegen.palette.advanced',
    items: [
      {
        type: 'RichText',
        component: 'RichText',
        icon: 'lucide:file-text',
        label: 'admin.system.codegen.palette.richText',
        defaultName: 'content',
      },
      {
        type: 'IconPicker',
        component: 'IconPicker',
        icon: 'lucide:star',
        label: 'admin.system.codegen.palette.icon',
        defaultName: 'icon',
      },
      {
        type: 'JSON',
        component: 'CodeEditor',
        icon: 'lucide:code-2',
        label: 'admin.system.codegen.palette.json',
        defaultName: 'config',
      },
      {
        type: 'String',
        component: 'ColorPicker',
        icon: 'lucide:palette',
        label: 'admin.system.codegen.palette.color',
        defaultName: 'theme_color',
      },
      {
        type: 'String',
        component: 'CronPicker',
        icon: 'lucide:clock-3',
        label: 'admin.system.codegen.palette.cronPicker',
        defaultName: 'cron_expression',
      },
    ],
  },
  {
    key: 'layout',
    title: 'admin.system.codegen.palette.layout',
    items: [
      {
        type: '__divider__',
        component: 'divider',
        icon: 'lucide:minus',
        label: 'admin.system.codegen.palette.divider',
        defaultName: '',
      },
    ],
  },
];

const COMMON_ITEM_SIGNATURES = new Set([
  'input:title:String',
  'input:name:String',
  'input:code:String',
  'input:email:String',
  'input:phone:String',
  'input:website:String',
  'textarea:description:Text',
  'number:sort_order:Integer',
  'number:price:Decimal',
  'select:status:Enum',
  'switch:is_active:Boolean',
  'date:created_at:DateTime',
  'date:updated_at:DateTime',
  'DictSelect:type:String',
  'ApiSelect:category_id:ForeignKey',
  'ApiTreeSelect:parent_id:TreeSelect',
  'ImageUpload:avatar:ImageUpload',
  'ImageUpload:cover_image:ImageUpload',
  'FilePicker:attachment:File',
  'RichText:content:RichText',
  'IconPicker:icon:IconPicker',
  'CodeEditor:config:JSON',
]);

const emit = defineEmits<{ (e: 'add', item: PaletteItem): void }>();

const searchText = ref('');

const paletteItems = computed<PaletteViewItem[]>(() =>
  PALETTE_GROUPS.flatMap((group) =>
    group.items.map((item) => ({
      ...item,
      groupKey: group.key,
      groupTitle: group.title,
      signature: `${item.component}:${item.defaultName}:${item.type}`,
    })),
  ),
);

const normalizedSearchText = computed(() =>
  searchText.value.trim().toLowerCase(),
);

function isCommonItem(item: PaletteViewItem): boolean {
  return COMMON_ITEM_SIGNATURES.has(item.signature);
}

function getSearchTokens(item: PaletteViewItem): string[] {
  return [
    String($t(item.label)),
    String($t(item.groupTitle)),
    item.defaultName,
    item.type,
    item.component,
  ].map((token) => token.toLowerCase());
}

function itemMatches(item: PaletteViewItem): boolean {
  const query = normalizedSearchText.value;
  if (!query) return true;
  return getSearchTokens(item).some((token) => token.includes(query));
}

const filteredItems = computed(() => paletteItems.value.filter(itemMatches));

const commonItems = computed(() =>
  filteredItems.value.filter((item) => isCommonItem(item)),
);

const showQuickSection = computed(
  () => !normalizedSearchText.value && commonItems.value.length > 0,
);

const visibleGroups = computed(() =>
  PALETTE_GROUPS.map((group) => ({
    ...group,
    titleText: $t(group.title),
    items: filteredItems.value.filter((item) => {
      if (item.groupKey !== group.key) return false;
      if (showQuickSection.value && isCommonItem(item)) return false;
      return true;
    }),
  })).filter((group) => group.items.length > 0),
);

function onDragStart(event: DragEvent, item: PaletteItem) {
  if (!event.dataTransfer) return;
  const payload = JSON.stringify(item);
  event.dataTransfer.effectAllowed = 'copy';
  event.dataTransfer.setData('application/json', payload);
  event.dataTransfer.setData('text/plain', payload);
}

function onClick(item: PaletteItem) {
  emit('add', item);
}
</script>

<template>
  <div
    class="flex min-w-0 flex-col overflow-hidden rounded-[18px] border border-border bg-background shadow-sm"
  >
    <div class="border-b border-border px-3 py-2.5">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <div class="truncate text-sm font-semibold text-foreground">
              {{ $t('admin.system.codegen.builder.paletteTitle') }}
            </div>
            <span
              class="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              {{
                $t('admin.system.codegen.palette.componentCount', {
                  count: paletteItems.length,
                })
              }}
            </span>
          </div>
          <div class="mt-1 text-[11px] leading-5 text-muted-foreground">
            {{ $t('admin.system.codegen.builder.paletteDesc') }}
          </div>
        </div>
        <span
          class="shrink-0 rounded-full border border-border/70 bg-background px-2 py-0.5 text-[11px] text-muted-foreground"
        >
          {{ filteredItems.length }}/{{ paletteItems.length }}
        </span>
      </div>

      <Input
        v-model:value="searchText"
        :placeholder="$t('admin.system.codegen.palette.searchPlaceholder')"
        allow-clear
        size="small"
        class="mt-2"
      >
        <template #prefix>
          <IconifyIcon
            icon="lucide:search"
            class="size-4 text-muted-foreground"
          />
        </template>
      </Input>
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto px-2.5 py-2.5">
      <div
        v-if="filteredItems.length === 0"
        class="flex h-full min-h-[180px] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-muted/15 px-4 text-center"
      >
        <IconifyIcon
          icon="lucide:search-x"
          class="size-8 text-muted-foreground"
        />
        <div class="mt-3 text-sm text-foreground">
          {{ $t('admin.system.codegen.palette.emptyTitle') }}
        </div>
        <div class="mt-1 text-xs leading-5 text-muted-foreground">
          {{ $t('admin.system.codegen.palette.emptyDesc') }}
        </div>
      </div>

      <div v-else class="flex flex-col gap-3">
        <section
          v-if="showQuickSection"
          class="rounded-2xl border border-border/70 bg-muted/10 p-2"
        >
          <div class="mb-2 flex items-center justify-between gap-2 px-1">
            <div class="text-[11px] font-medium text-muted-foreground">
              {{ $t('admin.system.codegen.palette.quickInsert') }}
            </div>
            <span class="text-[10px] text-muted-foreground">
              {{ commonItems.length }}
            </span>
          </div>

          <div class="grid grid-cols-2 gap-1.5">
            <button
              v-for="(item, index) in commonItems"
              :key="`${item.signature}-quick-${index}`"
              type="button"
              class="group rounded-xl border border-border/70 bg-background px-2 py-2 text-left transition-colors hover:border-primary/35 hover:bg-primary/5"
              draggable="true"
              @click="onClick(item)"
              @dragstart="onDragStart($event, item)"
            >
              <span class="flex items-center gap-2">
                <span
                  class="flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted/60 text-foreground ring-1 ring-border/70"
                >
                  <IconifyIcon :icon="item.icon" class="size-3.5" />
                </span>
                <span class="min-w-0 flex-1">
                  <span class="truncate text-xs font-medium text-foreground">
                    {{ $t(item.label) }}
                  </span>
                  <span
                    class="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground"
                  >
                    <span class="truncate font-mono">
                      {{ item.defaultName || '__divider__' }}
                    </span>
                    <span>·</span>
                    <span class="truncate">{{ item.type }}</span>
                  </span>
                </span>
              </span>
            </button>
          </div>
        </section>

        <section
          v-for="group in visibleGroups"
          :key="group.key"
          class="rounded-2xl border border-border/70 bg-background"
        >
          <div
            class="flex items-center justify-between gap-2 border-b border-border/70 px-3 py-2"
          >
            <span class="text-[11px] font-medium text-muted-foreground">
              {{ group.titleText }}
            </span>
            <span class="text-[10px] text-muted-foreground">
              {{ group.items.length }}
            </span>
          </div>

          <div class="grid gap-1.5 p-2">
            <button
              v-for="(item, index) in group.items"
              :key="`${item.signature}-${index}`"
              type="button"
              class="group flex cursor-grab items-center gap-2 rounded-xl border border-border/70 bg-background px-2.5 py-2 text-left transition-colors hover:border-primary/35 hover:bg-primary/5 active:cursor-grabbing"
              draggable="true"
              @click="onClick(item)"
              @dragstart="onDragStart($event, item)"
            >
              <span
                class="flex size-8 shrink-0 items-center justify-center rounded-xl bg-muted/60 text-foreground ring-1 ring-border/70"
              >
                <IconifyIcon :icon="item.icon" class="size-4" />
              </span>

              <span class="min-w-0 flex-1">
                <span class="flex items-center justify-between gap-2">
                  <span class="truncate text-xs font-medium text-foreground">
                    {{ $t(item.label) }}
                  </span>
                  <span
                    v-if="item.multiple"
                    class="shrink-0 rounded-full bg-primary/8 px-1.5 py-0.5 text-[10px] text-primary"
                  >
                    {{ $t('admin.system.codegen.palette.multiBadge') }}
                  </span>
                </span>
                <span
                  class="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground"
                >
                  <span class="truncate font-mono">
                    {{ item.defaultName || '__divider__' }}
                  </span>
                  <span>·</span>
                  <span class="truncate">{{ item.type }}</span>
                </span>
              </span>

              <IconifyIcon
                icon="lucide:plus"
                class="size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
              />
            </button>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
