<script setup lang="ts">
/**
 * SlotEditor — 自定义列渲染编辑器
 *
 * 三种模式:
 * 1. 预设选择 (13 种列渲染预设)
 * 2. 手写代码 (textarea Vue template)
 * 3. AI 生成 (通过 CRUD Agent 生成 Vue template)
 */
import { ref, watch } from 'vue';

import {
  Button,
  Drawer,
  Input,
  Radio,
  Select,
  Space,
  Spin,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CustomSlotConfig, ListRenderPreset } from '../types';

import { getRenderPresetOptions } from '../constants';

const T = 'admin.dev.crudGenerator';

type EditorMode = 'ai' | 'code' | 'preset';

const props = defineProps<{
  field?: string;
  slotType?: string;
  template?: string;
  description?: string;
}>();

const emit = defineEmits<{
  (e: 'apply', slot: CustomSlotConfig): void;
  (e: 'close'): void;
}>();

const drawerOpen = ref(false);
const mode = ref<EditorMode>('preset');
const selectedPreset = ref<ListRenderPreset | ''>('');
const codeContent = ref('');
const aiPrompt = ref('');
const aiGenerating = ref(false);
const aiResult = ref('');

function open() {
  drawerOpen.value = true;
  if (props.template) {
    codeContent.value = props.template;
    mode.value = 'code';
  } else {
    codeContent.value = '';
    mode.value = 'preset';
  }
  selectedPreset.value = '';
  aiPrompt.value = '';
  aiResult.value = '';
}

function close() {
  drawerOpen.value = false;
  emit('close');
}

defineExpose({ open, close });

// ============================================================
// Preset options
// ============================================================

const PRESETS = getRenderPresetOptions();

// ============================================================
// Preset → code template mapping
// ============================================================

const PRESET_TEMPLATES: Record<string, string> = {
  tag: '<Tag :color="getEnumColor(value)">{{ getEnumLabel(value) }}</Tag>',
  badge: '<Badge :color="getEnumColor(value)" :text="getEnumLabel(value)" />',
  switch: '<Switch :checked="!!value" size="small" />',
  money: '<span class="font-mono">¥ {{ Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2 }) }}</span>',
  percent: '<span>{{ Number(value).toFixed(1) }}%</span>',
  progress: '<Progress :percent="Number(value)" :show-info="false" size="small" style="width: 80px" />',
  relative_time: '<Tooltip :title="value"><span class="text-muted-foreground text-xs">{{ formatRelativeTime(value) }}</span></Tooltip>',
  datetime: '<span class="text-muted-foreground text-xs tabular-nums">{{ String(value).slice(0, 19) }}</span>',
  date: '<span class="text-muted-foreground text-xs tabular-nums">{{ String(value).slice(0, 10) }}</span>',
  avatar: '<Avatar :size="24" :src="value">{{ String(value).charAt(0) }}</Avatar>',
  image: '<img :src="value" class="h-8 w-8 rounded object-cover" />',
  link: '<a :href="value" target="_blank" class="text-primary truncate">{{ value }}</a>',
  copy: '<span class="flex items-center gap-1"><span class="truncate">{{ value }}</span><CopyIcon class="size-3" /></span>',
};

watch(selectedPreset, (val) => {
  if (val && PRESET_TEMPLATES[val]) {
    codeContent.value = PRESET_TEMPLATES[val]!;
  }
});

// ============================================================
// AI generation (via Agent — placeholder for actual integration)
// ============================================================

async function generateWithAi() {
  if (!aiPrompt.value.trim()) return;
  aiGenerating.value = true;
  aiResult.value = '';

  // Simulate typewriter effect — in production this sends to CRUD Agent
  const mockTemplate = `<Tag :color="getStatusColor(value)">{{ getStatusLabel(value) }}</Tag>`;
  for (let i = 0; i <= mockTemplate.length; i++) {
    aiResult.value = mockTemplate.slice(0, i);
    await new Promise((r) => setTimeout(r, 20));
  }

  codeContent.value = aiResult.value;
  aiGenerating.value = false;
}

