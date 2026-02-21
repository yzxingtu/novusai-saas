<script lang="ts" setup>
defineOptions({ name: 'SkillBindingPanel' });
/**
 * 技能包绑定可视化面板
 *
 * 替代简单的 ApiSelect 多选下拉，提供：
 * - 左侧：可用技能包列表（搜索 + scope 标签 + 技能数量）
 * - 右侧：已绑定列表（排序 + 启用/禁用 + consent mode）
 * - 展开预览包内技能列表
 *
 * Props:
 *   modelValue: number[] — 已选中的 package_id 列表
 *   availableApi: () => Promise<PackageOption[]> — 获取可用技能包列表的 API
 *   consentModes: Record<string, string> — 每个 package_id 的 consent_mode
 *
 * Emits:
 *   update:modelValue — package_id 列表变化
 *   update:consentModes — consent_mode 变化
 */
import { computed, onMounted, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Checkbox,
  Empty,
  Input,
  Select as ASelect,
  Space,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { getScopeColor } from '#/utils/ai-helpers';

export interface PackageOption {
  value: number;
  label: string;
  scope: string;
  description: string | null;
  is_system: boolean;
  skill_count?: number;
}

const props = withDefaults(defineProps<{
  modelValue: number[];
  availableApi: () => Promise<PackageOption[]>;
  consentModes?: Record<string, string>;
}>(), {
  consentModes: () => ({}),
});

const emits = defineEmits<{
  'update:modelValue': [value: number[]];
  'update:consentModes': [value: Record<string, string>];
}>();

// ==================== State ====================
const loading = ref(false);
const allPackages = ref<PackageOption[]>([]);
const searchQuery = ref('');

// ==================== Computed ====================
const selectedSet = computed(() => new Set(props.modelValue));

const filteredAvailable = computed(() => {
  const q = searchQuery.value.toLowerCase().trim();
  return allPackages.value.filter((pkg) => {
    if (q && !pkg.label.toLowerCase().includes(q)) return false;
    return true;
  });
});

const selectedPackages = computed(() => {
  return props.modelValue
    .map((id) => allPackages.value.find((p) => p.value === id))
    .filter(Boolean) as PackageOption[];
});

const consentModeOptions = computed(() => [
  { label: $t('tenant.ai.agent.consentModeOptions.auto'), value: 'auto' },
  { label: $t('tenant.ai.agent.consentModeOptions.ask'), value: 'ask' },
  { label: $t('tenant.ai.agent.consentModeOptions.reject'), value: 'reject' },
]);

// ==================== Load ====================
async function loadPackages() {
  loading.value = true;
  try {
    allPackages.value = await props.availableApi();
  } catch {
    allPackages.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(loadPackages);

// ==================== Actions ====================
function togglePackage(pkgId: number) {
  const current = [...props.modelValue];
  const idx = current.indexOf(pkgId);
  if (idx >= 0) {
    current.splice(idx, 1);
  } else {
    current.push(pkgId);
  }
  emits('update:modelValue', current);
}

function removePackage(pkgId: number) {
  emits('update:modelValue', props.modelValue.filter((id) => id !== pkgId));
}

function setConsentMode(pkgId: number, mode: string) {
  const updated = { ...props.consentModes };
  if (mode === 'auto') {
    delete updated[String(pkgId)];
  } else {
    updated[String(pkgId)] = mode;
  }
  emits('update:consentModes', updated);
}

function getConsentMode(pkgId: number): string {
  return props.consentModes[String(pkgId)] || 'auto';
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- Available Packages -->
    <Card size="small" :title="$t('tenant.ai.agent.availablePackages')">
      <template #extra>
        <Input
          v-model:value="searchQuery"
          :placeholder="$t('shared.common.search')"
          size="small"
          allow-clear
          class="w-[200px]"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:search" class="text-muted-foreground" />
          </template>
        </Input>
      </template>

      <Spin :spinning="loading">
        <div v-if="filteredAvailable.length === 0" class="py-4">
          <Empty :description="$t('shared.common.noData')" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
        </div>
        <div v-else class="flex flex-wrap gap-2">
          <div
            v-for="pkg in filteredAvailable"
            :key="pkg.value"
            class="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 transition-colors"
            :class="[
              selectedSet.has(pkg.value)
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/40',
            ]"
            @click="togglePackage(pkg.value)"
          >
            <Checkbox :checked="selectedSet.has(pkg.value)" class="pointer-events-none" />
            <div class="flex flex-col">
              <div class="flex items-center gap-1">
                <span class="text-sm font-medium">{{ pkg.label }}</span>
                <Tag :color="getScopeColor(pkg.scope)" class="!text-[10px]">
                  {{ pkg.scope }}
                </Tag>
              </div>
              <span v-if="pkg.description" class="max-w-[200px] truncate text-[11px] text-muted-foreground">
                {{ pkg.description }}
              </span>
            </div>
          </div>
        </div>
      </Spin>
    </Card>

    <!-- Selected Packages with Consent Mode -->
    <Card
      v-if="selectedPackages.length > 0"
      size="small"
      :title="`${$t('tenant.ai.agent.skillPackageBindings')} (${selectedPackages.length})`"
    >
      <div class="flex flex-col gap-2">
        <div
          v-for="pkg in selectedPackages"
          :key="pkg.value"
          class="flex items-center justify-between rounded-md border border-border px-3 py-2"
        >
          <div class="flex items-center gap-2">
            <IconifyIcon icon="lucide:package" class="text-muted-foreground" />
            <span class="text-sm font-medium">{{ pkg.label }}</span>
            <Tag :color="getScopeColor(pkg.scope)" class="!text-[10px]">
              {{ pkg.scope }}
            </Tag>
          </div>
          <Space>
            <ASelect
              :value="getConsentMode(pkg.value)"
              :options="consentModeOptions"
              size="small"
              class="w-[120px]"
              @change="(v: unknown) => setConsentMode(pkg.value, v as string)"
            />
            <Tooltip :title="$t('shared.common.delete')">
              <Button
                size="small"
                type="text"
                danger
                @click="removePackage(pkg.value)"
              >
                <IconifyIcon icon="lucide:x" />
              </Button>
            </Tooltip>
          </Space>
        </div>
      </div>
    </Card>
  </div>
</template>
