<script lang="ts" setup>
/**
 * 插件菜单位置配置弹窗
 *
 * 支持：
 * - 多级菜单树形选择（TreeSelect）
 * - 按菜单 scope 分组：admin_only → 管理端目录，all_tenants → 企业端目录
 * - admin_and_all scope：同时配置管理端和企业端父级
 */
import type {
  MenuOverrideItem,
  MenuParentOption,
  MenuParentOptionsResponse,
} from '#/api/admin/plugin';

import { computed, h, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Modal, Spin, TreeSelect } from 'ant-design-vue';

import { getMenuParentOptionsApi } from '#/api/admin/plugin';
import { $t } from '#/locales';

export interface MenuDeclItem {
  name: string;
  title: Record<string, string> | string;
  parent?: string;
  icon?: string;
  scope?: string;
  hidden?: boolean;
}

interface MenuEditRow {
  name: string;
  title: string;
  icon?: string;
  scope: string;
  /** 管理端父级（admin_only / admin_and_all） / Admin parent scope */
  adminParent: string;
  /** 企业端父级（all_tenants / admin_and_all） / Tenant parent scope */
  tenantParent: string;
}

const props = defineProps<{
  pluginDisplayName?: string;
}>();

const emit = defineEmits<{
  (e: 'confirm', overrides: MenuOverrideItem[]): void;
  (e: 'cancel'): void;
}>();

const visible = ref(false);
const loading = ref(false);
const optionsData = ref<MenuParentOptionsResponse>({ admin: [], tenant: [] });
const rows = ref<MenuEditRow[]>([]);

function resolveTitle(title: Record<string, string> | string): string {
  if (typeof title === 'string') return title;
  return title?.['zh-CN'] ?? title?.en ?? Object.values(title)[0] ?? '';
}

/** 规范化旧版 scope 值（manifest 未重新扫描时兼容旧数据） / Normalize legacy scope */
function normalizeScope(scope: string | undefined): string {
  if (scope === 'tenant') return 'all_tenants';
  if (scope === 'admin') return 'admin_only';
  return scope || 'admin_only';
}

/** 将 MenuParentOption[] 转为 AntD TreeSelect 需要的 treeData 格式，含图标渲染 / Convert to treeData for TreeSelect */
function toTreeData(options: MenuParentOption[]): object[] {
  return options.map((opt) => ({
    title: h('span', { class: 'flex items-center gap-1.5' }, [
      opt.icon
        ? h(IconifyIcon, {
            icon: opt.icon,
            class: 'size-3.5 shrink-0 text-muted-foreground',
          })
        : h('span', { class: 'size-3.5 shrink-0' }),
      h('span', opt.label),
    ]),
    value: opt.value,
    selectable: true,
    children: opt.children ? toTreeData(opt.children) : undefined,
  }));
}

const adminTreeData = computed(() => toTreeData(optionsData.value.admin));
const tenantTreeData = computed(() => toTreeData(optionsData.value.tenant));

async function open(
  menus: MenuDeclItem[],
  currentOverrides?: Record<
    string,
    { parent?: string; tenant_parent?: string }
  >,
) {
  rows.value = menus.map((m) => {
    const ov = currentOverrides?.[m.name] ?? {};
    return {
      name: m.name,
      title: resolveTitle(m.title),
      icon: m.icon,
      scope: normalizeScope(m.scope),
      adminParent: ov.parent ?? m.parent ?? '',
      tenantParent: ov.tenant_parent ?? '',
    };
  });

  visible.value = true;
  loading.value = true;
  try {
    optionsData.value = await getMenuParentOptionsApi();

    // Default select first option (when no saved config or manifest doesn't specify parent) / 默认选中第一个选项（无已保存配置或 manifest 未指定 parent 时）
    const firstAdmin = optionsData.value.admin[0]?.value ?? '';
    const firstTenant = optionsData.value.tenant[0]?.value ?? '';
    for (const row of rows.value) {
      const needsAdmin =
        row.scope === 'admin_only' || row.scope === 'admin_and_all';
      const needsTenant =
        row.scope === 'all_tenants' || row.scope === 'admin_and_all';
      if (needsAdmin && !row.adminParent) row.adminParent = firstAdmin;
      if (needsTenant && !row.tenantParent) row.tenantParent = firstTenant;
    }
  } catch {
    optionsData.value = { admin: [], tenant: [] };
  } finally {
    loading.value = false;
  }
}

