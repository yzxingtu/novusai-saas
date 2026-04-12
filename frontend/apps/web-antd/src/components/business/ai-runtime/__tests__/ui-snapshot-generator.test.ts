import { describe, expect, it } from 'vitest';

import type { PageContextSuggestedTool } from '#/api/shared/ai-chat';
import type { UISnapshotInput } from '../ui-snapshot-generator';

import { UISnapshotGenerator } from '../ui-snapshot-generator';

function buildInput(nodeCount = 40): UISnapshotInput {
  const primaryTools: PageContextSuggestedTool[] = [
    'ui_get_snapshot',
    'ui_read_region',
  ];
  const secondaryTools: PageContextSuggestedTool[] = ['ui_list_interactables'];

  return {
    active_form_session_id: 'form-1',
    active_form_summary: {
      can_submit: false,
      entity_name: 'Agent',
      form_session_id: 'form-1',
      mode: 'edit' as const,
      remaining_required_fields: ['name', 'model'],
      stage: 'ready' as const,
      submit_policy: 'confirm' as const,
    },
    active_surface_id: 'drawer-1',
    form_sessions: [
      {
        can_submit: false,
        entity_name: 'Agent',
        form_session_id: 'form-1',
        mode: 'edit' as const,
        remaining_required_fields: ['name'],
        stage: 'ready' as const,
        submit_policy: 'confirm' as const,
      },
    ],
    nodes: Array.from({ length: nodeCount }).map((_, index) => ({
      content: `content-${index}-${'x'.repeat(400)}`,
      interactable: index % 2 === 0,
      kind: index % 3 === 0 ? 'button' : 'text',
      locator: `node-${index}`,
      node_id: `node-${index}`,
      text: `node text ${index}`,
      title: `node title ${index}`,
    })),
    suggested_tools: {
      primary: primaryTools,
      reason: 'Need quick structure first.',
      secondary: secondaryTools,
    },
    surface_stack: [
      { kind: 'page' as const, surface_id: 'page-1', title: 'Agents' },
      { kind: 'drawer' as const, surface_id: 'drawer-1', title: 'Edit Agent' },
    ],
    ui_epoch: 12,
  };
}