// ============================================================
// Apply
// ============================================================

function apply() {
  const slot: CustomSlotConfig = {
    field: props.field || '',
    slot_type: props.slotType || 'list',
    template: codeContent.value,
    description: props.description || aiPrompt.value || selectedPreset.value || '',
    ai_generated: mode.value === 'ai',
  };
  emit('apply', slot);
  close();
}
</script>

<template>
  <Drawer
    :open="drawerOpen"
    :title="$t(`${T}.slotEditor.title`)"
    :width="560"
    @close="close"
  >
    <template #footer>
      <Space>
        <Button @click="close">{{ $t(`${T}.slotEditor.cancel`) }}</Button>
        <Button :disabled="!codeContent.trim()" type="primary" @click="apply">
          {{ $t(`${T}.slotEditor.apply`) }}
        </Button>
      </Space>
    </template>

    <!-- Mode selector -->
    <Radio.Group v-model:value="mode" button-style="solid" class="mb-4" size="small">
      <Radio.Button value="preset">{{ $t(`${T}.slotEditor.modePreset`) }}</Radio.Button>
      <Radio.Button value="code">{{ $t(`${T}.slotEditor.modeCode`) }}</Radio.Button>
      <Radio.Button value="ai">{{ $t(`${T}.slotEditor.modeAi`) }}</Radio.Button>
    </Radio.Group>

    <!-- Preset mode -->
    <div v-if="mode === 'preset'" class="space-y-3">
      <p class="text-muted-foreground text-sm">{{ $t(`${T}.slotEditor.presetHint`) }}</p>
      <Select
        v-model:value="selectedPreset"
        :options="PRESETS"
        :placeholder="$t(`${T}.slotEditor.presetHint`)"
        class="w-full"
      />
      <div v-if="codeContent" class="mt-3">
        <p class="mb-1 text-xs font-medium">{{ $t(`${T}.slotEditor.previewTitle`) }}</p>
        <pre class="bg-accent/30 overflow-auto rounded-md p-3 text-xs">{{ codeContent }}</pre>
      </div>
    </div>

    <!-- Code mode -->
    <div v-else-if="mode === 'code'" class="space-y-3">
      <p class="text-muted-foreground text-sm">{{ $t(`${T}.slotEditor.codeHint`) }}</p>
      <Input.TextArea
        v-model:value="codeContent"
        :auto-size="{ minRows: 8, maxRows: 20 }"
        :placeholder="$t(`${T}.slotEditor.codePlaceholder`)"
        class="font-mono text-xs"
      />
    </div>

    <!-- AI mode -->
    <div v-else-if="mode === 'ai'" class="space-y-3">
      <p class="text-muted-foreground text-sm">{{ $t(`${T}.slotEditor.aiHint`) }}</p>
      <Input.TextArea
        v-model:value="aiPrompt"
        :auto-size="{ minRows: 3, maxRows: 6 }"
        :disabled="aiGenerating"
        :placeholder="$t(`${T}.slotEditor.aiPlaceholder`)"
      />
      <Button
        :disabled="!aiPrompt.trim()"
        :loading="aiGenerating"
        type="primary"
        @click="generateWithAi"
      >
        {{ aiGenerating ? $t(`${T}.slotEditor.aiGenerating`) : $t(`${T}.slotEditor.aiGenerate`) }}
      </Button>

      <Spin v-if="aiGenerating" size="small" />

      <div v-if="aiResult" class="mt-3">
        <p class="mb-1 text-xs font-medium">{{ $t(`${T}.slotEditor.previewTitle`) }}</p>
        <pre class="bg-accent/30 overflow-auto rounded-md p-3 font-mono text-xs">{{ aiResult }}</pre>
      </div>
    </div>
  </Drawer>
</template>
