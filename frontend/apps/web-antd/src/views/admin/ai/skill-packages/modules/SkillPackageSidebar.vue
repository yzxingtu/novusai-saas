<script lang="ts" setup>
import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';

import { IconifyIcon, Plus } from '@vben/icons';

import {
  Badge,
  Button,
  Dropdown,
  Empty,
  Input,
  Menu,
  MenuItem,
  Space,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

interface Props {
  filteredPackages: AdminSkillPackageInfo[];
  getPackageRoleColor: (roleKey: null | string | undefined) => string;
  getPackageRoleText: (roleKey: null | string | undefined) => string;
  getRuntimeBindingModeColor: (mode: null | string | undefined) => string;
  getRuntimeBindingModeText: (mode: null | string | undefined) => string;
  getSourceSummaryText: (
    sourceSummary: null | string | undefined,
    sourcePlugin: null | string | undefined,
  ) => string;
  onCreatePackage: () => void;
  onImportClick: () => void;
  onOpenRecycleBin: () => void;
  onOpenSkillRegistry: () => void;
  onPackageMenuClick: (
    key: number | string,
    pkg: AdminSkillPackageInfo,
  ) => void;
  onSearchKeywordChange: (value: string) => void;
  onSelectPackage: (pkg: AdminSkillPackageInfo) => void;
  onUploadClick: () => void;
  packagesLoading: boolean;
  recycleBinCount: number;
  searchKeyword: string;
  selectedPackageId: null | number;
}

defineProps<Props>();
</script>

<template>
  <div
    class="flex h-full w-[280px] shrink-0 flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm"
  >
    <div
      class="flex shrink-0 items-center justify-between border-b border-border/50 px-3 py-2"
    >
      <span class="text-sm font-medium">{{
        $t('admin.ai.skillPackage.title')
      }}</span>
      <Space :size="4">
        <Tooltip :title="$t('common.recycleBin.title')">
          <Badge :count="recycleBinCount" :offset="[-2, 2]" size="small">
            <Button
              v-access:code="['ai_skill_package:recycle_bin']"
              type="text"
              size="small"
              @click="onOpenRecycleBin"
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
            <IconifyIcon icon="lucide:file-input" class="size-4 text-primary" />
          </Button>
        </Tooltip>
        <Tooltip :title="$t('admin.ai.skillRegistry.title')">
          <Button
            v-access:code="['plugin_skill_registry:list']"
            type="text"
            size="small"
            @click="onOpenSkillRegistry"
          >
            <IconifyIcon
              icon="lucide:package-search"
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
      <Input
        :value="searchKeyword"
        :placeholder="$t('admin.ai.skillPackage.placeholder.searchName')"
        allow-clear
        size="small"
        class="mb-3"
        @update:value="(value) => onSearchKeywordChange(value ?? '')"
      >
        <template #prefix>
          <IconifyIcon
            icon="lucide:search"
            class="size-3.5 text-muted-foreground"
          />
        </template>
      </Input>

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
                      :color="getPackageRoleColor(pkg.package_role_key)"
                      class="shrink-0"
                      style="
                        padding: 0 3px;
                        margin: 0;
                        font-size: 10px;
                        line-height: 14px;
                      "
                    >
                      {{ getPackageRoleText(pkg.package_role_key) }}
                    </Tag>
                    <Tag
                      v-if="pkg.is_recommended"
                      color="gold"
                      class="shrink-0"
                      style="
                        padding: 0 3px;
                        margin: 0;
                        font-size: 10px;
                        line-height: 14px;
                      "
                    >
                      {{ $t('admin.ai.skillPackage.isRecommended') }}
                    </Tag>
                  </div>
                  <div class="mt-0.5 flex items-center gap-1.5">
                    <Tag
                      :color="
                        getRuntimeBindingModeColor(pkg.runtime_binding_mode)
                      "
                      style="
                        padding: 0 3px;
                        margin: 0;
                        font-size: 10px;
                        line-height: 14px;
                      "
                    >
                      {{ getRuntimeBindingModeText(pkg.runtime_binding_mode) }}
                    </Tag>
                    <Tooltip
                      :title="
                        getSourceSummaryText(
                          pkg.source_summary,
                          pkg.source_plugin,
                        )
                      "
                    >
                      <Tag
                        color="blue"
                        class="shrink-0"
                        style="
                          padding: 0 3px;
                          margin: 0;
                          font-size: 10px;
                          line-height: 14px;
                        "
                      >
                        {{
                          getSourceSummaryText(
                            pkg.source_summary,
                            pkg.source_plugin,
                          )
                        }}
                      </Tag>
                    </Tooltip>
                  </div>
                  <div
                    class="mt-1 flex items-center gap-2 text-xs text-muted-foreground"
                  >
                    <span
                      class="whitespace-nowrap text-xs text-muted-foreground"
                    >
                      {{ pkg.skill_count }}
                      {{ $t('admin.ai.skillPackage.detail.skills') }}
                    </span>
                    <span
                      class="whitespace-nowrap text-xs text-muted-foreground"
                    >
                      {{ pkg.configured_valves_count }}/{{
                        pkg.valves_field_count
                      }}
                      {{ $t('admin.ai.skillPackage.detail.envVars') }}
                    </span>
                  </div>
                </div>
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
                          onPackageMenuClick(info.key, pkg)
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
                          <IconifyIcon
                            icon="lucide:download"
                            class="size-3.5"
                          />
                          <span>{{
                            $t('admin.ai.skillPackage.exportBtn')
                          }}</span>
                        </div>
                      </MenuItem>
                      <MenuItem key="clone">
                        <div class="flex items-center gap-2">
                          <IconifyIcon icon="lucide:copy" class="size-3.5" />
                          <span>{{
                            $t('admin.ai.skillPackage.cloneBtn')
                          }}</span>
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
</template>
