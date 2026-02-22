/**
 * SocketIOProvider — 自定义 Y.js 协作 Provider
 *
 * 基于 socket.io-client 连接 /collaboration 命名空间，
 * 将本地 Y.Doc update 事件转发为 Socket 消息，
 * 接收远程 update 并应用到本地 Y.Doc。
 * 实现 Awareness Protocol（光标位置 + 用户信息同步）。
 */
import { io, type Socket } from 'socket.io-client';
import * as Y from 'yjs';
import {
  Awareness,
  encodeAwarenessUpdate,
  applyAwarenessUpdate,
  removeAwarenessStates,
} from 'y-protocols/awareness';

export interface SocketIOProviderOptions {
  /** Socket.IO 服务器地址（不含 path，如 http://localhost:8000） */
  serverUrl: string;
  /** JWT 认证令牌 */
  token: string;
  /** 协作文档 ID */
  documentId: number;
  /** 当前用户信息 */
  user: {
    id: number;
    name: string;
    color?: string;
  };
  /** Socket.IO 路径（默认 /sio） */
  socketPath?: string;
  /** 是否自动重连（默认 true） */
  autoReconnect?: boolean;
}

export class SocketIOProvider {
  readonly doc: Y.Doc;
  readonly awareness: Awareness;

  private socket: Socket | null = null;
  private readonly options: Required<SocketIOProviderOptions>;
  private _synced = false;
  private _connected = false;
  private _destroyed = false;

  constructor(doc: Y.Doc, options: SocketIOProviderOptions) {
    this.doc = doc;
    this.awareness = new Awareness(doc);
    this.options = {
      socketPath: '/sio',
      autoReconnect: true,
      ...options,
      user: {
        color: '#2196F3',
        ...options.user,
      },
    };

    this._setupDocListeners();
    this._setupAwarenessListeners();
    this.connect();
  }

  get synced(): boolean {
    return this._synced;
  }

  get connected(): boolean {
    return this._connected;
  }

  // ==================== 连接管理 ====================

  connect(): void {
    if (this._destroyed || this.socket) return;

    this.socket = io(`${this.options.serverUrl}/collaboration`, {
      path: this.options.socketPath,
      transports: ['websocket'],
      auth: { token: this.options.token },
      autoConnect: true,
      reconnection: this.options.autoReconnect,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
    });

    this._setupSocketListeners();
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.emit('leave_doc', {
        document_id: this.options.documentId,
      });
      this.socket.disconnect();
      this.socket = null;
    }
    this._connected = false;
    this._synced = false;
  }

  destroy(): void {
    this._destroyed = true;
    this.disconnect();

    // 清理 awareness
    removeAwarenessStates(
      this.awareness,
      [this.doc.clientID],
      'provider destroyed',
    );

    // 移除 doc 监听器
    this.doc.off('update', this._onDocUpdate);
    this.awareness.off('update', this._onAwarenessUpdate);
  }

  // ==================== Socket 事件处理 ====================

  private _setupSocketListeners(): void {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      this._connected = true;
      // 加入文档房间
      this.socket?.emit('join_doc', {
        document_id: this.options.documentId,
        color: this.options.user.color,
      });

      // 设置本地 awareness 用户信息
      this.awareness.setLocalStateField('user', {
        id: this.options.user.id,
        name: this.options.user.name,
        color: this.options.user.color,
      });
    });

    this.socket.on('disconnect', () => {
      this._connected = false;
      this._synced = false;
    });

    // 初始 Y.js 快照
    this.socket.on('yjs_snapshot', (data: ArrayBuffer | Uint8Array) => {
      const update = new Uint8Array(data);
      Y.applyUpdate(this.doc, update, 'server');
      this._synced = true;
    });

    // 远程 Y.js 增量更新
    this.socket.on('yjs_update', (data: ArrayBuffer | Uint8Array) => {
      const update = new Uint8Array(data);
      Y.applyUpdate(this.doc, update, 'remote');
    });

    // 远程 awareness 更新
    this.socket.on(
      'awareness_update',
      (data: ArrayBuffer | Uint8Array) => {
        applyAwarenessUpdate(
          this.awareness,
          new Uint8Array(data),
          'remote',
        );
      },
    );

    // 用户加入/离开
    this.socket.on('user_joined', (_data: Record<string, unknown>) => {
      // 可触发自定义事件
    });

    this.socket.on('user_left', (data: { user_id: number }) => {
      // 移除离开用户的 awareness 状态
      const states = this.awareness.getStates();
      for (const [clientId, state] of states) {
        if (
          (state as Record<string, unknown>)?.user &&
          ((state as Record<string, unknown>).user as Record<string, unknown>)
            ?.id === data.user_id
        ) {
          removeAwarenessStates(
            this.awareness,
            [clientId],
            'user left',
          );
        }
      }
    });

    // 在线用户列表
    this.socket.on(
      'doc_users',
      (_data: { users: Array<Record<string, unknown>> }) => {
        // 可用于更新在线用户列表 UI
      },
    );

    this.socket.on('error', (_data: { message: string }) => {
      // 错误处理
    });
  }

  // ==================== Y.Doc 更新监听 ====================

  private _setupDocListeners(): void {
    this.doc.on('update', this._onDocUpdate);
  }

  private _onDocUpdate = (
    update: Uint8Array,
    origin: unknown,
  ): void => {
    // 只转发本地产生的更新，忽略从远程/服务端收到的更新
    if (origin === 'remote' || origin === 'server') return;
    if (!this.socket?.connected) return;

    this.socket.emit('yjs_update', update);
  };

  // ==================== 光标感知监听 ====================

  private _setupAwarenessListeners(): void {
    this.awareness.on('update', this._onAwarenessUpdate);
  }

  private _onAwarenessUpdate = (
    {
      added,
      updated,
      removed,
    }: { added: number[]; updated: number[]; removed: number[] },
    origin: unknown,
  ): void => {
    if (origin === 'remote') return;
    if (!this.socket?.connected) return;

    const changedClients = [...added, ...updated, ...removed];
    const update = encodeAwarenessUpdate(this.awareness, changedClients);
    this.socket.emit('awareness_update', update);
  };
}
