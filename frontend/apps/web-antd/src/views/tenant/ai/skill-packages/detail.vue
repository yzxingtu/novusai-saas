<script lang="ts" setup>
defineOptions({ name: 'TenantSkillPackageDetail' });
/**
 * 租户端技能包详情页
 *
 * - 顶部：技能包基本信息卡片
 * - Tab 1: 包内技能列表（只读展示 + 启用/禁用）
 * - Tab 2: Valves 环境变量配置
 * - global/admin 包只读不可编辑
 */
import type { TenantSkillPackageInfo } from '#/api/tenant/skill-packages';
import type { SkillInfo } from '#/api/tenant/skills';

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
} from '#/api/tenant/skill-packages';
import { updateSkillApi } from '#/api/tenant/skills';
import { $t } from '#/locales';
import { formatRelativeTime } from '#/utils/common';
import { getSkillTypeColor, getSkillTypeIcon } from '#/utils/ai-helpers';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';
import { getSkillTypeText } from '../skills/data';

const route = useRoute();
const router = useRouter();
const packageId = computed(() => Number(route.params.id));

// ==================== State ====================
const loading = ref(false);
const pkg = ref<TenantSkillPackageInfo | null>(null);
const skills = ref<SkillInfo[]>([]);
const skillsLoading = ref(false);
const activeTab = ref('skills');

// Valves
const valvesSchema = ref<Record<string, unknown> | null>(null);
const valvesConfig = ref<Record<string, unknown>>({});
const valvesSaving = ref(false);

// ==================== Computed ====================
const isReadonly = computed(() => {
  if (!pkg.value) return true;
  return pkg.value.scope !== 'all_tenants';
});

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

// ==================== Load ====================
async function loadPackage() {
  loading.value = true;
  try {
    pkg.value = await getSkillPackageDetailApi(packageId.value);
  } catch {
    router.replace('/tenant/ai/skill-packages');
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

onMounted(async () => {
  await loadPackage();
  await Promise.all([loadSkills(), loadValves()]);
});

// ==================== Actions ====================
async function handleToggleSkillStatus(skill: SkillInfo) {
  if (isReadonly.value) return;
  try {
    await updateSkillApi(skill.id, { is_active: !skill.is_active });
    message.success($t('shared.common.success'));
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
    message.success($t('tenant.ai.skillPackage.valves.saveSuccess'));
  } catch {
    // handled by interceptor
  } finally {
    valvesSaving.value = false;
  }
}

function goBack() {
  router.push('/tenant/ai/skill-packages');
}
</script>

<template>
  <Page>
    <Spin :spinning="loading">
      <!-- Header -->
      <div class="mb-4 flex items-center gap-3">
        <Button @click="goBack">
          <IconifyIcon icon="lucide:arrow-left" class="mr-1" />
          {{ $t('tenant.ai.skillPackage.detail.backToList') }}
        </Button>
        <div v-if="pkg" class="flex items-center gap-2">
          <IconifyIcon
            :icon="pkg.avatar || 'lucide:package'"
            class="size-5 text-primary"
          />
          <h2 class="m-0 text-lg font-semibold">{{ pkg.name }}</h2>
          <Tag :color="getScopeColor(pkg.scope)">{{ getScopeText(pkg.scope) }}</Tag>
          <Tag v-if="pkg.is_system" color="purple">
            {{ $t('tenant.ai.skillPackage.system') }}
          </Tag>
          <Badge
            :status="pkg.is_active ? 'success' : 'default'"
            :text="pkg.is_active ? $t('tenant.common.enabled') : $t('tenant.common.disabled')"
          />
          <Tag v-if="isReadonly" color="warning">
            {{ $t('shared.common.viewDetail') }}
          </Tag>
        </div>
      </div>

      <!-- Basic Info Card -->
      <Card v-if="pkg" class="mb-4" size="small" :title="$t('tenant.ai.skillPackage.detail.basicInfo')">
        <Descriptions :column="{ xs: 1, sm: 2, md: 3 }" size="small" bordered>
          <DescriptionsItem :label="$t('tenant.ai.skillPackage.name')" :span="3">
            {{ pkg.name }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.ai.skillPackage.description')" :span="3">
            <span v-if="pkg.description">{{ pkg.description }}</span>
            <span v-else class="text-muted-foreground">{{ $t('tenant.ai.skillPackage.detail.noDescription') }}</span>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.ai.skillPackage.scope')">
            <Tag :color="getScopeColor(pkg.scope)">{{ getScopeText(pkg.scope) }}</Tag>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.ai.skillPackage.isActive')">
            <Badge
              :status="pkg.is_active ? 'success' : 'default'"
              :text="pkg.is_active ? $t('tenant.common.enabled') : $t('tenant.common.disabled')"
            />
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.ai.skillPackage.detail.isSystem')">
            {{ pkg.is_system ? $t('tenant.ai.skillPackage.detail.yes') : $t('tenant.ai.skillPackage.detail.no') }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.ai.skillPackage.skillCount')">
            <Badge :count="pkg.skill_count" :number-style="{ backgroundColor: '#1890ff' }" show-zero />
          </DescriptionsItem>
          <DescriptionsItem v-if="pkg.source_plugin" :label="$t('tenant.ai.skillPackage.detail.sourcePlugin')">
            <Tag color="cyan">
              <IconifyIcon icon="lucide:plug" class="mr-0.5 inline size-3" />
              {{ pkg.source_plugin }}
            </Tag>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('shared.common.createdAt')">
            {{ formatRelativeTime(pkg.created_at) }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.ai.skillPackage.detail.updatedAt')">
            {{ formatRelativeTime(pkg.updated_at) }}
          </DescriptionsItem>
        </Descriptions>
      </Card>

      <!-- Tabs -->
      <Tabs v-model:activeKey="activeTab">
        <!-- Skills Tab -->
        <TabPane key="skills" :tab="`${$t('tenant.ai.skillPackage.detail.skills')} (${skills.length})`">
          <Spin :spinning="skillsLoading">
            <div v-if="skills.length === 0" class="py-8">
              <Empty :description="$t('tenant.ai.skillPackage.detail.empty')" />
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
                          {{ $t('tenant.ai.skillPackage.system') }}
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
                  <Tooltip :title="skill.is_active ? $t('tenant.common.disable') : $t('tenant.common.enable')">
                    <Switch
                      :checked="skill.is_active"
                      size="small"
                      :disabled="isReadonly || skill.is_system"
                      @change="handleToggleSkillStatus(skill)"
                    />
                  </Tooltip>
                </div>
              </Card>
            </div>
          </Spin>
        </TabPane>

        <!-- Valves Tab -->
        <TabPane
          key="valves"
          :tab="$t('tenant.ai.skillPackage.valves.title')"
          :disabled="!hasValves"
        >
          <Card size="small">
            <template v-if="hasValves">
              <p class="mb-4 text-sm text-muted-foreground">
                {{ $t('tenant.ai.skillPackage.valves.description') }}
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
                      {{ $t('tenant.ai.skillPackage.valves.required') }}
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
                    :disabled="isReadonly"
                    @input="(e: Event) => { valvesConfig[String(key)] = (e.target as HTMLInputElement).value; }"
                  />
                </div>
              </div>
              <div v-if="!isReadonly" class="mt-4 flex justify-end">
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
              <Empty :description="$t('tenant.ai.skillPackage.valves.noSchema')" />
            </template>
          </Card>
        </TabPane>
      </Tabs>
    </Spin>
  </Page>
</template>
