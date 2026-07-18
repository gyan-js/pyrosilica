import React, { useRef } from 'react';
import { usePlaybackStore } from '../stores/playbackStore';
import { useTelemetryStore } from '../stores/telemetryStore';

export default function KernelTimeline() {
  const { isPlaying, togglePlayPause, scrubPosition, setScrubPosition } = usePlaybackStore();
  const metadata = useTelemetryStore(state => state.runMetadata);
  const trackRef = useRef(null);

 
  const kernels = metadata?.kernels || [
    { id: 1, name: 'Attention_QKV', start: 5, width: 15, type: 'tensor' },
    { id: 2, name: 'Softmax', start: 22, width: 8, type: 'alu' },
    { id: 3, name: 'MatMul_Out', start: 32, width: 20, type: 'tensor' },
    { id: 4, name: 'LayerNorm', start: 55, width: 5, type: 'alu' },
    { id: 5, name: 'Dropout', start: 62, width: 4, type: 'alu' },
    { id: 6, name: 'FFN_Expand', start: 70, width: 25, type: 'tensor' }
  ];

  const totalFrames = 100; // Simulated 100% width
  const progressPercent = (scrubPosition / totalFrames) * 100;

  const handleScrub = (e) => {
    if (!trackRef.current) return;
    const rect = trackRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const newPos = Math.floor((x / rect.width) * totalFrames);
    setScrubPosition(newPos);
  };

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
     
        {kernels.map(kernel => (
          <div 
            key={kernel.id}
            className={`absolute top-1 bottom-1 rounded-[2px] border border-black/30 group-hover:opacity-80 transition-opacity`}
            style={{
              left: `${kernel.start}%`,
              width: `${kernel.width}%`,
              backgroundColor: kernel.type === 'tensor' ? '#FFB238' : '#FF6A00',
              opacity: progressPercent >= kernel.start ? 1 : 0.4 // Dim future kernels
            }}
            title={kernel.name}
          />
        ))}

        <div 
          className="absolute top-0 w-[2px] h-full bg-text shadow-[0_0_8px_#F0E6DC] pointer-events-none transition-all duration-75 ease-linear z-10"
          style={{ left: `${progressPercent}%` }}
        />
      </div>
      
      <div className="flex justify-between mt-2 font-mono text-[10px] text-muted">
        <span>T - 50ms</span>
        <span>NOW</span>
      </div>
    </div>
  );
}