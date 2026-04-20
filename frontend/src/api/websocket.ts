/**
 * WebSocket client for Forge v2.
 *
 * Replaces the SSE-based chat.ts. Handles:
 * - Persistent WebSocket connection with auto-reconnect
 * - Heartbeat ping every 5 minutes
 * - Offline message queue (messages typed while disconnected)
 * - Frame reassembly for chunked messages
 * - All chat and session actions over a single connection
 */

export type ServerMessage =
  | { type: 'connected'; user_id: string }
  | { type: 'session'; session_id: string; session_type: string; program_week?: number }
  | { type: 'session_update'; session_id: string; title: string }
  | { type: 'token'; session_id: string; content: string }
  | { type: 'tool_call'; session_id: string; tool: string; tool_call_id: string; args: Record<string, unknown> }
  | { type: 'tool_result'; session_id: string; tool_call_id: string; result: string }
  | { type: 'done'; session_id: string; usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null }
  | { type: 'error'; session_id?: string; message: string }
  | { type: 'intake_progress'; session_id: string; checklist: Array<{ field: string; label: string; done: boolean; value?: string }> }
  | { type: 'intake_complete'; session_id: string; suggestions: string[] }
  | { type: 'tip_ready'; session_id: string; tool_call_id?: string; title: string; content: string; tags: string[]; department: string }
  | { type: 'collab_ready'; session_id: string; tool_call_id?: string; title: string; problem: string; needed_skills: string[]; time_commitment: string; tags: string[]; department: string }
  | { type: 'idea_ready'; session_id: string; tool_call_id?: string; title: string; description: string; tags: string[] }
  | { type: 'pong' }
  | { type: 'ping' }
  | { type: 'chunk'; chunk_id: string; seq: number; total: number; data: string };

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

type MessageHandler = (msg: ServerMessage) => void;
type StatusHandler = (status: ConnectionStatus) => void;

let getTokenFn: (() => Promise<string | null>) | null = null;

export function setWsTokenGetter(fn: () => Promise<string | null>) {
  getTokenFn = fn;
}

const WS_BASE = import.meta.env.VITE_WS_URL || '';

class ForgeWebSocket {
  private ws: WebSocket | null = null;
  private messageHandlers: Set<MessageHandler> = new Set();
  private statusHandlers: Set<StatusHandler> = new Set();
  private status: ConnectionStatus = 'disconnected';
  private reconnectAttempt = 0;
  private maxReconnectDelay = 30000; // 30s max
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private offlineQueue: string[] = [];
  private chunkBuffers: Map<string, { total: number; parts: Map<number, string> }> = new Map();
  private intentionalClose = false;

  get connectionStatus(): ConnectionStatus {
    return this.status;
  }

  get isConnected(): boolean {
    return this.status === 'connected';
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }

  private setStatus(status: ConnectionStatus) {
    this.status = status;
    this.statusHandlers.forEach(h => h(status));
  }

  async connect() {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.setStatus('connecting');
    const token = await getTokenFn?.();
    if (!token) {
      this.setStatus('disconnected');
      return;
    }

    // Build WebSocket URL
    let wsUrl: string;
    if (WS_BASE) {
      wsUrl = `${WS_BASE}?token=${encodeURIComponent(token)}`;
    } else {
      // Derive from current page URL
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(token)}`;
    }

    // Masquerade: append target email so the backend swaps identity
    const masquerade = localStorage.getItem('forge-masquerade');
    if (masquerade) {
      wsUrl += `&masquerade=${encodeURIComponent(masquerade)}`;
    }

    try {
      this.ws = new WebSocket(wsUrl);
    } catch {
      this.setStatus('disconnected');
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempt = 0;
      // Don't set connected yet - wait for the 'connected' message from server
      this.startHeartbeat();
      // Flush offline queue
      this.flushQueue();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as ServerMessage;
        this.handleMessage(msg);
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      if (!this.intentionalClose) {
        this.setStatus('reconnecting');
        this.scheduleReconnect();
      } else {
        this.setStatus('disconnected');
      }
    };

    this.ws.onerror = () => {
      // onclose will fire after onerror
    };
  }

  disconnect() {
    this.intentionalClose = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('disconnected');
  }

  send(action: Record<string, unknown>) {
    const raw = JSON.stringify(action);
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(raw);
    } else {
      // Queue for when connection restores
      this.offlineQueue.push(raw);
    }
  }

  // Convenience methods for common actions
  startSession(type: string, ideaId?: string, message?: string) {
    const msg: Record<string, unknown> = { action: 'start_session', type };
    if (ideaId) msg.idea_id = ideaId;
    if (message) msg.message = message;
    this.send(msg);
  }

  chat(sessionId: string, message: string) {
    this.send({ action: 'chat', session_id: sessionId, message });
  }

  cancel(sessionId: string) {
    this.send({ action: 'cancel', session_id: sessionId });
  }

  private handleMessage(msg: ServerMessage) {
    // Handle chunk reassembly
    if (msg.type === 'chunk') {
      this.handleChunk(msg);
      return;
    }

    // Handle connection confirmation
    if (msg.type === 'connected') {
      this.setStatus('connected');
    }

    // Handle server pings
    if (msg.type === 'ping') {
      this.send({ action: 'ping' });
      return;
    }

    // Dispatch to handlers
    this.messageHandlers.forEach(h => h(msg));
  }

  private handleChunk(msg: Extract<ServerMessage, { type: 'chunk' }>) {
    let buffer = this.chunkBuffers.get(msg.chunk_id);
    if (!buffer) {
      buffer = { total: msg.total, parts: new Map() };
      this.chunkBuffers.set(msg.chunk_id, buffer);
    }
    buffer.parts.set(msg.seq, msg.data);

    if (buffer.parts.size === buffer.total) {
      // Reassemble
      const parts: string[] = [];
      for (let i = 0; i < buffer.total; i++) {
        parts.push(buffer.parts.get(i) || '');
      }
      const full = parts.join('');
      this.chunkBuffers.delete(msg.chunk_id);

      try {
        const reassembled = JSON.parse(full) as ServerMessage;
        this.handleMessage(reassembled);
      } catch {
        // Ignore malformed reassembled message
      }
    }
  }

  private flushQueue() {
    while (this.offlineQueue.length > 0) {
      const raw = this.offlineQueue.shift()!;
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(raw);
      } else {
        this.offlineQueue.unshift(raw);
        break;
      }
    }
  }

  private scheduleReconnect() {
    if (this.intentionalClose) return;

    const delay = Math.min(
      1000 * Math.pow(2, this.reconnectAttempt),
      this.maxReconnectDelay,
    );
    this.reconnectAttempt++;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send({ action: 'ping' });
      }
    }, 300000); // 5 minutes
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
}

// Singleton instance
export const forgeWs = new ForgeWebSocket();
