<script lang="ts" setup>
/**
 * DependencyBlockModal - Unified deletion dependency preview modal
 * DependencyBlockModal - 统一删除依赖预览弹窗
 *
 * Two modes:
 * 两种模式：
 * 1. Blocked mode: read-only, shows blocking deps, no footer
 *    阻止模式：只读，展示阻止依赖，无底部按钮
 * 2. Cascade mode: shows cascade/nullify effects, with confirm/cancel footer
 *    级联模式：展示级联/置空影响，有确认/取消底部按钮
 */
import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Modal, Tag } from 'ant-design-vue';

import { $t } from '#/locales';
import { router } from '#/router';

import { resolveDependencyPagePath } from './dependency-page-map';

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

interface DeletePreviewResult {
  blocked: boolean;
  blockers: DependencyGroup[];
  cascade_soft: DependencyGroup[];
  cascade_delete: DependencyGroup[];
  nullify: DependencyGroup[];
}

type StrategyType = 'blocked' | 'cascade_delete' | 'cascade_soft' | 'nullify';

interface DisplayGroup {
  dep: DependencyGroup;
  strategy: StrategyType;
}

const visible = ref(false);
const resourceName = ref('');
const isBlocked = ref(false);
const displayGroups = ref<DisplayGroup[]>([]);
let resolvePromise: ((value: boolean) => void) | null = null;

const MAX_PREVIEW = 5;

const strategyConfig: Record<
  StrategyType,
  { color: string; icon: string; labelKey: string }
> = {
  blocked: {
    color: 'red',
    icon: 'lucide:ban',
    labelKey: 'common.dependency.strategyBlocked',
  },
  cascade_soft: {
    color: 'orange',
    icon: 'lucide:archive',
    labelKey: 'common.dependency.strategyCascadeSoft',
  },
  cascade_delete: {
    color: 'red',
    icon: 'lucide:trash-2',
    labelKey: 'common.dependency.strategyCascadeDelete',
  },
  nullify: {
    color: 'blue',
    icon: 'lucide:unlink',
    labelKey: 'common.dependency.strategyNullify',
  },
};

/** Open blocked-only dependency modal / 打开仅阻止模式的依赖弹窗 */
function openBlocked(deps: DependencyGroup[], name?: string) {
  resourceName.value = name || '';
  isBlocked.value = true;
  displayGroups.value = deps.map((dep) => ({ dep, strategy: 'blocked' }));
  resolvePromise = null;
  visible.value = true;
}

/**
 * Open with full preview result, returns Promise<boolean> for cascade mode.
 * 使用完整预览结果打开，级联模式返回 Promise<boolean>。
 */
function openPreview(
  preview: DeletePreviewResult,
  name: string,
): Promise<boolean> {
  resourceName.value = name;
  isBlocked.value = preview.blocked;

  const groups: DisplayGroup[] = [];
  for (const dep of preview.blockers ?? []) {
    groups.push({ dep, strategy: 'blocked' });
  }
  for (const dep of preview.cascade_soft ?? []) {
    groups.push({ dep, strategy: 'cascade_soft' });
  }
  for (const dep of preview.cascade_delete ?? []) {
    groups.push({ dep, strategy: 'cascade_delete' });
  }
  for (const dep of preview.nullify ?? []) {
    groups.push({ dep, strategy: 'nullify' });
  }
  displayGroups.value = groups;
  visible.value = true;

  if (preview.blocked) {
    resolvePromise = null;
    return Promise.resolve(false);
  }

  return new Promise((resolve) => {
    resolvePromise = resolve;
  });
}

function onConfirm() {
  visible.value = false;
  resolvePromise?.(true);
  resolvePromise = null;
}

function onCancel() {
  visible.value = false;
  resolvePromise?.(false);
  resolvePromise = null;
}

function onModalClose() {
  resolvePromise?.(false);
  resolvePromise = null;
}

function getModelLabel(type: string): string {
  const key = `common.dependency.model.${type}`;
  const translated = $t(key);
  return translated === key ? type : translated;
}

function getTypeIcon(type: string): string {
  const iconMap: Record<string, string> = {
    ai_model: 'lucide:brain',
    ai_provider: 'lucide:server',
    agent: 'lucide:bot',
    agent_access: 'lucide:shield-check',
    agent_conversation: 'lucide:message-square',
    agent_version: 'lucide:git-commit',
    admin: 'lucide:user-cog',
    admin_role: 'lucide:shield',
    batch_run: 'lucide:play-circle',
    knowledge_base: 'lucide:book-open',
    resource_tenant_assignment: 'lucide:building-2',
    knowledge_document: 'lucide:file-text',
    provider_api_key: 'lucide:key',
    skill: 'lucide:wrench',
    skill_package: 'lucide:package',
    tenant: 'lucide:building-2',
    tenant_admin: 'lucide:user',
    tenant_admin_role: 'lucide:shield-check',
    tenant_domain: 'lucide:globe',
    tenant_plan: 'lucide:credit-card',
    tenant_plugin: 'lucide:puzzle',
    tenant_quota: 'lucide:gauge',
    tenant_rate_limit: 'lucide:timer',
    system_agent_assignment: 'lucide:link',
    codegen_config_version: 'lucide:history',
  };
  return iconMap[type] || 'lucide:box';
}

