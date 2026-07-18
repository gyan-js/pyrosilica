import React, { useState, useEffect, useRef } from 'react';
import GPUDieScene from './scene/GPUDieScene';
import GPUProfileSelector from './panels/GPUProfileSelector';
import KernelTimeline from './panels/KernelTimeline';
import LossCurvePanel from './panels/LossCurvePanel';
import ModelGraphPanel from './panels/ModelGraphPanel';
import ExplainModeTooltip from './panels/ExplainModeTooltip';
import { useTelemetryStore } from './stores/telemetryStore';
import { useMockTelemetry } from './lib/useMockTelemetry';
import { RunRecorder } from './lib/recorder'; 

export default function App() {
  const frame = useTelemetryStore(state => state.currentFrame);
  const [isReady, setIsReady] = useState(false);
  const isExplainMode = useTelemetryStore(state => state.isExplainMode);

  const [isRecording, setIsRecording] = useState(false);
  const [recTime, setRecTime] = useState(0);
  const [recSize, setRecSize] = useState(0);
  const recorderRef = useRef(null);

  useMockTelemetry(true);

  useEffect(() => {
    const timer = setTimeout(() => setIsReady(true), 150);
    return () => clearTimeout(timer);
  }, []);


  useEffect(() => {
    let interval;
    if (isRecording) {
      interval = setInterval(() => {
        setRecTime(t => t + 1);
      }, 1000);
    } else {
      setRecTime(0);
      setRecSize(0);
    }
    return () => clearInterval(interval);
  }, [isRecording]);

  const totalPower = frame?.power_draw || 0;
  const totalBandwidth = frame?.mem_bandwidth || 0;
  const avgUtil = frame?.global_utilization || 0;

  const glassPanel = "bg-[#1A1614]/40 backdrop-blur-xl border border-white/10 shadow-2xl rounded-lg pointer-events-auto";


  const toggleRecording = () => {
    if (!isRecording) {
      const canvas = document.querySelector('canvas');
      if (!canvas) return;
      recorderRef.current = new RunRecorder(canvas);
      

      recorderRef.current.startRecording(120, (newSize) => {
        setRecSize(newSize);
      });
      setIsRecording(true);
    } else {
      recorderRef.current?.stopAndDownload(`pyrosilica-run-${Date.now()}.webm`);
      setIsRecording(false);
    }
  };


  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const formatSize = (bytes) => {
    if (bytes === 0) return '0.00';
    return (bytes / (1024 * 1024)).toFixed(2);
  };
  return (
    <div className="h-screen w-screen bg-bg text-text overflow-hidden font-body selection:bg-primary/30 relative">
      <div className={`absolute inset-0 z-0 transition-opacity duration-1000 ${isReady ? 'opacity-100' : 'opacity-0'}`}>
        <GPUDieScene />
      </div>

      <div className={`relative z-10 w-full h-full p-6 pointer-events-none transition-opacity duration-1000 delay-300 ${isReady ? 'opacity-100' : 'opacity-0'}`}>
        
        <header className={`absolute top-6 left-6 right-6 flex justify-between items-start`}>
          
          <div className={`${glassPanel} p-4 flex flex-col gap-4 max-w-lg`}>
            <div className="flex items-center justify-between gap-8">
               <h1 className="font-display font-bold text-lg tracking-wider text-primary uppercase drop-shadow-md">Pyrosilica</h1>
               <span className="text-muted text-xs font-mono">v1.2</span>
            </div>
            
           <div className="flex items-center gap-2">
              <GPUProfileSelector />
             {/*} <button 
                onClick={() => useTelemetryStore.getState().toggleExplainMode()}
                className={`flex items-center justify-center border h-8 px-4 text-[10px] font-bold uppercase tracking-widest rounded-md transition-colors ${
                  isExplainMode 
                    ? 'bg-[#00a1ff]/20 border-[#00a1ff]/50 text-[#00a1ff] shadow-[0_0_15px_rgba(0,161,255,0.2)]' 
                    : 'bg-white/5 border-white/10 text-white/90 hover:bg-white/10'
                }`}
              >
                Explain
              </button>*/}
              <button 
                onClick={() => useTelemetryStore.getState().toggleExplodedView()}
                className="flex items-center justify-center bg-white/5 hover:bg-white/10 text-white/90 border border-white/10 h-8 px-4 text-[10px] font-bold uppercase tracking-widest rounded-md transition-colors"
              >
                Explode
              </button>

              <button 
                onClick={toggleRecording}
                className={`relative flex items-center h-8 rounded-md transition-all duration-500 ease-[cubic-bezier(0.23,1,0.32,1)] overflow-hidden border backdrop-blur-md ${
                  isRecording 
                    ? 'bg-[#FF4470]/10 border-[#FF4470]/40 text-[#FF4470] shadow-[0_0_15px_rgba(255,68,112,0.1)] w-[260px]' 
                    : 'bg-white/5 border-white/10 text-white/90 hover:bg-white/10 w-[96px]'
                }`}
              >
                <div className="flex items-center w-full px-3 h-full whitespace-nowrap">

                  <div className={`shrink-0 w-2 h-2 rounded-full mr-2 ${isRecording ? 'bg-[#FF4470] animate-pulse shadow-[0_0_8px_#FF4470]' : 'bg-red-500'}`} />
                  
               
                  <span className="text-[10px] uppercase tracking-widest font-bold">
                    {isRecording ? 'Recording ' : 'Record'}
                  </span>
                  
                 
                  {isRecording && (
                    <div className="ml-auto flex items-center gap-3 text-[10px] font-mono text-[#FF4470]/80 animate-in fade-in duration-700">
                       <span>120FPS</span>
                       <span>{formatTime(recTime)}</span>
                       <span className="w-8 text-right">{formatSize(recSize)}</span>
                    </div>
                  )}
                  
                </div>
              </button>
            </div>
          </div>

          <div className={`${glassPanel} p-4 flex gap-6 text-sm`}>

            <div className="flex flex-col">
              <span className="text-muted text-[10px] uppercase tracking-widest">PWR Draw</span> 
              <span className="font-mono text-primary text-lg">{totalPower.toFixed(0)}W</span>
            </div>
            <div className="flex flex-col">
              <span className="text-muted text-[10px] uppercase tracking-widest">Bandwidth</span> 
              <span className="font-mono text-secondary text-lg">{totalBandwidth.toFixed(1)} GB/s</span>
            </div>
            <div className="flex flex-col">
              <span className="text-muted text-[10px] uppercase tracking-widest">SM Util</span> 
              <span className="font-mono text-white text-lg">{(avgUtil * 100).toFixed(0)}%</span>
            </div>
          </div>
        </header>

   
        <aside className={`absolute top-36 right-6 bottom-40 w-80 ${glassPanel} flex flex-col`}>
          <ModelGraphPanel />
        </aside>

        <footer className={`absolute bottom-6 left-6 right-[22rem] h-32 ${glassPanel} flex flex-col justify-center p-4`}>
          <KernelTimeline />
        </footer>

        <div className={`absolute bottom-6 right-6 w-80 h-32 ${glassPanel} p-4`}>
          <LossCurvePanel />
        </div>
      </div>
    </div>
  );
}