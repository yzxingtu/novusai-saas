<script lang="ts" setup>
/**
 * 技能管理页面（平台端）— Master-Detail 布局
 *
 * 左侧：技能包紧凑列表（搜索 + 选中高亮 + CRUD）
 * 右侧：选中包的技能 CRUD（Ant Table + 抽屉表单）
 */
import type { UploadRequestOption } from 'ant-design-vue/es/vc-upload/interface';

import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';
import type { AdminSkillInfo } from '#/api/admin/skills';

import { computed, onMounted, ref, watch } from 'vue';

import { useRoute } from 'vue-router';

import { RecycleBinDrawer } from '#/adapter/vxe-table/components';
import { useRouter } from 'vue-router';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import {
  Badge,
  Button,
  Dropdown,
  Empty,
  Input,
  Menu,
  MenuItem,
  message,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Upload,
} from 'ant-design-vue';

import {
  cloneSkillPackageApi,
  deleteSkillPackageApi,
  exportSkillPackageApi,
  getSkillPackageListApi,
  getSkillPackageSkillsApi,
  getSkillPackageValvesApi,
  importSkillPackageApi,
  toggleSkillPackageStatusApi,
  updateSkillPackageValvesApi,
  uploadSkillPackageApi,
} from '#/api/admin/skill-packages';
import {
  deleteSkillApi,
  testSkillApi,
  toggleSkillStatusApi,
} from '#/api/admin/skills';
import ValvesConfigPanel from '#/components/business/valves-config-panel/ValvesConfigPanel.vue';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import { createFormOperations } from '#/composables/use-ai-operations';
import { usePageAIRegistration } from '#/composables/use-page-ai-registration';

import { getSkillTypeColor, getSkillTypeText } from '../skills/data';
import SkillForm from '../skills/modules/form.vue';
import { getAudienceColor, usePackageFormSchema } from './data';
import PackageForm from './modules/form.vue';

defineOptions({ name: 'AdminSkillPackageList' });

// ==================== 技能包列表（左侧） ====================
const packages = ref<AdminSkillPackageInfo[]>([]);
const packagesLoading = ref(false);
const searchKeyword = ref('');
const selectedPackageId = ref<null | number>(null);

const filteredPackages = computed(() => {
  const kw = searchKeyword.value.toLowerCase().trim();
  if (!kw) return packages.value;
  return packages.value.filter(
    (p) =>
      p.name.toLowerCase().includes(kw) ||
      (p.description && p.description.toLowerCase().includes(kw)),
  );
});

const selectedPackage = computed(
  () => packages.value.find((p) => p.id === selectedPackageId.value) ?? null,
);

async function loadPackages() {
  packagesLoading.value = true;
  try {
    const res = await getSkillPackageListApi({
      'page[size]': 200,
      sort: 'sort_order,-created_at',
    });
    packages.value = res.items;
    if (
      selectedPackageId.value === null ||
      !res.items.some((p) => p.id === selectedPackageId.value)
    ) {
      selectedPackageId.value = res.items.length > 0 ? res.items[0]!.id : null;
    }
  } catch {
    packages.value = [];
  } finally {
    packagesLoading.value = false;
  }
}

const router = useRouter();
const route = useRoute();

/** 从表策略跳转时的 table_policy_id 筛选 */
const tablePolicyIdFilter = computed(() => {
  const q = route.query.table_policy_id;
  if (!q) return null;
  const n = Number(q);
  return Number.isFinite(n) ? n : null;
});

/** 按 table_policy_id 筛选后的技能列表（null/空表策略 = 使用全部，应包含） */
const displayedSkills = computed(() => {
  const policyId = tablePolicyIdFilter.value;
  if (policyId == null) return skills.value;
  return skills.value.filter((s) => {
    const ids = s.config?.table_policy_ids as number[] | null | undefined;
    if (ids == null || (Array.isArray(ids) && ids.length === 0)) return true;
    return Array.isArray(ids) && ids.includes(policyId);
  });
});

function clearTablePolicyFilter() {
  const { table_policy_id: _, ...rest } = route.query;
  router.replace({ path: route.path, query: rest });
}

function onSelectPackage(pkg: AdminSkillPackageInfo) {
  selectedPackageId.value = pkg.id;
}

function goToDetail(pkg: AdminSkillPackageInfo) {
  router.push(`/admin/ai/skill-packages/${pkg.id}`);
}

// ==================== 导出 / 导入 ====================

