import { describe, expect, it } from 'vitest';

import { isRuntimePageToolName } from '../tool-call-utils';

describe('tool-call-utils', () => {
  it('only treats canonical ui tools as runtime page tools', () => {
    expect(isRuntimePageToolName('ui_click')).toBe(true);
    expect(isRuntimePageToolName('ui_submit_form')).toBe(true);
    expect(isRuntimePageToolName('navigate_menu')).toBe(false);
    expect(isRuntimePageToolName('submit_form')).toBe(false);
  });
});
