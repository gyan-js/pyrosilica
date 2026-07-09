import fs from 'node:fs';
import { EventEmitter } from 'node:events';

export class ReplayLoader extends EventEmitter {
  constructor(filePath) {
    super();
    this.filePath = filePath;
    this.frames = [];
    this.index = 0;
    this.speed = 1;
    this.playing = false;
    this._timer = null;
  }

  async load() {
    const raw = await fs.promises.readFile(this.filePath, 'utf-8');
    this.frames = raw
      .split('\n')
      .filter((line) => line.trim().length > 0)
      .map((line) => JSON.parse(line));
    return this.frames.length;
  }

  play() {
    if (this.playing || this.index >= this.frames.length) return;
    this.playing = true;
    this._scheduleNext();
  }

  pause() {
    this.playing = false;
    if (this._timer) {
      clearTimeout(this._timer);
      this._timer = null;
    }
  }

  /** Jump to a frame index; does not change play/pause state. */
  seek(index) {
    this.index = Math.max(0, Math.min(index, this.frames.length - 1));
  }

  setSpeed(multiplier) {
    this.speed = Math.max(0.1, Number(multiplier) || 1);
  }

  destroy() {
    this.pause();
    this.removeAllListeners();
  }

  _scheduleNext() {
    if (!this.playing || this.index >= this.frames.length) {
      this.playing = false;
      this.emit('end');
      return;
    }

    const frame = this.frames[this.index];
    const next = this.frames[this.index + 1];
    this.emit('frame', frame);
    this.index += 1;

    if (!next) {
      this._timer = setTimeout(() => this._scheduleNext(), 0);
      return;
    }

    const rawDeltaMs = (next.timestamp - frame.timestamp) * 1000;
    const delayMs = Math.max(0, rawDeltaMs / this.speed);
    this._timer = setTimeout(() => this._scheduleNext(), delayMs);
  }
}