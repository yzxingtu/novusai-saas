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

describe('markdownRender', () => {
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
    expect(links[0]?.attributes('target')).toBe('_blank');
    expect(links[0]?.attributes('rel')).toBe('noopener noreferrer');
    expect(links[1]?.text()).toContain(
      '长沙晚报网（稿源“长沙教育”微信公众号）',
    );
    expect(links[1]?.attributes('href')).toBe(
      'https://www.icswb.com/h/163/20250610/931068.html',
    );
    expect(links[1]?.attributes('target')).toBe('_blank');
    expect(links[1]?.attributes('rel')).toBe('noopener noreferrer');
  });

  it('does not rewrite standalone source lines inside fenced code blocks', () => {
    const wrapper = mount(MarkdownRender, {
      props: {
        content: `\`\`\`txt
星辰在线（长沙2025学年校历）：https://news.changsha.cn/xctt/html/110187/20250212/194152.shtml
\`\`\`

长沙晚报网（稿源“长沙教育”微信公众号）：https://www.icswb.com/h/163/20250610/931068.html`,
      },
    });

    const links = wrapper.findAll('a');
    expect(links).toHaveLength(1);
    expect(wrapper.text()).toContain(
      '星辰在线（长沙2025学年校历）：https://news.changsha.cn/xctt/html/110187/20250212/194152.shtml',
    );
    expect(links[0]?.attributes('href')).toBe(
      'https://www.icswb.com/h/163/20250610/931068.html',
    );
    expect(links[0]?.attributes('target')).toBe('_blank');
    expect(links[0]?.attributes('rel')).toBe('noopener noreferrer');
  });

  it('renders bare markdown urls as readable anchor text while preserving href', () => {
    const rawUrl = 'https://example.com/path/to/article?foo=bar&baz=qux';
    const wrapper = mount(MarkdownRender, {
      props: {
        content: `请参考这个链接：\n${rawUrl}`,
      },
    });

    const links = wrapper.findAll('a');
    expect(links).toHaveLength(1);
    expect(links[0]?.attributes('href')).toBe(rawUrl);
    expect(links[0]?.attributes('target')).toBe('_blank');
    expect(links[0]?.attributes('rel')).toBe('noopener noreferrer');
    expect((links[0]?.text() ?? '').trim()).toContain('example.com');
    expect((links[0]?.text() ?? '').trim()).not.toBe(rawUrl);
    expect(wrapper.text()).not.toContain(rawUrl);
  });
});
