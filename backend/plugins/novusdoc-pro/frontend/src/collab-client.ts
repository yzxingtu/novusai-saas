/**
 * NovusDoc Pro 协作客户端
 *
 * 封装 Socket.IO 连接 + Yjs 同步协议，供编辑器扩展注入使用。
 *
 * 职责：
 * 1. 连接 /plugin/novusdoc-pro/collab namespace（JWT 鉴权）
 * 2. 管理 join_doc / leave_doc 生命周期
 * 3. 转发 yjs_update / awareness_update 事件
 * 4. 提供 Yjs Y.Doc 实例供 Collaboration 扩展使用
 * 5. 断线重连与状态恢复
 *
 * 依赖：通过宿主 window 暴露的 socket.io-client（或独立引入）
 */

import * as Y from 'yjs';
import { Awareness, applyAwarenessUpdate, encodeAwarenessUpdate } from 'y-protocols/awareness';

const COLLAB_NAMESPACE = '/plugin/novusdoc-pro/collab';

export interface CollabUser {
  userId: number | null;
  username: string | null;
  color: string;
}

export interface CollabClientOptions {
  serverUrl?: string;
  token: string;
  docId: number;
  user: CollabUser;
  onUsersChange?: (users: CollabUser[]) => void;
  onError?: (message: string) => void;
}

const CURSOR_COLORS = [
  '#F87171', '#FB923C', '#FBBF24', '#34D399',
  '#60A5FA', '#A78BFA', '#F472B6', '#2DD4BF',
];

function pickColor(userId: number | null): string {
  if (!userId) return CURSOR_COLORS[0]!;
  return CURSOR_COLORS[userId % CURSOR_COLORS.length]!;
}

export class CollabClient {
  private socket: ReturnType<typeof import('socket.io-client').io> | null = null;
  private ydoc: Y.Doc;
  private _awareness: Awareness;
  private options: CollabClientOptions;
  private connected = false;
  private destroyed = false;
  private _onlineUsers: Map<string, CollabUser> = new Map();

  constructor(options: CollabClientOptions) {
    this.options = {
      ...options,
      user: {
        ...options.user,
        color: options.user.color || pickColor(options.user.userId),
      },
    };
    this.ydoc = new Y.Doc();
    this._awareness = new Awareness(this.ydoc);

    // Set local awareness state with user info
    this._awareness.setLocalStateField('user', {
      name: this.options.user.username || 'Anonymous',
      color: this.options.user.color,
      userId: this.options.user.userId,
    });
  }

  get doc(): Y.Doc {
    return this.ydoc;
  }

  /** Yjs Awareness instance — required by CollaborationCursor extension */
  get awareness(): Awareness {
    return this._awareness;
  }

  get isConnected(): boolean {
    return this.connected;
  }

  async connect(): Promise<void> {
    if (this.destroyed) return;

    try {
      // 动态导入 socket.io-client（宿主已暴露或插件自带）
      const { io } = await import('socket.io-client');

      const serverUrl = this.options.serverUrl || window.location.origin;
      const rawToken = this.options.token;
      const bearerToken = rawToken.startsWith('Bearer ') ? rawToken : `Bearer ${rawToken}`;

      this.socket = io(serverUrl + COLLAB_NAMESPACE, {
        path: '/sio',
        auth: { token: bearerToken },
        transports: ['websocket'],
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 30000,
      });

      this.socket.on('connect', () => {
        this.connected = true;
        this._joinDoc();
      });

      this.socket.on('disconnect', () => {
        this.connected = false;
      });

      this.socket.on('connect_error', (err: Error) => {
        console.warn('[novusdoc-pro] collab connect error:', err.message);
        this.options.onError?.(err.message);
      });

      this.socket.on('error', (data: { message: string; code?: number }) => {
        console.warn('[novusdoc-pro] collab error:', data.message);
        this.options.onError?.(data.message);
      });

      // Yjs 初始状态同步
      this.socket.on('yjs_sync_step1', (data: { state: string }) => {
        try {
          const stateBytes = this._hexToBytes(data.state);
          Y.applyUpdate(this.ydoc, stateBytes, 'remote');
        } catch (e) {
          console.warn('[novusdoc-pro] yjs sync error:', e);
        }
      });

      // 接收远端 Yjs 更新
      this.socket.on('yjs_update', (data: { update: string }) => {
        try {
          const updateBytes = this._hexToBytes(data.update);
          Y.applyUpdate(this.ydoc, updateBytes, 'remote');
        } catch (e) {
          console.warn('[novusdoc-pro] yjs update error:', e);
        }
      });

      // 用户加入/离开通知 — 维护在线用户列表
      this.socket.on('user_joined', (data: { sid: string; user: { user_id?: number; username?: string }; count: number }) => {
        if (data.user) {
          const uid = data.user.user_id ?? null;
          this._onlineUsers.set(data.sid, {
            userId: uid,
            username: data.user.username || 'Anonymous',
            color: pickColor(uid),
          });
        }
        this._emitUsersChange();
      });
      this.socket.on('user_left', (data: { sid: string; count: number }) => {
        this._onlineUsers.delete(data.sid);
        this._emitUsersChange();
      });

      // Awareness 更新：接收远端 awareness
      this.socket.on('awareness_update', (data: { awareness: string; doc_id: number }) => {
        try {
          const awarenessBytes = this._hexToBytes(data.awareness);
          applyAwarenessUpdate(this._awareness, awarenessBytes, 'remote');
        } catch (e) {
          console.error('[novusdoc-pro] awareness update error:', e);
        }
      });

      // 本地 awareness 变更 → 广播
      this._awareness.on('update', ({ added, updated, removed }: { added: number[]; updated: number[]; removed: number[] }) => {
        const changedClients = added.concat(updated).concat(removed);
        const encoded = encodeAwarenessUpdate(this._awareness, changedClients);
        this.socket?.emit('awareness_update', {
          doc_id: this.options.docId,
          awareness: this._bytesToHex(encoded),
        });
      });

      // 本地文档变更 → 广播
      this.ydoc.on('update', (update: Uint8Array, origin: unknown) => {
        if (origin === 'remote') return;
        this.socket?.emit('yjs_update', {
          doc_id: this.options.docId,
          update: this._bytesToHex(update),
        });
      });

    } catch (e) {
      console.warn('[novusdoc-pro] collab client init failed:', e);
    }
  }

  private _joinDoc(): void {
    this.socket?.emit('join_doc', {
      doc_id: this.options.docId,
    });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.emit('leave_doc', {
        doc_id: this.options.docId,
      });
      this.socket.disconnect();
      this.socket = null;
    }
    this.connected = false;
  }

  destroy(): void {
    this.destroyed = true;
    this.disconnect();
    this._awareness.destroy();
    this.ydoc.destroy();
  }

  private _emitUsersChange(): void {
    this.options.onUsersChange?.([...this._onlineUsers.values()]);
  }

  private _hexToBytes(hex: string): Uint8Array {
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < hex.length; i += 2) {
      bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
    }
    return bytes;
  }

  private _bytesToHex(bytes: Uint8Array): string {
    return Array.from(bytes)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  }
}
