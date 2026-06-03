<script lang="ts" setup>
import type {
  AgentRoutingModelOptions,
  AgentRoutingOption,
  AgentRoutingState,
} from '#/composables/use-agent-routing';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Select as ASelect, Button, InputNumber, Switch } from 'ant-design-vue';

import { $t } from '#/locales';

interface Props {
  canEdit?: boolean;
  i18nPrefix: string;
  modelOptions: AgentRoutingModelOptions;
  saving?: boolean;
  showSaveButton?: boolean;
  tierOptions: AgentRoutingOption<string>[];
}

const props = withDefaults(defineProps<Props>(), {
  canEdit: true,
  saving: false,
  showSaveButton: true,
});

const emit = defineEmits<{
  save: [];
}>();

const state = defineModel<AgentRoutingState>('state', { required: true });

const routingKey = computed(() => `${props.i18nPrefix}.routing`);

function tr(key: string): string {
  return $t(`${routingKey.value}.${key}`);
}

function onSave() {
  emit('save');
}
</script>

<template>
  <div class="p-5 pt-3">
    <div
      class="mb-5 rounded-xl border-2 p-5 transition-all duration-300"
      :class="
        state.enabled
          ? 'border-green-500/30 bg-green-500/5'
          : 'border-border bg-accent/20'
      "
    >
      <div class="flex items-start gap-4">
        <div
          class="flex size-12 shrink-0 items-center justify-center rounded-xl transition-all duration-300"
          :class="
            state.enabled
              ? 'bg-green-500/10 text-green-600 dark:text-green-400'
              : 'bg-muted text-muted-foreground'
          "
        >
          <IconifyIcon icon="lucide:git-branch" class="size-6" />
        </div>
        <div class="flex-1">
          <div class="flex items-center justify-between gap-4">
            <div>
              <h3 class="text-base font-semibold text-foreground">
                {{ tr('enableRouting') }}
              </h3>
              <p class="mt-0.5 text-sm text-muted-foreground">
                {{ tr('description') }}
              </p>
            </div>
            <Switch
              v-model:checked="state.enabled"
              :disabled="!canEdit"
              class="shrink-0"
              :aria-label="tr('enableRouting')"
            />
          </div>
          <div
            v-if="state.enabled"
            class="mt-3 inline-flex items-center gap-1.5 rounded-full bg-green-500/10 px-3 py-1 text-xs font-medium text-green-600 dark:text-green-400"
          >
            <span
              class="inline-block size-1.5 rounded-full bg-green-500"
            ></span>
            {{ tr('statusEnabled') }}
          </div>
        </div>
      </div>
    </div>

    <div v-if="state.enabled" class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div class="rounded-xl border bg-background p-5 shadow-sm">
        <div class="mb-4 flex items-center gap-3">
          <div
            class="flex size-9 items-center justify-center rounded-xl bg-amber-500/10"
          >
            <IconifyIcon icon="lucide:layers" class="size-5 text-amber-500" />
          </div>
          <div>
            <div class="text-sm font-semibold">{{ tr('maxTier') }}</div>
            <div class="text-xs text-muted-foreground">
              {{ tr('maxTierHelp') }}
            </div>
          </div>
        </div>
        <ASelect
          v-model:value="state.maxTier"
          :options="tierOptions"
          class="w-full"
          :allow-clear="true"
          :disabled="!canEdit"
          :placeholder="tr('noLimit')"
        />
      </div>

      <div class="rounded-xl border bg-background p-5 shadow-sm">
        <div class="mb-4 flex items-center gap-3">
          <div
            class="flex size-9 items-center justify-center rounded-xl bg-violet-500/10"
          >
            <IconifyIcon icon="lucide:eye" class="size-5 text-violet-500" />
          </div>
          <div>
            <div class="text-sm font-semibold">{{ tr('visionModel') }}</div>
            <div class="text-xs text-muted-foreground">
              {{ tr('visionModelHelp') }}
            </div>
          </div>
        </div>
        <ASelect
          v-model:value="state.visionModelId"
          :options="modelOptions.visionModelOptions"
          class="w-full"
          :allow-clear="true"
          :disabled="!canEdit"
          :placeholder="tr('autoSelect')"
          show-search
          option-filter-prop="label"
        />
      </div>

      <div class="rounded-xl border bg-background p-5 shadow-sm">
        <div class="mb-4 flex items-center gap-3">
          <div
            class="flex size-9 items-center justify-center rounded-xl bg-rose-500/10"
          >
            <IconifyIcon
              icon="lucide:audio-lines"
              class="size-5 text-rose-500"
            />
          </div>
          <div>
            <div class="text-sm font-semibold">{{ tr('audioModel') }}</div>
            <div class="text-xs text-muted-foreground">
              {{ tr('audioModelHelp') }}
            </div>
          </div>
        </div>
        <ASelect
          v-model:value="state.audioModelId"
          :options="modelOptions.audioModelOptions"
          class="w-full"
          :allow-clear="true"
          :disabled="!canEdit"
          :placeholder="tr('autoSelect')"
          show-search
          option-filter-prop="label"
        />
      </div>

      <div class="rounded-xl border bg-background p-5 shadow-sm">
        <div class="mb-4 flex items-center gap-3">
          <div
            class="flex size-9 items-center justify-center rounded-xl bg-fuchsia-500/10"
          >
            <IconifyIcon
              icon="lucide:clapperboard"
              class="size-5 text-fuchsia-500"
            />
          </div>
          <div>
            <div class="text-sm font-semibold">{{ tr('videoModel') }}</div>
            <div class="text-xs text-muted-foreground">
              {{ tr('videoModelHelp') }}
            </div>
          </div>
        </div>
        <ASelect
          v-model:value="state.videoModelId"
          :options="modelOptions.videoModelOptions"
          class="w-full"
          :allow-clear="true"
          :disabled="!canEdit"
          :placeholder="tr('autoSelect')"
          show-search
          option-filter-prop="label"
        />
      </div>

      <div class="rounded-xl border bg-background p-5 shadow-sm">
        <div class="mb-4 flex items-center gap-3">
          <div
            class="flex size-9 items-center justify-center rounded-xl bg-blue-500/10"
          >
            <IconifyIcon
              icon="lucide:scroll-text"
              class="size-5 text-blue-500"
            />
          </div>
          <div>
            <div class="text-sm font-semibold">
              {{ tr('longContextModel') }}
            </div>
            <div class="text-xs text-muted-foreground">
              {{ tr('longContextModelHelp') }}
            </div>
          </div>
        </div>
        <ASelect
          v-model:value="state.longContextModelId"
          :options="modelOptions.chatModelOptions"
          class="w-full"
          :allow-clear="true"
          :disabled="!canEdit"
          :placeholder="tr('autoSelect')"
          show-search
          option-filter-prop="label"
        />
      </div>

      <div class="rounded-xl border bg-background p-5 shadow-sm">
        <div class="mb-4 flex items-center gap-3">
          <div
            class="flex size-9 items-center justify-center rounded-xl bg-cyan-500/10"
          >
            <IconifyIcon icon="lucide:gauge" class="size-5 text-cyan-500" />
          </div>
          <div>
            <div class="text-sm font-semibold">
              {{ tr('longContextThreshold') }}
            </div>
            <div class="text-xs text-muted-foreground">
              {{ tr('longContextThresholdHelp') }}
            </div>
          </div>
        </div>
        <InputNumber
          v-model:value="state.longContextThreshold"
          :min="1000"
          :step="1000"
          class="w-full"
          :disabled="!canEdit"
        />
      </div>
    </div>

    <div v-if="showSaveButton" class="mt-5">
      <Button
        type="primary"
        :loading="saving"
        :disabled="!canEdit"
        @click="onSave"
      >
        {{ $t('common.save') }}
      </Button>
    </div>
  </div>
</template>
