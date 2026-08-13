import React, { useRef, useState, useEffect } from 'react';
import { usePlaybackStore } from '../stores/playbackStore';
import { useTelemetryStore } from '../stores/telemetryStore';

const KERNEL_COLORS = { tensor: '#FFB238', alu: '#FF6A00' };

export default function KernelTimeline() {
  const { isPlaying, togglePlayPause, scrubPosition, setScrubPosition } = usePlaybackStore();
  const kernelEvents = useTelemetryStore(state => state.kernelEvents);
  const windowMs = useTelemetryStore(state => state.KERNEL_WINDOW_MS);
  const trackRef = useRef(null);

 
  const [, forceTick] = useState(0);
  useEffect(() => {
    if (!isPlaying) return;
    const id = setInterval(() => forceTick(t => t + 1), 100);
    return () => clearInterval(id);
  }, [isPlaying]);

 
  const frozenAtRef = useRef(Date.now());
  useEffect(() => {
    if (!isPlaying) frozenAtRef.current = Date.now();
  }, [isPlaying]);

  const windowEnd = isPlaying ? Date.now() : frozenAtRef.current - scrubPosition;
  const windowStart = windowEnd - windowMs;

  const handleScrub = (e) => {
    if (!trackRef.current || isPlaying) return; // scrubbing only makes sense while paused
    const rect = trackRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const pct = x / rect.width; // 0 = left edge (oldest), 1 = right edge (most recent)
    const msBack = Math.round((1 - pct) * windowMs);
    setScrubPosition(msBack);
  };

  const visibleKernels = kernelEvents.filter(
    k => k.end_ms >= windowStart && k.start_ms <= windowEnd
  );

  return (
    <div className="w-full h-full flex flex-col justify-between">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-display text-sm text-secondary uppercase tracking-widest">Kernel Execution</h3>
        <button
          onClick={togglePlayPause}
          className="text-xs bg-idle hover:bg-border text-text px-3 py-1 rounded-sm uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        >
          {isPlaying ? 'Pause' : 'Live'}
        </button>
      </div>

      <div
        ref={trackRef}
        className="relative w-full h-10 bg-[#120F0E] border border-border cursor-pointer group rounded-sm overflow-hidden"
        onMouseDown={handleScrub}
      >
        {visibleKernels.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-[10px] font-mono text-muted uppercase tracking-widest">
            No kernel activity
          </div>
        )}

        {visibleKernels.map(kernel => {
          const leftPct = ((kernel.start_ms - windowStart) / windowMs) * 100;
          const widthPct = ((kernel.end_ms - kernel.start_ms) / windowMs) * 100;
          return (
            <div
              key={kernel.id}
              className="absolute top-1 bottom-1 rounded-[2px] border border-black/30 group-hover:opacity-80 transition-opacity"
              style={{
                left: `${Math.max(0, leftPct)}%`,
                width: `${Math.max(0.5, widthPct)}%`,
                backgroundColor: KERNEL_COLORS[kernel.type] ?? KERNEL_COLORS.alu,
              }}
              title={`${kernel.name} (${(kernel.end_ms - kernel.start_ms).toFixed(1)}ms)`}
            />
          );
        })}

        {isPlaying && (
          <div className="absolute top-0 right-0 w-[2px] h-full bg-text shadow-[0_0_8px_#F0E6DC] pointer-events-none z-10" />
        )}
      </div>

      <div className="flex justify-between mt-2 font-mono text-[10px] text-muted">
        <span>T - {windowMs}ms</span>
        <span>{isPlaying ? 'NOW' : `-${scrubPosition}ms`}</span>
      </div>
    </div>
  );
}