import type { ConfigFormFieldApi, ConfigFormModel } from '../types';

import type {
  ConfigItemMeta,
  ConfigObject,
  ConfigScalar,
  ConfigSubmitPayload,
  ConfigValue,
} from '#/types/config';

import { reactive, watch } from 'vue';

interface UseConfigFormModelOptions {
  configs: () => ConfigItemMeta[];
}

function isConfigObject(value: unknown): value is ConfigObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isConfigScalar(value: unknown): value is ConfigScalar {
  return (
    value === null ||
    typeof value === 'boolean' ||
    typeof value === 'number' ||
    typeof value === 'string'
  );
}

function getValueByPath(
  obj: ConfigObject | undefined,
  path: string,
): ConfigValue | undefined {
  if (!obj || !path) return undefined;
  const keys = path.split('.');
  let result: ConfigValue | undefined = obj;
  for (const key of keys) {
    if (!isConfigObject(result)) return undefined;
    result = result[key];
  }
  return result;
}

function setValueByPath(
  obj: ConfigObject,
  path: string,
  value: ConfigValue | undefined,
): void {
  if (!path) return;
  const keys = path.split('.');
  const lastKey = keys.at(-1);
  if (!lastKey) return;
  let current: ConfigObject = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i];
    if (!key) continue;
    if (!isConfigObject(current[key])) {
      current[key] = {};
    }
    current = current[key] as ConfigObject;
  }
  current[lastKey] = value;
}

function tryParseJson(val: unknown): ConfigObject {
  if (typeof val === 'string') {
    try {
      const parsed: unknown = JSON.parse(val);
      return isConfigObject(parsed) ? parsed : {};
    } catch {
      return {};
    }
  }
  return isConfigObject(val) ? val : {};
}

function initConfigValue(
  cfg: ConfigItemMeta,
  data: ConfigFormModel,
  parentJsonValue?: ConfigObject,
) {
  const raw = cfg.value ?? cfg.default_value;
  if (cfg.value_path && parentJsonValue !== undefined) {
    const val = getValueByPath(parentJsonValue, cfg.value_path);
    data[cfg.key] = val ?? cfg.default_value;
  } else if (cfg.value_type === 'html') {
    data[cfg.key] = raw === null || raw === undefined ? '' : String(raw);
  } else {
    data[cfg.key] = raw;
  }

  if (!cfg.children?.length) return;
  const currentValue = data[cfg.key];
  const jsonValue = isConfigObject(currentValue)
    ? currentValue
    : tryParseJson(raw);
  for (const child of cfg.children) {
    initConfigValue(child, data, jsonValue);
  }
}

function mergeChildrenToParent(
  cfg: ConfigItemMeta,
  payload: ConfigSubmitPayload,
  formModel: ConfigFormModel,
) {
  if (!cfg.children?.length) return;
  const parentValue = tryParseJson(payload[cfg.key]);

  for (const child of cfg.children) {
    if (child.value_path) {
      const childVal = formModel[child.key];
      if (child.value_type === 'password' && child.is_encrypted) {
        if (childVal && childVal !== '******') {
          setValueByPath(parentValue, child.value_path, childVal);
        }
      } else {
        setValueByPath(parentValue, child.value_path, childVal);
      }
      Reflect.deleteProperty(payload, child.key);
    }

    if (child.children?.length) {
      mergeChildrenToParent(child, payload, formModel);
    }
  }

  payload[cfg.key] = parentValue;
}

