import http from 'node:http';
import path from 'node:path';
import { WebSocketServer } from 'ws';

import { PORT, RING_BUFFER_SIZE, REPLAYS_DIR } from './config.js';
import { FrameBuffer } from './frameBuffer.js';
import { validateTelemetryFrame } from '../shared-schemas/telemetry-types.js';
import { validateTrainingEvent } from '../shared-schemas/trainingEventSchema.js';
import { handleHttpRequest } from './routes.js';
import { ReplayLoader } from './replayLoader.js';

const frameBuffer = new FrameBuffer(RING_BUFFER_SIZE);
const telemetryClients = new Set();


const ingestSockets = new Set();
let activeReplay = null;

const httpServer = http.createServer(handleHttpRequest);
const wss = new WebSocketServer({ noServer: true });

httpServer.on('upgrade', (req, socket, head) => {
  const { pathname } = new URL(req.url, `http://${req.headers.host}`);

  if (pathname === '/ingest') {
    if (activeReplay) {
      socket.write('HTTP/1.1 409 Conflict\r\n\r\n');
      socket.destroy();
      return;
    }
    wss.handleUpgrade(req, socket, head, handleIngestConnection);
    return;
  }

  if (pathname === '/telemetry') {
    wss.handleUpgrade(req, socket, head, handleTelemetryConnection);
    return;
  }

  socket.destroy();
});


function validateIngestPayload(payload) {
  if (payload && payload.stream === 'training') {
    return validateTrainingEvent(payload);
  }
  
  return validateTelemetryFrame(payload);
}

function handleIngestConnection(ws) {
  ingestSockets.add(ws);
  console.log(`[ingest] publisher connected (${ingestSockets.size} active)`);

  ws.on('message', (raw) => {
    let payload;
    try {
      payload = JSON.parse(raw.toString());
    } catch {
      console.warn('[ingest] dropped non-JSON message');
      return;
    }

    const { valid, errors } = validateIngestPayload(payload);
    if (!valid) {
      console.warn('[ingest] dropped invalid frame:', errors);
      return;
    }

    relayFrame(payload);
  });

  ws.on('close', () => {
    ingestSockets.delete(ws);
    console.log(`[ingest] publisher disconnected (${ingestSockets.size} active)`);
  });

  ws.on('error', (err) => console.error('[ingest] socket error:', err.message));
}

function handleTelemetryConnection(ws) {
  telemetryClients.add(ws);
  console.log(`[telemetry] client connected (${telemetryClients.size} total)`);

  const backfill = frameBuffer.getBackfill();
  if (backfill.length) {
    ws.send(JSON.stringify({ type: 'backfill', frames: backfill }));
  }

  ws.on('message', (raw) => handleTelemetryCommand(raw));

  ws.on('close', () => {
    telemetryClients.delete(ws);
    console.log(`[telemetry] client disconnected (${telemetryClients.size} total)`);
  });

  ws.on('error', (err) => console.error('[telemetry] socket error:', err.message));
}

// Frontend -> server control channel: drives replay playback (scrubber).
function handleTelemetryCommand(raw) {
  let msg;
  try {
    msg = JSON.parse(raw.toString());
  } catch {
    return;
  }

  switch (msg.type) {
    case 'replay:start':
      startReplay(msg.file);
      break;
    case 'replay:pause':
      activeReplay?.pause();
      break;
    case 'replay:play':
      activeReplay?.play();
      break;
    case 'replay:seek':
      activeReplay?.seek(msg.index);
      break;
    case 'replay:speed':
      activeReplay?.setSpeed(msg.multiplier);
      break;
    default:
      break;
  }
}

async function startReplay(fileName) {
  if (ingestSockets.size > 0) {
    console.warn('[replay] refused: live ingest is active');
    return;
  }
  if (typeof fileName !== 'string' || fileName.includes('..')) {
    console.warn('[replay] refused: bad file name');
    return;
  }

  activeReplay?.destroy();
  frameBuffer.clear();

  const loader = new ReplayLoader(path.join(REPLAYS_DIR, fileName));
  activeReplay = loader;

  try {
    await loader.load();
  } catch (err) {
    console.error('[replay] failed to load run:', err.message);
    activeReplay = null;
    return;
  }

  loader.on('frame', relayFrame);
  loader.on('end', () => {
    if (activeReplay === loader) activeReplay = null;
  });

  loader.play();
}

// Single fan-out path shared by both live ingest and replay — the
// frontend can't tell which one fed a given frame.
function relayFrame(frame) {
  frameBuffer.push(frame);
  const payload = JSON.stringify({ type: 'frame', frame });
  for (const client of telemetryClients) {
    if (client.readyState === client.OPEN) client.send(payload);
  }
}

httpServer.listen(PORT, () => {
  console.log(`[stream-server] listening on :${PORT}`);
  console.log(`  ingest:    ws://localhost:${PORT}/ingest`);
  console.log(`  telemetry: ws://localhost:${PORT}/telemetry`);
});



