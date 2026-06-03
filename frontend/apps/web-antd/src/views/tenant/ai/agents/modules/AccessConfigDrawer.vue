<script setup lang="ts">
import type {
  PermissionRoleTreeNode,
  TenantAccessRoleMode,
} from './access-config-drawer-support';

import type { TenantUserInfo } from '#/api/tenant/tenant-users';
import type { IdentitySelectOption } from '#/components/business/identity-display';

/**
 * 智能体访问与发布配置抽屉（企业端）
 * Agent access + tenant-user publication drawer
 *
 * - 企业管理员角色限制（agent_access.tenant_role_ids）
 * - 是否向企业终端用户发布及发布规则（publication）
 */
import { computed, onMounted, ref, watch } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Divider,
  Form,
  FormItem,
  message,
  Radio,
  RadioGroup,
  Select,
  Spin,
  Switch,
  TreeSelect,
} from 'ant-design-vue';

import {
  getAgentAccessApi,
  getAgentPublicationApi,
  updateAgentAccessApi,
  updateAgentPublicationApi,
} from '#/api/tenant/agents';
import { getAllTenantPermissionRoleListApi } from '#/api/tenant/role';
import { getTenantUserRoleListApi } from '#/api/tenant/tenant-user-roles';
import {
  getTenantUserDetailApi,
  getTenantUserIdentitySelectApi,
} from '#/api/tenant/tenant-users';
import { IdentityRemoteSelect } from '#/components/business/identity-display';
import { $t } from '#/locales';

import {
  deriveTenantAdminRoleMode,
  getAccessTypeOptions,
  mapTenantUserRoleOptions,
  mergeTenantUserOptions,
  normalizeIdList,
  PUB_ALL,
  PUB_ROLES,
  PUB_USERS,
  roleInfoToTreeData,
  tenantUserToIdentityOption,
} from './access-config-drawer-support';

defineOptions({ name: 'AccessConfigDrawer' });

const agentId = ref(0);
const agentName = ref('');
const loading = ref(false);
const saving = ref(false);

const tenantRoleMode = ref<TenantAccessRoleMode>('all');
const tenantRoleIds = ref<number[]>([]);

const pubEnabled = ref(false);
const pubAccessType = ref<string>(PUB_ALL);
const pubTenantUserRoleIds = ref<number[]>([]);
const pubTenantUserIds = ref<number[]>([]);

const tenantRoleTreeData = ref<PermissionRoleTreeNode[]>([]);
const tenantRoleTreeLoading = ref(false);
const tenantUserRoleOptions = ref<Array<{ label: string; value: number }>>([]);
const tenantUserRoleLoading = ref(false);
const tenantUserOptionCache = ref<Map<number, IdentitySelectOption>>(new Map());

const accessTypeOptions = computed(() => getAccessTypeOptions());

const tenantUserSelectedOptions = computed<IdentitySelectOption[]>(() =>
  normalizeIdList(pubTenantUserIds.value)
    .map((id) => tenantUserOptionCache.value.get(id))
    .filter((option): option is IdentitySelectOption => option !== undefined),
);

function handleTenantUserOptionsLoaded(options: IdentitySelectOption[]) {
  tenantUserOptionCache.value = mergeTenantUserOptions(
    tenantUserOptionCache.value,
    options,
  );
}

async function loadTenantPermissionRoles() {
  tenantRoleTreeLoading.value = true;
  try {
    const roles = await getAllTenantPermissionRoleListApi();
    tenantRoleTreeData.value = roleInfoToTreeData(roles);
  } catch {
    /* interceptor */
  } finally {
    tenantRoleTreeLoading.value = false;
  }
}

async function loadTenantUserRoleOptions() {
  tenantUserRoleLoading.value = true;
  try {
    const res = await getTenantUserRoleListApi({ 'page[size]': 100 });
    tenantUserRoleOptions.value = mapTenantUserRoleOptions(res.items);
  } catch {
    /* interceptor */
  } finally {
    tenantUserRoleLoading.value = false;
  }
}

