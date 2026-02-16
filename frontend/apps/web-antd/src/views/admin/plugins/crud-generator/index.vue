<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import { Alert, message, Modal } from 'ant-design-vue';

import { $t } from '#/locales';
import { useGlobalAIChatStore } from '#/store';

import { generateCrudApi } from '#/api/admin/crud-generator';
import { resolveAgentAssignmentApi } from '#/api/shared/agent-assignments';

import type { CrudConfig } from './types';
import type { CommandItem } from './components/CommandPalette.vue';

import AiPromptBar from './components/AiPromptBar.vue';
import CommandPalette from './components/CommandPalette.vue';
import ConfigPanel from './components/ConfigPanel.vue';
import FieldImportWizard from './components/FieldImportWizard.vue';
import GeneratorToolbar from './components/GeneratorToolbar.vue';
import JsonEditorDrawer from './components/JsonEditorDrawer.vue';
import PreviewPanel from './components/PreviewPanel.vue';
import { createDefaultField } from './composables/field-inference';
import { useCrudConfig } from './composables/use-crud-config';
import { useCrudFormBridge } from './composables/use-crud-form-bridge';
import { useMockData } from './composables/use-mock-data';
import { useShortcuts } from './composables/use-shortcuts';


const crudConfig = useCrudConfig();
const {
  config,
  isDirty,
  isGenerating,
  undo,
  redo,
  canUndo,
  canRedo,
  snapshot,
  configWarnings,
  resetConfig,
  loadConfig,
} = crudConfig;

// ============================================================
// Mock data for List/Form preview
// ============================================================

const { mockData } = useMockData(() => config.value);

// AI tool call → CRUD form bridge
const { handleToolCall: bridgeHandleToolCall } = useCrudFormBridge({
  config,
  loadConfig,
  snapshot,
});

const globalChatStore = useGlobalAIChatStore();

// AI Prompt Bar
const aiBarCollapsed = ref(false);

// Resolve CRUD Generator agent binding
const crudAgentId = ref<number | undefined>(undefined);
onMounted(async () => {
  try {
    const result = await resolveAgentAssignmentApi('/admin', 'crud_generator');
    if (result.agent_id && result.is_active) {
      crudAgentId.value = result.agent_id;
    }
  } catch {
    // fallback: no agent pre-selected
  }
});

function openCrudAIChat() {
  if (crudAgentId.value) {
    globalChatStore.openWithAgent(crudAgentId.value);
  } else {
    globalChatStore.show();
  }
}

// ============================================================
// JSON Mode
// ============================================================

const jsonDrawerOpen = ref(false);

function toggleJsonMode() {
  jsonDrawerOpen.value = !jsonDrawerOpen.value;
}

function onJsonApply(newConfig: CrudConfig) {
  loadConfig(newConfig);
  message.success($t('admin.dev.crudGenerator.mode.syncSuccess'));
}

// ============================================================
// Generate
// ============================================================

const hasModule = computed(() => Boolean(config.value.module));
const hasFields = computed(() => config.value.fields.length > 0);

async function handleGenerate() {
  if (!hasModule.value || !hasFields.value) {
    message.warning($t('admin.dev.crudGenerator.generateValidation'));
    return;
  }

  isGenerating.value = true;
  try {
    const res = await generateCrudApi(config.value, { confirmed: false });

    const { total_new: fileCount = 0, total_conflict: conflictCount = 0 } = res;

    isGenerating.value = false;

    Modal.confirm({
      title: $t('admin.dev.crudGenerator.generateConfirm.title'),
      content: $t('admin.dev.crudGenerator.generateConfirm.content', {
        files: fileCount,
        conflicts: conflictCount,
      }),
      okText: $t('admin.dev.crudGenerator.generateConfirm.ok'),
      cancelText: $t('admin.dev.crudGenerator.generateConfirm.cancel'),
      onOk: async () => {
        isGenerating.value = true;
        try {
          const genRes = await generateCrudApi(config.value, {
            confirmed: true,
            conflictAction: 'skip',
          });
          message.success(
            $t('admin.dev.crudGenerator.generateSuccess', {
              count: genRes.written?.length ?? 0,
            }),
          );
          snapshot();
        } catch (err) {
          message.error(String(err));
        } finally {
          isGenerating.value = false;
        }
      },
    });
  } catch (err) {
    message.error(String(err));
    isGenerating.value = false;
  }
}

