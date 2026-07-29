
export function adaptTelemetryFrame(rawFrame, activeGpuProfile) {
  const smState = rawFrame.sm_state;

  if (!smState) {
  
    return {
      timestamp: Date.now(),
      power_draw: 0,
      mem_bandwidth: 0,
      global_utilization: 0,
      global_occupancy: 0,
      bank_conflicts: [],
      sm_states: {},
    };
  }

  const utilizationFraction = smState.sm_utilization_pct / 100;
  const smCount = activeGpuProfile?.smCount ?? 0;

  const sm_states = {};
  for (let i = 0; i < smCount; i++) {
    sm_states[i] = {
      utilization: utilizationFraction,
      
      tensor_active: utilizationFraction > 0.7,
    };
  }

  return {
    timestamp: smState.timestamp_ms,
    power_draw: smState.power_draw_w ?? 0,
    mem_bandwidth: 0, // not available 
    global_utilization: utilizationFraction,
    global_occupancy: 0, // not available 
    bank_conflicts: [], // not available 
    sm_states,
  };
}