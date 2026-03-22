<script lang="ts" setup>
/**
 * 预设模板选择弹窗 / Preset Select Modal
 *
 * 动态读取后端预设元数据，支持搜索与分类展示
 * Loads preset metadata dynamically from backend, with search and categorized cards.
 */
import type { PresetInfo } from '#/api/admin/codegen';

import { computed, onMounted, ref, watch } from 'vue';

import { Input, Modal, Spin, Tag, message } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';

import { getCodegenPresetsApi } from '#/api/admin/codegen';
import { $t } from '#/locales';

defineOptions({ name: 'PresetSelectModal' });

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{
  'update:open': [boolean];
  select: [string | null];
}>();

const currentLocale = computed(() => preferences.app.locale || 'zh-CN');

const modalOpen = computed({
  get: () => props.open,
  set: (v) => emit('update:open', v),
});

const loading = ref(false);
const loadError = ref<string | null>(null);
const searchText = ref('');
const presets = ref<PresetInfo[]>([]);

const isZh = computed(() =>
  String(currentLocale.value || '')
    .toLowerCase()
    .startsWith('zh'),
);

function getPresetLabel(item: PresetInfo) {
  return isZh.value
    ? item.label_zh || item.label_en || item.name
    : item.label_en || item.label_zh || item.name;
}

function getPresetDescription(item: PresetInfo) {
  return isZh.value
    ? item.description_zh || item.description_en || ''
    : item.description_en || item.description_zh || '';
}

function getPresetIcon(item: PresetInfo): string {
  const category = item.category || '';
  if (category === 'workflow') return 'lucide:workflow';
  if (category === 'sub_form') return 'lucide:table';
  if ((item.tags || []).includes('tree')) return 'lucide:git-branch-plus';
  if ((item.tags || []).includes('dual_scope')) return 'lucide:git-branch';
  return 'lucide:layers';
}

const blankCard = computed(() => ({
  id: null as null | string,
  label: $t('admin.system.codegen.preset.blank'),
  desc: $t('admin.system.codegen.preset.blankDesc'),
  icon: 'lucide:file-plus',
  category: 'blank',
  tags: [] as string[],
}));

function getCategoryText(category: string) {
  const map: Record<string, string> = {
    blank: $t('admin.system.codegen.preset.category.blank'),
    crud: $t('admin.system.codegen.preset.category.crud'),
    general: $t('admin.system.codegen.preset.category.general'),
    sub_form: $t('admin.system.codegen.preset.category.subForm'),
    workflow: $t('admin.system.codegen.preset.category.workflow'),
  };
  return (
    map[category] ||
    category ||
    $t('admin.system.codegen.preset.category.general')
  );
}

const displayGroups = computed(() => {
  const keyword = searchText.value.trim().toLowerCase();
  const dynamicCards = presets.value
    .filter((item) => {
      if (!keyword) return true;
      const haystack = [
        item.name,
        getPresetLabel(item),
        getPresetDescription(item),
        item.category,
        ...(item.tags || []),
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(keyword);
    })
    .map((item) => ({
      id: item.name,
      label: getPresetLabel(item),
      desc: getPresetDescription(item),
      icon: getPresetIcon(item),
      category: item.category || 'general',
      tags: item.tags || [],
    }));

  const groups = new Map<
    string,
    Array<{
      category: string;
      desc: string;
      icon: string;
      id: null | string;
      label: string;
      tags: string[];
    }>
  >();

  for (const card of [blankCard.value, ...dynamicCards]) {
    const groupKey = card.category || 'general';
    const current = groups.get(groupKey) || [];
    current.push(card);
    groups.set(groupKey, current);
  }

  const orderedCategories = [
    'blank',
    'crud',
    'workflow',
    'sub_form',
    'general',
  ];
  return orderedCategories
    .filter((category) => groups.has(category))
    .concat(
      [...groups.keys()].filter(
        (category) => !orderedCategories.includes(category),
      ),
    )
    .map((category) => ({
      category,
      label: getCategoryText(category),
      items: groups.get(category) || [],
    }));
});

async function loadPresets() {
  loading.value = true;
  loadError.value = null;
  try {
    presets.value = await getCodegenPresetsApi();
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : $t('common.failed');
    message.error(loadError.value);
    presets.value = [];
  } finally {
    loading.value = false;
  }
}

function onSelect(presetId: string | null) {
  modalOpen.value = false;
  emit('select', presetId);
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      searchText.value = '';
      loadPresets();
    }
  },
);

onMounted(() => {
  if (props.open) loadPresets();
});
</script>

<template>
  <Modal
    v-model:open="modalOpen"
    :title="$t('admin.system.codegen.preset.title')"
    width="760"
    destroy-on-close
    :footer="null"
  >
    <Spin :spinning="loading">
      <div class="mb-4 flex flex-col gap-3">
        <Input
          v-model:value="searchText"
          :placeholder="$t('admin.system.codegen.preset.searchPlaceholder')"
          allow-clear
        >
          <template #prefix>
            <IconifyIcon
              icon="lucide:search"
              class="size-4 text-muted-foreground"
            />
          </template>
        </Input>
        <div
          v-if="loadError"
          class="rounded bg-red-50 p-2 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400"
        >
          {{ loadError }}
        </div>
      </div>

      <div
        v-if="displayGroups.length === 0"
        class="py-12 text-center text-sm text-muted-foreground"
      >
        {{ $t('admin.system.codegen.preset.empty') }}
      </div>

      <div v-else class="flex max-h-[70vh] flex-col gap-5 overflow-y-auto pr-1">
        <section
          v-for="group in displayGroups"
          :key="group.category"
          class="flex flex-col gap-3"
        >
          <div class="flex items-center justify-between gap-3">
            <div class="text-sm font-semibold text-foreground">
              {{ group.label }}
            </div>
            <Tag color="processing" class="!mr-0">
              {{ group.items.length }}
            </Tag>
          </div>
          <div class="grid grid-cols-2 gap-4 xl:grid-cols-3">
            <button
              v-for="card in group.items"
              :key="card.id ?? 'blank'"
              type="button"
              class="group flex min-h-44 flex-col items-start rounded-2xl border border-border bg-background px-4 py-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/45 hover:bg-primary/5"
              @click="onSelect(card.id)"
            >
              <span
                class="group-hover:bg-primary/12 mb-4 inline-flex size-11 items-center justify-center rounded-xl bg-muted text-muted-foreground transition-colors group-hover:text-primary"
              >
                <IconifyIcon :icon="card.icon" class="size-6" />
              </span>
              <span class="mb-2 text-base font-semibold leading-5">{{
                card.label
              }}</span>
              <span class="mb-3 line-clamp-3 text-sm text-muted-foreground">
                {{ card.desc }}
              </span>
              <div
                class="mt-auto flex w-full items-center justify-between gap-2"
              >
                <span
                  class="text-xs uppercase tracking-wide text-muted-foreground/80"
                >
                  {{ group.label }}
                </span>
                <span
                  v-if="card.tags.length > 0"
                  class="truncate text-[11px] text-muted-foreground"
                >
                  {{ card.tags.slice(0, 2).join(' · ') }}
                </span>
              </div>
            </button>
          </div>
        </section>
      </div>
    </Spin>
  </Modal>
</template>
