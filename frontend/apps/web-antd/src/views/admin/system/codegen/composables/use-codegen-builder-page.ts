import type { Ref } from 'vue';
import type { Router } from 'vue-router';

import type { CodegenConfigInfo } from '#/api/admin/codegen';

import { computed, onMounted, onUnmounted, watch } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';

import { message, Modal } from 'ant-design-vue';

import {
  getCodegenConfigDetailApi,
  getCodegenPresetApi,
} from '#/api/admin/codegen';
import { $t } from '#/locales';

type BuilderStoreLike = {
  configJson: Record<string, unknown>;
  isDirty: boolean;
  loadConfig: (id: null | number, json: Record<string, unknown>) => void;
  redo: () => boolean;
  resetWizard: () => void;
  selectedFieldKey: null | string;
  showFieldManager: boolean;
  undo: () => boolean;
  updateConfig: (patch: Record<string, unknown>) => void;
};

type UseCodegenBuilderPageOptions = {
  configId: Ref<null | number>;
  configMeta: Ref<CodegenConfigInfo | null>;
  isNewMode: Ref<boolean>;
  loadModules: () => Promise<void> | void;
  onSave: () => Promise<void> | void;
  resourceInputRef: Ref<HTMLElement | null>;
  routeId: Ref<unknown>;
  router: Router;
  store: BuilderStoreLike;
  watchPresetQuery: Ref<string | undefined>;
};

export function useCodegenBuilderPage(options: UseCodegenBuilderPageOptions) {
  const fields = computed(
    () =>
      (options.store.configJson.fields as Array<Record<string, unknown>>) || [],
  );

  async function loadConfigIfEdit() {
    const id = options.configId.value;
    if (id !== null && id !== undefined) {
      try {
        const config = await getCodegenConfigDetailApi(id);
        options.configMeta.value = config;
        options.store.loadConfig(config.id, config.config_json || {});
        options.store.showFieldManager = true;
      } catch (error) {
        const status = (error as { response?: { status?: number } })?.response
          ?.status;
        if (status === 404) {
          message.error($t('admin.system.codegen.builder.configNotFound'));
        } else {
          message.error($t('common.failed'));
        }
        options.store.resetWizard();
        await options.router.replace({ name: 'AdminSystemCodegen' });
      }
      return;
    }

    const presetQuery = options.watchPresetQuery.value;
    if (presetQuery) {
      try {
        const result = await getCodegenPresetApi(presetQuery);
        const parsed = result?.parsed ?? {};
        if (parsed && typeof parsed === 'object') {
          options.configMeta.value = null;
          options.store.loadConfig(null, parsed);
          options.store.showFieldManager = true;
          return;
        }
      } catch {
        message.error($t('admin.system.codegen.builder.presetNotFound'));
      }
    }

    options.configMeta.value = null;
    options.store.resetWizard();
    options.store.updateConfig({ module: 'system' });
    options.store.showFieldManager = true;
  }

  function removeSelectedField() {
    const key = options.store.selectedFieldKey;
    if (!key) return;
    const next = fields.value.filter((field) => field.__key !== key);
    options.store.updateConfig({ fields: next });
    options.store.selectedFieldKey = null;
  }

  function selectPrevField() {
    const key = options.store.selectedFieldKey;
    if (!key) return;
    const index = fields.value.findIndex((field) => field.__key === key);
    const prevField = index > 0 ? fields.value[index - 1] : undefined;
    if (prevField) {
      options.store.selectedFieldKey = String(prevField.__key);
    }
  }

  function selectNextField() {
    const key = options.store.selectedFieldKey;
    if (!key) return;
    const index = fields.value.findIndex((field) => field.__key === key);
    const nextField =
      index !== -1 && index < fields.value.length - 1
        ? fields.value[index + 1]
        : undefined;
    if (nextField) {
      options.store.selectedFieldKey = String(nextField.__key);
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    const target = event.target as HTMLElement;
    const tag = target?.tagName?.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) {
      return;
    }

    if (event.ctrlKey && event.key === 'z') {
      event.preventDefault();
      event.shiftKey ? options.store.redo() : options.store.undo();
    } else if (event.ctrlKey && event.key === 'y') {
      event.preventDefault();
      options.store.redo();
    } else if (event.ctrlKey && event.key === 's') {
      event.preventDefault();
      void options.onSave();
    } else if (event.key === 'Delete' && options.store.selectedFieldKey) {
      removeSelectedField();
    } else if (event.key === 'Escape') {
      options.store.selectedFieldKey = null;
    } else if (event.key === 'ArrowUp' && options.store.selectedFieldKey) {
      selectPrevField();
    } else if (event.key === 'ArrowDown' && options.store.selectedFieldKey) {
      selectNextField();
    }
  }

  function onBeforeUnload(event: BeforeUnloadEvent) {
    if (!options.store.isDirty) return;
    event.preventDefault();
    (event as BeforeUnloadEvent & { returnValue: string }).returnValue = '';
  }

  onBeforeRouteLeave((_to, _from, next) => {
    if (!options.store.isDirty) {
      next();
      return;
    }

    Modal.confirm({
      content: $t('admin.system.codegen.toolbar.unsavedContent'),
      onCancel: () => next(false),
      onOk: () => {
        options.store.isDirty = false;
        next();
      },
      title: $t('admin.system.codegen.toolbar.unsavedTitle'),
    });
  });

  onMounted(() => {
    void loadConfigIfEdit();
    void options.loadModules();
    document.addEventListener('keydown', handleKeydown);
    window.addEventListener('beforeunload', onBeforeUnload);
    if (options.isNewMode.value) {
      setTimeout(() => options.resourceInputRef.value?.focus(), 100);
    }
  });

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown);
    window.removeEventListener('beforeunload', onBeforeUnload);
  });

  watch(options.routeId, async () => {
    if (options.store.isDirty) {
      return new Promise<void>((resolve) => {
        Modal.confirm({
          cancelText: $t('common.cancel'),
          content: $t('admin.system.codegen.toolbar.unsavedContent'),
          okText: $t('common.discard'),
          onCancel: () => resolve(),
          onOk: () => {
            void loadConfigIfEdit();
            resolve();
          },
          title: $t('admin.system.codegen.toolbar.unsavedTitle'),
        });
      });
    }
    await loadConfigIfEdit();
  });

  return {
    fields,
    loadConfigIfEdit,
  };
}
