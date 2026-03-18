<script lang="ts" setup>
/**
 * 自定义操作编辑器 / Custom actions editor
 *
 * 可增删: name, label_zh, label_en, method, path, permission, confirm, icon, type, bulk
 */
import { computed } from 'vue';

import { Button, Form, Input, Select, Switch } from 'ant-design-vue';

import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

defineOptions({ name: 'CustomActionsEditor' });

const store = useCodegenBuilderStore();

const actions = computed({
  get: () => (store.configJson.actions as Array<Record<string, unknown>>) || [],
  set: (v) => store.updateConfig({ actions: v }),
});

const resource = computed(() => (store.configJson.resource as string) || '');

const actionTypeOptions = computed(() => [
  { label: $t('admin.system.codegen.enum.actionTypeDefault'), value: 'default' },
  { label: $t('admin.system.codegen.enum.actionTypePrimary'), value: 'primary' },
  { label: $t('admin.system.codegen.enum.actionTypeDanger'), value: 'danger' },
]);

function addAction() {
  const list = [...actions.value];
  list.push({
    name: '',
    label_zh: '',
    label_en: '',
    method: 'POST',
    path: `/${resource.value}s/:id/action`,
    permission: '',
    confirm: false,
    icon: '',
    type: 'default',
    bulk: false,
  });
  store.updateConfig({ actions: list });
}

function removeAction(index: number) {
  const list = actions.value.filter((_, i) => i !== index);
  store.updateConfig({ actions: list });
}

function updateAction(index: number, patch: Record<string, unknown>) {
  const list = actions.value;
  if (index < 0 || index >= list.length) return;
  const next = [...list];
  next[index] = { ...next[index], ...patch };
  store.updateConfig({ actions: next });
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <Button
      size="small"
      type="dashed"
      @click="addAction"
    >
      {{ $t('admin.system.codegen.enum.addAction') }}
    </Button>
    <div
      v-for="(item, idx) in actions"
      :key="(item.name as string) || `action-${idx}`"
      class="flex flex-wrap items-start gap-3 rounded border border-border p-3"
    >
      <Form layout="vertical" class="min-w-40 flex-1">
        <Form.Item :label="$t('admin.system.codegen.enum.actionName')">
          <Input
            :value="item.name"
            @update:value="(v: string) => updateAction(idx, { name: v })"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.codegen.enum.labelZh')">
          <Input
            :value="item.label_zh"
            @update:value="(v: string) => updateAction(idx, { label_zh: v })"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.codegen.enum.labelEn')">
          <Input
            :value="item.label_en"
            @update:value="(v: string) => updateAction(idx, { label_en: v })"
          />
        </Form.Item>
      </Form>
      <Form layout="vertical" class="min-w-40 flex-1">
        <Form.Item :label="$t('admin.system.codegen.enum.method')">
          <Select
            :value="item.method"
            :options="[
              { label: 'GET', value: 'GET' },
              { label: 'POST', value: 'POST' },
              { label: 'PUT', value: 'PUT' },
              { label: 'DELETE', value: 'DELETE' },
            ]"
            class="w-full"
            @change="(v: string) => updateAction(idx, { method: v })"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.codegen.enum.path')">
          <Input
            :value="item.path"
            :placeholder="$t('admin.system.codegen.enum.pathPlaceholder')"
            @update:value="(v: string) => updateAction(idx, { path: v })"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.codegen.enum.actionPermission')">
          <Input
            :value="item.permission"
            @update:value="(v: string) => updateAction(idx, { permission: v })"
          />
        </Form.Item>
      </Form>
      <Form layout="vertical" class="min-w-32 flex-1">
        <Form.Item :label="$t('admin.system.codegen.enum.actionType')">
          <Select
            :value="item.type"
            :options="actionTypeOptions"
            class="w-full"
            @change="(v: string) => updateAction(idx, { type: v })"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.codegen.enum.confirm')">
          <Switch
            :checked="!!item.confirm"
            @change="(v: boolean) => updateAction(idx, { confirm: v })"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.codegen.enum.bulk')">
          <Switch
            :checked="!!item.bulk"
            @change="(v: boolean) => updateAction(idx, { bulk: v })"
          />
        </Form.Item>
      </Form>
      <Button
        danger
        size="small"
        type="text"
        @click="removeAction(idx)"
      >
        {{ $t('common.delete') }}
      </Button>
    </div>
    <div
      v-if="actions.length === 0"
      class="text-muted-foreground rounded border border-dashed border-border py-6 text-center text-sm"
    >
      {{ $t('admin.system.codegen.enum.noActions') }}
    </div>
  </div>
</template>
