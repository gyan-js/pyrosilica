import { useTelemetryStore } from '../stores/telemetryStore';
import { adaptTelemetryFrame } from './frameAdapter';

class TelemetryWSClient {
  constructor(url) {
    this.url = url;
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectDelay = 5000;
    this.intentionalClose = false;
  }

  connect() {
    this.intentionalClose = false;
    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      console.log(`[WS] Connected to ${this.url}`);
      this.reconnectAttempts = 0;

      this.sendCommand({ type: 'subscribe_live' });
    };

    this.socket.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch (err) {
        console.error('[WS] Failed to parse incoming message:', err);
        return;
      }

      if (msg.type === 'backfill') {
        this._handleBackfill(msg.frames ?? []);
        return;
      }

      if (msg.type === 'frame') {
        this._handleFrame(msg.frame);
        return;
      }

      console.warn('[WS] Ignoring message with unrecognized type:', msg.type);
    };

    this.socket.onclose = () => {
      if (!this.intentionalClose) {
        this.attemptReconnect();
      }
    };

    this.socket.onerror = (error) => {
      console.error('[WS] Error:', error);
      this.socket.close();
    };
  }

  _handleBackfill(frames) {
   
    for (const frame of frames) {
      this._handleFrame(frame);
    }
  }

  _handleFrame(frame) {
    if (!frame) return;

 
    if (frame.stream === 'training') {
      useTelemetryStore.getState().ingestTrainingEvent(frame);
      return;
    }

    const { activeGpuProfile } = useTelemetryStore.getState();
    const viewFrame = adaptTelemetryFrame(frame, activeGpuProfile);
    useTelemetryStore.getState().ingestFrame(viewFrame);
  }

  attemptReconnect() {
    const delay = Math.min(1000 * (2 ** this.reconnectAttempts), this.maxReconnectDelay);
    console.log(`[WS] Reconnecting in ${delay}ms...`);
    setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  sendCommand(commandObj) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(commandObj));
    }
  }

  disconnect() {
    this.intentionalClose = true;
    if (this.socket) {
      this.socket.close();
    }
  }
}

export const wsClient = new TelemetryWSClient('ws://localhost:8080/telemetry');