export function useConfigFormModel(options: UseConfigFormModelOptions) {
  const formModel = reactive<ConfigFormModel>({});
  let initialSnapshot = '';

  watch(
    options.configs,
    (list) => {
      const data: ConfigFormModel = {};
      (list || []).forEach((cfg) => {
        initConfigValue(cfg, data);
      });
      Object.keys(formModel).forEach((key) =>
        Reflect.deleteProperty(formModel, key),
      );
      Object.assign(formModel, data);
      initialSnapshot = JSON.stringify(data);
    },
    { immediate: true },
  );

  function formatJsonValue(val: ConfigValue | undefined): string {
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') return val;
    try {
      return JSON.stringify(val, null, 2);
    } catch {
      return '';
    }
  }

  function updateJsonValue(key: string, val: string) {
    try {
      formModel[key] = JSON.parse(val);
    } catch {
      formModel[key] = val;
    }
  }

  function getStringValue(key: string): string | undefined {
    const value = formModel[key];
    if (typeof value === 'string') return value;
    if (typeof value === 'number') return String(value);
    return undefined;
  }

  function setStringValue(
    key: string,
    value: null | number | string | undefined,
  ): void {
    formModel[key] =
      value === null || value === undefined ? undefined : String(value);
  }

  function getNumberValue(key: string): number | undefined {
    const value = formModel[key];
    if (typeof value === 'number') return value;
    if (typeof value === 'string' && value.trim()) {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
    return undefined;
  }

  function setNumberValue(
    key: string,
    value: null | number | string | undefined,
  ): void {
    if (value === null || value === undefined || value === '') {
      formModel[key] = undefined;
      return;
    }
    const parsed = typeof value === 'number' ? value : Number(value);
    formModel[key] = Number.isFinite(parsed) ? parsed : undefined;
  }

  function getBooleanValue(key: string): boolean {
    return Boolean(formModel[key]);
  }

  function setBooleanValue(key: string, value: unknown): void {
    formModel[key] = Boolean(value);
  }

  function getSelectValue(key: string): number | string | undefined {
    const value = formModel[key];
    return typeof value === 'number' || typeof value === 'string'
      ? value
      : undefined;
  }

  function setSelectValue(key: string, value: unknown): void {
    formModel[key] =
      typeof value === 'number' || typeof value === 'string'
        ? value
        : undefined;
  }

  function getMultiSelectValue(key: string): Array<number | string> {
    const value = formModel[key];
    if (!Array.isArray(value)) return [];
    return value.filter(
      (item): item is number | string =>
        typeof item === 'number' || typeof item === 'string',
    );
  }

  function setMultiSelectValue(key: string, value: unknown): void {
    if (!Array.isArray(value)) {
      formModel[key] = [];
      return;
    }
    formModel[key] = value.filter(
      (item): item is number | string =>
        typeof item === 'number' || typeof item === 'string',
    );
  }

  function getHtmlValue(key: string): string {
    return getStringValue(key) ?? '';
  }

  function setHtmlValue(key: string, value: string): void {
    formModel[key] = value;
  }

  function getImageValue(key: string): string {
    return getStringValue(key) ?? '';
  }

  function setImageValue(key: string, value: string): void {
    formModel[key] = value;
  }

  const fieldApi: ConfigFormFieldApi = {
    getBooleanValue,
    getHtmlValue,
    getImageValue,
    getMultiSelectValue,
    getNumberValue,
    getSelectValue,
    getStringValue,
    setBooleanValue,
    setHtmlValue,
    setImageValue,
    setMultiSelectValue,
    setNumberValue,
    setSelectValue,
    setStringValue,
  };

  function getValues(): ConfigFormModel {
    return { ...formModel };
  }

  function prepareSubmitData(): ConfigSubmitPayload {
    const payload: ConfigSubmitPayload = {};
    const configs = options.configs() || [];

    const collectValues = (items: ConfigItemMeta[]) => {
      for (const cfg of items) {
        const val = formModel[cfg.key];
        if (cfg.value_type === 'password' && cfg.is_encrypted) {
          if (val && val !== '******') {
            payload[cfg.key] = val;
          }
        } else {
          payload[cfg.key] = val;
        }
        if (cfg.children?.length) {
          collectValues(cfg.children);
        }
      }
    };

    collectValues(configs);
    configs.forEach((cfg) => {
      mergeChildrenToParent(cfg, payload, formModel);
    });

    return payload;
  }

  function isDirty(): boolean {
    return JSON.stringify(formModel) !== initialSnapshot;
  }

  return {
    fieldApi,
    formModel,
    formatJsonValue,
    getValues,
    isConfigScalar,
    isDirty,
    prepareSubmitData,
    updateJsonValue,
  };
}
