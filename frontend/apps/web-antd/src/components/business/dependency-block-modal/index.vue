<script lang="ts" setup>
/**
 * DependencyBlockModal - 删除依赖阻止弹窗
 *
 * 当删除被 4221 错误阻止时，展示被引用资源列表。
 * 支持独立使用或通过 useCrudPage 自动触发。
 */
import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Modal, Tag } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'DependencyBlockModal' });

interface DependencyItem {
  id: number;
  label?: string;
}

interface DependencyGroup {
  type: string;
  count: number;
  items: DependencyItem[];
}

const visible = ref(false);
const dependencies = ref<DependencyGroup[]>([]);
const resourceName = ref('');

const MAX_PREVIEW = 5;

/** 打开弹窗 */
function open(deps: DependencyGroup[], name?: string) {
  dependencies.value = deps;
  resourceName.value = name || '';
  visible.value = true;
}

/** 关闭弹窗 */
function close() {
  visible.value = false;
}

/** 获取模型的 i18n 名称 */
function getModelLabel(type: string): string {
  const key = `common.dependency.model.${type}`;
  const translated = $t(key);
  return translated === key ? type : translated;
}

/** 获取依赖类型图标 */
function getTypeIcon(type: string): string {
  const iconMap: Record<string, string> = {
    ai_model: 'lucide:brain',
    ai_provider: 'lucide:server',
    agent: 'lucide:bot',
    agent_conversation: 'lucide:message-square',
    admin: 'lucide:user-cog',
    admin_role: 'lucide:shield',
    batch_run: 'lucide:play-circle',
    knowledge_base: 'lucide:book-open',
    knowledge_document: 'lucide:file-text',
    provider_api_key: 'lucide:key',
    skill: 'lucide:wrench',
    skill_package: 'lucide:package',
    table_policy: 'lucide:table',
    table_policy_override: 'lucide:table-2',
    tenant: 'lucide:building-2',
    tenant_admin: 'lucide:user',
    tenant_admin_role: 'lucide:shield-check',
    tenant_domain: 'lucide:globe',
    tenant_plan: 'lucide:credit-card',
    tenant_plugin: 'lucide:puzzle',
    tenant_quota: 'lucide:gauge',
    tenant_rate_limit: 'lucide:timer',
    system_agent_assignment: 'lucide:link',
  };
  return iconMap[type] || 'lucide:box';
}

/** 标题 */
const title = computed(() => {
  if (resourceName.value) {
    return `${$t('common.dependency.title')}「${resourceName.value}」`;
  }
  return $t('common.dependency.title');
});

defineExpose({ open, close });
</script>

<template>
  <Modal
    v-model:open="visible"
    :title="title"
    :footer="null"
    :width="520"
    centered
  >
    <!-- 提示文案 -->
    <div class="mb-4 flex items-start gap-2 rounded-lg bg-warning/10 px-4 py-3">
      <IconifyIcon
        icon="lucide:alert-triangle"
        class="mt-0.5 size-5 shrink-0 text-warning"
      />
      <span class="text-sm text-foreground">
        {{ $t('common.dependency.blocked') }}
      </span>
    </div>

    <!-- 依赖分组列表 -->
    <div class="space-y-3">
      <div
        v-for="dep in dependencies"
        :key="dep.type"
        class="rounded-lg border border-border/50 bg-accent/5 px-4 py-3"
      >
        <!-- 类型标题 -->
        <div class="mb-2 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <IconifyIcon
              :icon="getTypeIcon(dep.type)"
              class="size-4 text-primary"
            />
            <span class="text-sm font-medium text-foreground">
              {{ getModelLabel(dep.type) }}
            </span>
          </div>
          <Tag color="orange" class="mr-0">
            {{ $t('common.dependency.itemCount', { count: dep.count }) }}
          </Tag>
        </div>

        <!-- 记录摘要 -->
        <div v-if="dep.items && dep.items.length > 0" class="space-y-1 pl-6">
          <div
            v-for="item in dep.items.slice(0, MAX_PREVIEW)"
            :key="item.id"
            class="flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <span class="inline-block size-1 rounded-full bg-muted-foreground/40" />
            <span>{{ item.label || `#${item.id}` }}</span>
          </div>
          <div
            v-if="dep.count > MAX_PREVIEW"
            class="text-xs text-muted-foreground/60 italic"
          >
            {{ $t('common.dependency.moreItems', { count: dep.count - MAX_PREVIEW }) }}
          </div>
        </div>
      </div>
    </div>

    <!-- 引导文案 -->
    <div
      class="mt-4 flex items-center gap-2 rounded-lg bg-primary/5 px-4 py-2.5"
    >
      <IconifyIcon
        icon="lucide:lightbulb"
        class="size-4 shrink-0 text-primary"
      />
      <span class="text-xs text-muted-foreground">
        {{ $t('common.dependency.description') }}
      </span>
    </div>
  </Modal>
</template>
