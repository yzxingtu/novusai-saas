import type { UploadRequestOption } from 'ant-design-vue/es/vc-upload/interface';

import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';

import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { useVbenDrawer } from '@vben/common-ui';

import { message, Modal } from 'ant-design-vue';

import {
  cloneSkillPackageApi,
  deleteSkillPackageApi,
  exportSkillPackageApi,
  importSkillPackageApi,
  toggleSkillPackageStatusApi,
  uploadSkillPackageApi,
} from '#/api/admin/skill-packages';
import { $t } from '#/locales';
import { buildFormExtraData } from '#/utils/form-extra-data';

import PackageForm from './modules/form.vue';

type UseSkillPackageActionsOptions = {
  loadPackages: () => Promise<void>;
  refreshRecycleBin?: () => void;
};

export function useSkillPackageActions(options: UseSkillPackageActionsOptions) {
  const router = useRouter();

  const [PackageFormDrawer, packageFormApi] = useVbenDrawer({
    connectedComponent: PackageForm,
    destroyOnClose: true,
  });

  const importModalVisible = ref(false);
  const importing = ref(false);
  const importConflictMode = ref<'rename' | 'skip'>('rename');

  const uploadModalVisible = ref(false);
  const uploading = ref(false);

  function openSkillRegistry() {
    router.push('/admin/plugins/marketplace?catalog=skills');
  }

  function goToDetail(pkg: AdminSkillPackageInfo) {
    router.push(`/admin/ai/skill-packages/${pkg.id}`);
  }

  function onCreatePackage() {
    packageFormApi
      .setData({
        mode: 'add',
        _resource: '/admin/ai/skill-packages',
        ...buildFormExtraData({
          defaults: { is_active: true, sort_order: 0 },
        }),
      })
      .open();
  }

  function onEditPackage(pkg: AdminSkillPackageInfo) {
    packageFormApi
      .setData({
        ...pkg,
        mode: 'edit',
        _resource: '/admin/ai/skill-packages',
        ...buildFormExtraData(),
      })
      .open();
  }

  async function onExportPackage(pkg: AdminSkillPackageInfo) {
    try {
      const data = await exportSkillPackageApi(pkg.id);
      const json = JSON.stringify(data, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `skill-package-${pkg.name.replaceAll(/\s+/g, '_')}.json`;
      link.click();
      URL.revokeObjectURL(url);
      message.success($t('admin.ai.skillPackage.messages.exportSuccess'));
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

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
      await options.loadPackages();
    } catch {
      message.error($t('admin.ai.skillPackage.messages.importFailed'));
    } finally {
      importing.value = false;
    }

    return false;
  }

  function onUploadClick() {
    uploadModalVisible.value = true;
  }

  async function handleCustomUpload(optionsArg: UploadRequestOption) {
    const file = optionsArg.file as File;
    uploading.value = true;
    try {
      await uploadSkillPackageApi(file);
      message.success($t('admin.ai.skillPackage.messages.uploadSuccess'));
      uploadModalVisible.value = false;
      await options.loadPackages();
      optionsArg.onSuccess?.({}, new XMLHttpRequest());
    } catch {
      optionsArg.onError?.(new Error($t('common.uploadFailed')));
    } finally {
      uploading.value = false;
    }
  }

  async function onDeletePackage(pkg: AdminSkillPackageInfo) {
    Modal.confirm({
      title: $t('admin.common.confirmDelete'),
      onOk: async () => {
        try {
          await deleteSkillPackageApi(pkg.id);
          message.success($t('common.deleteSuccess'));
          await options.loadPackages();
          options.refreshRecycleBin?.();
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
          await options.loadPackages();
        } catch {
          // handled by interceptor / 错误由请求拦截器处理
        }
      },
    });
  }

  async function onClonePackage(pkg: AdminSkillPackageInfo) {
    try {
      const result = await cloneSkillPackageApi(pkg.id);
      message.success(
        $t('admin.ai.skillPackage.messages.cloneSuccess', {
          name: result.package_name,
        }),
      );
      await options.loadPackages();
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  function handlePackageMenuClick(
    key: number | string,
    pkg: AdminSkillPackageInfo,
  ) {
    switch (String(key)) {
      case 'clone': {
        void onClonePackage(pkg);
        break;
      }
      case 'delete': {
        void onDeletePackage(pkg);
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
        void onExportPackage(pkg);
        break;
      }
      default: {
        break;
      }
    }
  }

  function onPackageFormSuccess() {
    void options.loadPackages();
  }

  return {
    goToDetail,
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
  };
}