describe('ui-snapshot-generator', () => {
  it('generates compact snapshot without heavy content and keeps byte budget', () => {
    const generator = new UISnapshotGenerator({
      compactMaxBytes: 4 * 1024,
      compactNodeLimit: 120,
      textPreviewLength: 60,
    });

    const snapshot = generator.generateSnapshot(buildInput(120), 'compact');

    expect(snapshot.mode).toBe('compact');
    expect(snapshot.size_bytes).toBeLessThanOrEqual(4 * 1024);
    expect(snapshot.nodes.length).toBeGreaterThan(0);
    expect(
      snapshot.nodes.every((node) => typeof node.content === 'undefined'),
    ).toBe(true);
    expect(snapshot.interactables_count).toBeGreaterThan(0);
  });

  it('generates full snapshot with content previews', () => {
    const generator = new UISnapshotGenerator({
      fullMaxBytes: 30 * 1024,
      textPreviewLength: 80,
    });

    const snapshot = generator.generateSnapshot(buildInput(16), 'full');

    expect(snapshot.mode).toBe('full');
    expect(snapshot.nodes.length).toBe(16);
    expect(
      snapshot.nodes.some(
        (node) => typeof node.content === 'string' && node.content.length > 0,
      ),
    ).toBe(true);
  });

  it('builds thin page context from generated snapshot', () => {
    const generator = new UISnapshotGenerator();
    const snapshot = generator.generateSnapshot(buildInput(8), 'compact');

    const pageContext = generator.buildThinPageContext({
      locale: 'zh-CN',
      pageKey: 'admin.ai.agents',
      pageSessionId: 'session-1',
      pageTitle: 'Agent List',
      snapshot,
    });

    expect(pageContext.locale).toBe('zh-CN');
    expect(pageContext.page_key).toBe('admin.ai.agents');
    expect(pageContext.page_session_id).toBe('session-1');
    expect(pageContext.ui_epoch).toBe(12);
    expect(pageContext.surface_stack?.length).toBe(2);
    expect(pageContext.active_form_summary?.form_session_id).toBe('form-1');
    expect(pageContext.suggested_tools?.primary).toEqual([
      'ui_get_snapshot',
      'ui_read_region',
    ]);
  });

  it('normalizes and truncates surface stack and form sessions with fallbacks', () => {
    const generator = new UISnapshotGenerator();
    const input = buildInput(3);

    input.active_surface_id = '   ';
    input.active_form_session_id = '   ';
    input.ui_epoch = Number.POSITIVE_INFINITY;
    input.surface_stack = [
      { kind: 'page', surface_id: '   ', title: 'ignored' },
      ...Array.from({ length: 15 }).map((_, index) => ({
        kind: index % 2 === 0 ? ('drawer' as const) : ('page' as const),
        surface_id: `surface-${Math.min(index, 12)}`,
        title: `Surface ${index}`,
      })),
      { kind: 'drawer', surface_id: 'surface-1', title: 'dup' },
    ];
    input.form_sessions = [
      {
        ...input.active_form_summary,
        form_session_id: '   ',
      },
      ...Array.from({ length: 12 }).map((_, index) => ({
        can_submit: false,
        entity_name: `Entity ${index}`,
        form_session_id: `form-${Math.min(index, 9)}`,
        mode: 'edit' as const,
        remaining_required_fields:
          index % 2 === 0
            ? [
                'a',
                '',
                '   ',
                ...Array.from({ length: 40 }).map((__, i) => `${i}`),
              ]
            : (undefined as unknown as string[]),
        stage: 'ready' as const,
        submit_policy: 'confirm' as const,
      })),
    ];

    const snapshot = generator.generateSnapshot(input, 'compact');

    expect(snapshot.surface_stack).toHaveLength(12);
    expect(snapshot.surface_stack.map((item) => item.surface_id)).toEqual([
      'surface-0',
      'surface-1',
      'surface-2',
      'surface-3',
      'surface-4',
      'surface-5',
      'surface-6',
      'surface-7',
      'surface-8',
      'surface-9',
      'surface-10',
      'surface-11',
    ]);
    expect(snapshot.active_surface_id).toBe('surface-11');

    expect(snapshot.form_sessions).toHaveLength(8);
    expect(snapshot.form_sessions[0]?.form_session_id).toBe('form-0');
    expect(snapshot.form_sessions[0]?.remaining_required_fields).toEqual([
      'a',
      '0',
      '1',
      '2',
      '3',
      '4',
      '5',
      '6',
      '7',
      '8',
      '9',
      '10',
      '11',
      '12',
      '13',
      '14',
      '15',
      '16',
      '17',
      '18',
      '19',
      '20',
      '21',
      '22',
      '23',
      '24',
      '25',
      '26',
      '27',
      '28',
      '29',
      '30',
    ]);
    expect(snapshot.form_sessions[1]?.remaining_required_fields).toEqual([]);
    expect(snapshot.active_form_session_id).toBe('form-1');
    expect(snapshot.ui_epoch).toBe(0);
  });

  it('handles empty form sessions and normalizes nodes with fallback ids and counts', () => {
    const generator = new UISnapshotGenerator({
      compactNodeLimit: 10,
      fullMaxBytes: 1024 * 1024,
      textPreviewLength: 30,
    });
    const input = buildInput(0);
    input.form_sessions = [];
    input.nodes = [
      undefined as unknown as (typeof input.nodes)[number],
      {
        children_count: -3.8,
        content: '',
        kind: 'button',
        locator: 'locator-node',
        node_id: '',
        text: 'locator fallback',
      },
      {
        children_count: 1.1,
        kind: '   ',
        node_id: 'kind-node',
        text: 'kind fallback',
      },
    ];

    const snapshot = generator.generateSnapshot(input, 'full');

    expect(snapshot.form_sessions).toEqual([]);
    expect(snapshot.nodes).toHaveLength(2);
    expect(snapshot.nodes[0]).toMatchObject({
      children_count: 0,
      kind: 'button',
      node_id: 'locator-node',
      summary: 'locator fallback',
    });
    expect(snapshot.nodes[0]?.content).toBe('locator fallback');
    expect(snapshot.nodes[1]).toMatchObject({
      children_count: 1,
      kind: 'unknown',
      node_id: 'kind-node',
      summary: 'kind fallback',
    });

    const fallbackIdSnapshot = generator.generateSnapshot(
      {
        ...buildInput(0),
        nodes: [
          {
            children_count: 2.9,
            kind: 'fallback-kind',
            text: 'node id from kind-index',
          },
        ],
      },
      'full',
    );
    expect(fallbackIdSnapshot.nodes).toHaveLength(1);
    expect(fallbackIdSnapshot.nodes[0]).toMatchObject({
      children_count: 2,
      kind: 'fallback-kind',
      node_id: 'fallback-kind-0',
      summary: 'node id from kind-index',
    });
  });

  it('compacts by budget via node clipping and full-mode content/summary shrinking', () => {
    const clippingGenerator = new UISnapshotGenerator({
      compactMaxBytes: 1200,
      compactNodeLimit: 160,
      textPreviewLength: 140,
    });
    const compactSnapshot = clippingGenerator.generateSnapshot(buildInput(80), 'compact');

    expect(compactSnapshot.truncated).toBe(true);
    expect(compactSnapshot.nodes.length).toBeLessThan(80);
    expect(compactSnapshot.size_bytes).toBeLessThanOrEqual(1200);

    const shrinkingGenerator = new UISnapshotGenerator({
      fullMaxBytes: 700,
      textPreviewLength: 500,
    });
    const fullInput = buildInput(1);
    fullInput.nodes = [
      {
        content: `content-${'x'.repeat(2500)}`,
        kind: 'text',
        node_id: 'single-1',
        text: `summary-${'y'.repeat(600)}`,
      },
    ];

    const fullSnapshot = shrinkingGenerator.generateSnapshot(fullInput, 'full');

    expect(fullSnapshot.truncated).toBe(true);
    expect(fullSnapshot.nodes).toHaveLength(1);
    expect(fullSnapshot.nodes[0]?.content?.length).toBeLessThanOrEqual(515);
    expect(fullSnapshot.nodes[0]?.summary?.length).toBeLessThanOrEqual(83);
  });
});