function handleOk() {
  const overrides: MenuOverrideItem[] = rows.value.map((r) => ({
    name: r.name,
    parent: r.adminParent || r.tenantParent,
    ...(r.scope === 'admin_and_all' && r.tenantParent
      ? { tenant_parent: r.tenantParent }
      : {}),
  }));
  emit('confirm', overrides);
  visible.value = false;
}

function handleCancel() {
  emit('cancel');
  visible.value = false;
}

const hasMenus = computed(() => rows.value.length > 0);

/** 需要展示管理端区块的行 / Rows showing admin block */
const adminRows = computed(() =>
  rows.value.filter(
    (r) => r.scope === 'admin_only' || r.scope === 'admin_and_all',
  ),
);
/** 需要展示企业端区块的行 / Rows showing tenant block */
const tenantRows = computed(() =>
  rows.value.filter(
    (r) => r.scope === 'all_tenants' || r.scope === 'admin_and_all',
  ),
);

defineExpose({ open });
</script>

<template>
  <Modal
    v-model:open="visible"
    :title="$t('admin.plugin.menu_config.title')"
    :ok-text="$t('common.confirm')"
    :cancel-text="$t('common.cancel')"
    :width="600"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <div
      v-if="props.pluginDisplayName"
      class="mb-4 text-sm text-muted-foreground"
    >
      {{
        $t('admin.plugin.menu_config.description', {
          name: props.pluginDisplayName,
        })
      }}
    </div>

    <Spin :spinning="loading">
      <div v-if="hasMenus" class="space-y-4">
        <!-- ── 管理端菜单 ── -->
        <div v-if="adminRows.length > 0">
          <div class="mb-2 flex items-center gap-2">
            <IconifyIcon icon="lucide:monitor" class="size-3.5 text-primary" />
            <span class="text-xs font-semibold text-foreground">{{
              $t('admin.plugin.menu_config.admin_section')
            }}</span>
            <div class="h-px flex-1 bg-border/60"></div>
          </div>
          <div class="space-y-2">
            <div
              v-for="row in adminRows"
              :key="`admin-${row.name}`"
              class="flex items-center gap-2 rounded-lg border border-border/40 bg-muted/20 px-3 py-2"
            >
              <IconifyIcon
                :icon="row.icon || 'lucide:menu'"
                class="size-4 shrink-0 text-primary/70"
              />
              <span class="min-w-0 flex-1 truncate text-sm font-medium">{{
                row.title
              }}</span>
              <TreeSelect
                v-model:value="row.adminParent"
                :tree-data="adminTreeData"
                :placeholder="$t('admin.plugin.menu_config.select_parent')"
                tree-default-expand-all
                allow-clear
                class="w-52"
                size="small"
              />
            </div>
          </div>
        </div>

        <!-- ── 企业端菜单 ── -->
        <div v-if="tenantRows.length > 0">
          <div class="mb-2 flex items-center gap-2">
            <IconifyIcon icon="lucide:users" class="size-3.5 text-success" />
            <span class="text-xs font-semibold text-foreground">{{
              $t('admin.plugin.menu_config.tenant_section')
            }}</span>
            <div class="h-px flex-1 bg-border/60"></div>
          </div>
          <div class="space-y-2">
            <div
              v-for="row in tenantRows"
              :key="`tenant-${row.name}`"
              class="flex items-center gap-2 rounded-lg border border-border/40 bg-muted/20 px-3 py-2"
            >
              <IconifyIcon
                :icon="row.icon || 'lucide:menu'"
                class="size-4 shrink-0 text-success/70"
              />
              <span class="min-w-0 flex-1 truncate text-sm font-medium">{{
                row.title
              }}</span>
              <TreeSelect
                v-model:value="row.tenantParent"
                :tree-data="tenantTreeData"
                :placeholder="$t('admin.plugin.menu_config.select_parent')"
                tree-default-expand-all
                allow-clear
                class="w-52"
                size="small"
              />
            </div>
          </div>
        </div>
      </div>
      <div v-else class="py-6 text-center text-sm text-muted-foreground">
        {{ $t('admin.plugin.menu_config.no_menus') }}
      </div>
    </Spin>
  </Modal>
</template>
