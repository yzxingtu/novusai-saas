<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Alert, Button, Tag } from 'ant-design-vue';

import { $t } from '#/locales';

import { useFieldPropertyPanelContext } from './context';

defineOptions({ name: 'FieldPropertySelectedHeader' });

const {
  applyRecommendedConfig,
  recommendMessage,
  selectedField,
  selectedFieldIcon,
  selectedFieldLabel,
  showInferHint,
  showRecommend,
  summaryTags,
} = useFieldPropertyPanelContext();
</script>

<template>
  <div class="border-b border-border/70 px-3 py-3">
    <div class="flex items-start justify-between gap-3">
      <div class="flex min-w-0 items-start gap-3">
        <div
          class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted/20 ring-1 ring-border/70"
        >
          <IconifyIcon
            :icon="selectedFieldIcon"
            class="size-4.5 text-foreground"
          />
        </div>
        <div class="min-w-0">
          <div class="truncate text-sm font-semibold text-foreground">
            {{
              selectedFieldLabel || $t('admin.system.codegen.property.unnamed')
            }}
          </div>
          <div class="mt-1 truncate font-mono text-xs text-muted-foreground">
            {{ selectedField?.name || 'field' }}
          </div>
          <div class="mt-2 flex flex-wrap gap-1.5">
            <Tag
              v-for="tag in summaryTags"
              :key="tag"
              class="!mr-0 !rounded-full"
            >
              {{ tag }}
            </Tag>
            <Tag
              v-if="selectedField?._auto_detected"
              color="success"
              class="!mr-0 !rounded-full"
            >
              {{ $t('admin.system.codegen.field.autoDetected') }}
            </Tag>
          </div>
        </div>
      </div>
      <Button
        v-if="showRecommend"
        size="small"
        type="primary"
        ghost
        @click="applyRecommendedConfig"
      >
        {{ $t('admin.system.codegen.property.applyRecommend') }}
      </Button>
    </div>

    <Alert
      v-if="showInferHint"
      type="success"
      show-icon
      class="mt-3 !py-1 text-xs"
      :message="$t('admin.system.codegen.property.inferHint')"
    />
    <Alert
      v-else-if="
        showRecommend &&
        typeof recommendMessage === 'string' &&
        recommendMessage.trim()
      "
      type="info"
      show-icon
      class="mt-3 !py-1 text-xs"
      :message="recommendMessage"
    />
  </div>
</template>
