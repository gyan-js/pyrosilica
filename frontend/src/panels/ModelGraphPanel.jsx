import React from 'react';
import ReactFlow, { Background } from 'reactflow';
import 'reactflow/dist/style.css';
import { useTelemetryStore } from '../stores/telemetryStore';

const initialNodes = [
  { id: '1', position: { x: 50, y: 20 }, data: { label: 'Input Batch' }, type: 'input' },
  { id: '2', position: { x: 50, y: 80 }, data: { label: 'Attention_L1' } },
  { id: '3', position: { x: 50, y: 140 }, data: { label: 'FFN_L1' } },
  { id: '4', position: { x: 50, y: 200 }, data: { label: 'Output Logits' }, type: 'output' },
];

const initialEdges = [
  { id: 'e1-2', source: '1', target: '2', animated: true },
  { id: 'e2-3', source: '2', target: '3', animated: true },
  { id: 'e3-4', source: '3', target: '4', animated: true },
];

export default function ModelGraphPanel() {
  const currentFrame = useTelemetryStore(state => state.currentFrame);
  const activeLayer = currentFrame?.active_layer || '2';

  
  const nodes = initialNodes.map(node => ({
    ...node,
    style: {
      background: node.id === activeLayer ? '#332C24' : '#1A1614',
      color: node.id === activeLayer ? '#FF6A00' : '#8A7C6E',
      border: `1px solid ${node.id === activeLayer ? '#FF6A00' : '#2C2620'}`,
      borderRadius: '4px',
      fontSize: '12px',
      fontFamily: 'Inter',
      padding: '8px 12px',
      transition: 'all 0.2s ease',
    }
  }));

  return (
    <div className="w-full h-full flex flex-col p-4">
      <h3 className="font-display text-sm text-secondary uppercase tracking-widest mb-4">Compute Graph</h3>
      <div className="flex-grow rounded-sm border border-border bg-bg overflow-hidden">
        <ReactFlow 
          nodes={nodes} 
          edges={initialEdges} 
          fitView 
          proOptions={{ hideAttribution: true }} 
        >
       
          <Background color="#2C2620" gap={12} size={1} />
        </ReactFlow>
      </div>
    </div>
  );
}