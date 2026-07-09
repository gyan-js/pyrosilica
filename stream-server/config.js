import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const PORT = parseInt(process.env.PORT || '8080', 10);



export const RING_BUFFER_SIZE = parseInt(process.env.RING_BUFFER_SIZE || '300', 10);

export const REPLAYS_DIR = process.env.REPLAYS_DIR || path.join(__dirname, 'replays');
export const GPU_PROFILES_DIR = process.env.GPU_PROFILES_DIR || path.join(__dirname, 'gpu-profiles');