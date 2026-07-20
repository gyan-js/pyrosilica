import React, { useState } from 'react';


const dict = {
  'SM': 'Streaming Multiprocessor. The core computational unit of the GPU responsible for executing warps.',
  'Bank Conflict': 'Occurs when multiple threads in a warp attempt to access different addresses mapping to the same memory bank, serializing the request.',
  'Warp': 'A group of 32 threads executing exactly the same instruction at the same time in parallel.'
};

export default function ExplainModeTooltip({ term, children }) {
  const [show, setShow] = useState(false);
  const explanation = dict[term] || 'No definition available.';

  return (
    <span 
      className="relative inline-block cursor-help border-b border-dashed border-muted group"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)}
      onBlur={() => setShow(false)}
      tabIndex={0}
    >
      {children || term}
      
      {show && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-surface border border-border text-xs text-text font-body z-50 shadow-lg pointer-events-none animate-in fade-in slide-in-from-bottom-1">
          <strong className="block text-secondary mb-1">{term}</strong>
          {explanation}
        </div>
      )}
    </span>
  );
}