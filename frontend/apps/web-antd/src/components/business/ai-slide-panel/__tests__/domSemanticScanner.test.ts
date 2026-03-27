// @vitest-environment happy-dom

import { describe, expect, it } from 'vitest';

import { scanDomSemantics } from '../dom-semantic-scanner';

describe('scanDomSemantics', () => {
  it('collects stats, visible details, text blocks, and active overlays', () => {
    document.body.innerHTML = `
      <div class="ant-breadcrumb-link">管理端</div>
      <div class="ant-breadcrumb-link">智能体中心</div>
      <div class="ant-statistic">
        <div class="ant-statistic-title">调用次数</div>
        <div class="ant-statistic-content">128</div>
      </div>
      <div class="ant-descriptions-item">
        <div class="ant-descriptions-item-label">状态</div>
        <div class="ant-descriptions-item-content">运行中</div>
      </div>
      <main>
        <p>这是页面上的第一段说明文字，用于帮助 AI 理解当前业务上下文。</p>
        <p>这是页面上的第二段摘要，描述了当前列表和配置的作用。</p>
      </main>
      <button>新建智能体</button>
      <div class="ant-tabs-tab ant-tabs-tab-active">概览</div>
      <div class="ant-tabs-tab">日志</div>
      <div class="ant-modal">
        <div class="ant-modal-title">新建供应商</div>
        <div class="ant-modal-body">
          <p>请填写供应商名称和接入参数。</p>
        </div>
      </div>
      <div class="ant-drawer-content">
        <div class="ant-drawer-title">调试面板</div>
        <div class="ant-drawer-body">
          <p>这里展示最近一次请求的诊断信息。</p>
        </div>
      </div>
    `;

    const snapshot = scanDomSemantics();

    expect(snapshot).not.toBeNull();
    expect(snapshot?.page_title).toBe('智能体中心');
    expect(snapshot?.stat_cards).toEqual([{ label: '调用次数', value: '128' }]);
    expect(snapshot?.detail_fields).toContainEqual({
      label: '状态',
      value: '运行中',
    });
    expect(snapshot?.text_blocks[0]).toContain('第一段说明文字');
    expect(snapshot?.action_buttons).toContain('新建智能体');
    expect(snapshot?.tabs).toContainEqual({
      active: true,
      label: '概览',
    });
    expect(snapshot?.overlays).toContainEqual(
      expect.objectContaining({
        title: '新建供应商',
        type: 'modal',
      }),
    );
    expect(snapshot?.overlays).toContainEqual({
      summary: '这里展示最近一次请求的诊断信息。',
      title: '调试面板',
      type: 'drawer',
    });
  });

  it('trims oversized snapshots back under the output budget', () => {
    const longText = '这是一个很长的页面摘要段落。'.repeat(24);
    const detailFields = Array.from(
      { length: 16 },
      (_, index) => `
      <div class="ant-descriptions-item">
        <div class="ant-descriptions-item-label">字段${index}</div>
        <div class="ant-descriptions-item-content">${longText}</div>
      </div>
    `,
    ).join('');
    const paragraphs = Array.from(
      { length: 10 },
      () => `<main><p>${longText}</p></main>`,
    ).join('');

    document.body.innerHTML = `
      <h1>超长页面</h1>
      ${detailFields}
      ${paragraphs}
      <div class="ant-modal">
        <div class="ant-modal-title">超长弹窗</div>
        <div class="ant-modal-body"><p>${longText}</p></div>
      </div>
    `;

    const snapshot = scanDomSemantics();

    expect(snapshot).not.toBeNull();
    const size = new TextEncoder().encode(JSON.stringify(snapshot)).length;
    expect(size).toBeLessThanOrEqual(3072);
    expect((snapshot?.detail_fields.length ?? 0) <= 8).toBe(true);
    expect((snapshot?.text_blocks.length ?? 0) <= 4).toBe(true);
  });
});
