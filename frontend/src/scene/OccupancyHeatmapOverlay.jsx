import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useTelemetryStore } from '../stores/telemetryStore';
import { lerp } from '../lib/interpolation';

export default function OccupancyHeatmapOverlay() {
  const materialRef = useRef();

  const coldColor = new THREE.Color('#332C24');
  const hotColor = new THREE.Color('#FF4470');

  useFrame(() => {
    if (!materialRef.current) return;
    
    const frame = useTelemetryStore.getState().currentFrame;
    const occupancy = frame?.global_occupancy || 0; 
    
    const currentOpacity = materialRef.current.opacity;
    materialRef.current.opacity = lerp(currentOpacity, occupancy * 0.4, 0.1);
    
    materialRef.current.color.lerpColors(coldColor, hotColor, occupancy);
  });

  return (
    <mesh position={[0, -0.2, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[40, 40]} />
      <meshBasicMaterial 
        ref={materialRef}
        color="#332C24"
        transparent
        opacity={0.1}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}