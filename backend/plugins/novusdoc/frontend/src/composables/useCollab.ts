/**
 * NovusDoc 协作集成 composable
 *
 * 检测 NovusDoc Pro 插件是否加载，如果是则：
 * 1. 创建 CollabClient（Socket.IO + Yjs）
 * 2. 生成 Tiptap Collaboration + CollaborationCursor 扩展
 * 3. 管理连接生命周期和在线用户列表
 *
 * 如果 Pro 未加载，返回空扩展列表，编辑器正常工作（无协作）。
 */

import { ref, onUnmounted } from 'vue';
import type { AnyExtension } from '@tiptap/core';

const DEFAULT_ANONYMOUS_NAME = 'Anonymous';

const CURSOR_COLORS = [
  '#F87171', '#FB923C', '#FBBF24', '#34D399',
  '#60A5FA', '#A78BFA', '#F472B6', '#2DD4BF',
];

function pickColor(userId: number | null): string {
  if (!userId) return CURSOR_COLORS[0]!;
  return CURSOR_COLORS[userId % CURSOR_COLORS.length]!;
}

export interface CollabUser {
  userId: number | null;
  username: string | null;
  color: string;
}

interface CollabClientLike {
  doc: unknown;
  awareness: unknown;
  isConnected: boolean;
  connect(): Promise<void>;
  disconnect(): void;
  destroy(): void;
}

/**
 * 检测 NovusDoc Pro 是否已加载
 */
function isProLoaded(): boolean {
  const w = window as unknown as Record<string, unknown>;
  const proMod = w.NovusPlugin_novusdoc_pro as Record<string, unknown> | undefined;
  return !!proMod?.CollabClient;
}

/**
 * 从 plugin-shared 获取 JWT token
 */
function getToken(): string | null {
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as { getAuthToken?: () => string | null } | undefined;
  return shared?.getAuthToken?.() ?? null;
}

/**
 * 获取后端 API 基础 URL（用于 Socket.IO 连接）
 *
 * 开发环境下 window.location.origin 指向前端 dev server（如 localhost:5666），
 * 但 Socket.IO 必须连接到后端（如 localhost:8000）。
 * 通过 requestClient.getBaseUrl() 获取正确的后端地址。
 */
function getServerUrl(): string {
  try {
    const shared = (window as unknown as Record<string, unknown>)
      .NovusPluginShared as { requestClient?: { getBaseUrl?: () => string | undefined } } | undefined;
    const baseUrl = shared?.requestClient?.getBaseUrl?.();
    if (baseUrl) {
      // baseUrl 可能是 "http://127.0.0.1:8000" 或 "/api" 等
      // 如果是绝对 URL 直接使用，否则用 window.location.origin 拼接
      if (baseUrl.startsWith('http://') || baseUrl.startsWith('https://')) {
        return baseUrl.replace(/\/+$/, '');
      }
      return `${window.location.origin}${baseUrl}`.replace(/\/+$/, '');
    }
  } catch { /* fallback */ }
  return window.location.origin;
}

/**
 * 获取当前用户信息（从宿主 plugin-shared API）
 */
function getCurrentUser(): { userId: number | null; username: string | null } {
  try {
    const shared = (window as unknown as Record<string, unknown>)
      .NovusPluginShared as Record<string, unknown> | undefined;
    if (shared?.getCurrentUser) {
      const userFn = shared.getCurrentUser as () => { id?: number; userId?: number; username?: string; name?: string } | null;
      const u = userFn();
      if (u) {
        return {
          userId: u.id ?? u.userId ?? null,
          username: u.username ?? u.name ?? DEFAULT_ANONYMOUS_NAME,
        };
      }
    }
    return { userId: null, username: DEFAULT_ANONYMOUS_NAME };
  } catch {
    return { userId: null, username: DEFAULT_ANONYMOUS_NAME };
  }
}

