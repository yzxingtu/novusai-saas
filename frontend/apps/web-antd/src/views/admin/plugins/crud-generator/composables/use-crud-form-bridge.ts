/**
 * useCrudFormBridge — Bridge between Global AI Chat tool calls and CRUD form
 *
 * Listens for tool calls with `__crud_form_fill__` marker in their output,
 * then applies the patch to the current CRUD config via deep merge or replace.
 */

import type { Ref } from 'vue';

import { onMounted, onUnmounted } from 'vue';

import { message } from 'ant-design-vue';

import { $t } from '#/locales';
import { useGlobalAIChatStore } from '#/store';

import type { CrudConfig } from '../types';

const HANDLER_KEY = 'crud-form-bridge';
const FILL_MARKER = '__crud_form_fill__';

/** Runtime check for minimal CrudConfig shape from AI patch */
function isCrudConfigLike(obj: object): obj is CrudConfig {
  const o = obj as Record<string, unknown>;
  return (
    typeof o.module === 'string' &&
    typeof o.table_name === 'string' &&
    Array.isArray(o.fields)
  );
}

/** Merge AI patch into existing CrudConfig (array fields are concatenated) */
function mergePatchInto(
  base: CrudConfig,
  patch: Record<string, unknown>,
): CrudConfig {
  const merged = { ...base };
  for (const [key, value] of Object.entries(patch)) {
    if (!(key in merged)) continue;
    const k = key as keyof CrudConfig;
    const baseVal = merged[k];
    if (Array.isArray(value) && Array.isArray(baseVal)) {
      // @ts-expect-error -- dynamic AI patch assignment
      merged[k] = [...baseVal, ...value];
    } else {
      // @ts-expect-error -- dynamic AI patch assignment
      merged[k] = value;
    }
  }
  return merged;
}

export interface FillStats {
  fieldsCount: number;
  enumsCount: number;
  relationsCount: number;
  action: string;
}

export interface UseCrudFormBridgeOptions {
  config: Ref<CrudConfig>;
  loadConfig: (newConfig: CrudConfig) => void;
  snapshot: () => void;
  onFilled?: (stats: FillStats) => void;
}

export function useCrudFormBridge(options: UseCrudFormBridgeOptions) {
  const globalChat = useGlobalAIChatStore();

  function handleToolCall(_toolName: string, output: string) {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(output);
    } catch {
      return;
    }

    if (!parsed[FILL_MARKER]) {
      return;
    }

    if (parsed.error) {
      message.error(String(parsed.error));
      return;
    }

    const patch = parsed.patch as Record<string, unknown> | undefined;
    if (!patch || typeof patch !== 'object') {
      return;
    }

    const action = (parsed.action as string) || 'replace';

    if (action === 'replace') {
      if (!isCrudConfigLike(patch)) {
        message.error(
          $t('admin.dev.crudGenerator.aiFill.invalidFormat'),
        );
        return;
      }
      options.loadConfig(patch);
    } else if (action === 'merge') {
      options.loadConfig(mergePatchInto(options.config.value, patch));
    }

    options.snapshot();

    const stats: FillStats = {
      fieldsCount: Array.isArray(patch.fields) ? (patch.fields as unknown[]).length : 0,
      enumsCount: Array.isArray(patch.enums) ? (patch.enums as unknown[]).length : 0,
      relationsCount: Array.isArray(patch.relations) ? (patch.relations as unknown[]).length : 0,
      action,
    };

    if (options.onFilled) {
      options.onFilled(stats);
    }

    const patchKeys = Object.keys(patch);
    const summary = patchKeys.length <= 3
      ? patchKeys.join(', ')
      : `${patchKeys.slice(0, 3).join(', ')} +${patchKeys.length - 3}`;
    message.success(
      $t('admin.dev.crudGenerator.aiFill.applied', { fields: summary }),
    );
  }

  onMounted(() => {
    globalChat.registerToolCallHandler(HANDLER_KEY, handleToolCall);
  });

  onUnmounted(() => {
    globalChat.unregisterToolCallHandler(HANDLER_KEY);
  });

  return { handleToolCall };
}
