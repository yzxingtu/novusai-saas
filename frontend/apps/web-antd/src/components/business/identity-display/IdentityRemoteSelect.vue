<script lang="ts" setup>
import type {
  IdentityOptionLike,
  IdentityOptionResolverConfig,
} from './identity-option';

import { computed, useAttrs } from 'vue';

import { Tag } from 'ant-design-vue';

import { ApiSelect } from '#/components/business/api-select';

import { resolveIdentityOption } from './identity-option';
import IdentityDisplay from './IdentityDisplay.vue';
import { createIdentityDisplayModel } from './types';

type OptionValue = number | string;
type SelectModelValue = OptionValue | OptionValue[] | undefined;

interface Props extends IdentityOptionResolverConfig {
  optionAvatarSize?: number;
  selectedAvatarSize?: number;
  showArchitectureTag?: boolean;
  showSecondaryText?: boolean;
  tagAvatarSize?: number;
}

defineOptions({
  name: 'IdentityRemoteSelect',
  inheritAttrs: false,
});

const props = withDefaults(defineProps<Props>(), {
  avatarField: 'avatar',
  displayField: 'nickname',
  displayFallbackFields: () => [
    'display_name',
    'displayName',
    'real_name',
    'realName',
    'label',
    'username',
  ],
  secondaryField: 'username',
  secondaryFallbackFields: () => ['email'],
  tagField: 'orgNodeName',
  tagFallbackFields: () => ['org_node_name'],
  optionAvatarSize: 32,
  selectedAvatarSize: 24,
  tagAvatarSize: 18,
  showArchitectureTag: true,
  showSecondaryText: true,
});

const modelValue = defineModel<SelectModelValue>('value');
const attrs = useAttrs();

const resolverConfig = computed<IdentityOptionResolverConfig>(() => ({
  avatarField: props.avatarField,
  displayField: props.displayField,
  displayFallbackFields: props.displayFallbackFields,
  secondaryField: props.secondaryField,
  secondaryFallbackFields: props.secondaryFallbackFields,
  tagField: props.tagField,
  tagFallbackFields: props.tagFallbackFields,
}));

function resolveStringExtra(
  extra: Record<string, unknown>,
  primaryKey: string,
  fallbackKey: string,
): null | string {
  const primaryValue = extra[primaryKey];
  if (typeof primaryValue === 'string') {
    return primaryValue;
  }
  const fallbackValue = extra[fallbackKey];
  return typeof fallbackValue === 'string' ? fallbackValue : null;
}

function resolveBooleanExtra(
  extra: Record<string, unknown>,
  primaryKey: string,
  fallbackKey: string,
): boolean | undefined {
  const primaryValue = extra[primaryKey];
  if (typeof primaryValue === 'boolean') {
    return primaryValue;
  }
  const fallbackValue = extra[fallbackKey];
  return typeof fallbackValue === 'boolean' ? fallbackValue : undefined;
}

function hasObjectKey(
  extra: Record<string, unknown>,
  key: string,
): boolean {
  return Object.prototype.hasOwnProperty.call(extra, key);
}

function resolveDisplayRoleExtra(
  extra: Record<string, unknown>,
): null | string {
  if (hasObjectKey(extra, 'displayRoleName')) {
    return typeof extra.displayRoleName === 'string'
      ? extra.displayRoleName
      : null;
  }
  if (hasObjectKey(extra, 'display_role_name')) {
    return typeof extra.display_role_name === 'string'
      ? extra.display_role_name
      : null;
  }
  return resolveStringExtra(extra, 'roleName', 'role_name');
}

function getIdentity(option: IdentityOptionLike | undefined) {
  if (!option) return null;
  const resolved = resolveIdentityOption(option, resolverConfig.value);
  const extra =
    option.extra && typeof option.extra === 'object'
      ? (option.extra as Record<string, unknown>)
      : {};

  const roleName = resolveDisplayRoleExtra(extra);
  const userType = resolveStringExtra(extra, 'userType', 'user_type');
  const userTypeLabel = resolveStringExtra(
    extra,
    'userTypeLabel',
    'user_type_label',
  );
  const isActive = resolveBooleanExtra(extra, 'isActive', 'is_active');
  const isLeader = resolveBooleanExtra(extra, 'isLeader', 'is_leader');
  const isOwner = resolveBooleanExtra(extra, 'isOwner', 'is_owner');
  return createIdentityDisplayModel({
    avatar: resolved.avatar || null,
    displayName: resolved.displayName,
    id: resolved.value ?? option.value ?? option.label ?? '-',
    isActive,
    isLeader,
    isOwner,
    orgNodeName: resolved.architectureLabel || null,
    roleName,
    secondaryText: props.showSecondaryText ? resolved.secondaryText : null,
    userType,
    userTypeLabel,
    username: resolved.secondaryText || null,
  });
}
</script>

<template>
  <ApiSelect
    v-model:value="modelValue"
    v-bind="attrs"
    class="identity-remote-select"
  >
    <template #option="{ option }">
      <IdentityDisplay
        v-if="getIdentity(option)"
        :avatar-size="optionAvatarSize"
        :model="getIdentity(option)!"
        :show-org-line="showArchitectureTag"
      />
    </template>

    <template #optionLabel="{ option }">
      <IdentityDisplay
        v-if="getIdentity(option)"
        :avatar-size="selectedAvatarSize"
        :model="getIdentity(option)!"
        :show-org-line="showArchitectureTag"
        :show-status-badge="false"
      />
    </template>

    <template #tag="{ option, tagProps }">
      <Tag
        v-if="getIdentity(option)"
        :closable="tagProps.closable && !tagProps.disabled"
        class="identity-remote-select__tag !m-0 !inline-flex !max-w-full !items-center !rounded-full !px-1.5 !py-1"
        @close="tagProps.onClose"
        @mousedown.prevent.stop
      >
        <IdentityDisplay
          :avatar-size="tagAvatarSize"
          :model="getIdentity(option)!"
          :show-org-line="showArchitectureTag"
          :show-status-badge="false"
        />
      </Tag>
    </template>
  </ApiSelect>
</template>

<style scoped>
.identity-remote-select :deep(.ant-select-selector) {
  height: auto !important;
  min-height: 44px !important;
  padding-top: 4px !important;
  padding-bottom: 4px !important;
}

.identity-remote-select :deep(.ant-select-selection-item) {
  align-items: center;
  display: flex;
  height: auto !important;
  justify-content: flex-start;
  max-width: 100%;
  min-width: 0;
  text-align: left;
  width: 100%;
}

.identity-remote-select :deep(.ant-select-selection-item-content) {
  min-width: 0;
  text-align: left;
  width: 100%;
}

.identity-remote-select :deep(.ant-select-selection-overflow) {
  align-items: flex-start;
  gap: 4px;
}

.identity-remote-select :deep(.ant-select-selection-overflow-item) {
  align-self: flex-start;
  max-width: 100%;
}

.identity-remote-select :deep(.ant-select-selection-placeholder) {
  text-align: left;
}

.identity-remote-select__tag :deep(.identity-display) {
  min-width: 0;
}

.identity-remote-select__tag :deep(.ant-tag-close-icon) {
  margin-inline-start: 4px;
}
</style>
