// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';

import { describe, expect, it } from 'vitest';

import AttachmentDetailDescriptions from '../AttachmentDetailDescriptions.vue';

describe('attachmentDetailDescriptions', () => {
  it('renders text, code, and tag fields while respecting visibility flags', () => {
    const wrapper = mount(AttachmentDetailDescriptions, {
      props: {
        sections: [
          {
            title: 'Basic',
            fields: [
              { label: 'Name', value: 'report.pdf' },
              { label: 'Hash', value: 'abc123', kind: 'code' },
              {
                label: 'Visibility',
                value: 'Public',
                kind: 'tag',
                color: 'green',
              },
              { label: 'Hidden', value: 'x', show: false },
            ],
          },
        ],
      },
    });

    expect(wrapper.text()).toContain('Basic');
    expect(wrapper.text()).toContain('report.pdf');
    expect(wrapper.text()).toContain('abc123');
    expect(wrapper.text()).toContain('Public');
    expect(wrapper.text()).not.toContain('Hidden');
  });
});
