<script lang="ts" setup>
defineOptions({ name: 'AdminSkillPackageDetail' });
/**
 * 管理端技能包详情页
 *
 * - 顶部：返回按钮 + 包名 + scope/status 标签
 * - 基本信息卡片：完整展示所有字段（描述/作用域/系统标识/排序/来源插件/时间等）
 * - Tab 1: 包内技能列表（翻译类型、超时、描述、状态切换、删除）
 * - Tab 2: Valves 环境变量配置
 */
import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';
import type { AdminSkillInfo } from '#/api/admin/skills';

import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Card,
  Descriptions,
  DescriptionsItem,
  Empty,
  message,
  Popconfirm,
  Space,
  Spin,
  Switch,
  Tabs,
  TabPane,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  getSkillPackageDetailApi,
  getSkillPackageSkillsApi,
  getSkillPackageValvesApi,
  updateSkillPackageValvesApi,
} from '#/api/admin/skill-packages';
import { requestClient } from '#/utils/request';
import {
  deleteSkillApi,
  toggleSkillStatusApi,
} from '#/api/admin/skills';
import { $t } from '#/locales';
import { formatRelativeTime } from '#/utils/common';
import { getScopeColor, getSkillTypeColor, getSkillTypeIcon } from '#/utils/ai-helpers';
import { getScopeText } from './data';
import { getSkillTypeText } from '../skills/data';

const route = useRoute();
const router = useRouter();
const packageId = computed(() => Number(route.params.id));

// ==================== State ====================
const loading = ref(false);
const pkg = ref<AdminSkillPackageInfo | null>(null);
const skills = ref<AdminSkillInfo[]>([]);
const skillsLoading = ref(false);
const activeTab = ref('skills');

// Valves
const valvesSchema = ref<Record<string, unknown> | null>(null);
const valvesConfig = ref<Record<string, unknown>>({});
const valvesSaving = ref(false);

// Resolved Tools
interface ResolvedTool {
  name: string;
  description: string;
  parameters: Array<{
    name: string;
    type: string;
    description: string;
    required: boolean;
    default?: unknown;
  }>;
  timeout: number;
  source_skill_id: number;
  source_skill_name: string;
}
const resolvedTools = ref<ResolvedTool[]>([]);
const toolsLoading = ref(false);

// ==================== Load ====================
async function loadPackage() {
  loading.value = true;
  try {
    const data = await getSkillPackageDetailApi(packageId.value);
    pkg.value = data;
  } catch {
    router.replace('/admin/ai/skill-packages');
  } finally {
    loading.value = false;
  }
}

async function loadSkills() {
  skillsLoading.value = true;
  try {
    const res = await getSkillPackageSkillsApi(packageId.value, {
      'page[size]': 100,
      sort: 'sort_order',
    });
    skills.value = res.items;
  } catch {
    skills.value = [];
  } finally {
    skillsLoading.value = false;
  }
}

async function loadValves() {
  try {
    const data = await getSkillPackageValvesApi(packageId.value);
    valvesSchema.value = data.valves_schema;
    valvesConfig.value = data.valves_config || {};
  } catch {
    valvesSchema.value = null;
    valvesConfig.value = {};
  }
}

async function loadResolvedTools() {
  toolsLoading.value = true;
  try {
    const data = await requestClient.get<{ tools: ResolvedTool[]; tool_count: number }>(
      `/admin/ai/skill-packages/${packageId.value}/resolved-tools`,
    );
    resolvedTools.value = data.tools || [];
  } catch {
    resolvedTools.value = [];
  } finally {
    toolsLoading.value = false;
  }
}

onMounted(async () => {
  await loadPackage();
  await Promise.all([loadSkills(), loadValves(), loadResolvedTools()]);
});

// ==================== Actions ====================
async function handleToggleSkillStatus(skill: AdminSkillInfo) {
  try {
    await toggleSkillStatusApi(skill.id);
    message.success($t('admin.ai.skill.messages.toggleSuccess'));
    await loadSkills();
  } catch {
    // handled by interceptor
  }
}

