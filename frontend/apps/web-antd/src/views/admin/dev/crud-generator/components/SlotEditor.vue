<script setup lang="ts">
/**
 * SlotEditor — 自定义列渲染编辑器
 *
 * 三种模式:
 * 1. 预设选择 (13 种列渲染预设，含效果描述)
 * 2. 手写代码 (textarea Vue template)
 * 3. AI 生成 (通过 aiGenerator prop 调用 CRUD Agent)
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
  message,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CustomSlotConfig, ListRenderPreset } from '../types';

import { getRenderPresetOptions } from '../constants';

const T = 'admin.dev.crudGenerator';

type EditorMode = 'ai' | 'code' | 'preset';

/** AI 生成器函数签名：接收 prompt，返回生成的 template 代码 */
type AiGeneratorFn = (prompt: string) => Promise<string>;

const props = defineProps<{
  field?: string;
  slotType?: string;
  template?: string;
  description?: string;
  aiGenerator?: AiGeneratorFn;
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
// Preset → code template + description mapping
// ============================================================

interface PresetInfo {
  template: string;
  descKey: string;
}

const PRESET_TEMPLATES: Record<string, PresetInfo> = {
  tag: {
    template: '<Tag :color="getEnumColor(value)">{{ getEnumLabel(value) }}</Tag>',
    descKey: 'presetDesc.tag',
  },
  badge: {
    template: '<Badge :color="getEnumColor(value)" :text="getEnumLabel(value)" />',
    descKey: 'presetDesc.badge',
  },
  switch: {
    template: '<Switch :checked="!!value" size="small" />',
    descKey: 'presetDesc.switch',
  },
  money: {
    template: '<span class="font-mono">¥ {{ Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2 }) }}</span>',
    descKey: 'presetDesc.money',
  },
  percent: {
    template: '<span>{{ Number(value).toFixed(1) }}%</span>',
    descKey: 'presetDesc.percent',
  },
  progress: {
    template: '<Progress :percent="Number(value)" :show-info="false" size="small" style="width: 80px" />',
    descKey: 'presetDesc.progress',
  },
  relative_time: {
    template: '<Tooltip :title="value"><span class="text-muted-foreground text-xs">{{ formatRelativeTime(value) }}</span></Tooltip>',
    descKey: 'presetDesc.relativeTime',
  },
  datetime: {
    template: '<span class="text-muted-foreground text-xs tabular-nums">{{ String(value).slice(0, 19) }}</span>',
    descKey: 'presetDesc.datetime',
  },
  date: {
    template: '<span class="text-muted-foreground text-xs tabular-nums">{{ String(value).slice(0, 10) }}</span>',
    descKey: 'presetDesc.date',
  },
  avatar: {
    template: '<Avatar :size="24" :src="value">{{ String(value).charAt(0) }}</Avatar>',
    descKey: 'presetDesc.avatar',
  },
  image: {
    template: '<img :src="value" class="h-8 w-8 rounded object-cover" />',
    descKey: 'presetDesc.image',
  },
  link: {
    template: '<a :href="value" target="_blank" class="text-primary truncate">{{ value }}</a>',
    descKey: 'presetDesc.link',
  },
  copy: {
    template: '<span class="flex items-center gap-1"><span class="truncate">{{ value }}</span><CopyIcon class="size-3" /></span>',
    descKey: 'presetDesc.copy',
  },
};

const selectedPresetDesc = ref('');

watch(selectedPreset, (val) => {
  if (val && PRESET_TEMPLATES[val]) {
    const info = PRESET_TEMPLATES[val]!;
    codeContent.value = info.template;
    selectedPresetDesc.value = $t(`${T}.slotEditor.${info.descKey}`);
  } else {
    selectedPresetDesc.value = '';
  }
});

// ============================================================
// AI generation (via aiGenerator prop → CRUD Agent)
// ============================================================

async function generateWithAi() {
  if (!aiPrompt.value.trim()) return;

  if (!props.aiGenerator) {
    message.warning($t(`${T}.slotEditor.aiUnavailable`));
    return;
  }

  aiGenerating.value = true;
  aiResult.value = '';

  try {
    const result = await props.aiGenerator(aiPrompt.value);
    aiResult.value = result;
    codeContent.value = result;
  } catch (err: unknown) {
    message.error((err as Error).message || String(err));
  } finally {
    aiGenerating.value = false;
  }
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
        :options="getRenderPresetOptions()"
        :placeholder="$t(`${T}.slotEditor.presetHint`)"
        class="w-full"
      >
        <template #option="{ icon, label }">
          <div class="flex items-center gap-1.5">
            <span v-if="icon" :class="[icon, 'size-3.5 opacity-60']" />
            <span>{{ label }}</span>
          </div>
        </template>
      </Select>
      <div v-if="selectedPresetDesc" class="mt-2 rounded-md bg-primary/5 p-2.5 text-xs text-muted-foreground">
        <span class="icon-[lucide--info] mr-1 inline-block size-3 align-text-bottom" />
        {{ selectedPresetDesc }}
      </div>
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
