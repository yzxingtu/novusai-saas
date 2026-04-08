// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import MarkdownRender from '../index.vue';

vi.mock('ant-design-vue', () => ({
  message: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('MarkdownRender', () => {
  it('formats standalone source lines as labeled links', () => {
    const wrapper = mount(MarkdownRender, {
      props: {
        content: `来源：
星辰在线（长沙2025学年校历）：https://news.changsha.cn/xctt/html/110187/20250212/194152.shtml
长沙晚报网（稿源“长沙教育”微信公众号）：https://www.icswb.com/h/163/20250610/931068.html`,
      },
    });

    const links = wrapper.findAll('a');
    expect(links).toHaveLength(2);
    expect(links[0]?.text()).toContain('星辰在线（长沙2025学年校历）');
    expect(links[0]?.attributes('href')).toBe(
      'https://news.changsha.cn/xctt/html/110187/20250212/194152.shtml',
    );
    expect(links[1]?.text()).toContain(
      '长沙晚报网（稿源“长沙教育”微信公众号）',
    );
    expect(links[1]?.attributes('href')).toBe(
      'https://www.icswb.com/h/163/20250610/931068.html',
    );
  });
});
