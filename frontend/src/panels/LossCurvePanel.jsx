import React from 'react';
import { Line } from 'react-chartjs-2';
import { Chart, LineElement, PointElement, LinearScale, CategoryScale, Tooltip } from 'chart.js';
import { useTelemetryStore } from '../stores/telemetryStore';

Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip);

export default function LossCurvePanel() {
  const metadata = useTelemetryStore(state => state.runMetadata);
  const lossHistory = metadata?.lossHistory || [2.4, 2.1, 1.8, 1.5, 1.4, 1.25, 1.1];
  const labels = lossHistory.map((_, i) => i.toString());

  const data = {
    labels,
    datasets: [
      {
        data: lossHistory,
        borderColor: '#FFB238', 
        borderWidth: 1.5,
        pointRadius: 0, 
        pointHoverRadius: 4,
        pointBackgroundColor: '#FF6A00',
        tension: 0.2 
      }
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300, easing: 'easeOutQuart' }, 
    scales: {
      x: { 
        display: false 
      },
      y: {
        grid: { color: '#2C2620', tickLength: 0 },
        border: { display: false },
        ticks: { color: '#8A7C6E', font: { family: '"JetBrains Mono", monospace', size: 10 } }
      }
    },
    plugins: {
      tooltip: {
        backgroundColor: '#1A1614',
        titleFont: { family: 'Inter' },
        bodyFont: { family: '"JetBrains Mono"' },
        borderColor: '#2C2620',
        borderWidth: 1
      }
    }
  };

  return (
    <div className="w-full h-full flex flex-col">
      <h3 className="font-display text-sm text-secondary uppercase tracking-widest mb-2">Training Loss</h3>
      <div className="flex-grow relative">
        <Line data={data} options={options} />
      </div>
    </div>
  );
}