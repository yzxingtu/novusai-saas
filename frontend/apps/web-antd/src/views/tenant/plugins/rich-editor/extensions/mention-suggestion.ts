/**
 * Mention suggestion 配置
 *
 * 为 @tiptap/extension-mention 提供 suggestion 选项
 * 使用 VueRenderer 渲染 MentionList.vue 浮窗
 */
import { VueRenderer } from '@tiptap/vue-3';
import tippy, { type Instance as TippyInstance } from 'tippy.js';

import MentionList from '../components/MentionList.vue';

import type { SuggestionOptions, SuggestionProps } from '@tiptap/suggestion';

export interface MentionUser {
  id: number;
  label: string;
  avatar?: string;
}

/**
 * 创建 Mention suggestion 配置
 *
 * @param fetchUsers - 异步搜索用户函数
 */
export function createMentionSuggestion(
  fetchUsers: (query: string) => Promise<MentionUser[]>,
): Partial<SuggestionOptions> {
  return {
    items: async ({ query }: { query: string }) => {
      if (!query) return [];
      return fetchUsers(query);
    },

    render: () => {
      let component: VueRenderer;
      let popup: TippyInstance[];

      return {
        onStart: (props: SuggestionProps) => {
          component = new VueRenderer(MentionList, {
            props,
            editor: props.editor,
          });

          if (!props.clientRect) return;

          popup = tippy('body', {
            getReferenceClientRect: props.clientRect as () => DOMRect,
            appendTo: () => document.body,
            content: component.element,
            showOnCreate: true,
            interactive: true,
            trigger: 'manual',
            placement: 'bottom-start',
          });
        },

        onUpdate(props: SuggestionProps) {
          component?.updateProps(props);

          if (!props.clientRect) return;

          popup?.[0]?.setProps({
            getReferenceClientRect: props.clientRect as () => DOMRect,
          });
        },

        onKeyDown(props: { event: KeyboardEvent }) {
          if (props.event.key === 'Escape') {
            popup?.[0]?.hide();
            return true;
          }

          return (component?.ref as unknown as { onKeyDown: (event: KeyboardEvent) => boolean })
            ?.onKeyDown(props.event);
        },

        onExit() {
          popup?.[0]?.destroy();
          component?.destroy();
        },
      };
    },
  };
}