async function onExportPackage(pkg: AdminSkillPackageInfo) {
  try {
    const data = await exportSkillPackageApi(pkg.id);
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `skill-package-${pkg.name.replaceAll(/\s+/g, '_')}.json`;
    a.click();
    URL.revokeObjectURL(url);
    message.success($t('admin.ai.skillPackage.messages.exportSuccess'));
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  }
}

const importModalVisible = ref(false);
const importing = ref(false);
const importConflictMode = ref<'rename' | 'skip'>('rename');

function onImportClick() {
  importConflictMode.value = 'rename';
  importModalVisible.value = true;
}

async function handleImportFile(file: File) {
  importing.value = true;
  try {
    const text = await file.text();
    const exportData = JSON.parse(text);
    const result = await importSkillPackageApi({
      export_data: exportData,
      conflict_mode: importConflictMode.value,
    });
    if (result.status === 'skipped') {
      message.info($t('admin.ai.skillPackage.messages.importSkipped'));
    } else {
      message.success(
        $t('admin.ai.skillPackage.messages.importSuccess', {
          name: result.package_name,
          count: result.skills_created,
        }),
      );
    }
    importModalVisible.value = false;
    await loadPackages();
  } catch {
    message.error($t('admin.ai.skillPackage.messages.importFailed'));
  } finally {
    importing.value = false;
  }
  return false;
}

// ==================== 技能包 ZIP 上传 ====================
const uploadModalVisible = ref(false);
const uploading = ref(false);

function onUploadClick() {
  uploadModalVisible.value = true;
}

async function handleCustomUpload(options: UploadRequestOption) {
  const file = options.file as File;
  uploading.value = true;
  try {
    await uploadSkillPackageApi(file);
    message.success($t('admin.ai.skillPackage.messages.uploadSuccess'));
    uploadModalVisible.value = false;
    await loadPackages();
    options.onSuccess?.({}, new XMLHttpRequest());
  } catch {
    options.onError?.(new Error('upload failed'));
  } finally {
    uploading.value = false;
  }
}

// ==================== 技能包 CRUD 抽屉 ====================
const [PackageFormDrawer, packageFormApi] = useVbenDrawer({
  connectedComponent: PackageForm,
  destroyOnClose: true,
});

const PKG_PAGE_KEY = 'admin.ai.skill-packages';

function onCreatePackage() {
  packageFormApi
    .setData({
      mode: 'add',
      _resource: '/admin/ai/skill-packages',
      _defaults: { is_active: true, sort_order: 0 },
      _aiPageKey: PKG_PAGE_KEY,
    })
    .open();
}

function onEditPackage(pkg: AdminSkillPackageInfo) {
  packageFormApi
    .setData({
      ...pkg,
      mode: 'edit',
      _resource: '/admin/ai/skill-packages',
      _aiPageKey: PKG_PAGE_KEY,
    })
    .open();
}

async function onDeletePackage(pkg: AdminSkillPackageInfo) {
  Modal.confirm({
    title: $t('admin.common.confirmDelete'),
    onOk: async () => {
      try {
        await deleteSkillPackageApi(pkg.id);
        message.success($t('common.deleteSuccess'));
        await loadPackages();
        recycleBinRef.value?.refreshCount();
      } catch {
        // handled by interceptor / 错误由请求拦截器处理
      }
    },
  });
}

async function onTogglePackageStatus(pkg: AdminSkillPackageInfo) {
  const confirmKey = pkg.is_active
    ? 'admin.ai.skillPackage.messages.confirmDisable'
    : 'admin.ai.skillPackage.messages.confirmEnable';
  Modal.confirm({
    title: $t(confirmKey),
    onOk: async () => {
      try {
        await toggleSkillPackageStatusApi(pkg.id);
        message.success($t('admin.ai.skillPackage.messages.toggleSuccess'));
        await loadPackages();
      } catch {
        // handled by interceptor / 错误由请求拦截器处理
      }
    },
  });
}

function handlePkgMenuClick(key: number | string, pkg: AdminSkillPackageInfo) {
  switch (String(key)) {
    case 'clone': {
      onClonePackage(pkg);
      break;
    }
    case 'delete': {
      onDeletePackage(pkg);
      break;
    }
    case 'detail': {
      goToDetail(pkg);
      break;
    }
    case 'edit': {
      onEditPackage(pkg);
      break;
    }
    case 'export': {
      onExportPackage(pkg);
      break;
    }
  }
}

