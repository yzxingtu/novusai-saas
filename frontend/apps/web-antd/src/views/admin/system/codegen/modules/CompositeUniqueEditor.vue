<script lang="ts" setup>
/**
 * 复合唯一约束编辑器 / Composite unique constraint editor
 *
 * 可增删的子表单，每条：多选字段 + 约束名
 */
import { computed } from 'vue';

import { Button, Select } from 'ant-design-vue';

import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

defineOptions({ name: 'CompositeUniqueEditor' });

const store = useCodegenBuilderStore();

interface UniqueConstraintItem {
  fields: string[];
  name?: string;
}

const fields = computed(
  () => (store.configJson.fields as Array<Record<string, unknown>>) || [],
);

const fieldOptions = computed(() =>
  fields.value
    .filter((f) => f.type !== '__divider__' && !f.divider && (f.name as string))
    .map((f) => ({ label: f.name as string, value: f.name as string })),
);

const constraints = computed(() => {
  const model = (store.configJson.model as Record<string, unknown>) || {};
  const ut = model.unique_together as UniqueConstraintItem[] | undefined;
  return ut && Array.isArray(ut) ? [...ut] : [];
});

function addConstraint() {
  const model = (store.configJson.model as Record<string, unknown>) || {};
  const ut = (model.unique_together as Array<Record<string, unknown>>) || [];
  const firstTwo = fieldOptions.value.slice(0, 2).map((o) => o.value);
  store.updateConfig({
    model: {
      ...model,
      unique_together: [...ut, { fields: firstTwo, name: `uq_${Date.now()}` }],
    },
  });
}

function removeConstraint(idx: number) {
  const model = (store.configJson.model as Record<string, unknown>) || {};
  const ut = [...((model.unique_together as Array<Record<string, unknown>>) || [])];
  ut.splice(idx, 1);
  store.updateConfig({ model: { ...model, unique_together: ut } });
}

function updateConstraint(idx: number, patch: Partial<UniqueConstraintItem>) {
  const model = (store.configJson.model as Record<string, unknown>) || {};
  const ut = [...((model.unique_together as Array<Record<string, unknown>>) || [])];
  if (idx < 0 || idx >= ut.length) return;
  const next = { ...ut[idx], ...patch };
  const fields = (next.fields as string[]) || [];
  if (patch.fields !== undefined && fields.length < 2) {
    return;
  }
  ut[idx] = next;
  store.updateConfig({ model: { ...model, unique_together: ut } });
}

function onConstraintFieldsChange(idx: number, value: unknown) {
  const fields = Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : [];
  updateConstraint(idx, { fields });
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div
      v-for="(c, idx) in constraints"
      :key="(c.name as string) || `c-${idx}`"
      class="flex items-center gap-2 rounded border border-border p-2"
    >
      <Select
        :value="c.fields"
        :options="fieldOptions"
        mode="multiple"
        :placeholder="$t('admin.system.codegen.model.uniquePlaceholder')"
        class="flex-1"
        @change="(value) => onConstraintFieldsChange(idx, value)"
      />
      <Button
        type="text"
        danger
        size="small"
        @click="removeConstraint(idx)"
      >
        {{ $t('common.delete') }}
      </Button>
    </div>
    <Button type="dashed" @click="addConstraint">
      {{ $t('admin.system.codegen.model.addUnique') }}
    </Button>
  </div>
</template>