async function handleDeleteSkill(skill: AdminSkillInfo) {
  try {
    await deleteSkillApi(skill.id);
    message.success($t('shared.common.deleteSuccess'));
    await loadSkills();
  } catch {
    // handled by interceptor
  }
}

async function handleSaveValves() {
  valvesSaving.value = true;
  try {
    await updateSkillPackageValvesApi(packageId.value, {
      valves_config: valvesConfig.value,
    });
    message.success($t('admin.ai.skillPackage.valves.saveSuccess'));
  } catch {
    // handled by interceptor
  } finally {
    valvesSaving.value = false;
  }
}

function goBack() {
  router.push('/admin/ai/skill-packages');
}

// ==================== Computed ====================
const hasValves = computed(() => {
  if (!valvesSchema.value) return false;
  const props = (valvesSchema.value as Record<string, unknown>)?.properties;
  return props && typeof props === 'object' && Object.keys(props).length > 0;
});

const valvesProperties = computed(() => {
  if (!valvesSchema.value) return {};
  return ((valvesSchema.value as Record<string, unknown>)?.properties || {}) as Record<
    string,
    { type?: string; description?: string; default?: unknown }
  >;
});

const valvesRequired = computed(() => {
  if (!valvesSchema.value) return [];
  return ((valvesSchema.value as Record<string, unknown>)?.required || []) as string[];
});
</script>

