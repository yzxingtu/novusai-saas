// @vitest-environment happy-dom
/**
 * Test type: behavioral
 * Verifies: the shared assistant avatar/profile UI stays on the common.globalAiChat
 * copy contract for labels, aria text, and fallback chips across all surfaces.
 * Mock strategy: ant-design popover and icon wrappers plus avatar URL resolution
 * are stubbed, while the profile chip/fallback selection logic runs real.
 */
import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import ChatMessageAgentAvatar from '../ChatMessageAgentAvatar.vue';

vi.mock('#/locales', () => ({
  $t: (key: string, params?: Record<string, unknown>) => {
    if (!params || Object.keys(params).length === 0) {
      return key;
    }
    const suffix = Object.entries(params)
      .toSorted(([left], [right]) => left.localeCompare(right))
      .map(([name, value]) => `${name}=${String(value)}`)
      .join(',');
    return `${key}:${suffix}`;
  },
}));

vi.mock('#/utils/image', () => ({
  toAvatarDisplayUrl: (value: string) => value,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('ant-design-vue', () => ({
  Popover: defineComponent({
    name: 'PopoverStub',
    setup(_, { slots }) {
      return () =>
        h('div', { class: 'popover-stub', 'data-testid': 'popover-stub' }, [
          slots.default?.(),
          h(
            'div',
            { 'data-testid': 'popover-content-stub' },
            slots.content?.(),
          ),
        ]);
    },
  }),
}));

describe('chatMessageAgentAvatar', () => {
  it('uses shared common.globalAiChat keys for labels, aria copy, and fallback chips', () => {
    const wrapper = mount(ChatMessageAgentAvatar, {
      props: {
        agentId: 17,
        agentKnowledgeBases: [
          {
            enabled: true,
            kb_name: 'Trips',
            knowledge_base_id: 101,
          },
          {
            enabled: true,
            knowledge_base_id: 202,
          },
        ],
        agentName: 'Navigator',
        agentSkills: [
          {
            enabled: true,
            package_id: 1,
            package_name: 'Routing',
            skill_id: 21,
          },
          {
            enabled: true,
            name: 'route-planner',
            package_id: 1,
            package_name: 'Routing',
            skill_id: 22,
          },
        ],
        modelName: 'gpt-5.4-mini',
      },
    });

    const rendered = wrapper.text();
    expect(
      wrapper.get('[data-testid="assistant-agent-avatar"]').attributes(),
    ).toMatchObject({
      'aria-label': 'common.globalAiChat.agentProfileAria:agent=Navigator',
    });
    expect(rendered).toContain('common.globalAiChat.noDescription');
    expect(rendered).toContain('common.globalAiChat.skillPackages');
    expect(rendered).toContain('common.globalAiChat.skillEntries');
    expect(rendered).toContain('common.globalAiChat.mentionSectionKbs');
    expect(rendered).toContain('common.globalAiChat.agentProfileHint');
    expect(rendered).toContain(
      'common.globalAiChat.skillBindingFallback:id=21',
    );
    expect(rendered).toContain(
      'common.globalAiChat.knowledgeBaseFallback:id=202',
    );
    expect(rendered).not.toContain('admin.ai.');
  });

  it('uses shared common.globalAiChat empty-state keys when no bindings are present', () => {
    const wrapper = mount(ChatMessageAgentAvatar, {
      props: {
        agentName: 'Navigator',
      },
    });

    const rendered = wrapper.text();
    expect(rendered).toContain('common.globalAiChat.noDescription');
    expect(rendered).toContain('common.globalAiChat.noSkillPackages');
    expect(rendered).toContain('common.globalAiChat.noSkillsInPackage');
    expect(rendered).toContain('common.globalAiChat.noKnowledgeBases');
    expect(rendered).toContain('common.globalAiChat.agentProfileHint');
    expect(rendered).not.toContain('admin.ai.');
  });
});
