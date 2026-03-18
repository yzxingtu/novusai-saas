<script lang="ts" setup>
/**
 * 详情字段分组编辑器 / Detail group editor
 *
 * 可增删组: title_zh, title_en, fields 多选
 */
import { computed } from 'vue';

import { Button, Form, Input, Select } from 'ant-design-vue';

import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

defineOptions({ name: 'DetailGroupEditor' });

const store = useCodegenBuilderStore();

const detail = computed({
  get: () => (store.configJson.detail as Record<string, unknown>) || {},
  set: (v) => store.updateConfig({ detail: v }),
});

const groups = computed(() => (detail.value.groups as Array<Record<string, unknown>>) || []);

function getGroupKey(g: Record<string, unknown>, idx: number) {
  return (g.title_zh as string) || (g.title_en as string) || `group-${idx}`;
}

const fields = computed(
  () => (store.configJson.fields as Array<Record<string, unknown>>) || [],
);

const fieldOptions = computed(() =>
  fields.value
    .filter((f) => f.type !== '__divider__' && !f.divider && f.name)
    .map((f) => ({ label: `${f.name as string} (${f.comment || f.type})`, value: f.name as string })),
);

function updateDetail(patch: Record<string, unknown>) {
  store.updateConfig({ detail: { ...detail.value, ...patch } });
}

function addGroup() {
  const list = [...groups.value];
  list.push({ title_zh: '', title_en: '', fields: [] });
  updateDetail({ groups: list });
}

function removeGroup(index: number) {
  const list = groups.value.filter((_, i) => i !== index);
  updateDetail({ groups: list });
}

function updateGroup(index: number, patch: Record<string, unknown>) {
  const list = groups.value;
  if (index < 0 || index >= list.length) return;
  const next = [...list];
  next[index] = { ...next[index], ...patch };
  updateDetail({ groups: next });
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <Button
      size="small"
      type="dashed"
      @click="addGroup"
    >
      {{ $t('admin.system.codegen.frontend.addGroup') }}
    </Button>
    <div
      v-for="(g, idx) in groups"
      :key="getGroupKey(g, idx)"
      class="flex flex-wrap items-start gap-3 rounded border border-border p-3"
    >
      <Form layout="vertical" class="min-w-40 flex-1">
        <Form.Item :label="$t('admin.system.codegen.frontend.groupTitleZh')">
          <Input
            :value="g.title_zh"
            @update:value="(v: string) => updateGroup(idx, { title_zh: v })"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.codegen.frontend.groupTitleEn')">
          <Input
            :value="g.title_en"
            @update:value="(v: string) => updateGroup(idx, { title_en: v })"
          />
        </Form.Item>
      </Form>
      <Form layout="vertical" class="min-w-48 flex-1">
        <Form.Item :label="$t('admin.system.codegen.frontend.groupFields')">
          <Select
            :value="(g.fields || []) as string[]"
            :options="fieldOptions"
            mode="multiple"
            class="w-full"
            :placeholder="$t('admin.system.codegen.frontend.selectFieldsPlaceholder')"
            @change="(v: string[]) => updateGroup(idx, { fields: v })"
          />
        </Form.Item>
      </Form>
      <Button
        danger
        size="small"
        type="text"
        @click="removeGroup(idx)"
      >
        {{ $t('common.delete') }}
      </Button>
    </div>
    <div
      v-if="groups.length === 0"
      class="text-muted-foreground rounded border border-dashed border-border py-4 text-center text-sm"
    >
      {{ $t('admin.system.codegen.frontend.detailGroupsEmptyHint') }}
    </div>
  </div>
</template>
