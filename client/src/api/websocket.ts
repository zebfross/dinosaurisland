// WebSocket connection manager

import { BASE_URL } from './client';
import type { WsMessage } from './types';

type MessageHandler = (msg: WsMessage) => void;

export class GameWebSocket {
  private ws: WebSocket | null = null;
  private handlers: MessageHandler[] = [];
  private gameId: string;
  private reconnectTimeout: number | null = null;
  private spectator: boolean;

  constructor(gameId: string, spectator = true) {
    this.gameId = gameId;
    this.spectator = spectator;
  }

  connect(token?: string) {
    // Build WebSocket URL
    let wsBase: string;
    if (BASE_URL) {
      // Explicit backend URL (dev mode) — convert http(s) to ws(s)
      wsBase = BASE_URL.replace(/^http/, 'ws');
    } else {
      // Same origin (production) — derive from current page
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsBase = `${proto}//${window.location.host}`;
    }
    const path = this.spectator
      ? `/ws/spectate/${this.gameId}`
      : `/ws/games/${this.gameId}?token=${token}`;
    const url = `${wsBase}${path}`;

    this.ws = new WebSocket(url);

    this.ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        this.handlers.forEach(h => h(msg));
      } catch {
        // ignore parse errors
      }
    };

    this.ws.onclose = () => {
      // Reconnect after 2s
      this.reconnectTimeout = window.setTimeout(() => this.connect(token), 2000);
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  onMessage(handler: MessageHandler) {
    this.handlers.push(handler);
    return () => {
      this.handlers = this.handlers.filter(h => h !== handler);
    };
  }

  ping() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'ping' }));
    }
  }

  disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }
    this.ws?.close();
    this.ws = null;
    this.handlers = [];
  }
}
