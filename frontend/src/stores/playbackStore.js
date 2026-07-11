import { create } from "zustand";
export const usePlaybackStore = create((set) => ({
    mode: 'live',
    isPlaying: true,
    playbackSpeed: 1.0,
    scrubPosition: 0,

 setMode: (mode) => set({ mode }),
  togglePlayPause: () => set((state) => ({ isPlaying: !state.isPlaying })),
  setPlaybackSpeed: (speed) => set({ playbackSpeed: speed }),
  setScrubPosition: (position) => set({ scrubPosition: position }),

               
}))