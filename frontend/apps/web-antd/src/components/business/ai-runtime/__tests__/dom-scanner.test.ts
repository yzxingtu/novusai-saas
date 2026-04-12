// @vitest-environment happy-dom

import { describe, expect, it } from 'vitest';

import {
  DOMScanner,
  buildElementLocator,
  inferNodeKindFromElement,
  readElementLabel,
} from '../dom-scanner';
import { tAiRuntime } from '../i18n';

describe('dom-scanner helpers', () => {
  it('buildElementLocator resolves locator by priority and escapes values', () => {
    const aiElement = document.createElement('button');
    aiElement.setAttribute('data-ai-id', 'save"btn\\main');
    expect(buildElementLocator(aiElement)).toBe('[data-ai-id="save\\"btn\\\\main"]');

    const testIdElement = document.createElement('button');
    testIdElement.setAttribute('data-testid', 'submit');
    expect(buildElementLocator(testIdElement)).toBe('[data-testid="submit"]');

    const idElement = document.createElement('button');
    idElement.setAttribute('id', 'primary-cta');
    expect(buildElementLocator(idElement)).toBe('#primary-cta');

    const nameElement = document.createElement('input');
    nameElement.setAttribute('name', 'email');
    expect(buildElementLocator(nameElement)).toBe('input[name="email"]');

    const ariaElement = document.createElement('div');
    ariaElement.setAttribute('aria-label', 'More');
    expect(buildElementLocator(ariaElement)).toBe('div[aria-label="More"]');

    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
      <section>
        <span>first</span>
        <span>second</span>
      </section>
    `;
    const fallbackElement = wrapper.querySelectorAll('span')[1];
    expect(fallbackElement).toBeTruthy();
    expect(buildElementLocator(fallbackElement as Element)).toContain('span:nth-of-type(2)');
  });

  it('inferNodeKindFromElement recognizes common interactive kinds', () => {
    const menuByClass = document.createElement('div');
    menuByClass.className = 'ant-menu-item';
    expect(inferNodeKindFromElement(menuByClass)).toBe('menu-item');

    const tabByRole = document.createElement('div');
    tabByRole.setAttribute('role', 'tab');
    expect(inferNodeKindFromElement(tabByRole)).toBe('tab');

    const link = document.createElement('a');
    expect(inferNodeKindFromElement(link)).toBe('link');

    const textarea = document.createElement('textarea');
    expect(inferNodeKindFromElement(textarea)).toBe('textarea');

    const checkbox = document.createElement('input');
    checkbox.setAttribute('type', 'checkbox');
    expect(inferNodeKindFromElement(checkbox)).toBe('checkbox');

    const radio = document.createElement('input');
    radio.setAttribute('type', 'radio');
    expect(inferNodeKindFromElement(radio)).toBe('radio');

    const input = document.createElement('input');
    expect(inferNodeKindFromElement(input)).toBe('input');

    const select = document.createElement('select');
    expect(inferNodeKindFromElement(select)).toBe('select');

    const buttonByRole = document.createElement('div');
    buttonByRole.setAttribute('role', 'button');
    expect(inferNodeKindFromElement(buttonByRole)).toBe('button');

    const fallback = document.createElement('section');
    expect(inferNodeKindFromElement(fallback)).toBe('button');
  });

  it('readElementLabel uses attribute priority and text fallback', () => {
    const attrFirst = document.createElement('input');
    attrFirst.setAttribute('aria-label', '  主 按钮  ');
    attrFirst.setAttribute('title', '标题');
    attrFirst.setAttribute('placeholder', '占位');
    attrFirst.textContent = '文本';
    expect(readElementLabel(attrFirst)).toBe('主 按钮');

    const placeholder = document.createElement('input');
    placeholder.setAttribute('placeholder', '请输入关键词');
    expect(readElementLabel(placeholder)).toBe('请输入关键词');

    const textOnly = document.createElement('div');
    textOnly.textContent = '  hello    world  ';
    expect(readElementLabel(textOnly)).toBe('hello world');

    const empty = document.createElement('div');
    expect(readElementLabel(empty)).toBeUndefined();
  });
});

describe('DOMScanner.scan', () => {
  it('supports surfaces-only mode and collects overlay keys/title fallback', () => {
    document.body.innerHTML = `
      <div class="ant-modal-root">
        <div class="ant-modal-wrap" data-ai-surface-id="main-modal">
          <div class="ant-modal-title">审批弹窗</div>
        </div>
      </div>
      <div class="ant-drawer-content-wrapper" data-testid="settings-drawer"></div>
      <div class="ant-dropdown" id="actions-dropdown">
        <div title="操作菜单"></div>
      </div>
      <div class="ant-popover">
        <div class="ant-popover-title">提示卡片</div>
      </div>
      <div class="ant-popover hidden">
        <div class="ant-popover-title">隐藏提示</div>
      </div>
    `;

    const scanner = new DOMScanner({
      textMaxLength: 64,
    });
    const result = scanner.scan(
      {
        document,
      } as unknown as Parameters<DOMScanner['scan']>[0],
      'surfaces-only',
    );

    expect(result.mode).toBe('surfaces-only');
    expect(result.nodes).toHaveLength(0);
    expect(result.scannedElements).toBe(0);
    expect(result.truncated).toBe(false);

    const overlayMap = new Map(result.overlays.map((overlay) => [overlay.key, overlay]));
    expect(result.overlays).toHaveLength(4);
    expect(overlayMap.get('modal:main-modal')?.title).toBe('审批弹窗');
    expect(overlayMap.get('drawer:settings-drawer')?.title).toBe(
      tAiRuntime('surfaceTitle.drawer', { index: 1 }),
    );
    expect(overlayMap.get('dropdown:actions-dropdown')?.title).toBe(
      tAiRuntime('surfaceTitle.dropdown', { index: 1 }),
    );
    expect(overlayMap.get('popover:dom:1')?.title).toBe('提示卡片');
  });

  it('respects visibleOnly and maxDepth when scanning from a provided root', () => {
    document.body.innerHTML = `
      <div id="scan-root">
        <button data-testid="depth-1">shallow</button>
        <button data-testid="hidden-item" style="display:none">hidden</button>
        <div>
          <button data-testid="depth-2">deep</button>
        </div>
      </div>
    `;

    const scanner = new DOMScanner({
      maxDepth: 1,
      maxNodes: 20,
      visibleOnly: true,
    });
    const root = document.getElementById('scan-root');
    expect(root).toBeTruthy();

    const result = scanner.scan({
      activeSurfaceId: 'surface:page:1',
      document,
      root: root as Element,
    } as unknown as Parameters<DOMScanner['scan']>[0]);

    const locators = result.nodes.map((node) => node.locator);
    expect(locators).toContain('[data-testid="depth-1"]');
    expect(locators.some((locator) => locator.includes('hidden-item'))).toBe(false);
    expect(locators.some((locator) => locator.includes('depth-2'))).toBe(false);
    expect(result.nodes.every((node) => node.surfaceId === 'surface:page:1')).toBe(true);
    expect(result.truncated).toBe(false);
  });

  it('falls back to body root and truncates at maxNodes', () => {
    document.body.innerHTML = `
      <button data-testid="first-hidden" style="display:none">A</button>
      <button data-testid="second-visible">B</button>
      <button data-testid="third-visible">C</button>
    `;

    const scanner = new DOMScanner({
      maxNodes: 2,
      visibleOnly: false,
    });
    const result = scanner.scan({
      document,
    } as unknown as Parameters<DOMScanner['scan']>[0]);

    expect(result.nodes).toHaveLength(2);
    expect(result.truncated).toBe(true);
    expect(result.scannedElements).toBeGreaterThanOrEqual(3);
    expect(result.nodes[0]?.locator).toBe('[data-testid="first-hidden"]');
    expect(result.nodes[0]?.visible).toBe(false);
  });
});
