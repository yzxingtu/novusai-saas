import { describe, expect, it } from 'vitest';

import {
  buildComponentOptions,
  buildTypeOptions,
} from '../use-field-property-panel';

describe('field property panel option builders', () => {
  it('maps returned type inventory without hidden DictSelect filtering', () => {
    expect(
      buildTypeOptions([{ type: 'String' }, { type: 'DictSelect' }]),
    ).toEqual([
      { label: 'String', value: 'String' },
      { label: 'DictSelect', value: 'DictSelect' },
    ]);
  });

  it('maps returned component inventory without hidden DictSelect filtering', () => {
    expect(
      buildComponentOptions([
        { name: 'Input', label: 'Input' },
        { name: 'DictSelect', label: 'Dict Select' },
      ]),
    ).toEqual([
      { label: 'Input', value: 'Input' },
      { label: 'Dict Select', value: 'DictSelect' },
    ]);
  });
});
