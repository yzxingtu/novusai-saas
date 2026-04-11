import type { ConfigItemMeta } from '#/types/config';

import { nextTick, shallowRef } from 'vue';

import { describe, expect, it } from 'vitest';

import { useConfigFormModel } from '../composables/use-config-form-model';

describe('useConfigFormModel', () => {
  it('hydrates JSON child fields and merges them back into the parent payload', async () => {
    const configs = shallowRef<ConfigItemMeta[]>([
      {
        key: 'service_config',
        value_type: 'json',
        value: {
          mode: 'safe',
          retries: 3,
        },
        children: [
          {
            key: 'service_mode',
            value_path: 'mode',
            value_type: 'string',
          },
          {
            key: 'service_retries',
            value_path: 'retries',
            value_type: 'number',
          },
        ],
      },
    ]);

    const model = useConfigFormModel({
      configs: () => configs.value,
    });

    await nextTick();

    expect(model.formModel.service_mode).toBe('safe');
    expect(model.formModel.service_retries).toBe(3);

    model.fieldApi.setStringValue('service_mode', 'fast');
    model.fieldApi.setNumberValue('service_retries', 5);

    expect(model.prepareSubmitData()).toEqual({
      service_config: {
        mode: 'fast',
        retries: 5,
      },
    });
  });

  it('skips masked encrypted passwords until the user provides a new value', async () => {
    const configs = shallowRef<ConfigItemMeta[]>([
      {
        key: 'api_secret',
        is_encrypted: true,
        value: '******',
        value_type: 'password',
      },
    ]);

    const model = useConfigFormModel({
      configs: () => configs.value,
    });

    await nextTick();

    expect(model.prepareSubmitData()).toEqual({});

    model.fieldApi.setStringValue('api_secret', 'fresh-secret');

    expect(model.prepareSubmitData()).toEqual({
      api_secret: 'fresh-secret',
    });
  });

  it('resets the dirty snapshot when the config definition changes', async () => {
    const configs = shallowRef<ConfigItemMeta[]>([
      {
        key: 'feature_enabled',
        value: false,
        value_type: 'boolean',
      },
    ]);

    const model = useConfigFormModel({
      configs: () => configs.value,
    });

    await nextTick();

    expect(model.isDirty()).toBe(false);

    model.fieldApi.setBooleanValue('feature_enabled', true);

    expect(model.isDirty()).toBe(true);

    configs.value = [
      {
        key: 'feature_enabled',
        value: true,
        value_type: 'boolean',
      },
    ];

    await nextTick();

    expect(model.getValues()).toEqual({
      feature_enabled: true,
    });
    expect(model.isDirty()).toBe(false);
  });
});
