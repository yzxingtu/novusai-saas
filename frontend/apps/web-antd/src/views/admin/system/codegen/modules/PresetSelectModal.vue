<script lang="ts" setup>
/**
 * 预设模板选择弹窗 / Preset Select Modal
 *
 * 5 张卡片: 空白/基础CRUD/双端CRUD/树形/工作流
 */
import { computed, onMounted, ref } from 'vue';

import { Modal } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { getCodegenPresetsApi } from '#/api/admin/codegen';
import { $t } from '#/locales';

defineOptions({ name: 'PresetSelectModal' });

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ 'update:open': [boolean]; select: [string | null] }>();

const modalOpen = computed({
  get: () => props.open,
  set: (v) => emit('update:open', v),
});

interface PresetCard {
  id: string | null;
  label: string;
  labelEn: string;
  labelKey: string;
  icon: string;
  desc?: string;
}

const PRESET_CARDS: PresetCard[] = [
  {
    id: null,
    label: '空白',
    labelEn: 'Blank',
    labelKey: 'admin.system.codegen.preset.blank',
    icon: 'lucide:file-plus',
    desc: 'admin.system.codegen.preset.blankDesc',
  },
  {
    id: 'simple',
    label: '基础 CRUD',
    labelEn: 'Basic CRUD',
    labelKey: 'admin.system.codegen.preset.simple',
    icon: 'lucide:layers',
    desc: 'admin.system.codegen.preset.simpleDesc',
  },
  {
    id: 'dual_scope',
    label: '双端 CRUD',
    labelEn: 'Dual Scope',
    labelKey: 'admin.system.codegen.preset.dual',
    icon: 'lucide:git-branch',
    desc: 'admin.system.codegen.preset.dualDesc',
  },
  {
    id: 'tree',
    label: '树形',
    labelEn: 'Tree',
    labelKey: 'admin.system.codegen.preset.tree',
    icon: 'lucide:git-branch-plus',
    desc: 'admin.system.codegen.preset.treeDesc',
  },
  {
    id: 'workflow',
    label: '工作流',
    labelEn: 'Workflow',
    labelKey: 'admin.system.codegen.preset.workflow',
    icon: 'lucide:workflow',
    desc: 'admin.system.codegen.preset.workflowDesc',
  },
];

const availablePresets = ref<Set<string>>(new Set());

async function loadPresets() {
  try {
    const names = (await getCodegenPresetsApi()) as string[];
    availablePresets.value = new Set(names || []);
  } catch {
    availablePresets.value = new Set();
  }
}

const displayCards = computed(() =>
  PRESET_CARDS.map((c) => ({
    ...c,
    disabled: c.id !== null && !availablePresets.value.has(c.id),
  })),
);

function onSelect(presetId: string | null) {
  modalOpen.value = false;
  emit('select', presetId);
}

onMounted(loadPresets);
</script>

<template>
  <Modal
    v-model:open="modalOpen"
    :title="$t('admin.system.codegen.preset.title')"
    width="600"
    destroy-on-close
    :footer="null"
  >
    <div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
      <div
        v-for="card in displayCards"
        :key="card.id ?? 'blank'"
        class="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-border p-6 transition-colors"
        :class="
          card.disabled
            ? 'opacity-50 cursor-not-allowed'
            : 'cursor-pointer hover:border-primary/50 hover:bg-primary/5'
        "
        @click="!card.disabled && onSelect(card.id)"
      >
        <IconifyIcon :icon="card.icon" class="mb-2 size-10 text-muted-foreground" />
        <span class="font-medium">{{ $t(card.labelKey) }}</span>
        <span v-if="card.desc" class="mt-1 text-center text-xs text-muted-foreground">
          {{ $t(card.desc) }}
        </span>
      </div>
    </div>
  </Modal>
</template>
