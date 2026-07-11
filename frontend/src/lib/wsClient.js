import { useTelemetryStore } from '../stores/telemetryStore';

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
      try {
        const frame = JSON.parse(event.data);
       
        useTelemetryStore.getState().ingestFrame(frame);
      } catch (err) {
        console.error('[WS] Failed to parse incoming telemetry frame:', err);
      }
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