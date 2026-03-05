<script setup lang="ts">
/**
 * 智能体访问权限配置抽屉（管理端）
 *
 * 功能：配置可见性（public/private）和访问类型
 */
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

import { getAIAgentAccessApi, updateAIAgentAccessApi } from '#/api/admin/ai';
import { $t } from '#/locales';

defineOptions({ name: 'AdminAccessConfigDrawer' });

const agentId = ref(0);
const agentName = ref('');
const loading = ref(false);
const saving = ref(false);

const visibility = ref('public');
const accessType = ref('all_users');
const orgNodeIds = ref<number[]>([]);
const userIds = ref<number[]>([]);

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
  () => `${$t('admin.ai.agent.accessConfig')} - ${agentName.value}`,
);

const visibilityOptions = computed(() => [
  { label: $t('admin.ai.agent.visibility_options.public'), value: 'public' },
  { label: $t('admin.ai.agent.visibility_options.private'), value: 'private' },
]);

const accessTypeOptions = computed(() => [
  {
    label: $t('admin.ai.agent.access_type_options.all_users'),
    value: 'all_users',
  },
  {
    label: $t('admin.ai.agent.access_type_options.org_node'),
    value: 'org_node',
  },
  {
    label: $t('admin.ai.agent.access_type_options.specific_users'),
    value: 'specific_users',
  },
  {
    label: $t('admin.ai.agent.access_type_options.api_only'),
    value: 'api_only',
  },
]);

async function loadAccessConfig() {
  loading.value = true;
  try {
    const config = await getAIAgentAccessApi(agentId.value);
    visibility.value = config.visibility || 'public';
    accessType.value = config.access_type || 'all_users';
    orgNodeIds.value = config.org_node_ids ?? [];
    userIds.value = config.user_ids ?? [];
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
    message.success($t('admin.ai.agent.messages.accessUpdated'));
    drawerApi.close();
  } catch {
    // error handled by global interceptor
  } finally {
    saving.value = false;
  }
}

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
        <FormItem :label="$t('admin.ai.agent.visibility')">
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
                  :icon="
                    opt.value === 'public' ? 'lucide:globe' : 'lucide:lock'
                  "
                  class="size-3.5"
                />
                {{ opt.label }}
              </div>
            </Radio>
          </RadioGroup>
          <Alert
            :message="
              isPrivate
                ? $t('admin.ai.agent.messages.visibilityPrivateHint')
                : $t('admin.ai.agent.messages.visibilityPublicHint')
            "
            type="info"
            show-icon
            class="mt-1"
          />
        </FormItem>

        <!-- 访问类型（仅 private 时显示） -->
        <template v-if="isPrivate">
          <FormItem :label="$t('admin.ai.agent.accessType')">
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
          </FormItem>

          <FormItem
            v-if="accessType === 'org_node'"
            :label="$t('admin.ai.agent.orgNodes')"
          >
            <Select
              v-model:value="orgNodeIds"
              mode="tags"
              :placeholder="$t('admin.ai.agent.placeholder.selectOrgNodes')"
              :token-separators="[',']"
              style="width: 100%"
            />
          </FormItem>

          <FormItem
            v-if="accessType === 'specific_users'"
            :label="$t('admin.ai.agent.specificUsers')"
          >
            <Select
              v-model:value="userIds"
              mode="tags"
              :placeholder="$t('admin.ai.agent.placeholder.inputUserIds')"
              :token-separators="[',']"
              style="width: 100%"
            />
          </FormItem>
        </template>

        <FormItem class="mt-4">
          <Button type="primary" :loading="saving" @click="onSave">
            {{ $t('common.save') }}
          </Button>
        </FormItem>
      </Form>
    </Spin>
  </Drawer>
</template>
