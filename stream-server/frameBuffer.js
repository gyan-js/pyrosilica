/** Okay so basically , my frame ring buffer serves two jobs:
  - a late-joining frontend client gets a short backfill instead of
   starting on a blank scene
   - KernelTimeline.jsx(/frontend) gets a scrollback window to draw its strip from
 **/

export class FrameBuffer {
  constructor(size) {
    this.size = size;
    this.buffer = [];
  }

  push(frame) {
    this.buffer.push(frame);
    if (this.buffer.length > this.size) {
      this.buffer.shift();
    }
  }

  getBackfill(n = this.size) {
    return this.buffer.slice(-n);
  }

  clear() {
    this.buffer = [];
  }

  get length() {
    return this.buffer.length;
  }
}