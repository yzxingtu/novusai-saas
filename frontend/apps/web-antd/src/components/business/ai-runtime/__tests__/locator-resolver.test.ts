// @vitest-environment happy-dom

import { describe, expect, it } from 'vitest';

import {
  LocatorResolutionError,
  LocatorResolver,
} from '../locator-resolver';

describe('locatorResolver', () => {
  const expectLocatorError = (
    run: () => void,
    code: 'ambiguous' | 'invalid_locator' | 'not_found',
  ) => {
    try {
      run();
      throw new Error('Expected LocatorResolutionError');
    } catch (error) {
      expect(error).toBeInstanceOf(LocatorResolutionError);
      const typed = error as LocatorResolutionError;
      expect(typed.code).toBe(code);
      return typed;
    }
  };

  it('resolves exact locators by css/id/name/href/text/testid/ai-id', () => {
    document.body.innerHTML = `
      <button
        id="create-agent"
        name="agentCreate"
        data-testid="create-agent-testid"
        data-ai-id="agent-create"
      >
        Create Agent
      </button>
      <a id="docs-link" href="/docs">Docs</a>
    `;

    const resolver = new LocatorResolver();
    expect(resolver.resolve('css:#create-agent').element.id).toBe('create-agent');
    expect(resolver.resolve('#create-agent').element.id).toBe('create-agent');
    expect(resolver.resolve('id:create-agent').element.id).toBe('create-agent');
    expect(resolver.resolve('name:agentCreate').element.id).toBe('create-agent');
    expect(resolver.resolve('testid:create-agent-testid').element.id).toBe(
      'create-agent',
    );
    expect(resolver.resolve('ai-id:agent-create').element.id).toBe(
      'create-agent',
    );
    expect(resolver.resolve('href:/docs').element.id).toBe('docs-link');
    expect(resolver.resolve('text:Docs').element.id).toBe('docs-link');
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

  it('returns not_found candidates when exact resolve fails and fuzzy is disabled', () => {
    document.body.innerHTML = `
      <button>Submit</button>
      <button>Submit Draft</button>
      <a href="/next-step">Next Step</a>
    `;

    const resolver = new LocatorResolver();
    const typed = expectLocatorError(() => {
      resolver.resolve('text:Submit Form', {
        allowFuzzy: false,
        candidateLimit: 1,
      });
    }, 'not_found');

    expect(typed.candidates.length).toBe(1);
    expect(typed.candidates[0]?.label).toContain('Submit');
  });

  it('throws invalid_locator for empty input', () => {
    const resolver = new LocatorResolver();
    const typed = expectLocatorError(() => {
      resolver.resolve('   ');
    }, 'invalid_locator');
    expect(typed.candidates).toHaveLength(0);
  });

  it('throws ambiguous when fuzzy matches have close scores', () => {
    document.body.innerHTML = `
      <button>Submit Alpha</button>
      <button>Submit Beta</button>
      <button>Archive</button>
    `;

    const resolver = new LocatorResolver();
    const typed = expectLocatorError(() => {
      resolver.resolve('subm');
    }, 'ambiguous');
    expect(typed.candidates.length).toBeGreaterThan(1);
    expect(typed.candidates.every((item) => item.label.includes('Submit'))).toBe(
      true,
    );
  });

  it('throws ambiguous for css-like exact locator when multiple visible elements match', () => {
    document.body.innerHTML = `
      <div>
        <div><button id="first-match">First</button></div>
        <div><button id="second-match">Second</button></div>
      </div>
    `;

    const resolver = new LocatorResolver();
    const typed = expectLocatorError(() => {
      resolver.resolve('div > div > button');
    }, 'ambiguous');

    expect(typed.candidates.length).toBeGreaterThan(1);
    expect(typed.candidates.some((item) => item.locator === 'id:first-match')).toBe(
      true,
    );
    expect(typed.candidates.some((item) => item.locator === 'id:second-match')).toBe(
      true,
    );
  });

  it('returns null from resolveOrNull when resolution fails', () => {
    document.body.innerHTML = `<button id="save-btn">Save</button>`;
    const resolver = new LocatorResolver();

    expect(resolver.resolveOrNull('id:save-btn')?.element.id).toBe('save-btn');
    expect(resolver.resolveOrNull('id:missing-btn', { allowFuzzy: false })).toBeNull();
  });

  it('respects hidden filtering and includeHidden override', () => {
    document.body.innerHTML = `
      <button id="hidden-btn" hidden>Hidden Action</button>
      <button id="visible-btn">Visible Action</button>
    `;

    const defaultResolver = new LocatorResolver();
    const includeHiddenResolver = new LocatorResolver({ includeHidden: true });

    expect(defaultResolver.resolveOrNull('id:hidden-btn', { allowFuzzy: false })).toBeNull();
    expect(
      defaultResolver.findCandidates('hidden').some((item) => item.locator === 'id:hidden-btn'),
    ).toBe(false);

    expect(
      includeHiddenResolver.resolveOrNull('id:hidden-btn', { allowFuzzy: false })?.element.id,
    ).toBe('hidden-btn');
    expect(
      includeHiddenResolver.findCandidates('hidden').some((item) => item.locator === 'id:hidden-btn'),
    ).toBe(true);
  });

  it('infers kind, disabled state and ranks enabled candidates ahead of disabled ones', () => {
    document.body.innerHTML = `
      <button id="save-enabled">Save</button>
      <button id="save-disabled" disabled>Save</button>
      <div id="save-aria-disabled" role="button" aria-disabled="true">Save Role</div>
      <a id="help-link" href="/help">Help</a>
      <div id="menu-item" role="menuitem">Settings</div>
      <div id="tab-item" class="ant-tabs-tab">Logs</div>
      <div class="ant-pagination">
        <button id="page-next" class="ant-pagination-next">Next</button>
      </div>
    `;

    const resolver = new LocatorResolver();
    const saveCandidates = resolver.findCandidates('sav', 5);

    expect(saveCandidates[0]?.locator).toBe('id:save-enabled');
    expect(saveCandidates.find((item) => item.locator === 'id:save-disabled')?.disabled).toBe(
      true,
    );
    expect(
      saveCandidates.find((item) => item.locator === 'id:save-aria-disabled')?.disabled,
    ).toBe(true);

    expect(resolver.resolve('href:/help').candidate.kind).toBe('link');
    expect(resolver.resolve('id:menu-item').candidate.kind).toBe('menu_item');
    expect(resolver.resolve('id:tab-item').candidate.kind).toBe('tab');
    expect(resolver.resolve('id:page-next').candidate.kind).toBe('pagination');
  });
});
