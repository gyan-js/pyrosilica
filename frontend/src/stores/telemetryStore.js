import { create } from 'zustand';
import { gpuProfiles } from '../lib/gpuSpecProfiles';

export const useTelemetryStore = create((set, get) => ({

  currentFrame: null,
  
  runMetadata: {},
  

  activeGpuProfile: gpuProfiles['RTX 4090'], 
  
  isCustomProfile: false,

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