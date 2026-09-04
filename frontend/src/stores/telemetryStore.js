import { create } from 'zustand';
import { gpuProfiles } from '../lib/gpuSpecProfiles';

export const useTelemetryStore = create((set, get) => ({

  currentFrame: null,

  
  
  currentTrainingEvent: null,

 
  KERNEL_WINDOW_MS: 2000,
  kernelEvents: [],

  ingestTrainingEvent: (event) => set((state) => {
    if (event.event !== 'kernel') {
      return { currentTrainingEvent: event };
    }

    
    const end_ms = Date.now();
    const duration_ms = event.duration_ms ?? 0;
    const newEvent = {
      id: `${event.kernel_name}-${end_ms}-${Math.random().toString(36).slice(2, 7)}`,
      name: event.kernel_name,
      type: event.kernel_type === 'tensor' ? 'tensor' : 'alu',
      start_ms: end_ms - duration_ms,
      end_ms,
    };

    const cutoff = end_ms - state.KERNEL_WINDOW_MS;
    const kernelEvents = [...state.kernelEvents, newEvent].filter(k => k.end_ms >= cutoff);

    return { currentTrainingEvent: event, kernelEvents };
  }),

  runMetadata: {},
  

  activeGpuProfile: gpuProfiles['RTX 4090'], 
  
  isCustomProfile: false,

  isExplainMode: false,
  toggleExplainMode: () => set((state) => ({ isExplainMode: !state.isExplainMode })),

  isExplodedView: false,
  toggleExplodedView: () => set((state) => ({ isExplodedView: !state.isExplodedView })),

  ingestFrame: (frame) => set({ currentFrame: frame }),
  
  updateMetadata: (metadata) => set((state) => ({ 
    runMetadata: { ...state.runMetadata, ...metadata } 
  })),

  setActiveProfile: (profileKey) => {
    if (gpuProfiles[profileKey]) {
      set({ activeGpuProfile: gpuProfiles[profileKey], isCustomProfile: false });
    }
  },

  setCustomProfile: (smCount, coresPerSm) => {
    set({
      activeGpuProfile: {
        name: 'Custom',
        architecture: 'Custom',
        smCount,
        cudaCoresPerSm: coresPerSm,
      },
      isCustomProfile: true
    });
  },
  
  getSmUtilization: (smId) => {
    const frame = get().currentFrame;
    if (!frame || !frame.sm_states || !frame.sm_states[smId]) return 0;
    return frame.sm_states[smId].utilization; 
  }
}));