async function onClonePackage(pkg: AdminSkillPackageInfo) {
  try {
    const result = await cloneSkillPackageApi(pkg.id);
    message.success(
      $t('admin.ai.skillPackage.messages.cloneSuccess', {
        name: result.package_name,
      }),
    );
    await loadPackages();
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  }
}

function onPackageFormSuccess() {
  loadPackages();
}

// ==================== Valves 配置 ====================
const valvesConfigPanelRef = ref<InstanceType<typeof ValvesConfigPanel> | null>(
  null,
);

function onOpenValvesConfig() {
  valvesConfigPanelRef.value?.open();
}

// ==================== 技能列表（右侧） ====================
const skills = ref<AdminSkillInfo[]>([]);
const skillsLoading = ref(false);

async function loadSkills() {
  if (!selectedPackageId.value) {
    skills.value = [];
    return;
  }
  skillsLoading.value = true;
  try {
    const res = await getSkillPackageSkillsApi(selectedPackageId.value, {
      'page[size]': 100,
      sort: 'sort_order,-created_at',
    });
    skills.value = res.items;
  } catch {
    skills.value = [];
  } finally {
    skillsLoading.value = false;
  }
}

watch(selectedPackageId, () => {
  loadSkills();
});

// ==================== 技能 CRUD 抽屉 ====================
const [SkillFormDrawer, skillFormApi] = useVbenDrawer({
  connectedComponent: SkillForm,
  destroyOnClose: true,
});

function onCreateSkill() {
  skillFormApi
    .setData({
      mode: 'add',
      _resource: '/admin/ai/skills',
      _aiPageKey: PKG_PAGE_KEY,
      _defaults: {
        package_id: selectedPackageId.value,
        type: 'toolkit',
        timeout: 30,
        is_active: true,
        toolkit_content: '',
        valves_config: {},
        kb_ids: [],
        rag_enabled: true,
        rag_top_k: 5,
        rag_score_threshold: 0.5,
        rag_search_mode: 'hybrid',
        rag_rewrite_strategy: 'none',
        rag_reranker_enabled: false,
        rag_context_token_ratio: 0.3,
        di_table_policy_ids: [],
        di_max_rows_override: 0,
      },
    })
    .open();
}

function onEditSkill(row: AdminSkillInfo) {
  skillFormApi
    .setData({
      ...row,
      mode: 'edit',
      _resource: '/admin/ai/skills',
      _aiPageKey: PKG_PAGE_KEY,
    })
    .open();
}

function onSkillFormSuccess() {
  loadSkills();
  loadPackages();
}

// ==================== 技能操作 ====================
async function onToggleSkillStatus(row: AdminSkillInfo) {
  try {
    await toggleSkillStatusApi(row.id);
    message.success($t('admin.ai.skill.messages.toggleSuccess'));
    await loadSkills();
    await loadPackages();
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  }
}

async function onDeleteSkill(row: AdminSkillInfo) {
  Modal.confirm({
    title: $t('admin.common.confirmDelete'),
    onOk: async () => {
      try {
        await deleteSkillApi(row.id);
        message.success($t('common.deleteSuccess'));
        await loadSkills();
        await loadPackages();
      } catch {
        // handled by interceptor / 错误由请求拦截器处理
      }
    },
  });
}

async function onTestSkill(row: AdminSkillInfo) {
  try {
    const res = await testSkillApi(row.id);
    const detailStr = res.details
      ? `\n\n${JSON.stringify(res.details, null, 2)}`
      : '';
    Modal[res.success ? 'success' : 'error']({
      title: `${row.name} — ${res.success ? $t('admin.ai.skill.messages.testSuccess') : $t('admin.ai.skill.messages.testFailed')}`,
      content: res.message + detailStr,
      width: 520,
    });
  } catch {
    Modal.error({
      title: row.name,
      content: $t('admin.ai.skill.messages.testFailed'),
    });
  }
}

// ==================== 回收站 (using RecycleBinDrawer) ====================
const recycleBinRef = ref<InstanceType<typeof RecycleBinDrawer> | null>(null);
const recycleBinCount = computed(() => recycleBinRef.value?.deletedCount ?? 0);

function openRecycleBin() {
  recycleBinRef.value?.open();
}