<template>
  <Page>
    <Spin :spinning="loading">
      <!-- Header -->
      <div class="mb-4 flex items-center gap-3">
        <Button @click="goBack">
          <IconifyIcon icon="lucide:arrow-left" class="mr-1" />
          {{ $t('admin.ai.skillPackage.detail.backToList') }}
        </Button>
        <div v-if="pkg" class="flex items-center gap-2">
          <IconifyIcon
            :icon="pkg.avatar || 'lucide:package'"
            class="size-5 text-primary"
          />
          <h2 class="m-0 text-lg font-semibold">{{ pkg.name }}</h2>
          <Tag :color="getScopeColor(pkg.scope)">{{ getScopeText(pkg.scope) }}</Tag>
          <Tag v-if="pkg.is_system" color="purple">
            {{ $t('admin.ai.skillPackage.system') }}
          </Tag>
          <Badge
            :status="pkg.is_active ? 'success' : 'default'"
            :text="pkg.is_active ? $t('admin.common.enabled') : $t('admin.common.disabled')"
          />
        </div>
      </div>

      <!-- Basic Info Card -->
      <Card v-if="pkg" class="mb-4" size="small" :title="$t('admin.ai.skillPackage.detail.basicInfo')">
        <Descriptions :column="{ xs: 1, sm: 2, md: 3 }" size="small" bordered>
          <DescriptionsItem :label="$t('admin.ai.skillPackage.name')" :span="3">
            {{ pkg.name }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.ai.skillPackage.description')" :span="3">
            <span v-if="pkg.description">{{ pkg.description }}</span>
            <span v-else class="text-muted-foreground">{{ $t('admin.ai.skillPackage.detail.noDescription') }}</span>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.ai.skillPackage.scope')">
            <Tag :color="getScopeColor(pkg.scope)">{{ getScopeText(pkg.scope) }}</Tag>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.ai.skillPackage.isActive')">
            <Badge
              :status="pkg.is_active ? 'success' : 'default'"
              :text="pkg.is_active ? $t('admin.common.enabled') : $t('admin.common.disabled')"
            />
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.ai.skillPackage.detail.isSystem')">
            {{ pkg.is_system ? $t('admin.ai.skillPackage.detail.yes') : $t('admin.ai.skillPackage.detail.no') }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.ai.skillPackage.skillCount')">
            <Badge :count="pkg.skill_count" :number-style="{ backgroundColor: '#1890ff' }" show-zero />
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.ai.skillPackage.sortOrder')">
            {{ pkg.sort_order }}
          </DescriptionsItem>
          <DescriptionsItem v-if="pkg.source_plugin" :label="$t('admin.ai.skillPackage.detail.sourcePlugin')">
            <Tag color="cyan">
              <IconifyIcon icon="lucide:plug" class="mr-0.5 inline size-3" />
              {{ pkg.source_plugin }}
            </Tag>
          </DescriptionsItem>
          <DescriptionsItem v-if="pkg.tenant_id" :label="$t('admin.ai.skillPackage.detail.tenantName')">
            ID: {{ pkg.tenant_id }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.common.createdAt')">
            {{ formatRelativeTime(pkg.created_at) }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.ai.skillPackage.detail.updatedAt')">
            {{ formatRelativeTime(pkg.updated_at) }}
          </DescriptionsItem>
        </Descriptions>
      </Card>

      <!-- Tabs: Skills + Valves -->
      <Tabs v-model:activeKey="activeTab">
        <!-- Skills Tab -->
        <TabPane key="skills" :tab="`${$t('admin.ai.skillPackage.detail.skills')} (${skills.length})`">
          <div class="mb-3 flex justify-end">
            <Button
              type="primary"
              @click="router.push('/admin/ai/skill-packages')"
            >
              <IconifyIcon icon="lucide:plus" class="mr-1" />
              {{ $t('admin.ai.skill.create') }}
            </Button>
          </div>

          <Spin :spinning="skillsLoading">
            <div v-if="skills.length === 0" class="py-8">
              <Empty :description="$t('admin.ai.skillPackage.detail.empty')" />
            </div>
            <div v-else class="flex flex-col gap-3">
              <Card
                v-for="skill in skills"
                :key="skill.id"
                size="small"
                :body-style="{ padding: '12px 16px' }"
                class="transition-shadow hover:shadow-sm"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-3">
                    <div
                      class="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10"
                    >
                      <IconifyIcon
                        :icon="getSkillTypeIcon(skill.type)"
                        class="size-4 text-primary"
                      />
                    </div>
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center gap-2">
                        <span class="font-medium">{{ skill.name }}</span>
                        <Tag :color="getSkillTypeColor(skill.type)" size="small">
                          {{ getSkillTypeText(skill.type) }}
                        </Tag>
                        <Tag v-if="skill.is_system" color="purple" size="small">
                          {{ $t('admin.ai.skillPackage.system') }}
                        </Tag>
                      </div>
                      <div v-if="skill.description" class="mt-1 line-clamp-2 text-xs text-muted-foreground">
                        {{ skill.description }}
                      </div>
                      <div class="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                        <span v-if="skill.timeout">
                          <IconifyIcon icon="lucide:clock" class="mr-0.5 inline size-3" />
                          {{ skill.timeout }}s
                        </span>
                        <span>
                          <IconifyIcon icon="lucide:calendar" class="mr-0.5 inline size-3" />
                          {{ formatRelativeTime(skill.created_at) }}
                        </span>
                      </div>
                    </div>
                  </div>
                  <Space>
                    <Tooltip :title="skill.is_active ? $t('admin.common.disable') : $t('admin.common.enable')">
                      <Switch
                        :checked="skill.is_active"
                        size="small"
                        :disabled="skill.is_system"
                        @change="handleToggleSkillStatus(skill)"
                      />
                    </Tooltip>
                    <Popconfirm
                      v-if="!skill.is_system"
                      :title="$t('admin.common.confirmDelete')"
                      @confirm="handleDeleteSkill(skill)"
                    >
                      <Button danger size="small" type="text">
                        <IconifyIcon icon="lucide:trash-2" />
                      </Button>
                    </Popconfirm>
                  </Space>
                </div>
              </Card>
            </div>
          </Spin>
        </TabPane>

        <!-- Tools Tab -->
        <TabPane
          key="tools"
          :tab="`${$t('admin.ai.skillPackage.detail.tools')} (${resolvedTools.length})`"
        >
          <Spin :spinning="toolsLoading">
            <div v-if="resolvedTools.length === 0" class="py-8">
              <Empty :description="$t('admin.ai.skillPackage.detail.noTools')" />
            </div>
            <div v-else class="flex flex-col gap-3">
              <Card
                v-for="tool in resolvedTools"
                :key="tool.name"
                size="small"
                :body-style="{ padding: '12px 16px' }"
                class="transition-shadow hover:shadow-sm"
              >
                <div class="flex items-start gap-3">
                  <div class="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                    <IconifyIcon icon="lucide:wrench" class="size-4 text-primary" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                      <span class="font-mono text-sm font-semibold text-foreground">{{ tool.name }}</span>
                      <Tag v-if="tool.timeout" size="small" color="default">
                        <IconifyIcon icon="lucide:clock" class="mr-0.5 inline size-3" />
                        {{ tool.timeout }}s
                      </Tag>
                    </div>
                    <p v-if="tool.description" class="mt-1 text-xs leading-relaxed text-muted-foreground">
                      {{ tool.description }}
                    </p>
                    <!-- 参数列表 -->
                    <div v-if="tool.parameters?.length" class="mt-2">
                      <div class="text-xs font-medium text-muted-foreground mb-1">
                        {{ $t('admin.ai.skillPackage.detail.toolParams') }}
                      </div>
                      <div class="flex flex-col gap-1">
                        <div
                          v-for="param in tool.parameters"
                          :key="param.name"
                          class="flex items-center gap-2 rounded bg-muted/50 px-2 py-1 text-xs"
                        >
                          <span class="font-mono font-medium text-foreground">{{ param.name }}</span>
                          <Tag size="small" :color="param.required ? 'red' : 'default'">
                            {{ param.type }}{{ param.required ? ' *' : '' }}
                          </Tag>
                          <span v-if="param.description" class="truncate text-muted-foreground">
                            {{ param.description }}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          </Spin>
        </TabPane>

        <!-- Valves Tab -->
        <TabPane
          key="valves"
          :tab="$t('admin.ai.skillPackage.valves.title')"
          :disabled="!hasValves"
        >
          <Card size="small">
            <template v-if="hasValves">
              <p class="mb-4 text-sm text-muted-foreground">
                {{ $t('admin.ai.skillPackage.valves.description') }}
              </p>
              <div class="flex flex-col gap-4">
                <div
                  v-for="(prop, key) in valvesProperties"
                  :key="String(key)"
                  class="flex flex-col gap-1"
                >
                  <label class="flex items-center gap-1 text-sm font-medium">
                    {{ key }}
                    <Tag v-if="valvesRequired.includes(String(key))" color="error" size="small">
                      {{ $t('admin.ai.skillPackage.valves.required') }}
                    </Tag>
                  </label>
                  <div v-if="prop.description" class="text-xs text-muted-foreground">
                    {{ prop.description }}
                  </div>
                  <input
                    :value="(valvesConfig[String(key)] as string) || ''"
                    class="rounded border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                    :type="String(key).toLowerCase().includes('password') || String(key).toLowerCase().includes('secret') || String(key).toLowerCase().includes('key') ? 'password' : 'text'"
                    :placeholder="prop.default !== undefined ? String(prop.default) : ''"
                    @input="(e: Event) => { valvesConfig[String(key)] = (e.target as HTMLInputElement).value; }"
                  />
                </div>
              </div>
              <div class="mt-4 flex justify-end">
                <Button
                  type="primary"
                  :loading="valvesSaving"
                  @click="handleSaveValves"
                >
                  {{ $t('shared.common.save') }}
                </Button>
              </div>
            </template>
            <template v-else>
              <Empty :description="$t('admin.ai.skillPackage.valves.noSchema')" />
            </template>
          </Card>
        </TabPane>
      </Tabs>
    </Spin>
  </Page>
</template>