// ============================================================
// Command Palette
// ============================================================

const commandPaletteOpen = ref(false);
const importWizardOpen = ref(false);

function onImportApplied(fields: import('./types').FieldConfig[]) {
  config.value = { ...config.value, fields };
  snapshot();
  importWizardOpen.value = false;
}

const CT = 'admin.dev.crudGenerator.command';

const commands = computed<CommandItem[]>(() => [
  {
    key: 'addField',
    label: $t(`${CT}.addField`),
    icon: 'icon-[lucide--plus]',
    action: () => {
      config.value.fields.push(createDefaultField());
      snapshot();
    },
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
    key: 'generate',
    label: $t(`${CT}.generate`),
    icon: 'icon-[lucide--play]',
    action: handleGenerate,
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
    action: toggleJsonMode,
  },
]);

// ============================================================
// Shortcuts
// ============================================================

useShortcuts(crudConfig, {
  toggleCommandPalette: () => {
    commandPaletteOpen.value = !commandPaletteOpen.value;
  },
  toggleMode: toggleJsonMode,
  openGlobalChat: () => openCrudAIChat(),
  generate: handleGenerate,
  addField: () => {
    config.value.fields.push(createDefaultField());
    snapshot();
  },
});
</script>

<template>
  <Page :title="$t('admin.dev.crudGenerator.title')" content-class="p-0">
    <!-- Toolbar -->
    <GeneratorToolbar
      :can-undo="canUndo"
      :can-redo="canRedo"
      :is-dirty="isDirty"
      :is-generating="isGenerating"
      :has-module="hasModule"
      :has-fields="hasFields"
      @undo="undo"
      @redo="redo"
      @reset="resetConfig"
      @generate="handleGenerate"
      @toggle-json="toggleJsonMode"
      @open-history="() => {}"
      @open-import="importWizardOpen = true"
      @quick-start-select="(c) => loadConfig(c)"
      @open-ai-chat="openCrudAIChat"
      @open-command-palette="commandPaletteOpen = true"
    />

    <!-- AI Prompt Bar -->
    <AiPromptBar
      v-if="crudAgentId"
      :agent-id="crudAgentId"
      v-model:collapsed="aiBarCollapsed"
      @tool-call="bridgeHandleToolCall"
    />

    <!-- Main Split Layout: Config (left 45%) | Preview (right 55%) -->
    <div class="crud-layout flex" style="height: calc(100vh - 180px)">
      <!-- Left: Config Panel (scrollable) -->
      <div class="config-side w-[45%] min-w-[380px] overflow-y-auto border-r">
        <ConfigPanel
          :config="config"
          @update:config="loadConfig"
          @snapshot="snapshot"
          @open-import="importWizardOpen = true"
        />
      </div>

      <!-- Right: Preview Panel (sticky) -->
      <div class="preview-side flex-1 overflow-y-auto">
        <PreviewPanel
          :config="config"
          :mock-data="mockData"
        />
      </div>
    </div>

    <!-- Config Warnings -->
    <Alert
      v-if="configWarnings.length > 0"
      class="mx-4 mt-3"
      :type="configWarnings.some((w) => w.severity === 'error') ? 'error' : 'warning'"
      show-icon
      closable
    >
      <template #message>
        <ul class="m-0 list-disc pl-4 text-xs">
          <li v-for="(w, i) in configWarnings" :key="i">
            <span v-if="w.field" class="font-mono">{{ w.field }}: </span>
            {{ $t(`admin.dev.crudGenerator.validation.${w.message}`) }}
          </li>
        </ul>
      </template>
    </Alert>

    <!-- JSON Editor Drawer -->
    <JsonEditorDrawer
      :config="config"
      :open="jsonDrawerOpen"
      @update:open="(v) => (jsonDrawerOpen = v)"
      @apply="onJsonApply"
    />

    <!-- Field Import Wizard -->
    <FieldImportWizard
      :entity="config"
      :open="importWizardOpen"
      @update:open="(v) => (importWizardOpen = v)"
      @applied="(fields) => onImportApplied(fields)"
    />

    <!-- Command Palette -->
    <CommandPalette
      :commands="commands"
      :open="commandPaletteOpen"
      @close="commandPaletteOpen = false"
    />
  </Page>
</template>
