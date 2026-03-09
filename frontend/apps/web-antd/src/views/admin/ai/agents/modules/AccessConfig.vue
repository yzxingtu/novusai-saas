<script setup lang="ts">
/**
 * 智能体访问权限配置抽屉（管理端）
 *
 * 仅配置 admin_role_ids（管理端角色权限控制）。
 * 租户端/用户端的角色权限由租户管理员自行配置。
 */
import { computed, onMounted, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Form,
  FormItem,
  message,
  Radio,
  RadioGroup,
  Spin,
  TreeSelect,
} from 'ant-design-vue';

import { getAIAgentAccessApi, updateAIAgentAccessApi } from '#/api/admin/ai';
import { getRoleTreeApi } from '#/api/admin/role';
import { $t } from '#/locales';

import type { RoleInfo } from '#/api/admin/role';

defineOptions({ name: 'AdminAccessConfigDrawer' });

const agentId = ref(0);
const agentName = ref('');
const targetAudience = ref<string>('admin_tenant');
const loading = ref(false);
const saving = ref(false);

const adminRoleMode = ref<'all' | 'specific'>('all');
const adminRoleIds = ref<number[]>([]);

const roleTreeData = ref<Record<string, unknown>[]>([]);
const roleTreeLoading = ref(false);

const showAdminBlock = computed(() =>
  ['all', 'admin_only', 'admin_tenant'].includes(targetAudience.value),
);

function roleInfoToTreeData(roles: RoleInfo[]): Record<string, unknown>[] {
  return roles.map((r) => ({
    title: r.name,
    value: r.id,
    key: r.id,
    children: r.children?.length ? roleInfoToTreeData(r.children) : undefined,
  }));
}

async function loadRoleTree() {
  roleTreeLoading.value = true;
  try {
    const tree = await getRoleTreeApi();
    roleTreeData.value = roleInfoToTreeData(tree);
  } catch {
    // error handled by global interceptor
  } finally {
    roleTreeLoading.value = false;
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
  () => `${$t('admin.ai.agent.accessConfig')} - ${agentName.value}`,
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
    const config = await getAIAgentAccessApi(agentId.value);
    adminRoleMode.value = idsToMode(config.admin_role_ids ?? null);
    adminRoleIds.value = config.admin_role_ids ?? [];
  } catch {
    // error handled by global interceptor
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  saving.value = true;
  try {
    await updateAIAgentAccessApi(agentId.value, {
      admin_role_ids: showAdminBlock.value
        ? modeToIds(adminRoleMode.value, adminRoleIds.value)
        : null,
    });
    message.success($t('admin.ai.agent.messages.accessUpdated'));
    drawerApi.close();
  } catch {
    // error handled by global interceptor
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  loadRoleTree();
});
</script>

<template>
  <Drawer :title="title" class="w-[560px]">
    <Spin :spinning="loading">
      <Form layout="vertical" class="px-1">
        <Alert
          :message="$t('admin.ai.agent.messages.accessRoleHint')"
          type="info"
          show-icon
          class="mb-4"
        />

        <!-- Admin 端角色区块 -->
        <div v-if="showAdminBlock" class="mb-4 rounded-lg border border-border/60 p-4">
          <div class="mb-3 flex items-center gap-2">
            <IconifyIcon icon="lucide:shield" class="size-4 text-primary" />
            <span class="text-sm font-medium">{{ $t('admin.ai.agent.adminRoleAccess') }}</span>
          </div>
          <RadioGroup v-model:value="adminRoleMode" class="mb-2">
            <Radio value="all">{{ $t('admin.ai.agent.roleMode.all') }}</Radio>
            <Radio value="specific">{{ $t('admin.ai.agent.roleMode.specific') }}</Radio>
          </RadioGroup>
          <TreeSelect
            v-if="adminRoleMode === 'specific'"
            v-model:value="adminRoleIds"
            :tree-data="roleTreeData"
            tree-checkable
            :show-checked-strategy="TreeSelect.SHOW_CHILD"
            :placeholder="$t('admin.ai.agent.placeholder.selectRoles')"
            :loading="roleTreeLoading"
            allow-clear
            style="width: 100%"
            class="mt-2"
          />
        </div>

        <div v-if="!showAdminBlock" class="py-8 text-center text-muted-foreground">
          <IconifyIcon icon="lucide:info" class="mb-2 size-8 opacity-40" />
          <p class="text-sm">{{ $t('admin.ai.agent.messages.noAdminAccess') }}</p>
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
