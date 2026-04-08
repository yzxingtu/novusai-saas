import { describe, expect, it } from 'vitest';

import type { PageContextSuggestedTool } from '#/api/shared/ai-chat';

import { UISnapshotGenerator } from '../ui-snapshot-generator';

function buildInput(nodeCount = 40) {
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
      pageKey: 'admin.ai.agents',
      pageSessionId: 'session-1',
      pageTitle: 'Agent List',
      snapshot,
    });

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
});
