import type { ConfigSubmitPayload, ConfigValue } from '#/types/config';

export type ConfigFormModel = Record<string, ConfigValue | undefined>;

export interface ConfigFormFieldApi {
  getStringValue: (key: string) => string | undefined;
  setStringValue: (
    key: string,
    value: null | number | string | undefined,
  ) => void;
  getNumberValue: (key: string) => number | undefined;
  setNumberValue: (
    key: string,
    value: null | number | string | undefined,
  ) => void;
  getBooleanValue: (key: string) => boolean;
  setBooleanValue: (key: string, value: unknown) => void;
  getSelectValue: (key: string) => number | string | undefined;
  setSelectValue: (key: string, value: unknown) => void;
  getMultiSelectValue: (key: string) => Array<number | string>;
  setMultiSelectValue: (key: string, value: unknown) => void;
  getHtmlValue: (key: string) => string;
  setHtmlValue: (key: string, value: string) => void;
  getImageValue: (key: string) => string;
  setImageValue: (key: string, value: string) => void;
}

export interface ConfigFormExpose {
  validate: () => Promise<void>;
  getValues: () => ConfigFormModel;
  prepareSubmitData: () => ConfigSubmitPayload;
  reset: () => void;
  isDirty: () => boolean;
}
