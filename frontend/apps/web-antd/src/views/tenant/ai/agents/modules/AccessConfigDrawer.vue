<script setup lang="ts">
/**
 * 智能体访问权限配置抽屉
 *
 * 功能：配置可见性（public/private）和访问类型（all_users/org_node/specific_users/api_only）
 */
defineOptions({ name: 'AccessConfigDrawer' });

import { computed, ref, watch } from 'vue';

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
  Select,
  Spin,
} from 'ant-design-vue';

import {
  getAgentAccessApi,
  updateAgentAccessApi,
} from '#/api/tenant/agents';
import { $t } from '#/locales';

const agentId = ref(0);
const agentName = ref('');
const loading = ref(false);
const saving = ref(false);

// 表单数据
const visibility = ref('public');
const accessType = ref('all_users');
const orgNodeIds = ref<number[]>([]);
const userIds = ref<number[]>([]);

// 用户 ID 输入（逗号分隔字符串 → number[]）
const userIdsInput = ref('');

const isPrivate = computed(() => visibility.value === 'private');

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange: async (isOpen) => {
    if (isOpen) {
      const data = drawerApi.getData<{ id: number; name: string }>();
      if (data) {
        agentId.value = data.id;
        agentName.value = data.name;
        await loadAccessConfig();
      }
    }
  },
});

const title = computed(
  () => `${$t('tenant.ai.agent.access.title')} - ${agentName.value}`,
);

/** 可见性选项 */
const visibilityOptions = computed(() => [
  {
    label: $t('tenant.ai.agent.access.visibility_options.public'),
    value: 'public',
  },
  {
    label: $t('tenant.ai.agent.access.visibility_options.private'),
    value: 'private',
  },
]);

/** 访问类型选项 */
const accessTypeOptions = computed(() => [
  {
    label: $t('tenant.ai.agent.access.access_type_options.all_users'),
    value: 'all_users',
  },
  {
    label: $t('tenant.ai.agent.access.access_type_options.org_node'),
    value: 'org_node',
  },
  {
    label: $t('tenant.ai.agent.access.access_type_options.specific_users'),
    value: 'specific_users',
  },
  {
    label: $t('tenant.ai.agent.access.access_type_options.api_only'),
    value: 'api_only',
  },
]);

/** 当前可见性的提示文本 */
const visibilityHint = computed(() => {
  return visibility.value === 'private'
    ? $t('tenant.ai.agent.access.hint.private')
    : $t('tenant.ai.agent.access.hint.public');
});

/** 当前访问类型的提示文本 */
const accessTypeHint = computed(() => {
  const key = `tenant.ai.agent.access.hint.${accessType.value}`;
  return $t(key);
});

/** 加载配置 */
async function loadAccessConfig() {
  loading.value = true;
  try {
    const config = await getAgentAccessApi(agentId.value);
    visibility.value = config.visibility || 'public';
    accessType.value = config.access_type || 'all_users';
    orgNodeIds.value = config.org_node_ids ?? [];
    userIds.value = config.user_ids ?? [];
    userIdsInput.value = userIds.value.join(', ');
  } catch {
    // error handled by global interceptor
  } finally {
    loading.value = false;
  }
}

/** 保存配置 */
async function onSave() {
  // 解析用户 ID 输入
  if (accessType.value === 'specific_users' && userIdsInput.value.trim()) {
    const parsed = userIdsInput.value
      .split(',')
      .map((s) => Number.parseInt(s.trim(), 10))
      .filter((n) => !Number.isNaN(n) && n > 0);
    userIds.value = parsed;
  }

  saving.value = true;
  try {
    await updateAgentAccessApi(agentId.value, {
      visibility: visibility.value,
      access_type: isPrivate.value ? accessType.value : 'all_users',
      org_node_ids:
        isPrivate.value && accessType.value === 'org_node'
          ? orgNodeIds.value
          : null,
      user_ids:
        isPrivate.value && accessType.value === 'specific_users'
          ? userIds.value
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

/** visibility 切换时重置 accessType */
watch(visibility, (val) => {
  if (val === 'public') {
    accessType.value = 'all_users';
  }
});
</script>

<template>
  <Drawer :title="title" class="w-[520px]">
    <Spin :spinning="loading">
      <Form layout="vertical" class="px-1">
        <!-- 可见性 -->
        <FormItem :label="$t('tenant.ai.agent.access.visibility')">
          <RadioGroup
            v-model:value="visibility"
            button-style="solid"
            class="mb-2"
          >
            <Radio
              v-for="opt in visibilityOptions"
              :key="opt.value"
              :value="opt.value"
            >
              <div class="flex items-center gap-1">
                <IconifyIcon
                  :icon="opt.value === 'public' ? 'lucide:globe' : 'lucide:lock'"
                  class="size-3.5"
                />
                {{ opt.label }}
              </div>
            </Radio>
          </RadioGroup>
          <Alert :message="visibilityHint" type="info" show-icon class="mt-1" />
        </FormItem>

        <!-- 访问类型（仅 private 时显示） -->
        <template v-if="isPrivate">
          <FormItem :label="$t('tenant.ai.agent.access.accessType')">
            <RadioGroup v-model:value="accessType" class="mb-2">
              <Radio
                v-for="opt in accessTypeOptions"
                :key="opt.value"
                :value="opt.value"
                class="mb-1 block"
              >
                {{ opt.label }}
              </Radio>
            </RadioGroup>
            <Alert
              :message="accessTypeHint"
              type="info"
              show-icon
              class="mt-1"
            />
          </FormItem>

          <!-- 组织节点 ID（org_node 时显示） -->
          <FormItem
            v-if="accessType === 'org_node'"
            :label="$t('tenant.ai.agent.access.orgNodes')"
          >
            <Select
              v-model:value="orgNodeIds"
              mode="tags"
              :placeholder="$t('tenant.ai.agent.access.placeholder.selectOrgNodes')"
              :token-separators="[',']"
              style="width: 100%"
            />
          </FormItem>

          <!-- 用户 ID（specific_users 时显示） -->
          <FormItem
            v-if="accessType === 'specific_users'"
            :label="$t('tenant.ai.agent.access.users')"
          >
            <Select
              v-model:value="userIds"
              mode="tags"
              :placeholder="$t('tenant.ai.agent.access.placeholder.inputUserIds')"
              :token-separators="[',']"
              style="width: 100%"
            />
          </FormItem>
        </template>

        <!-- 操作按钮 -->
        <FormItem class="mt-4">
          <Button type="primary" :loading="saving" @click="onSave">
            {{ $t('common.save') }}
          </Button>
        </FormItem>
      </Form>
    </Spin>
  </Drawer>
</template>
