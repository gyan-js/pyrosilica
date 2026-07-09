import fs from 'node:fs';
import { REPLAYS_DIR, GPU_PROFILES_DIR } from './config.js';

function sendJson(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

function listDir(dir, extension) {
  return new Promise((resolve, reject) => {
    fs.readdir(dir, (err, files) => {
      if (err) return reject(err);
      resolve(files.filter((f) => f.endsWith(extension)));
    });
  });
}

export async function handleHttpRequest(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (url.pathname === '/api/health') {
    return sendJson(res, 200, { status: 'ok', uptime: process.uptime() });
  }

  if (url.pathname === '/api/replays' && req.method === 'GET') {
    try {
      const runs = await listDir(REPLAYS_DIR, '.ndjson');
      return sendJson(res, 200, { runs });
    } catch {
      return sendJson(res, 500, { error: 'failed to list replays' });
    }
  }

  if (url.pathname === '/api/gpu-profiles' && req.method === 'GET') {
    try {
      const profiles = await listDir(GPU_PROFILES_DIR, '.json');
      return sendJson(res, 200, { profiles });
    } catch {
      return sendJson(res, 500, { error: 'failed to list gpu profiles' });
    }
  }

  return sendJson(res, 404, { error: 'not found' });
}