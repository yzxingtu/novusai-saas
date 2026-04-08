// @vitest-environment happy-dom

import { describe, expect, it } from 'vitest';

import {
  LocatorResolutionError,
  LocatorResolver,
} from '../locator-resolver';

describe('locatorResolver', () => {
  it('resolves exact locator by testid', () => {
    document.body.innerHTML = `
      <button data-testid="create-agent">Create Agent</button>
      <a href="/docs">Docs</a>
    `;

    const resolver = new LocatorResolver();
    const resolved = resolver.resolve('testid:create-agent');

    expect(resolved.candidate.kind).toBe('button');
    expect(resolved.candidate.label).toContain('Create Agent');
  });

  it('supports fuzzy resolution for high-frequency targets', () => {
    document.body.innerHTML = `
      <div class="ant-menu-item">供应商管理</div>
      <div class="ant-tabs-tab">日志</div>
      <button>刷新列表</button>
    `;

    const resolver = new LocatorResolver();
    const resolved = resolver.resolve('供应商 菜单');
    expect(resolved.candidate.kind).toBe('menu_item');
    expect(resolved.candidate.label).toContain('供应商管理');
  });

  it('returns candidates when exact resolve fails', () => {
    document.body.innerHTML = `
      <button>Submit</button>
      <button>Submit Draft</button>
      <a href="/next-step">Next Step</a>
    `;

    const resolver = new LocatorResolver();
    expect(() =>
      resolver.resolve('text:Submit Form', { allowFuzzy: false }),
    ).toThrowError(LocatorResolutionError);

    try {
      resolver.resolve('text:Submit Form', { allowFuzzy: false });
    } catch (error) {
      const typed = error as LocatorResolutionError;
      expect(typed.code).toBe('not_found');
      expect(typed.candidates.length).toBeGreaterThan(0);
      expect(typed.candidates.some((item) => item.label.includes('Submit'))).toBe(
        true,
      );
    }
  });
});

