<script setup lang="ts">
/**
 * 智能体访问权限配置抽屉（企业端）
 *
 * 仅配置 tenant_role_ids 和 user_role_ids（企业端/用户端角色权限控制）。
 * 企业端不显示 Admin 端角色选择（企业无权控制管理端角色）。
 * 根据 target_audience 动态显隐 User 端区块。
 */
import { computed, onMounted, ref, watch } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Divider,
  Form,
  FormItem,
  message,
  Radio,
  RadioGroup,
  Select,
  Spin,
  TreeSelect,
} from 'ant-design-vue';

import { getAgentAccessApi, updateAgentAccessApi } from '#/api/tenant/agents';
import { getTenantRoleTreeApi } from '#/api/tenant/role';
import { getTenantUserRoleListApi } from '#/api/tenant/tenant-user-roles';
import { $t } from '#/locales';

import type { TenantRoleInfo } from '#/api/tenant/role';

defineOptions({ name: 'AccessConfigDrawer' });

const agentId = ref(0);
const agentName = ref('');
const targetAudience = ref<string>('admin_tenant');
const loading = ref(false);
const saving = ref(false);

const tenantRoleMode = ref<'all' | 'specific'>('all');
const tenantRoleIds = ref<number[]>([]);
const userRoleMode = ref<'all' | 'specific'>('all');
const userRoleIds = ref<number[]>([]);

const tenantRoleTreeData = ref<Record<string, unknown>[]>([]);
const tenantRoleTreeLoading = ref(false);
const userRoleOptions = ref<Array<{ label: string; value: number }>>([]);
const userRoleLoading = ref(false);

const showTenantBlock = computed(() =>
  ['all', 'admin_tenant'].includes(targetAudience.value),
);
const showUserBlock = computed(() => targetAudience.value === 'all');

function roleInfoToTreeData(roles: TenantRoleInfo[]): Record<string, unknown>[] {
  return roles.map((r) => ({
    title: r.name,
    value: r.id,
    key: r.id,
    children: r.children?.length ? roleInfoToTreeData(r.children) : undefined,
  }));
}

async function loadTenantRoleTree() {
  tenantRoleTreeLoading.value = true;
  try {
    const tree = await getTenantRoleTreeApi();
    tenantRoleTreeData.value = roleInfoToTreeData(tree);
  } catch {
    // error handled by global interceptor
  } finally {
    tenantRoleTreeLoading.value = false;
  }
}

async function loadUserRoleOptions() {
  userRoleLoading.value = true;
  try {
    const res = await getTenantUserRoleListApi({ 'page[size]': 100 });
    userRoleOptions.value = res.items.map((r) => ({
      label: r.name,
      value: r.id,
    }));
  } catch {
    // error handled by global interceptor
  } finally {
    userRoleLoading.value = false;
  }
}

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange: async (isOpen) => {
    if (isOpen) {
      const data = drawerApi.getData<{
        id: number;
        name: string;
        target_audience?: string;
      }>();
      if (data) {
        agentId.value = data.id;
        agentName.value = data.name;
        targetAudience.value = data.target_audience ?? 'admin_tenant';
        await loadAccessConfig();
      }
    }
  },
});

const title = computed(
  () => `${$t('tenant.ai.agent.access.title')} - ${agentName.value}`,
);

function idsToMode(ids: null | number[]): 'all' | 'specific' {
  return ids === null ? 'all' : 'specific';
}

function modeToIds(mode: 'all' | 'specific', ids: number[]): null | number[] {
  return mode === 'all' ? null : ids;
}

async function loadAccessConfig() {
  loading.value = true;
  try {
    const config = await getAgentAccessApi(agentId.value);
    tenantRoleMode.value = idsToMode(config.tenant_role_ids ?? null);
    tenantRoleIds.value = config.tenant_role_ids ?? [];
    userRoleMode.value = idsToMode(config.user_role_ids ?? null);
    userRoleIds.value = config.user_role_ids ?? [];
  } catch {
    // error handled by global interceptor
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  saving.value = true;
  try {
    await updateAgentAccessApi(agentId.value, {
      tenant_role_ids: showTenantBlock.value
        ? modeToIds(tenantRoleMode.value, tenantRoleIds.value)
        : null,
      user_role_ids: showUserBlock.value
        ? modeToIds(userRoleMode.value, userRoleIds.value)
        : null,
    });
    message.success($t('tenant.ai.agent.access.messages.updateSuccess'));
    drawerApi.close();
  } catch {
    // error handled by global interceptor
  } finally {
    saving.value = false;
  }
}

watch(showUserBlock, (val) => {
  if (!val) { userRoleMode.value = 'all'; userRoleIds.value = []; }
});

onMounted(() => {
  loadTenantRoleTree();
  loadUserRoleOptions();
});
</script>

<template>
  <Drawer :title="title" class="w-[560px]">
    <Spin :spinning="loading">
      <Form layout="vertical" class="px-1">
        <Alert
          :message="$t('tenant.ai.agent.access.hint.roleOnly')"
          type="info"
          show-icon
          class="mb-4"
        />

        <!-- Tenant 端角色区块 -->
        <div v-if="showTenantBlock" class="mb-4 rounded-lg border border-border/60 p-4">
          <div class="mb-3 flex items-center gap-2">
            <IconifyIcon icon="lucide:building-2" class="size-4 text-primary" />
            <span class="text-sm font-medium">{{ $t('tenant.ai.agent.access.tenantRoleAccess') }}</span>
          </div>
          <RadioGroup v-model:value="tenantRoleMode" class="mb-2">
            <Radio value="all">{{ $t('admin.ai.agent.roleMode.all') }}</Radio>
            <Radio value="specific">{{ $t('admin.ai.agent.roleMode.specific') }}</Radio>
          </RadioGroup>
          <TreeSelect
            v-if="tenantRoleMode === 'specific'"
            v-model:value="tenantRoleIds"
            :tree-data="tenantRoleTreeData"
            tree-checkable
            :show-checked-strategy="TreeSelect.SHOW_CHILD"
            :placeholder="$t('tenant.ai.agent.access.placeholder.selectTenantRoles')"
            :loading="tenantRoleTreeLoading"
            allow-clear
            style="width: 100%"
            class="mt-2"
          />
        </div>

        <Divider v-if="showTenantBlock && showUserBlock" class="my-2" />

        <!-- User 端角色区块（仅 all 时显示） -->
        <div v-if="showUserBlock" class="mb-4 rounded-lg border border-border/60 p-4">
          <div class="mb-3 flex items-center gap-2">
            <IconifyIcon icon="lucide:users" class="size-4 text-primary" />
            <span class="text-sm font-medium">{{ $t('tenant.ai.agent.access.userRoleAccess') }}</span>
          </div>
          <RadioGroup v-model:value="userRoleMode" class="mb-2">
            <Radio value="all">{{ $t('admin.ai.agent.roleMode.all') }}</Radio>
            <Radio value="specific">{{ $t('admin.ai.agent.roleMode.specific') }}</Radio>
          </RadioGroup>
          <Select
            v-if="userRoleMode === 'specific'"
            v-model:value="userRoleIds"
            mode="multiple"
            :options="userRoleOptions"
            :placeholder="$t('tenant.ai.agent.access.placeholder.selectUserRoles')"
            :loading="userRoleLoading"
            allow-clear
            style="width: 100%"
            class="mt-2"
          />
        </div>

        <FormItem class="mt-4">
          <Button type="primary" :loading="saving" @click="onSave">
            {{ $t('common.save') }}
          </Button>
        </FormItem>
      </Form>
    </Spin>
  </Drawer>
</template>