function getDependencyHandlePath(type: string): null | string {
  return resolveDependencyPagePath(type);
}

function getDependencyHandleText(type: string): string {
  return $t('common.dependency.goToHandle', {
    name: getModelLabel(type),
  });
}

function onNavigateToDependency(type: string) {
  const path = getDependencyHandlePath(type);
  if (!path) {
    return;
  }
  onModalClose();
  void router.push(path);
}

const title = computed(() => {
  if (isBlocked.value) {
    return resourceName.value
      ? $t('common.dependency.titleWithName', { name: resourceName.value })
      : $t('common.dependency.title');
  }
  return $t('common.dependency.confirmDeleteTitle', {
    name: resourceName.value,
  });
});

const warningText = computed(() =>
  isBlocked.value
    ? $t('common.dependency.blocked')
    : $t('common.dependency.cascadeWarning'),
);

const guidanceText = computed(() =>
  isBlocked.value
    ? $t('common.dependency.description')
    : $t('common.dependency.cascadeDescription'),
);

const guidanceIcon = computed(() =>
  isBlocked.value ? 'lucide:lightbulb' : 'lucide:info',
);

defineExpose({ close: onCancel, openBlocked, openPreview });
</script>

<template>
  <Modal
    v-model:open="visible"
    :title="title"
    :footer="null"
    :width="520"
    centered
    @cancel="onModalClose"
  >
    <!-- Warning message / 提示文案 -->
    <div class="mb-4 flex items-start gap-2 rounded-lg bg-warning/10 px-4 py-3">
      <IconifyIcon
        icon="lucide:alert-triangle"
        class="mt-0.5 size-5 shrink-0 text-warning"
      />
      <span class="text-sm text-foreground">
        {{ warningText }}
      </span>
    </div>

    <!-- Dependency group list / 依赖分组列表 -->
    <div class="space-y-3">
      <div
        v-for="(group, idx) in displayGroups"
        :key="`${group.strategy}-${group.dep.type}-${idx}`"
        class="rounded-lg border border-border/50 bg-accent/5 px-4 py-3"
      >
        <!-- Type heading / 类型标题 -->
        <div class="mb-2 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <IconifyIcon
              :icon="getTypeIcon(group.dep.type)"
              class="size-4 text-primary"
            />
            <span class="text-sm font-medium text-foreground">
              {{ getModelLabel(group.dep.type) }}
            </span>
          </div>
          <div class="flex items-center gap-1.5">
            <Tag
              :color="strategyConfig[group.strategy].color"
              class="mr-0 text-xs"
            >
              {{ $t(strategyConfig[group.strategy].labelKey) }}
            </Tag>
            <Tag color="default" class="mr-0">
              {{
                $t('common.dependency.itemCount', { count: group.dep.count })
              }}
            </Tag>
          </div>
        </div>

        <!-- Record summary / 记录摘要 -->
        <div
          v-if="group.dep.items && group.dep.items.length > 0"
          class="space-y-1 pl-6"
        >
          <div
            v-for="item in group.dep.items.slice(0, MAX_PREVIEW)"
            :key="item.id"
            class="flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <span
              class="inline-block size-1 rounded-full bg-muted-foreground/40"
            ></span>
            <span>{{ item.label || `#${item.id}` }}</span>
          </div>
          <div
            v-if="group.dep.count > MAX_PREVIEW"
            class="text-xs italic text-muted-foreground/60"
          >
            {{
              $t('common.dependency.moreItems', {
                count: group.dep.count - MAX_PREVIEW,
              })
            }}
          </div>
        </div>

        <div
          v-if="isBlocked && getDependencyHandlePath(group.dep.type)"
          class="mt-3 pl-6"
        >
          <Button
            type="link"
            size="small"
            class="px-0"
            @click="onNavigateToDependency(group.dep.type)"
          >
            {{ getDependencyHandleText(group.dep.type) }}
          </Button>
        </div>
      </div>
    </div>

    <!-- Guidance message / 引导文案 -->
    <div
      class="mt-4 flex items-center gap-2 rounded-lg px-4 py-2.5"
      :class="isBlocked ? 'bg-primary/5' : 'bg-warning/5'"
    >
      <IconifyIcon
        :icon="guidanceIcon"
        class="size-4 shrink-0"
        :class="isBlocked ? 'text-primary' : 'text-warning'"
      />
      <span class="text-xs text-muted-foreground">
        {{ guidanceText }}
      </span>
    </div>

    <!-- Confirm/Cancel footer for cascade mode / 级联模式的确认/取消底部 -->
    <div v-if="!isBlocked" class="mt-5 flex justify-end gap-2">
      <Button @click="onCancel">{{ $t('common.cancel') }}</Button>
      <Button type="primary" danger @click="onConfirm">
        {{ $t('common.dependency.cascadeConfirm') }}
      </Button>
    </div>
  </Modal>
</template>
