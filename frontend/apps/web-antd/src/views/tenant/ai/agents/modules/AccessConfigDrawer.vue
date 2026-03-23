<script setup lang="ts">
import type { TenantPermissionRoleInfo } from '#/api/tenant/role';

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
import { getTenantUserListApi } from '#/api/tenant/tenant-users';
import { $t } from '#/locales';

defineOptions({ name: 'AccessConfigDrawer' });

interface PermissionRoleTreeNode {
  disabled?: boolean;
  key: number;
  title: string;
  value: number;
}

const PUB_ALL = 'all_users';
const PUB_ROLES = 'tenant_user_roles';
const PUB_USERS = 'specific_users';

const agentId = ref(0);
const agentName = ref('');
const loading = ref(false);
const saving = ref(false);

const tenantRoleMode = ref<'all' | 'specific'>('all');
const tenantRoleIds = ref<number[]>([]);

const pubEnabled = ref(false);
const pubAccessType = ref<string>(PUB_ALL);
const pubTenantUserRoleIds = ref<number[]>([]);
const pubTenantUserIds = ref<number[]>([]);

const tenantRoleTreeData = ref<PermissionRoleTreeNode[]>([]);
const tenantRoleTreeLoading = ref(false);
const tenantUserRoleOptions = ref<Array<{ label: string; value: number }>>([]);
const tenantUserRoleLoading = ref(false);
const tenantUserOptions = ref<Array<{ label: string; value: number }>>([]);
const tenantUserLoading = ref(false);

const accessTypeOptions = computed(() => [
  {
    label: $t('tenant.ai.agent.publication.accessAllUsers'),
    value: PUB_ALL,
  },
  {
    label: $t('tenant.ai.agent.publication.accessByUserRoles'),
    value: PUB_ROLES,
  },
  {
    label: $t('tenant.ai.agent.publication.accessSpecificUsers'),
    value: PUB_USERS,
  },
]);

/** TreeSelect / Select 可能返回 string，统一为 number，避免保存丢数据 / TreeSelect and Select may return strings, normalize to numbers */
function normalizeIdList(raw: unknown): number[] {
  if (raw === null || raw === undefined || !Array.isArray(raw)) return [];
  return raw
    .map((x) => (typeof x === 'string' ? Number.parseInt(x, 10) : Number(x)))
    .filter((n) => Number.isFinite(n) && n > 0);
}

function deriveTenantAdminRoleMode(
  ids: null | number[] | undefined,
): 'all' | 'specific' {
  if (ids === null || ids === undefined || ids.length === 0) return 'all';
  return 'specific';
}

function roleInfoToTreeData(
  roles: TenantPermissionRoleInfo[],
): PermissionRoleTreeNode[] {
  return roles.map((r) => ({
    disabled: !r.isActive,
    title: r.name,
    value: r.id,
    key: r.id,
  }));
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
    tenantUserRoleOptions.value = res.items.map((r) => ({
      label: r.name,
      value: r.id,
    }));
  } catch {
    /* interceptor */
  } finally {
    tenantUserRoleLoading.value = false;
  }
}

async function loadTenantUserOptions() {
  tenantUserLoading.value = true;
  try {
    const res = await getTenantUserListApi({ 'page[size]': 200 });
    tenantUserOptions.value = res.items.map((u) => ({
      label: u.nickname || u.username || `ID:${u.id}`,
      value: u.id,
    }));
  } catch {
    /* interceptor */
  } finally {
    tenantUserLoading.value = false;
  }
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
  loadTenantUserOptions();
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
          <Select
            v-if="pubEnabled && pubAccessType === PUB_USERS"
            v-model:value="pubTenantUserIds"
            mode="multiple"
            :options="tenantUserOptions"
            :placeholder="
              $t('tenant.ai.agent.publication.placeholderSpecificUsers')
            "
            :loading="tenantUserLoading"
            allow-clear
            style="width: 100%"
            class="mt-2"
          />
        </div>
      </Form>
    </Spin>
  </Drawer>
</template>
