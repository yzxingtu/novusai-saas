<script lang="ts" setup>
/**
 * WYSIWYG 详情页预览 / WYSIWYG Detail View
 *
 * 模拟 Detail Drawer，支持 groups 分组
 */
import { computed } from 'vue';
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

type BuilderField = Record<string, unknown>;

interface DetailGroup {
  fields?: string[];
  title_en?: string;
  title_zh?: string;
}

const displayNameStr = computed(() => String(features.displayName.value ?? ''));

function normalizeDetailGroup(group: unknown): DetailGroup | null {
  if (typeof group !== 'object' || group === null) return null;
  const raw = group as Record<string, unknown>;
  return {
    fields: Array.isArray(raw.fields)
      ? raw.fields.filter((field): field is string => typeof field === 'string')
      : [],
    title_en: typeof raw.title_en === 'string' ? raw.title_en : undefined,
    title_zh: typeof raw.title_zh === 'string' ? raw.title_zh : undefined,
  };
}

const detailGroups = computed<DetailGroup[]>(() => {
  const rawGroups = features.detailGroups.value;
  return Array.isArray(rawGroups)
    ? rawGroups
        .map((group) => normalizeDetailGroup(group))
        .filter((group): group is DetailGroup => Boolean(group))
    : [];
});
const detailFields = computed<BuilderField[]>(() => features.detailFields.value ?? []);

function getFieldsForGroup(groupFields: string[] | undefined): BuilderField[] {
  if (!groupFields?.length) return [];
  const all = (store.configJson.fields as BuilderField[]) || [];
  return groupFields
    .map((name) => all.find((field) => field.name === name))
    .filter((field): field is BuilderField => Boolean(field));
}

function onFieldClick(field: BuilderField) {
  const key = (field.__key as string) || (field.name as string);
  if (!key) return;
  store.selectedFieldKey = key;
}

function isFieldSelected(field: BuilderField): boolean {
  const key = (field.__key as string) || (field.name as string);
  return key ? store.selectedFieldKey === key : false;
}

function onCloseDetail() {
  store.wysiwygViewMode = 'list';
}

const displayFields = computed<BuilderField[]>(() => {
  if (detailGroups.value.length > 0) {
    return detailGroups.value.flatMap((group) => getFieldsForGroup(group.fields));
  }
  return detailFields.value;
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
    <div v-if="detailGroups.length > 0" class="p-4">
      <div v-for="(g, idx) in detailGroups" :key="g.title_zh || g.title_en || `group-${idx}`" class="mb-4">
        <template v-if="getFieldsForGroup(g.fields).length > 0">
          <div class="text-muted-foreground mb-2 text-xs font-medium">
            {{ g.title_zh || g.title_en || $t('admin.system.codegen.preview.groupTitle', { idx: idx + 1 }) }}
          </div>
          <Descriptions :column="1" bordered size="small" class="mb-0">
            <Descriptions.Item
              v-for="(f, fi) in getFieldsForGroup(g.fields)"
              :key="(f.__key as string) || (f.name as string) || `group-${idx}-${fi}`"
              :label="getFieldLabel(f)"
            >
              <DetailFieldValue
                :field="f"
                :class="[isFieldSelected(f) && 'ring-2 ring-primary']"
                @click="onFieldClick(f)"
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
          :key="(f.__key as string) || (f.name as string) || `field-${fieldIdx}`"
          :label="getFieldLabel(f)"
        >
          <DetailFieldValue
            :field="f"
            :class="[isFieldSelected(f) && 'ring-2 ring-primary']"
            @click="onFieldClick(f)"
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
