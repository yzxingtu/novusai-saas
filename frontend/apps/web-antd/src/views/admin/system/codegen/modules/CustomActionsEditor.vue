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

type ActionMethod = 'DELETE' | 'GET' | 'POST' | 'PUT';
type ActionType = 'danger' | 'default' | 'primary';

interface CustomActionItem {
  bulk: boolean;
  confirm: boolean;
  icon: string;
  label_en: string;
  label_zh: string;
  method: ActionMethod;
  name: string;
  path: string;
  permission: string;
  type: ActionType;
}

const ACTION_METHODS = new Set<ActionMethod>(['DELETE', 'GET', 'POST', 'PUT']);
const ACTION_TYPES = new Set<ActionType>(['danger', 'default', 'primary']);

function normalizeAction(item?: Partial<CustomActionItem>): CustomActionItem {
  const method = item?.method;
  const type = item?.type;
  return {
    bulk: Boolean(item?.bulk),
    confirm: Boolean(item?.confirm),
    icon: item?.icon ?? '',
    label_en: item?.label_en ?? '',
    label_zh: item?.label_zh ?? '',
    method: ACTION_METHODS.has(method as ActionMethod) ? (method as ActionMethod) : 'POST',
    name: item?.name ?? '',
    path: item?.path ?? '',
    permission: item?.permission ?? '',
    type: ACTION_TYPES.has(type as ActionType) ? (type as ActionType) : 'default',
  };
}

const actions = computed<CustomActionItem[]>({
  get: () =>
    Array.isArray(store.configJson.actions)
      ? (store.configJson.actions as Partial<CustomActionItem>[]).map((item) =>
          normalizeAction(item),
        )
      : [],
  set: (v) => store.updateConfig({ actions: v }),
});

const resource = computed(() => (store.configJson.resource as string) || '');

const actionTypeOptions = computed(() => [
  { label: $t('admin.system.codegen.enum.actionTypeDefault'), value: 'default' },
  { label: $t('admin.system.codegen.enum.actionTypePrimary'), value: 'primary' },
  { label: $t('admin.system.codegen.enum.actionTypeDanger'), value: 'danger' },
]);

function toStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : [];
}

function toStringValue(value: unknown): string {
  return toStringArray([value])[0] ?? '';
}

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

function updateAction(index: number, patch: Partial<CustomActionItem>) {
  const list = actions.value;
  if (index < 0 || index >= list.length) return;
  const next = [...list];
  next[index] = normalizeAction({ ...next[index], ...patch });
  store.updateConfig({ actions: next });
}

function onMethodChange(index: number, value: unknown) {
  const method = toStringValue(value);
  if (ACTION_METHODS.has(method as ActionMethod)) {
    updateAction(index, { method: method as ActionMethod });
  }
}

function onTypeChange(index: number, value: unknown) {
  const type = toStringValue(value);
  if (ACTION_TYPES.has(type as ActionType)) {
    updateAction(index, { type: type as ActionType });
  }
}

function onSwitchChange(index: number, field: 'bulk' | 'confirm', value: unknown) {
  if (field === 'bulk') {
    updateAction(index, { bulk: Boolean(value) });
    return;
  }
  updateAction(index, { confirm: Boolean(value) });
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
            @change="(value) => onMethodChange(idx, value)"
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
            @change="(value) => onTypeChange(idx, value)"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.codegen.enum.confirm')">
          <Switch
            :checked="!!item.confirm"
            @change="(value) => onSwitchChange(idx, 'confirm', value)"
          />
        </Form.Item>
        <Form.Item :label="$t('admin.system.codegen.enum.bulk')">
          <Switch
            :checked="!!item.bulk"
            @change="(value) => onSwitchChange(idx, 'bulk', value)"
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
