import React, { useState } from 'react';
import { useTelemetryStore } from '../stores/telemetryStore';
import { gpuProfiles, getProfileOptions } from '../lib/gpuSpecProfiles';

export default function GPUProfileSelector() {
  const { activeGpuProfile, isCustomProfile, setActiveProfile, setCustomProfile } = useTelemetryStore();
  const [showCustom, setShowCustom] = useState(isCustomProfile);

  const handleSelect = (e) => {
    const val = e.target.value;
    if (val === 'Custom') {
      setShowCustom(true);
    } else {
      setShowCustom(false);
      setActiveProfile(val);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <select 
        value={showCustom ? 'Custom' : activeGpuProfile.name}
        onChange={handleSelect}
        className="bg-bg border border-border text-text text-sm rounded-sm px-2 py-1 focus:border-secondary outline-none transition-colors"
      >
        {getProfileOptions().map(opt => <option key={opt} value={opt}>{opt}</option>)}
        <option value="Custom">Custom Target...</option>
      </select>

      {showCustom && (
        <div className="flex items-center gap-2 animate-in fade-in slide-in-from-left-2 duration-200">
          <input 
            type="number" 
            placeholder="SM Count"
            className="w-20 bg-bg border border-border px-2 py-1 text-sm font-mono focus:border-secondary outline-none placeholder:text-muted"
            onChange={(e) => setCustomProfile(parseInt(e.target.value) || 1, activeGpuProfile.cudaCoresPerSm)}
          />
          <input 
            type="number" 
            placeholder="Cores/SM"
            className="w-20 bg-bg border border-border px-2 py-1 text-sm font-mono focus:border-secondary outline-none placeholder:text-muted"
            onChange={(e) => setCustomProfile(activeGpuProfile.smCount, parseInt(e.target.value) || 1)}
          />
        </div>
      )}
    </div>
  );
}