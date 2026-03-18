<script lang="ts" setup>
/**
 * WYSIWYG 详情页预览 / WYSIWYG Detail View
 *
 * 模拟 Detail Drawer，支持 groups 分组
 */

import { computed, unref } from 'vue';
import { Button, Descriptions, Empty } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import DetailFieldValue from './DetailFieldValue.vue';
import { getFieldLabel } from './field-utils';
import { useConfigFeatures } from './useConfigFeatures';

defineOptions({ name: 'WysiwygDetailView' });

const store = useCodegenBuilderStore();
const features = useConfigFeatures(store);
const displayNameStr = computed(() => String(unref(features.displayName) ?? ''));

function getFieldsForGroup(groupFields: string[] | undefined): Record<string, unknown>[] {
  if (!groupFields?.length) return [];
  const all = (store.configJson.fields as Record<string, unknown>[]) || [];
  return groupFields.map((name) => all.find((f) => f.name === name)).filter(Boolean) as Record<string, unknown>[];
}

function onFieldClick(f: Record<string, unknown>) {
  store.selectedFieldKey = (f.__key as string) || (f.name as string);
}

function isFieldSelected(f: Record<string, unknown>): boolean {
  const key = (f.__key as string) || (f.name as string);
  return store.selectedFieldKey === key;
}

function onCloseDetail() {
  store.wysiwygViewMode = 'list';
}

const displayFields = computed(() => {
  const groups = unref(features.detailGroups);
  if (groups?.length) {
    return groups.flatMap((g) => getFieldsForGroup(g.fields));
  }
  return unref(features.detailFields);
});
</script>

<template>
  <div class="overflow-hidden rounded-xl border border-border/40 bg-card">
    <!-- 详情标题 -->
    <div class="flex items-center justify-between border-b border-border px-4 py-2">
      <span class="font-medium">
        {{ $t('admin.system.codegen.wysiwyg.detailTitle', { name: displayNameStr }) }}
      </span>
      <Button type="text" size="small" @click="onCloseDetail">
        <IconifyIcon icon="lucide:x" />
      </Button>
    </div>

    <!-- D41 详情内容：分组使用 Descriptions -->
    <div v-if="features.detailGroups?.length" class="p-4">
      <div v-for="(g, idx) in features.detailGroups" :key="g.title_zh || g.title_en || `group-${idx}`" class="mb-4">
        <template v-if="getFieldsForGroup(g.fields).length > 0">
          <div class="text-muted-foreground mb-2 text-xs font-medium">
            {{ g.title_zh || g.title_en || $t('admin.system.codegen.preview.groupTitle', { idx: idx + 1 }) }}
          </div>
          <Descriptions :column="1" bordered size="small" class="mb-0">
            <Descriptions.Item
              v-for="(f, fi) in getFieldsForGroup(g.fields)"
              :key="(f as Record<string, unknown>).__key || (f as Record<string, unknown>).name || `group-${idx}-${fi}`"
              :label="getFieldLabel(f as Record<string, unknown>)"
            >
              <DetailFieldValue
                :field="f as Record<string, unknown>"
                :class="[isFieldSelected(f as Record<string, unknown>) && 'ring-2 ring-primary']"
                @click="onFieldClick(f as Record<string, unknown>)"
              />
            </Descriptions.Item>
          </Descriptions>
        </template>
      </div>
    </div>

    <!-- D41 平铺：使用 Descriptions -->
    <div v-else-if="displayFields.length > 0" class="p-4">
      <Descriptions :column="1" bordered size="small" class="mb-0">
        <Descriptions.Item
          v-for="(f, fieldIdx) in displayFields"
          :key="(f as Record<string, unknown>).__key || (f as Record<string, unknown>).name || `field-${fieldIdx}`"
          :label="getFieldLabel(f as Record<string, unknown>)"
        >
          <DetailFieldValue
            :field="f as Record<string, unknown>"
            :class="[isFieldSelected(f as Record<string, unknown>) && 'ring-2 ring-primary']"
            @click="onFieldClick(f as Record<string, unknown>)"
          />
        </Descriptions.Item>
      </Descriptions>
    </div>

    <!-- 空状态 - 与 List/Form 统一使用 Empty -->
    <div v-else class="py-12">
      <Empty :image="Empty.PRESENTED_IMAGE_SIMPLE">
        <template #description>
          <p class="mb-1">{{ $t('admin.system.codegen.wysiwyg.emptyHint') }}</p>
          <p class="text-muted-foreground text-xs">{{ $t('admin.system.codegen.wysiwyg.dragHint') }}</p>
        </template>
      </Empty>
    </div>
  </div>
</template>
