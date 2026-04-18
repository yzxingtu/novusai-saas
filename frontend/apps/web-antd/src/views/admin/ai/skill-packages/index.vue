<script lang="ts" setup>
import type { VNodeRef } from 'vue';

import { computed, ref } from 'vue';

import { Page } from '@vben/common-ui';

import { RecycleBinDrawer } from '#/adapter/vxe-table/components';
import {
  getSkillPackageValvesApi,
  updateSkillPackageValvesApi,
} from '#/api/admin/skill-packages';
import ValvesConfigPanel from '#/components/business/valves-config-panel/ValvesConfigPanel.vue';
import { $t } from '#/locales';

import AIPageHeroCard from '../_shared/AIPageHeroCard.vue';
import {
  getPackageRoleColor,
  getPackageRoleText,
  getRuntimeBindingModeColor,
  getRuntimeBindingModeText,
  getSourceSummaryText,
} from './data';
import SkillPackageDetailPanel from './modules/SkillPackageDetailPanel.vue';
import SkillPackageImportModal from './modules/SkillPackageImportModal.vue';
import SkillPackageSidebar from './modules/SkillPackageSidebar.vue';
import SkillPackageUploadModal from './modules/SkillPackageUploadModal.vue';
import { useSkillPackageActions } from './use-skill-package-actions';
import { useSkillPackageDetail } from './use-skill-package-detail';
import { useSkillPackagePage } from './use-skill-package-page';

defineOptions({ name: 'AdminSkillPackageList' });

type RecycleBinDrawerRef = InstanceType<typeof RecycleBinDrawer> & {
  deletedCount?: number;
  open?: () => void;
  refreshCount?: () => void;
};

const routeCreateSkillAction = ref<(() => void) | null>(null);

const {
  filteredPackages,
  loadPackages,
  onSelectPackage,
  packagesLoading,
  searchKeyword,
  selectedPackage,
  selectedPackageId,
  updateSearchKeyword,
} = useSkillPackagePage({
  onCreateSkill: routeCreateSkillAction,
});

const recycleBinRef = ref<null | RecycleBinDrawerRef>(null);
const recycleBinCount = computed(() => recycleBinRef.value?.deletedCount ?? 0);

function openRecycleBin() {
  recycleBinRef.value?.open?.();
}

const {
  handleCustomUpload,
  handleImportFile,
  handlePackageMenuClick,
  importConflictMode,
  importModalVisible,
  importing,
  onCreatePackage,
  onImportClick,
  onPackageFormSuccess,
  onTogglePackageStatus,
  onUploadClick,
  openSkillRegistry,
  PackageFormDrawer,
  uploadModalVisible,
  uploading,
} = useSkillPackageActions({
  loadPackages,
  refreshRecycleBin: () => recycleBinRef.value?.refreshCount?.(),
});

const {
  onCreateSkill,
  onDeleteSkill,
  onEditSkill,
  onOpenValvesConfig,
  onSkillFormSuccess,
  onTestSkill,
  onToggleSkillStatus,
  skillColumns,
  SkillFormDrawer,
  skills,
  skillsLoading,
  valvesConfigPanelRef,
} = useSkillPackageDetail({
  loadPackages,
  selectedPackageId,
});

const setValvesConfigPanelRef: VNodeRef = (value) => {
  valvesConfigPanelRef.value = value as InstanceType<
    typeof ValvesConfigPanel
  > | null;
};

routeCreateSkillAction.value = onCreateSkill;

const heroChips = computed(() => {
  const chips = [
    {
      key: 'overview',
      icon: 'lucide:blocks',
      className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
      text: `${$t('admin.ai.skillPackage.title')} / ${$t('admin.ai.skill.title')}`,
    },
  ];

  if (selectedPackage.value) {
    chips.push(
      {
        key: 'role',
        icon: 'lucide:badge-check',
        className: 'bg-background/90 text-foreground',
        text: getPackageRoleText(selectedPackage.value.package_role_key),
      },
      {
        key: 'binding',
        icon: 'lucide:workflow',
        className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
        text: getRuntimeBindingModeText(
          selectedPackage.value.runtime_binding_mode,
        ),
      },
      {
        key: 'source',
        icon: 'lucide:package-search',
        className: 'bg-amber-500/10 text-amber-700 dark:text-amber-200',
        text: getSourceSummaryText(
          selectedPackage.value.source_summary,
          selectedPackage.value.source_plugin,
        ),
      },
    );
  }

  return chips;
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AIPageHeroCard
      :chips="heroChips"
      :description="$t('admin.ai.skillPackage.pageDesc')"
      icon="lucide:package-open"
      icon-wrap-class="bg-primary/10 text-primary"
      :title="$t('admin.ai.skillPackage.title')"
    />

    <PackageFormDrawer @success="onPackageFormSuccess" />
    <SkillFormDrawer @success="onSkillFormSuccess" />

    <SkillPackageUploadModal
      v-model:open="uploadModalVisible"
      :on-upload="handleCustomUpload"
      :uploading="uploading"
    />

    <SkillPackageImportModal
      v-model:conflict-mode="importConflictMode"
      v-model:open="importModalVisible"
      :importing="importing"
      :on-import-file="handleImportFile"
    />

    <div class="flex h-full gap-4 overflow-hidden">
      <SkillPackageSidebar
        :filtered-packages="filteredPackages"
        :get-package-role-color="getPackageRoleColor"
        :get-package-role-text="getPackageRoleText"
        :get-runtime-binding-mode-color="getRuntimeBindingModeColor"
        :get-runtime-binding-mode-text="getRuntimeBindingModeText"
        :get-source-summary-text="getSourceSummaryText"
        :on-create-package="onCreatePackage"
        :on-import-click="onImportClick"
        :on-open-recycle-bin="openRecycleBin"
        :on-open-skill-registry="openSkillRegistry"
        :on-package-menu-click="handlePackageMenuClick"
        :on-search-keyword-change="updateSearchKeyword"
        :on-select-package="onSelectPackage"
        :on-upload-click="onUploadClick"
        :packages-loading="packagesLoading"
        :recycle-bin-count="recycleBinCount"
        :search-keyword="searchKeyword"
        :selected-package-id="selectedPackageId"
      />

      <SkillPackageDetailPanel
        :on-create-package="onCreatePackage"
        :on-create-skill="onCreateSkill"
        :on-delete-skill="onDeleteSkill"
        :on-edit-skill="onEditSkill"
        :on-open-valves-config="onOpenValvesConfig"
        :on-test-skill="onTestSkill"
        :on-toggle-package-status="onTogglePackageStatus"
        :on-toggle-skill-status="onToggleSkillStatus"
        :selected-package="selectedPackage"
        :skill-columns="skillColumns"
        :skills="skills"
        :skills-loading="skillsLoading"
      />
    </div>

    <RecycleBinDrawer
      ref="recycleBinRef"
      resource="/admin/ai/skill-packages"
      name-field="name"
      side="admin"
      @restored="loadPackages"
    />

    <ValvesConfigPanel
      :ref="setValvesConfigPanelRef"
      :package-id="selectedPackageId"
      :package-name="selectedPackage?.name"
      i18n-prefix="admin.ai.skillPackage"
      :get-valves-api="getSkillPackageValvesApi"
      :update-valves-api="updateSkillPackageValvesApi"
      @success="loadPackages"
    />
  </Page>
</template>
