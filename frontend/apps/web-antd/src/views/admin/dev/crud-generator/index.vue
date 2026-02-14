<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';

import { Button, message, Radio, Steps, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

import type { CommandItem } from './components/CommandPalette.vue';

import AiAssistant from './components/AiAssistant.vue';
import BatchEntityEditor from './components/BatchEntityEditor.vue';
import CommandPalette from './components/CommandPalette.vue';
import StepBasicInfo from './components/StepBasicInfo.vue';
import StepCodePreview from './components/StepCodePreview.vue';
import StepFieldDefine from './components/StepFieldDefine.vue';
import StepFormConfig from './components/StepFormConfig.vue';
import StepListConfig from './components/StepListConfig.vue';
import { createDefaultField } from './composables/field-inference';
import { useBatchEditor } from './composables/use-batch-editor';
import { useCrudAiAssistant } from './composables/use-crud-ai-assistant';
import { useTouchedPaths } from './composables/use-config-merge';
import { useCrudConfig } from './composables/use-crud-config';
import { useMockData } from './composables/use-mock-data';
import { useShortcuts } from './composables/use-shortcuts';

import type { WizardStep } from './types';

const crudConfig = useCrudConfig();
const {
  config,
  currentStep,
  isDirty,
  isGenerating,
  undo,
  redo,
  canUndo,
  canRedo,
  snapshot,
  nextStep,
  prevStep,
  goToStep,
  resetConfig,
  loadConfig,
} = crudConfig;

// ============================================================
// Batch (multi-entity) mode
// ============================================================

type GeneratorMode = 'single' | 'batch';
const generatorMode = ref<GeneratorMode>('single');
const batchEditor = useBatchEditor();

// ============================================================
// Mock data for List/Form preview
// ============================================================

const { mockData } = useMockData(() => config.value);

// ============================================================
// TouchedPaths — tracks user-edited fields
// ============================================================

const touchedPaths = useTouchedPaths();

// ============================================================
// AI Assistant
// ============================================================

const aiAssistant = useCrudAiAssistant({
  config,
  loadConfig,
  snapshot,
  touchedPaths,
});

// ============================================================
// Wizard ↔ Code dual mode
// ============================================================

type EditMode = 'code' | 'wizard';
const editMode = ref<EditMode>('wizard');
const codeContent = ref('');

function toggleMode() {
  if (editMode.value === 'wizard') {
    codeContent.value = JSON.stringify(config.value, null, 2);
    editMode.value = 'code';
  } else {
    try {
      const parsed = JSON.parse(codeContent.value);
      loadConfig(parsed);
      editMode.value = 'wizard';
      message.success($t('admin.dev.crudGenerator.mode.syncSuccess'));
    } catch {
      message.error($t('admin.dev.crudGenerator.mode.jsonError'));
    }
  }
}

watch(
  config,
  () => {
    if (editMode.value === 'code') {
      codeContent.value = JSON.stringify(config.value, null, 2);
    }
  },
  { deep: true },
);

// ============================================================
// Command Palette
// ============================================================

const commandPaletteOpen = ref(false);

const CT = 'admin.dev.crudGenerator.command';

const commands = computed<CommandItem[]>(() => [
  {
    key: 'addField',
    label: $t(`${CT}.addField`),
    icon: 'icon-[lucide--plus]',
    action: () => {
      config.value.fields.push(createDefaultField());
      snapshot();
      goToStep(1);
    },
  },
  {
    key: 'addRelation',
    label: $t(`${CT}.addRelation`),
    icon: 'icon-[lucide--link]',
    action: () => {
      goToStep(0);
    },
  },
  {
    key: 'nextStep',
    label: $t(`${CT}.nextStep`),
    icon: 'icon-[lucide--arrow-right]',
    shortcut: 'Ctrl+Enter',
    action: nextStep,
  },
  {
    key: 'prevStep',
    label: $t(`${CT}.prevStep`),
    icon: 'icon-[lucide--arrow-left]',
    action: prevStep,
  },
  {
    key: 'undo',
    label: $t(`${CT}.undo`),
    icon: 'icon-[lucide--undo-2]',
    shortcut: 'Ctrl+Z',
    action: undo,
  },
  {
    key: 'redo',
    label: $t(`${CT}.redo`),
    icon: 'icon-[lucide--redo-2]',
    shortcut: 'Ctrl+Shift+Z',
    action: redo,
  },
  {
    key: 'preview',
    label: $t(`${CT}.preview`),
    icon: 'icon-[lucide--eye]',
    shortcut: 'Ctrl+P',
    action: () => goToStep(4),
  },
  {
    key: 'generate',
    label: $t(`${CT}.generate`),
    icon: 'icon-[lucide--play]',
    action: () => {
      goToStep(4);
      snapshot();
    },
  },
  {
    key: 'reset',
    label: $t(`${CT}.reset`),
    icon: 'icon-[lucide--rotate-ccw]',
    action: resetConfig,
  },
  {
    key: 'toggleMode',
    label: $t(`${CT}.toggleMode`),
    icon: 'icon-[lucide--code-2]',
    shortcut: 'Ctrl+M',
    action: toggleMode,
  },
]);

// ============================================================
// Shortcuts
// ============================================================

useShortcuts(crudConfig, {
  toggleCommandPalette: () => {
    commandPaletteOpen.value = !commandPaletteOpen.value;
  },
  toggleMode,
  openAiAssistant: () => aiAssistant.open(),
});

// ============================================================
// Steps
// ============================================================

const steps = computed(() => [
  {
    title: $t('admin.dev.crudGenerator.steps.basicInfo'),
    icon: 'lucide:file-text',
  },
  {
    title: $t('admin.dev.crudGenerator.steps.fields'),
    icon: 'lucide:columns',
  },
  {
    title: $t('admin.dev.crudGenerator.steps.listConfig'),
    icon: 'lucide:table',
  },
  {
    title: $t('admin.dev.crudGenerator.steps.formConfig'),
    icon: 'lucide:layout',
  },
  {
    title: $t('admin.dev.crudGenerator.steps.preview'),
    icon: 'lucide:code',
  },
]);

const isFirstStep = computed(() => currentStep.value === 0);
const isLastStep = computed(() => currentStep.value === 4);

function handleStepClick(step: number) {
  goToStep(step as WizardStep);
}
</script>

<template>
  <Page :title="$t('admin.dev.crudGenerator.title')" content-class="p-4">
    <!-- Header: Steps + Undo/Redo + Mode Toggle -->
    <div class="mb-6 flex items-center justify-between">
      <Steps
        v-if="editMode === 'wizard'"
        :current="currentStep"
        class="flex-1"
        size="small"
        @change="handleStepClick"
      >
        <Steps.Step
          v-for="(step, idx) in steps"
          :key="idx"
          :title="step.title"
        />
      </Steps>
      <div v-else class="flex-1">
        <span class="text-lg font-medium">{{ $t('admin.dev.crudGenerator.mode.code') }}</span>
      </div>

      <div class="ml-4 flex shrink-0 items-center gap-2">
        <!-- Generator Mode: Single / Batch -->
        <Radio.Group
          v-model:value="generatorMode"
          button-style="solid"
          size="small"
        >
          <Radio.Button value="single">
            <span class="icon-[lucide--file-text] mr-1 size-3.5" />
            {{ $t('admin.dev.crudGenerator.mode.wizard') }}
          </Radio.Button>
          <Radio.Button value="batch">
            <span class="icon-[lucide--layers] mr-1 size-3.5" />
            {{ $t('admin.dev.crudGenerator.batchEditor.title') }}
          </Radio.Button>
        </Radio.Group>

        <div class="bg-border mx-1 h-5 w-px" />

        <!-- Edit Mode Toggle (wizard/code) — only in single mode -->
        <Radio.Group
          v-if="generatorMode === 'single'"
          :value="editMode"
          button-style="solid"
          size="small"
          @change="toggleMode"
        >
          <Radio.Button value="wizard">
            <span class="icon-[lucide--wand-2] mr-1 size-3.5" />
            {{ $t('admin.dev.crudGenerator.mode.wizard') }}
          </Radio.Button>
          <Radio.Button value="code">
            <span class="icon-[lucide--code-2] mr-1 size-3.5" />
            {{ $t('admin.dev.crudGenerator.mode.code') }}
          </Radio.Button>
        </Radio.Group>

        <div class="bg-border mx-1 h-5 w-px" />

        <!-- AI Assistant trigger -->
        <Tooltip title="Ctrl+I">
          <Button
            size="small"
            type="text"
            @click="aiAssistant.open()"
          >
            <template #icon>
              <span class="icon-[lucide--sparkles] size-4" />
            </template>
          </Button>
        </Tooltip>

        <!-- Command Palette trigger -->
        <Tooltip title="Ctrl+K">
          <Button
            size="small"
            type="text"
            @click="commandPaletteOpen = true"
          >
            <template #icon>
              <span class="icon-[lucide--command] size-4" />
            </template>
          </Button>
        </Tooltip>

        <Button
          :disabled="!canUndo"
          size="small"
          type="text"
          @click="undo"
        >
          <template #icon>
            <span class="icon-[lucide--undo-2] size-4" />
          </template>
        </Button>
        <Button
          :disabled="!canRedo"
          size="small"
          type="text"
          @click="redo"
        >
          <template #icon>
            <span class="icon-[lucide--redo-2] size-4" />
          </template>
        </Button>
      </div>
    </div>

    <!-- ============ Batch Mode: Multi-Entity Editor ============ -->
    <div v-if="generatorMode === 'batch'" class="min-h-[500px]">
      <BatchEntityEditor :editor="batchEditor" />
    </div>

    <!-- ============ Single Mode ============ -->
    <template v-else>
      <!-- Wizard Mode: Step Content -->
      <div v-if="editMode === 'wizard'" class="wizard-content relative min-h-[400px] overflow-hidden">
        <Transition :name="'slide-left'" mode="out-in">
          <div :key="currentStep" class="w-full">
            <!-- Step 0: 基本信息 -->
            <div v-if="currentStep === 0">
              <StepBasicInfo :config="config" @update:config="loadConfig" @snapshot="snapshot" />
            </div>

            <!-- Step 1: 字段定义 -->
            <div v-else-if="currentStep === 1">
              <StepFieldDefine :config="config" @update:config="loadConfig" @snapshot="snapshot" />
            </div>

            <!-- Step 2: 列表配置 -->
            <div v-else-if="currentStep === 2">
              <StepListConfig
                :config="config"
                :mock-data="mockData"
                @update:config="loadConfig"
              />
            </div>

            <!-- Step 3: 表单配置 -->
            <div v-else-if="currentStep === 3">
              <StepFormConfig
                :config="config"
                :mock-data="mockData"
                @update:config="loadConfig"
              />
            </div>

            <!-- Step 4: 代码预览 -->
            <div v-else-if="currentStep === 4">
              <StepCodePreview :config="config" />
            </div>
          </div>
        </Transition>
      </div>

      <!-- Code Mode: JSON Editor -->
      <div v-else class="code-mode min-h-[400px]">
        <textarea
          v-model="codeContent"
          class="bg-accent/50 h-[600px] w-full resize-y rounded-lg border p-4 font-mono text-sm leading-relaxed focus:border-primary focus:outline-none"
          spellcheck="false"
        />
      </div>
    </template>

    <!-- Command Palette -->
    <CommandPalette
      :commands="commands"
      :open="commandPaletteOpen"
      @close="commandPaletteOpen = false"
    />

    <!-- AI Assistant Drawer -->
    <AiAssistant :assistant="aiAssistant" />

    <!-- Footer: Navigation -->
    <div class="mt-6 flex items-center justify-between border-t pt-4">
      <div>
        <Button
          v-if="isDirty"
          danger
          type="text"
          @click="resetConfig"
        >
          {{ $t('admin.dev.crudGenerator.reset') }}
        </Button>
      </div>

      <div class="flex items-center gap-3">
        <Button
          v-if="!isFirstStep"
          @click="prevStep"
        >
          {{ $t('admin.dev.crudGenerator.prev') }}
        </Button>
        <Button
          v-if="!isLastStep"
          type="primary"
          @click="nextStep"
        >
          {{ $t('admin.dev.crudGenerator.next') }}
        </Button>
        <Button
          v-if="isLastStep"
          :loading="isGenerating"
          type="primary"
          @click="snapshot"
        >
          {{ $t('admin.dev.crudGenerator.generate') }}
        </Button>
      </div>
    </div>
  </Page>
</template>

<style scoped>
/* Slide left transition */
.slide-left-enter-active,
.slide-left-leave-active {
  transition: all 0.25s ease;
}

.slide-left-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.slide-left-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}
</style>