export interface UseCollabReturn {
  /** 是否启用协作（Pro 已加载且连接成功） */
  collabEnabled: ReturnType<typeof ref<boolean>>;
  /** 在线协作用户列表 */
  onlineUsers: ReturnType<typeof ref<CollabUser[]>>;
  /** 需要注入到编辑器的额外扩展（Collaboration + CollaborationCursor） */
  collabExtensions: AnyExtension[];
  /** 连接协作服务 */
  connect: () => Promise<void>;
  /** 断开协作 */
  disconnect: () => void;
}

export function useCollab(docId: number): UseCollabReturn {
  const collabEnabled = ref(false);
  const onlineUsers = ref<CollabUser[]>([]);
  const collabExtensions: AnyExtension[] = [];
  let collabClient: CollabClientLike | null = null;

  if (isProLoaded() && docId > 0) {
    const token = getToken();
    if (token) {
      try {
        const proMod = (window as unknown as Record<string, Record<string, unknown>>)
          .NovusPlugin_novusdoc_pro;

        const CollabClientClass = proMod.CollabClient as new (opts: Record<string, unknown>) => CollabClientLike;
        const user = getCurrentUser();

        collabClient = new CollabClientClass({
          serverUrl: getServerUrl(),
          token,
          docId,
          user: {
            userId: user.userId,
            username: user.username,
            color: '',
          },
          onUsersChange: (users: CollabUser[]) => {
            onlineUsers.value = users;
          },
          onError: (msg: string) => {
            console.warn('[novusdoc] collab error:', msg);
          },
        });

        // 动态导入 Tiptap Collaboration 扩展
        // 这些扩展由宿主 app 或 novusdoc-pro 提供
        _createCollabExtensions(collabClient, user, collabExtensions);
      } catch (e) {
        console.warn('[novusdoc] Failed to initialize collaboration:', e);
      }
    }
  }

  async function connect() {
    if (!collabClient) return;
    try {
      await collabClient.connect();
      collabEnabled.value = true;
    } catch (e) {
      console.warn('[novusdoc] collab connect failed:', e);
    }
  }

  function disconnect() {
    if (collabClient) {
      collabClient.disconnect();
      collabEnabled.value = false;
    }
  }

  onUnmounted(() => {
    if (collabClient) {
      collabClient.destroy();
      collabClient = null;
      collabEnabled.value = false;
      onlineUsers.value = [];
    }
  });

  return {
    collabEnabled,
    onlineUsers,
    collabExtensions,
    connect,
    disconnect,
  };
}

/**
 * 创建 Tiptap Collaboration 和 CollaborationCursor 扩展
 *
 * 使用 CollabClient 提供的 Y.Doc 实例。
 * Collaboration 扩展将编辑器内容绑定到 Y.Doc 的 "default" fragment。
 * CollaborationCursor 扩展通过 Yjs Awareness 显示其他用户的光标位置。
 */
function _createCollabExtensions(
  client: CollabClientLike,
  user: { userId: number | null; username: string | null },
  extensions: AnyExtension[],
): void {
  try {
    // 尝试从 novusdoc-pro 暴露的模块获取扩展
    const proMod = (window as unknown as Record<string, Record<string, unknown>>)
      .NovusPlugin_novusdoc_pro;

    // Collaboration 扩展需要 @tiptap/extension-collaboration
    // 这些通常由 Pro 插件提供或宿主已安装
    const Collaboration = proMod?.Collaboration as { configure?: (opts: unknown) => AnyExtension } | undefined;
    const CollaborationCursor = proMod?.CollaborationCursor as { configure?: (opts: unknown) => AnyExtension } | undefined;

    if (Collaboration?.configure) {
      extensions.push(
        Collaboration.configure({
          document: client.doc,
        }),
      );
    }

    if (CollaborationCursor?.configure && client.awareness) {
      extensions.push(
        CollaborationCursor.configure({
          provider: { awareness: client.awareness },
          user: {
            name: user.username || DEFAULT_ANONYMOUS_NAME,
            color: pickColor(user.userId),
          },
        }),
      );
    }
  } catch (e) {
    console.warn('[novusdoc] Failed to create collab extensions:', e);
  }
}
