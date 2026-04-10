import type { ComputedRef, Ref } from 'vue';

import type { PaletteItem } from '../modules/ComponentPalette.vue';

import { nextTick } from 'vue';

import {
  createFieldFromPalette,
  ensureFieldKeys,
} from '../modules/field-utils';
import { inferFieldConfigForMerge } from '../modules/infer';

type BuilderStoreLike = {
  configJson: Record<string, unknown>;
  selectedFieldKey: null | string;
  updateConfig: (patch: Record<string, unknown>) => void;
};

type WysiwygCenterLike = {
  addFromPalette: (item: PaletteItem) => void;
};

type UseCodegenBuilderFieldWorkspaceOptions = {
  builderTopRef: Ref<HTMLElement | null>;
  dbImportOpen: Ref<boolean>;
  fields: ComputedRef<Record<string, unknown>[]>;
  resourceInputRef: Ref<HTMLElement | null>;
  store: BuilderStoreLike;
  wysiwygRef: Ref<null | WysiwygCenterLike>;
};

function createGeneratedFieldKey() {
  return `f_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function withInferredImportedFields(incoming: Record<string, unknown>[]) {
  return incoming.map((field) => {
    const name = (field.name as string) || '';
    if (!name) return field;
    const inferred = inferFieldConfigForMerge(name);
    return {
      ...inferred,
      ...field,
      __key: field.__key || createGeneratedFieldKey(),
    };
  });
}

export function useCodegenBuilderFieldWorkspace(
  options: UseCodegenBuilderFieldWorkspaceOptions,
) {
  function focusBuilderTop() {
    options.builderTopRef.value?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
    options.resourceInputRef.value?.focus?.();
  }

  function scrollToField(fieldKey: string) {
    options.store.selectedFieldKey = fieldKey;
    nextTick(() => {
      document
        .querySelector(`[data-field-key="${fieldKey}"]`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }

  function locateValidationIssue(item: { field?: string; path?: string }) {
    const path = String(item.path || '');
    const fieldName = String(item.field || '');

    const fieldIndexMatch = path.match(/^fields\[(\d+)\]/);
    if (fieldIndexMatch) {
      const index = Number(fieldIndexMatch[1]);
      const field = options.fields.value[index];
      if (field?.__key) {
        scrollToField(String(field.__key));
        return;
      }
    }

    if (fieldName) {
      const targetField = options.fields.value.find(
        (field) => field.name === fieldName,
      );
      if (targetField?.__key) {
        scrollToField(String(targetField.__key));
        return;
      }
    }

    focusBuilderTop();
  }

  function onPaletteAdd(item: PaletteItem) {
    if (options.wysiwygRef.value) {
      options.wysiwygRef.value.addFromPalette(item);
      return;
    }

    const current = ensureFieldKeys(
      (options.store.configJson.fields as Record<string, unknown>[]) || [],
    );
    const newField = createFieldFromPalette(item, current);
    options.store.updateConfig({ fields: [...current, newField] });
    options.store.selectedFieldKey = String(newField.__key);
  }

  function onDbImported(patch: Record<string, unknown>) {
    const withInferred = withInferredImportedFields(
      (patch.fields as Record<string, unknown>[]) || [],
    );
    const mode = (patch._importMode as 'merge' | 'replace') || 'replace';
    const currentFields =
      (options.store.configJson.fields as Record<string, unknown>[]) || [];

    let finalFields: Record<string, unknown>[];
    if (mode === 'merge') {
      const incomingByName = new Map(
        withInferred.map((field) => [(field.name as string) || '', field]),
      );
      const currentNames = new Set(
        currentFields
          .map((field) => (field.name as string) || '')
          .filter(Boolean),
      );
      const merged = currentFields.map((field) => {
        const name = (field.name as string) || '';
        const imported = incomingByName.get(name);
        return imported ? { ...field, ...imported } : field;
      });
      const appended = withInferred.filter(
        (field) => !currentNames.has((field.name as string) || ''),
      );
      finalFields = [...merged, ...appended];
    } else {
      finalFields = withInferred;
    }

    const { _importMode: _ignoredImportMode, ...rest } = patch;
    options.store.selectedFieldKey = null;
    options.store.updateConfig({ ...rest, fields: finalFields });
    options.dbImportOpen.value = false;
  }

  return {
    focusBuilderTop,
    locateValidationIssue,
    onDbImported,
    onPaletteAdd,
  };
}
