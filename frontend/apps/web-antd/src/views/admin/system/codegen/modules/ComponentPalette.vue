<script lang="ts" setup>
import { computed, ref } from 'vue';
import { Button, Input } from 'ant-design-vue';
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

const PALETTE_GROUPS: PaletteGroup[] = [
  {
    key: 'basic',
    title: 'admin.system.codegen.palette.basicInput',
    items: [
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
        icon: 'lucide:clock',
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

const GROUP_TONES: Record<string, string> = {
  advanced: 'from-violet-500/15 to-fuchsia-500/5',
  basic: 'from-sky-500/15 to-cyan-500/5',
  layout: 'from-slate-500/15 to-slate-400/5',
  relation: 'from-emerald-500/15 to-lime-500/5',
  selector: 'from-amber-500/15 to-orange-500/5',
  upload: 'from-rose-500/15 to-pink-500/5',
};

const emit = defineEmits<{ (e: 'add', item: PaletteItem): void }>();

const searchText = ref('');
const activeGroupKey = ref<'all' | string>('all');

const groupOptions = computed(() => [
  {
    key: 'all',
    title: $t('admin.system.codegen.palette.allComponents'),
    count: PALETTE_GROUPS.reduce(
      (total, group) => total + group.items.length,
      0,
    ),
  },
  ...PALETTE_GROUPS.map((group) => ({
    key: group.key,
    title: $t(group.title),
    count: group.items.length,
  })),
]);

const highlightedItems = computed(() =>
  [
    PALETTE_GROUPS[0]?.items[0],
    PALETTE_GROUPS[0]?.items[1],
    PALETTE_GROUPS[1]?.items[0],
    PALETTE_GROUPS[3]?.items[0],
  ].filter((item): item is PaletteItem => Boolean(item)),
);

const filteredGroups = computed(() => {
  const query = searchText.value.trim().toLowerCase();
  return PALETTE_GROUPS.filter((group) => {
    if (activeGroupKey.value !== 'all' && activeGroupKey.value !== group.key) {
      return false;
    }
    return true;
  })
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => {
        if (!query) return true;
        const label = ($t(item.label) as string).toLowerCase();
        return (
          label.includes(query) ||
          item.defaultName.toLowerCase().includes(query) ||
          item.type.toLowerCase().includes(query)
        );
      }),
    }))
    .filter((group) => group.items.length > 0);
});

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
    class="flex min-w-0 flex-col rounded-[24px] border border-border bg-background p-3 shadow-sm"
  >
    <div class="flex flex-col gap-2">
      <div class="flex items-center justify-between gap-3">
        <div class="flex min-w-0 items-center gap-2">
          <div class="text-sm font-semibold text-foreground">
            {{ $t('admin.system.codegen.builder.paletteTitle') }}
          </div>
          <span
            class="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
          >
            {{
              $t('admin.system.codegen.palette.componentCount', {
                count: groupOptions[0]?.count ?? 0,
              })
            }}
          </span>
        </div>
        <Input
          v-model:value="searchText"
          :placeholder="$t('admin.system.codegen.palette.searchPlaceholder')"
          allow-clear
          size="small"
          class="w-full max-w-[180px]"
        >
          <template #prefix>
            <IconifyIcon
              icon="lucide:search"
              class="size-4 text-muted-foreground"
            />
          </template>
        </Input>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <Button
          v-for="item in highlightedItems"
          :key="`${item.type}-${item.defaultName}`"
          class="!flex !items-center !gap-2 !rounded-full !px-3"
          size="small"
          @click="onClick(item)"
        >
          <IconifyIcon :icon="item.icon" class="size-4 text-muted-foreground" />
          <span>{{ $t(item.label) }}</span>
        </Button>
      </div>
    </div>

    <div class="mt-3 flex flex-wrap gap-2">
      <button
        v-for="group in groupOptions"
        :key="group.key"
        type="button"
        class="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition-colors"
        :class="
          activeGroupKey === group.key
            ? 'bg-primary/8 border-primary text-primary'
            : 'border-border bg-background text-muted-foreground hover:border-primary/30 hover:text-foreground'
        "
        @click="activeGroupKey = group.key"
      >
        <span>{{ group.title }}</span>
        <span
          class="rounded-full bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground"
        >
          {{ group.count }}
        </span>
      </button>
    </div>

    <div class="mt-3 max-h-[680px] min-h-0 flex-1 overflow-y-auto pr-1">
      <div
        v-if="filteredGroups.length === 0"
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

      <div v-else class="flex flex-col gap-4">
        <section
          v-for="group in filteredGroups"
          :key="group.key"
          class="rounded-2xl border border-border/70 bg-background"
        >
          <div
            class="rounded-t-2xl border-b border-border/60 bg-gradient-to-r px-3 py-2.5"
            :class="GROUP_TONES[group.key] ?? 'from-muted/30 to-background'"
          >
            <div class="flex items-center justify-between gap-3">
              <div class="text-sm font-medium text-foreground">
                {{ $t(group.title) }}
              </div>
              <span
                class="rounded-full bg-background/80 px-2 py-0.5 text-[11px] text-muted-foreground"
              >
                {{ group.items.length }}
              </span>
            </div>
          </div>

          <div class="grid gap-2 p-2.5">
            <button
              v-for="(item, index) in group.items"
              :key="`${group.key}-${item.type}-${item.defaultName || index}`"
              type="button"
              class="group flex cursor-grab items-start gap-3 rounded-xl border border-border/70 bg-muted/10 px-3 py-2.5 text-left transition-all hover:border-primary/35 hover:bg-primary/5 active:cursor-grabbing"
              draggable="true"
              @click="onClick(item)"
              @dragstart="onDragStart($event, item)"
            >
              <div
                class="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-background shadow-sm ring-1 ring-border/80"
              >
                <IconifyIcon :icon="item.icon" class="size-5 text-foreground" />
              </div>

              <div class="min-w-0 flex-1">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="truncate text-sm font-medium text-foreground">
                      {{ $t(item.label) }}
                    </div>
                    <div
                      class="mt-1 truncate font-mono text-[11px] text-muted-foreground"
                    >
                      {{ item.defaultName || '__divider__' }}
                    </div>
                  </div>
                  <IconifyIcon
                    icon="lucide:plus"
                    class="mt-0.5 size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
                  />
                </div>

                <div class="mt-2 flex flex-wrap gap-1.5">
                  <span
                    class="rounded-full bg-background px-2 py-0.5 text-[11px] text-muted-foreground ring-1 ring-border/70"
                  >
                    {{ item.type }}
                  </span>
                  <span
                    v-if="item.multiple"
                    class="bg-primary/8 rounded-full px-2 py-0.5 text-[11px] text-primary"
                  >
                    {{ $t('admin.system.codegen.palette.multiBadge') }}
                  </span>
                </div>
              </div>
            </button>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