// ==================== 技能列定义 ====================
const skillColumns = computed(() => [
  {
    title: $t('admin.ai.skill.name'),
    dataIndex: 'name',
    key: 'name',
    width: 240,
  },
  {
    title: $t('admin.ai.skill.type'),
    dataIndex: 'type',
    key: 'type',
    width: 120,
    align: 'center' as const,
  },
  {
    title: $t('admin.ai.skill.isActive'),
    dataIndex: 'is_active',
    key: 'is_active',
    width: 100,
    align: 'center' as const,
  },
  {
    title: $t('admin.ai.skill.timeout'),
    dataIndex: 'timeout',
    key: 'timeout',
    width: 100,
    align: 'center' as const,
  },
  {
    title: $t('admin.common.createdAt'),
    dataIndex: 'created_at',
    key: 'created_at',
    width: 140,
  },
  {
    title: $t('admin.common.operation'),
    key: 'action',
    width: 200,
    align: 'center' as const,
  },
]);

// ==================== 初始化 ====================
onMounted(() => {
  loadPackages();
});

const packageFormOps = createFormOperations({
  pageKey: PKG_PAGE_KEY,
  formSchema: usePackageFormSchema,
  resource: '/admin/ai/skill-packages',
});

usePageAIRegistration({
  pageKey: PKG_PAGE_KEY,
  title: () => $t('admin.ai.skillPackage.name'),
  resource: '/admin/ai/skill-packages',
  entityName: () => $t('admin.ai.skillPackage.name'),
  entityDescription: () => $t('admin.ai.skillPackage.pageDesc'),
  data: () => ({
    selected_package: selectedPackage.value?.name ?? null,
    total_packages: packages.value.length,
  }),
  operations: [
    {
      name: 'refresh_list',
      label: $t('shared.pageOperation.refreshList'),
      description: 'Reload the skill package list / 重新加载技能包列表',
      readonly: true,
      handler: async () => {
        await loadPackages();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.listRefreshed'),
        };
      },
    },
    {
      name: 'create_record',
      label: $t('shared.pageOperation.createRecord'),
      description:
        'Open the skill package creation form / 打开技能包创建表单',
      readonly: false,
      handler: async () => {
        onCreatePackage();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.createFormOpenedEmpty'),
        };
      },
    },
    {
      name: 'search',
      label: $t('shared.pageOperation.searchByKeyword'),
      description:
        'Search skill packages by keyword / 按关键词搜索技能包',
      readonly: true,
      params: {
        keyword: { type: 'string', description: 'Search keyword / 搜索关键词' },
      },
      handler: async (params) => {
        searchKeyword.value = (params?.keyword as string) || '';
        return {
          success: true,
          message: searchKeyword.value
            ? $t('shared.pageOperation.msg.searchApplied', {
                fields: 'keyword',
              })
            : $t('shared.pageOperation.msg.searchCleared'),
        };
      },
    },
    ...packageFormOps,
  ],
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.ai.skillPackage.pageDesc')"
  >
    <!-- 技能包表单抽屉 -->
    <PackageFormDrawer @success="onPackageFormSuccess" />
    <!-- 技能表单抽屉 -->
    <SkillFormDrawer @success="onSkillFormSuccess" />

    <!-- ZIP 上传弹窗 -->
    <Modal
      v-model:open="uploadModalVisible"
      :title="$t('admin.ai.skillPackage.uploadZip')"
      :footer="null"
      :destroy-on-close="true"
      width="520px"
    >
      <div class="py-2">
        <Upload.Dragger
          :custom-request="handleCustomUpload"
          accept=".zip"
          :multiple="false"
          :show-upload-list="false"
          :disabled="uploading"
        >
          <div class="flex flex-col items-center gap-4 py-8">
            <div
              class="flex size-14 items-center justify-center rounded-2xl"
              :style="{
                background:
                  'linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 75%) 100%)',
              }"
            >
              <IconifyIcon
                :icon="uploading ? 'lucide:loader-2' : 'lucide:cloud-upload'"
                class="size-8 text-white"
                :class="{ 'animate-spin': uploading }"
              />
            </div>
            <div class="flex flex-col items-center gap-1">
              <span class="text-sm font-semibold text-foreground">
                {{
                  uploading
                    ? $t('admin.ai.skillPackage.messages.uploading')
                    : $t('admin.ai.skillPackage.uploadDragText')
                }}
              </span>
              <span class="text-xs text-muted-foreground">
                {{ $t('admin.ai.skillPackage.uploadDesc') }}
              </span>
            </div>
          </div>
        </Upload.Dragger>
      </div>
    </Modal>

    <!-- JSON 导入弹窗 -->
    <Modal
      v-model:open="importModalVisible"
      :title="$t('admin.ai.skillPackage.importBtn')"
      :footer="null"
      :destroy-on-close="true"
      width="520px"
    >
      <div class="flex flex-col gap-3 py-2">
        <div class="flex gap-4">
          <div class="flex flex-1 flex-col gap-1">
            <span class="text-xs font-medium text-muted-foreground">
              {{ $t('admin.ai.skillPackage.importConflictMode') }}
            </span>
            <Select
              v-model:value="importConflictMode"
              size="small"
              :options="[
                {
                  label: $t('admin.ai.skillPackage.importConflictRename'),
                  value: 'rename',
                },
                {
                  label: $t('admin.ai.skillPackage.importConflictSkip'),
                  value: 'skip',
                },
              ]"
            />
          </div>
          <!-- scope 选择器已移除 / scope selector removed -->
        </div>
        <Upload.Dragger
          :before-upload="handleImportFile"
          accept=".json"
          :multiple="false"
          :show-upload-list="false"
          :disabled="importing"
        >
          <div class="flex flex-col items-center gap-4 py-8">
            <div
              class="flex size-14 items-center justify-center rounded-2xl"
              :style="{
                background:
                  'linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 75%) 100%)',
              }"
            >
              <IconifyIcon
                :icon="importing ? 'lucide:loader-2' : 'lucide:file-input'"
                class="size-8 text-white"
                :class="{ 'animate-spin': importing }"
              />
            </div>
            <div class="flex flex-col items-center gap-1">
              <span class="text-sm font-semibold text-foreground">
                {{
                  importing
                    ? $t('admin.ai.skillPackage.messages.uploading')
                    : $t('admin.ai.skillPackage.importDragText')
                }}
              </span>
              <span class="text-xs text-muted-foreground">
                {{ $t('admin.ai.skillPackage.importDesc') }}
              </span>
            </div>
          </div>
        </Upload.Dragger>
      </div>
    </Modal>

    <!-- ========== 左右面板容器 ========== -->
    <div class="flex h-full gap-4 overflow-hidden">

    <!-- ========== 左侧：技能包列表 ========== -->
    <div class="flex h-full w-[280px] shrink-0 flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm">
      <div class="flex shrink-0 items-center justify-between border-b border-border/50 px-3 py-2">
        <span class="text-sm font-medium">{{ $t('admin.ai.skillPackage.title') }}</span>
        <Space :size="4">
          <Tooltip :title="$t('common.recycleBin.title')">
            <Badge :count="recycleBinCount" :offset="[-2, 2]" size="small">
              <Button
                v-access:code="['ai_skill_package:recycle_bin']"
                type="text"
                size="small"
                @click="openRecycleBin"
              >
                <IconifyIcon
                  icon="lucide:trash-2"
                  class="size-4 text-muted-foreground"
                />
              </Button>
            </Badge>
          </Tooltip>
          <Tooltip :title="$t('admin.ai.skillPackage.importBtn')">
            <Button
              v-access:code="['ai_skill_package:create']"
              type="text"
              size="small"
              @click="onImportClick"
            >
              <IconifyIcon
                icon="lucide:file-input"
                class="size-4 text-primary"
              />
            </Button>
          </Tooltip>
          <Tooltip :title="$t('admin.ai.skillPackage.uploadZip')">
            <Button
              v-access:code="['ai_skill_package:create']"
              type="text"
              size="small"
              @click="onUploadClick"
            >
              <IconifyIcon icon="lucide:upload" class="size-4 text-primary" />
            </Button>
          </Tooltip>
          <Tooltip :title="$t('admin.ai.skillPackage.create')">
            <Button
              v-access:code="['ai_skill_package:create']"
              type="text"
              size="small"
              @click="onCreatePackage"
            >
              <Plus class="size-4 text-primary" />
            </Button>
          </Tooltip>
        </Space>
      </div>
      <div class="flex min-h-0 flex-1 flex-col overflow-hidden p-3">
      <!-- 搜索框 -->
      <Input
        v-model:value="searchKeyword"
        :placeholder="$t('admin.ai.skillPackage.placeholder.searchName')"
        allow-clear
        size="small"
        class="mb-3"
      >
        <template #prefix>
          <IconifyIcon
            icon="lucide:search"
            class="size-3.5 text-muted-foreground"
          />
        </template>
      </Input>

      <!-- 包列表 -->
      <div class="min-h-0 flex-1 overflow-y-auto">
      <Spin :spinning="packagesLoading">
        <div
          v-if="filteredPackages.length === 0"
          class="flex h-full items-center justify-center"
        >
          <Empty
            :description="$t('admin.ai.skillPackage.detail.empty')"
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
          />
        </div>
        <div v-else class="flex flex-col gap-1">
          <div
            v-for="pkg in filteredPackages"
            :key="pkg.id"
            class="group cursor-pointer rounded-lg border p-2.5 transition-all duration-150"
            :class="
              pkg.id === selectedPackageId
                ? 'border-primary/30 bg-primary/5'
                : 'border-transparent hover:bg-muted/50'
            "
            @click="onSelectPackage(pkg)"
          >
            <div class="flex items-start gap-2">
              <div
                class="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md"
                :class="pkg.is_active ? 'bg-primary/10' : 'bg-muted'"
              >
                <IconifyIcon
                  :icon="pkg.avatar || 'lucide:package'"
                  class="size-3.5"
                  :class="
                    pkg.is_active ? 'text-primary' : 'text-muted-foreground'
                  "
                />
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-1">
                  <span class="truncate text-sm font-medium text-foreground">
                    {{ pkg.name }}
                  </span>
                  <Tag
                    v-if="pkg.is_system"
                    color="purple"
                    class="shrink-0"
                    style="
                      padding: 0 3px;
                      margin: 0;
                      font-size: 10px;
                      line-height: 14px;
                    "
                  >
                    {{ $t('admin.ai.skillPackage.system') }}
                  </Tag>
                  <Tooltip v-if="pkg.source_plugin" :title="pkg.source_plugin">
                    <Tag
                      color="cyan"
                      class="shrink-0"
                      style="
                        padding: 0 3px;
                        margin: 0;
                        font-size: 10px;
                        line-height: 14px;
                      "
                    >
                      <IconifyIcon
                        icon="lucide:plug"
                        class="mr-0.5 inline size-2.5"
                      />
                      {{ $t('admin.ai.skillPackage.sourcePlugin') }}
                    </Tag>
                  </Tooltip>
                </div>
                <div class="mt-0.5 flex items-center gap-1.5">
                  <Tag
                    :color="getAudienceColor(pkg.target_audience)"
                    style="
                      padding: 0 3px;
                      margin: 0;
                      font-size: 10px;
                      line-height: 14px;
                    "
                  >
                    {{ pkg.target_audience }}
                  </Tag>
                  <span class="whitespace-nowrap text-xs text-muted-foreground">
                    {{ pkg.skill_count }}
                    {{ $t('admin.ai.skillPackage.detail.skills') }}
                  </span>
                </div>
              </div>
              <!-- hover 操作：单个下拉菜单按钮 -->
              <Dropdown
                :trigger="['click']"
                placement="bottomRight"
                @click.stop
              >
                <Button
                  type="text"
                  size="small"
                  class="!size-6 !min-w-0 shrink-0 !p-0 opacity-0 transition-opacity group-hover:opacity-100"
                  @click.stop
                >
                  <IconifyIcon
                    icon="lucide:ellipsis-vertical"
                    class="size-3.5 text-muted-foreground"
                  />
                </Button>
                <template #overlay>
                  <Menu
                    @click="
                      (info: { key: string | number }) =>
                        handlePkgMenuClick(info.key, pkg)
                    "
                  >
                    <MenuItem key="detail">
                      <div class="flex items-center gap-2">
                        <IconifyIcon
                          icon="lucide:external-link"
                          class="size-3.5"
                        />
                        <span>{{ $t('shared.common.viewDetail') }}</span>
                      </div>
                    </MenuItem>
                    <MenuItem key="export">
                      <div class="flex items-center gap-2">
                        <IconifyIcon icon="lucide:download" class="size-3.5" />
                        <span>{{ $t('admin.ai.skillPackage.exportBtn') }}</span>
                      </div>
                    </MenuItem>
                    <MenuItem key="clone">
                      <div class="flex items-center gap-2">
                        <IconifyIcon icon="lucide:copy" class="size-3.5" />
                        <span>{{ $t('admin.ai.skillPackage.cloneBtn') }}</span>
                      </div>
                    </MenuItem>
                    <MenuItem v-if="!pkg.is_system" key="edit">
                      <div class="flex items-center gap-2">
                        <IconifyIcon icon="lucide:pencil" class="size-3.5" />
                        <span>{{ $t('admin.common.edit') }}</span>
                      </div>
                    </MenuItem>
                    <MenuItem
                      v-if="!pkg.is_system"
                      key="delete"
                      class="!text-destructive"
                    >
                      <div class="flex items-center gap-2">
                        <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
                        <span>{{ $t('admin.common.delete') }}</span>
                      </div>
                    </MenuItem>
                  </Menu>
                </template>
              </Dropdown>
            </div>
            <p
              v-if="pkg.description"
              class="mt-1 line-clamp-2 pl-9 text-xs text-muted-foreground"
            >
              {{ pkg.description }}
            </p>
          </div>
        </div>
      </Spin>
      </div>
      </div>
    </div>

    <!-- ========== 右侧：技能列表 ========== -->
    <div class="flex h-full min-w-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card p-4 shadow-sm">
      <!-- 选中包的信息头 -->
      <div
        v-if="selectedPackage"
        class="mb-4 flex items-center justify-between"
      >
        <div class="flex items-center gap-3">
          <div
            class="flex size-9 items-center justify-center rounded-lg bg-primary/10"
          >
            <IconifyIcon
              :icon="selectedPackage.avatar || 'lucide:package'"
              class="size-4.5 text-primary"
            />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="text-base font-semibold text-foreground">
                {{ selectedPackage.name }}
              </span>
              <Tag
                v-if="selectedPackage.is_system"
                color="purple"
                style="
                  padding: 0 4px;
                  margin: 0;
                  font-size: 10px;
                  line-height: 16px;
                "
              >
                {{ $t('admin.ai.skillPackage.system') }}
              </Tag>
              <Tag
                :color="selectedPackage.is_active ? 'success' : 'default'"
                :class="{ 'cursor-pointer': !selectedPackage.is_system }"
                style="
                  padding: 0 4px;
                  margin: 0;
                  font-size: 10px;
                  line-height: 16px;
                "
                @click="
                  !selectedPackage.is_system &&
                  onTogglePackageStatus(selectedPackage)
                "
              >
                {{
                  selectedPackage.is_active
                    ? $t('admin.common.enabled')
                    : $t('admin.common.disabled')
                }}
              </Tag>
            </div>
            <span
              v-if="selectedPackage.description"
              class="text-xs text-muted-foreground"
            >
              {{ selectedPackage.description }}
            </span>
          </div>
        </div>
        <Space>
          <Button
            v-if="selectedPackage.valves_schema"
            size="small"
            @click="onOpenValvesConfig"
          >
            <IconifyIcon icon="lucide:settings" class="mr-1 size-3.5" />
            {{ $t('admin.ai.skillPackage.valves.configBtn') }}
          </Button>
          <Button
            v-access:code="['ai_skill:create']"
            type="primary"
            size="small"
            @click="onCreateSkill"
          >
            <Plus class="mr-1 size-3.5" />
            {{ $t('admin.ai.skill.create') }}
          </Button>
        </Space>
      </div>

      <!-- 表策略筛选横幅 -->
      <div
        v-if="selectedPackage && tablePolicyIdFilter"
        class="mb-3 flex items-center justify-between rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm"
      >
        <span class="text-primary">
          {{ $t('admin.ai.skillPackage.tablePolicyFilterHint', { id: tablePolicyIdFilter }) }}
          ({{ displayedSkills.length }}/{{ skills.length }})
        </span>
        <Button type="link" size="small" class="!h-auto !p-0" @click="clearTablePolicyFilter">
          {{ $t('admin.ai.skillPackage.clearTablePolicyFilter') }}
        </Button>
      </div>

      <!-- 技能表格 -->
      <div v-if="selectedPackage" class="min-h-0 flex-1 overflow-auto">
        <Table
          :columns="skillColumns"
          :data-source="displayedSkills"
          :loading="skillsLoading"
          :pagination="false"
          row-key="id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <!-- 名称 -->
            <template v-if="column.key === 'name'">
              <div class="flex items-center gap-2">
                <IconifyIcon
                  :icon="record.avatar || 'lucide:sparkles'"
                  class="size-4 text-muted-foreground"
                />
                <div class="flex flex-col">
                  <span class="font-medium">
                    {{ record.name }}
                    <Tag
                      v-if="record.is_system"
                      color="purple"
                      class="ml-1"
                      style="padding: 0 4px; font-size: 10px; line-height: 16px"
                    >
                      {{ $t('admin.ai.skill.system') }}
                    </Tag>
                  </span>
                  <span
                    v-if="record.description"
                    class="line-clamp-1 text-xs text-muted-foreground"
                  >
                    {{ record.description }}
                  </span>
                </div>
              </div>
            </template>

            <!-- 类型 -->
            <template v-else-if="column.key === 'type'">
              <Tag :color="getSkillTypeColor(record.type)">
                {{ getSkillTypeText(record.type) }}
              </Tag>
              <Badge
                v-if="
                  record.type === 'toolkit' &&
                  record.toolkit_meta?.tools?.length
                "
                :count="record.toolkit_meta.tools.length"
                :number-style="{
                  backgroundColor: 'hsl(var(--primary))',
                  fontSize: '10px',
                  minWidth: '16px',
                  height: '16px',
                  lineHeight: '16px',
                }"
                :title="`${record.toolkit_meta.tools.length} tools`"
                class="ml-1"
              />
              <Badge
                v-if="
                  record.type === 'builtin' &&
                  Array.isArray(
                    (record.config as Record<string, unknown>)?.tools,
                  )
                "
                :count="
                  (
                    (record.config as Record<string, unknown>)
                      .tools as unknown[]
                  ).length
                "
                :number-style="{
                  backgroundColor: '#722ed1',
                  fontSize: '10px',
                  minWidth: '16px',
                  height: '16px',
                  lineHeight: '16px',
                }"
                :title="`${((record.config as Record<string, unknown>).tools as unknown[]).length} tools`"
                class="ml-1"
              />
            </template>

            <!-- 状态 -->
            <template v-else-if="column.key === 'is_active'">
              <Tag
                :color="record.is_active ? 'success' : 'default'"
                :class="{ 'cursor-pointer': !record.is_system }"
                @click="
                  !record.is_system &&
                  onToggleSkillStatus(record as AdminSkillInfo)
                "
              >
                {{
                  record.is_active
                    ? $t('admin.common.enabled')
                    : $t('admin.common.disabled')
                }}
              </Tag>
            </template>

            <!-- 超时 -->
            <template v-else-if="column.key === 'timeout'">
              <span class="font-mono text-sm text-muted-foreground">
                {{ record.timeout }}s
              </span>
            </template>

            <!-- 创建时间 -->
            <template v-else-if="column.key === 'created_at'">
              <Tooltip :title="formatDate(record.created_at)">
                <span class="text-muted-foreground">
                  {{ formatRelativeTime(record.created_at) }}
                </span>
              </Tooltip>
            </template>

            <!-- 操作 -->
            <template v-else-if="column.key === 'action'">
              <Space>
                <Tooltip :title="$t('admin.ai.skill.testBtn')">
                  <Button
                    type="link"
                    size="small"
                    @click="onTestSkill(record as AdminSkillInfo)"
                  >
                    <IconifyIcon icon="lucide:play" class="size-3.5" />
                  </Button>
                </Tooltip>
                <Button
                  v-access:code="['ai_skill:update']"
                  type="link"
                  size="small"
                  @click="onEditSkill(record as AdminSkillInfo)"
                >
                  {{ $t('admin.common.edit') }}
                </Button>
                <Button
                  v-if="!record.is_system"
                  v-access:code="['ai_skill:delete']"
                  type="link"
                  size="small"
                  danger
                  @click="onDeleteSkill(record as AdminSkillInfo)"
                >
                  {{ $t('admin.common.delete') }}
                </Button>
              </Space>
            </template>
          </template>

          <template #emptyText>
            <Empty :description="$t('admin.ai.skillPackage.detail.empty')" />
          </template>
        </Table>
      </div>

      <!-- 未选中任何包 -->
      <div v-else class="flex h-full items-center justify-center">
        <Empty :description="$t('admin.ai.skillPackage.detail.empty')">
          <Button
            v-access:code="['ai_skill_package:create']"
            type="primary"
            @click="onCreatePackage"
          >
            <Plus class="mr-1 size-4" />
            {{ $t('admin.ai.skillPackage.create') }}
          </Button>
        </Empty>
      </div>
    </div>
    </div>
    <!-- 回收站抽屉 (RecycleBinDrawer) -->
    <RecycleBinDrawer
      ref="recycleBinRef"
      resource="/admin/ai/skill-packages"
      name-field="name"
      side="admin"
      @restored="loadPackages"
    />
    <!-- Valves 配置面板 -->
    <ValvesConfigPanel
      ref="valvesConfigPanelRef"
      :package-id="selectedPackageId"
      :package-name="selectedPackage?.name"
      i18n-prefix="admin.ai.skillPackage"
      :get-valves-api="getSkillPackageValvesApi"
      :update-valves-api="updateSkillPackageValvesApi"
      @success="loadPackages"
    />
  </Page>
</template>

<style scoped>
/* Remove Card import warning — Card is no longer used in template / 移除 Card 导入警告 */
</style>
