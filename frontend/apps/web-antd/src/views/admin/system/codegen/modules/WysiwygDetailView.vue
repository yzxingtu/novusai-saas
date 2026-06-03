<script lang="ts" setup>
/**
 * WYSIWYG 详情页预览 / WYSIWYG Detail View
 *
 * 模拟 Detail Drawer，支持 groups 分组
 */
import { computed } from 'vue';

import { Descriptions, Empty } from 'ant-design-vue';

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
        .filter((group): group is DetailGroup => group !== null)
    : [];
});
const detailFields = computed<BuilderField[]>(
  () => features.detailFields.value ?? [],
);

function getFieldsForGroup(groupFields: string[] | undefined): BuilderField[] {
  if (!groupFields?.length) return [];
  const all = (store.configJson.fields as BuilderField[]) || [];
  return groupFields
    .map((name) => all.find((field) => field.name === name))
    .filter((field): field is BuilderField => field !== undefined);
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

const displayFields = computed<BuilderField[]>(() => {
  if (detailGroups.value.length > 0) {
    return detailGroups.value.flatMap((group) =>
      getFieldsForGroup(group.fields),
    );
  }
  return detailFields.value;
});
const previewBadges = computed(() => [
  {
    key: 'fields',
    label: $t('admin.system.codegen.builder.previewDetailFields', {
      count: displayFields.value.length,
    }),
  },
  {
    key: 'groups',
    label: $t('admin.system.codegen.builder.previewDetailGroups', {
      count: detailGroups.value.length,
    }),
  },
]);
</script>

<template>
  <div
    class="overflow-hidden rounded-[24px] border border-border/70 bg-card shadow-sm"
  >
    <div class="border-b border-border/50 px-5 py-4">
      <div
        class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between"
      >
        <div class="min-w-0">
          <div
            class="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground"
          >
            {{ $t('admin.system.codegen.wysiwyg.detailView') }}
          </div>
          <div class="mt-2 text-lg font-semibold text-foreground">
            {{
              $t('admin.system.codegen.wysiwyg.detailTitle', {
                name: displayNameStr,
              })
            }}
          </div>
          <div class="mt-1 text-sm leading-6 text-muted-foreground">
            {{ $t('admin.system.codegen.builder.previewDetailDesc') }}
          </div>
        </div>

        <div class="flex flex-wrap gap-2">
          <span
            v-for="item in previewBadges"
            :key="item.key"
            class="rounded-full border border-border/70 bg-muted/15 px-3 py-1 text-xs text-muted-foreground"
          >
            {{ item.label }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="detailGroups.length > 0" class="bg-muted/10 p-5">
      <div class="mx-auto max-w-5xl space-y-4">
        <section
          v-for="(group, index) in detailGroups"
          :key="group.title_zh || group.title_en || `group-${index}`"
          class="overflow-hidden rounded-[24px] border border-border/70 bg-background shadow-sm"
        >
          <template v-if="getFieldsForGroup(group.fields).length > 0">
            <div class="border-b border-border/50 px-5 py-4">
              <div
                class="text-[11px] uppercase tracking-[0.16em] text-muted-foreground"
              >
                {{ $t('admin.system.codegen.palette.divider') }}
              </div>
              <div class="mt-1 text-sm font-semibold text-foreground">
                {{
                  group.title_zh ||
                  group.title_en ||
                  $t('admin.system.codegen.preview.groupTitle', {
                    idx: index + 1,
                  })
                }}
              </div>
            </div>

            <div class="p-5">
              <Descriptions :column="1" bordered size="small" class="mb-0">
                <Descriptions.Item
                  v-for="(field, fieldIndex) in getFieldsForGroup(group.fields)"
                  :key="
                    (field.__key as string) ||
                    (field.name as string) ||
                    `group-${index}-${fieldIndex}`
                  "
                  :label="getFieldLabel(field)"
                >
                  <DetailFieldValue
                    :field="field"
                    :class="[isFieldSelected(field) && 'ring-2 ring-primary']"
                    @click="onFieldClick(field)"
                  />
                </Descriptions.Item>
              </Descriptions>
            </div>
          </template>
        </section>
      </div>
    </div>

    <div v-else-if="displayFields.length > 0" class="bg-muted/10 p-5">
      <div
        class="mx-auto max-w-5xl overflow-hidden rounded-[24px] border border-border/70 bg-background shadow-sm"
      >
        <div class="border-b border-border/50 px-5 py-4">
          <div
            class="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground"
          >
            {{ $t('common.detail') }}
          </div>
          <div class="mt-1 text-sm font-semibold text-foreground">
            {{
              displayNameStr || $t('admin.system.codegen.wysiwyg.sampleData')
            }}
          </div>
        </div>

        <div class="p-5">
          <Descriptions :column="1" bordered size="small" class="mb-0">
            <Descriptions.Item
              v-for="(field, fieldIdx) in displayFields"
              :key="
                (field.__key as string) ||
                (field.name as string) ||
                `field-${fieldIdx}`
              "
              :label="getFieldLabel(field)"
            >
              <DetailFieldValue
                :field="field"
                :class="[isFieldSelected(field) && 'ring-2 ring-primary']"
                @click="onFieldClick(field)"
              />
            </Descriptions.Item>
          </Descriptions>
        </div>
      </div>
    </div>

    <div v-else class="bg-muted/10 py-12">
      <Empty :image="Empty.PRESENTED_IMAGE_SIMPLE">
        <template #description>
          <p class="mb-1">{{ $t('admin.system.codegen.wysiwyg.emptyHint') }}</p>
          <p class="text-xs text-muted-foreground">
            {{ $t('admin.system.codegen.wysiwyg.dragHint') }}
          </p>
        </template>
      </Empty>
    </div>
  </div>
</template>
