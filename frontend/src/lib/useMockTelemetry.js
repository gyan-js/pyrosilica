import { useEffect } from 'react';
import { useTelemetryStore } from '../stores/telemetryStore';

export function useMockTelemetry(isActive = true) {
  useEffect(() => {
    if (!isActive) return;

    console.log('[MockTelemetry] Starting simulation generator...');
    let frameCount = 0;

    const interval = setInterval(() => {
      frameCount++;
      const { activeGpuProfile } = useTelemetryStore.getState();
      const smCount = activeGpuProfile.smCount;

      const wave = (Math.sin(frameCount / 20) + 1) / 2; 

      const sm_states = {};
      const conflicts = [];
      
      for (let i = 0; i < smCount; i++) {  
        const localWave = (Math.sin((frameCount / 15) + (i / 10)) + 1) / 2;
        
        sm_states[i] = {
          utilization: localWave * 0.9 + (Math.random() * 0.1),
          tensor_active: localWave > 0.7 
        };

        if (Math.random() < 0.01) {
          conflicts.push(i);
        }
      }

     
      const mockFrame = {
        timestamp: Date.now(),
        power_draw: 150 + (wave * 250) + (Math.random() * 10), 
        mem_bandwidth: 200 + (wave * 700) + (Math.random() * 50), 
        global_utilization: wave,
        global_occupancy: wave * 0.8, 
        bank_conflicts: conflicts,
        sm_states: sm_states,
        active_layer: (Math.floor(frameCount / 50) % 4) + 1 + "" 
      };

   
      useTelemetryStore.getState().ingestFrame(mockFrame);

    }, 100);

    return () => clearInterval(interval);
  }, [isActive]);
}