import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useTelemetryStore } from '../stores/telemetryStore';
import { lerp } from '../lib/interpolation';


const getSMPosition = (idx, smCount) => {
  const cols = Math.ceil(Math.sqrt(smCount * 1.2));
  const rows = Math.ceil(smCount / cols);
  const spacing = 1.3;
  const col = idx % cols;
  const row = Math.floor(idx / cols);
  return {
    x: col * spacing - ((cols - 1) * spacing) / 2,
    z: row * spacing - ((rows - 1) * spacing) / 2
  };
};


const pickHotSM = (frame, smCount) => {
  if (!frame || !frame.sm_states) return Math.floor(Math.random() * smCount);
  
  let totalWeight = 0;
  const weights = [];
  
  for (let i = 0; i < smCount; i++) {

    const weight = (frame.sm_states[i]?.utilization || 0) + 0.02; 
    totalWeight += weight;
    weights.push(totalWeight);
  }
  
  const roll = Math.random() * totalWeight;
  for (let i = 0; i < smCount; i++) {
    if (roll < weights[i]) return i;
  }
  return 0;
};

export default function MemoryFlowParticles() {
  const pointsRef = useRef();
  

  const ORBITAL_COUNT = 1500;
  const TRANSIT_COUNT = 100; 
  const totalCount = ORBITAL_COUNT + TRANSIT_COUNT;
  
  const smCount = useTelemetryStore(state => state.activeGpuProfile?.smCount || 128);


  const colorHBM = useMemo(() => new THREE.Color('#0022ff'), []);
  const colorL2 = useMemo(() => new THREE.Color('#0088ff'), []);
  const colorL1 = useMemo(() => new THREE.Color('#00ffff'), []);
  const colorSM = useMemo(() => new THREE.Color('#ffffff'), []);
  const scratchColor = useMemo(() => new THREE.Color(), []);

  const { positions, colors, data } = useMemo(() => {
    const pos = new Float32Array(totalCount * 3);
    const col = new Float32Array(totalCount * 3);
    const pData = new Array(totalCount);
    
    for (let i = 0; i < totalCount; i++) {
      if (i < ORBITAL_COUNT) {

        const tier = i % 3; 
        pData[i] = {
          isTransit: false,
          tier: tier, 
          angle: Math.random() * Math.PI * 2,
          radiusOffset: (Math.random() - 0.5) * 1.5
        };
      } else {
        pData[i] = { 
          isTransit: true,
          t: Math.random(), 
          smIdx: 0,
          isOutbound: false,
          l1Angle: 0
        };
      }
    }
    return { positions: pos, colors: col, data: pData };
  }, [totalCount]);

  const currentSpeed = useRef(0.01);
  const heights = useRef({ hbm: -0.2, l2: -0.1, l1: 0.1, sm: 0.2 });

  useFrame(() => {
    const state = useTelemetryStore.getState();
    const frame = state.currentFrame;
    const isExploded = state.isExplodedView || false; 
    const bandwidth = frame?.mem_bandwidth || 0; 

    heights.current.hbm = lerp(heights.current.hbm, isExploded ? -2.5 : -0.2, 0.08);
    heights.current.l2 = lerp(heights.current.l2, isExploded ? -1.0 : -0.1, 0.08);
    heights.current.l1 = lerp(heights.current.l1, isExploded ? 1.8 : 0.1, 0.08);
    heights.current.sm = lerp(heights.current.sm, isExploded ? 2.0 : 0.2, 0.08);
    

    const rHBM = 15;
    const rL2 = 11;
    const rL1 = 7;


    const baseSpeed = (bandwidth / 1000) * 0.015 + 0.005;
    currentSpeed.current = lerp(currentSpeed.current, baseSpeed, 0.1);

    const pos = pointsRef.current.geometry.attributes.position.array;
    const col = pointsRef.current.geometry.attributes.color.array;
    
    for (let i = 0; i < totalCount; i++) {
      const p = data[i];

      if (!p.isTransit) {

        p.angle += currentSpeed.current * (p.tier === 2 ? 1.5 : 1.0); 
        
        let radius, yLevel, targetColor;
        if (p.tier === 0) { radius = rHBM; yLevel = heights.current.hbm; targetColor = colorHBM; }
        else if (p.tier === 1) { radius = rL2; yLevel = heights.current.l2; targetColor = colorL2; }
        else { radius = rL1; yLevel = heights.current.l1; targetColor = colorL1; }

        const r = radius + p.radiusOffset;
        pos[i*3] = Math.cos(p.angle) * r;
        pos[i*3+1] = yLevel;
        pos[i*3+2] = Math.sin(p.angle) * r;

        col[i*3] = targetColor.r;
        col[i*3+1] = targetColor.g;
        col[i*3+2] = targetColor.b;

      } else {

        p.t += currentSpeed.current * 1.5; 


        if (p.t >= 1.0) {
          p.t = 0;
          p.smIdx = pickHotSM(frame, smCount);

          p.isOutbound = Math.random() < 0.2; 
          
          const smPos = getSMPosition(p.smIdx, smCount);

          p.l1Angle = Math.atan2(smPos.z, smPos.x); 
        }

        const smPos = getSMPosition(p.smIdx, smCount);
        const l1X = Math.cos(p.l1Angle) * rL1;
        const l1Z = Math.sin(p.l1Angle) * rL1;

        const startX = p.isOutbound ? smPos.x : l1X;
        const startY = p.isOutbound ? heights.current.sm : heights.current.l1;
        const startZ = p.isOutbound ? smPos.z : l1Z;

        const endX = p.isOutbound ? l1X : smPos.x;
        const endY = p.isOutbound ? heights.current.l1 : heights.current.sm;
        const endZ = p.isOutbound ? l1Z : smPos.z;

        const ctrlX = (startX + endX) / 2;
        const ctrlY = Math.max(startY, endY) + 1.2;
        const ctrlZ = (startZ + endZ) / 2;

     
        const mt = 1 - p.t;
        pos[i*3] = mt * mt * startX + 2 * mt * p.t * ctrlX + p.t * p.t * endX;
        pos[i*3+1] = mt * mt * startY + 2 * mt * p.t * ctrlY + p.t * p.t * endY;
        pos[i*3+2] = mt * mt * startZ + 2 * mt * p.t * ctrlZ + p.t * p.t * endZ;


        scratchColor.lerpColors(
          p.isOutbound ? colorSM : colorL1, 
          p.isOutbound ? colorL1 : colorSM, 
          p.t
        );


        let fade = 1.0;
        if (p.t < 0.15) fade = p.t / 0.15; 
        if (p.t > 0.85) fade = (1.0 - p.t) / 0.15; 
        if (p.isOutbound) fade *= 0.4; 

        col[i*3] = scratchColor.r * fade;
        col[i*3+1] = scratchColor.g * fade;
        col[i*3+2] = scratchColor.b * fade;
      }
    }
    
    pointsRef.current.geometry.attributes.position.needsUpdate = true;
    pointsRef.current.geometry.attributes.color.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" count={totalCount} array={positions} itemSize={3} />
        <bufferAttribute attach="attributes-color" count={totalCount} array={colors} itemSize={3} />
      </bufferGeometry>
      <pointsMaterial 
        size={0.12} 
        vertexColors={true} 
        transparent 
        opacity={0.7}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        toneMapped={false}
      />
    </points>
  );
}