async function loadSelectedTenantUserOptions(ids: number[]) {
  const normalizedIds = normalizeIdList(ids);
  if (normalizedIds.length === 0) {
    return;
  }

  const results = await Promise.allSettled(
    normalizedIds.map((id) => getTenantUserDetailApi(id)),
  );

  const options = results
    .filter(
      (result): result is PromiseFulfilledResult<TenantUserInfo> =>
        result.status === 'fulfilled',
    )
    .map((result) => tenantUserToIdentityOption(result.value));

  tenantUserOptionCache.value = mergeTenantUserOptions(
    tenantUserOptionCache.value,
    options,
  );
}

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange: async (isOpen) => {
    if (isOpen) {
      const data = drawerApi.getData<{ id: number; name: string }>();
      if (data) {
        agentId.value = data.id;
        agentName.value = data.name;
        await Promise.all([loadTenantPermissionRoles(), loadConfigs()]);
      }
    }
  },
  onConfirm: () => onSave(),
});

const title = computed(
  () => `${$t('tenant.ai.agent.access.title')} - ${agentName.value}`,
);

function buildTenantRoleIdsPayload(): null | number[] {
  if (tenantRoleMode.value === 'all') return null;
  return normalizeIdList(tenantRoleIds.value);
}

async function loadConfigs() {
  loading.value = true;
  try {
    const [access, pub] = await Promise.all([
      getAgentAccessApi(agentId.value),
      getAgentPublicationApi(agentId.value),
    ]);
    const tr = access.tenant_role_ids;
    tenantRoleMode.value = deriveTenantAdminRoleMode(tr ?? undefined);
    tenantRoleIds.value = normalizeIdList(tr);

    pubEnabled.value = pub.enabled_for_users;
    pubAccessType.value = pub.access_type || PUB_ALL;
    pubTenantUserRoleIds.value = normalizeIdList(pub.tenant_user_role_ids);
    pubTenantUserIds.value = normalizeIdList(pub.tenant_user_ids);
    await loadSelectedTenantUserOptions(pubTenantUserIds.value);
  } catch {
    /* interceptor */
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  saving.value = true;
  try {
    if (
      tenantRoleMode.value === 'specific' &&
      normalizeIdList(tenantRoleIds.value).length === 0
    ) {
      message.warning(
        $t('tenant.ai.agent.access.messages.specificRolesRequired'),
      );
      return;
    }

    const accessType = pubAccessType.value;
    if (
      pubEnabled.value &&
      accessType === PUB_ROLES &&
      normalizeIdList(pubTenantUserRoleIds.value).length === 0
    ) {
      message.warning($t('tenant.ai.agent.publication.warnSelectUserRoles'));
      return;
    }
    if (
      pubEnabled.value &&
      accessType === PUB_USERS &&
      normalizeIdList(pubTenantUserIds.value).length === 0
    ) {
      message.warning($t('tenant.ai.agent.publication.warnSelectUsers'));
      return;
    }

    await updateAgentAccessApi(agentId.value, {
      tenant_role_ids: buildTenantRoleIdsPayload(),
    });

    await updateAgentPublicationApi(agentId.value, {
      enabled_for_users: pubEnabled.value,
      access_type: accessType,
      tenant_user_role_ids:
        accessType === PUB_ROLES
          ? normalizeIdList(pubTenantUserRoleIds.value)
          : null,
      tenant_user_ids:
        accessType === PUB_USERS
          ? normalizeIdList(pubTenantUserIds.value)
          : null,
      org_node_ids: null,
    });
    message.success($t('tenant.ai.agent.access.messages.updateSuccess'));
    drawerApi.close();
  } catch {
    /* interceptor */
  } finally {
    saving.value = false;
  }
}

watch(pubAccessType, (t) => {
  if (t !== PUB_ROLES) pubTenantUserRoleIds.value = [];
  if (t !== PUB_USERS) pubTenantUserIds.value = [];
});

watch(tenantRoleMode, (m) => {
  if (m === 'all') tenantRoleIds.value = [];
});

onMounted(() => {
  loadTenantUserRoleOptions();
});
</script>

<template>
  <Drawer :title="title" class="w-[560px]" :confirm-loading="saving">
    <Spin :spinning="loading">
      <Form layout="vertical" class="px-1">
        <Alert
          :message="$t('tenant.ai.agent.access.hint.twoLayers')"
          type="info"
          show-icon
          class="mb-4"
        />

        <!-- 企业管理员角色（PUT /access → tenant_role_ids） -->
        <div class="mb-4 rounded-lg border border-border/60 p-4">
          <div class="mb-3 flex items-center gap-2">
            <IconifyIcon icon="lucide:building-2" class="size-4 text-primary" />
            <span class="text-sm font-medium">{{
              $t('tenant.ai.agent.access.tenantRoleAccess')
            }}</span>
          </div>
          <p class="mb-3 text-xs text-muted-foreground">
            {{ $t('tenant.ai.agent.access.hint.tenantAdminLayer') }}
          </p>
          <RadioGroup v-model:value="tenantRoleMode" class="mb-2">
            <Radio value="all">{{ $t('admin.ai.agent.roleMode.all') }}</Radio>
            <Radio value="specific">
              {{ $t('admin.ai.agent.roleMode.specific') }}
            </Radio>
          </RadioGroup>
          <TreeSelect
            v-if="tenantRoleMode === 'specific'"
            v-model:value="tenantRoleIds"
            :tree-data="tenantRoleTreeData"
            tree-checkable
            :show-checked-strategy="TreeSelect.SHOW_CHILD"
            :placeholder="
              $t('tenant.ai.agent.access.placeholder.selectTenantRoles')
            "
            :loading="tenantRoleTreeLoading"
            allow-clear
            style="width: 100%"
            class="mt-2"
            tree-default-expand-all
          />
        </div>

        <Divider class="my-4" />

        <!-- 发布给企业终端用户（PUT /publication → tenant_user_*） -->
        <div class="mb-4 rounded-lg border border-border/60 p-4">
          <div class="mb-3 flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <IconifyIcon icon="lucide:users" class="size-4 text-primary" />
              <span class="text-sm font-medium">{{
                $t('tenant.ai.agent.publication.title')
              }}</span>
            </div>
            <Switch v-model:checked="pubEnabled" />
          </div>
          <p class="mb-3 text-xs text-muted-foreground">
            {{ $t('tenant.ai.agent.access.hint.endUserLayer') }}
          </p>
          <Alert
            type="warning"
            show-icon
            class="mb-3 !text-xs"
            :message="$t('tenant.ai.agent.publication.orgNodeDisabledHint')"
          />
          <FormItem
            :label="$t('tenant.ai.agent.publication.accessType')"
            class="!mb-2"
          >
            <Select
              v-model:value="pubAccessType"
              :options="accessTypeOptions"
              style="width: 100%"
              :disabled="!pubEnabled"
            />
          </FormItem>
          <Select
            v-if="pubEnabled && pubAccessType === PUB_ROLES"
            v-model:value="pubTenantUserRoleIds"
            mode="multiple"
            :options="tenantUserRoleOptions"
            :placeholder="
              $t('tenant.ai.agent.publication.placeholderUserRoles')
            "
            :loading="tenantUserRoleLoading"
            allow-clear
            style="width: 100%"
            class="mt-2"
          />
          <IdentityRemoteSelect
            v-if="pubEnabled && pubAccessType === PUB_USERS"
            v-model:value="pubTenantUserIds"
            :api="getTenantUserIdentitySelectApi"
            mode="multiple"
            :click-pagination="true"
            :immediate="false"
            :pagination="true"
            :selected-options="tenantUserSelectedOptions"
            :placeholder="
              $t('tenant.ai.agent.publication.placeholderSpecificUsers')
            "
            @options-loaded="handleTenantUserOptionsLoaded"
            allow-clear
            style="width: 100%"
            class="mt-2"
          />
        </div>
      </Form>
    </Spin>
  </Drawer>
</template>
