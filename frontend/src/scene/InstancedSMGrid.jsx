import React, { useRef, useMemo, useEffect, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import { useTelemetryStore } from '../stores/telemetryStore';
import { lerp } from '../lib/interpolation';

const SMTooltip = ({ smId, localPosition }) => {

  const smData = useTelemetryStore(state => state.currentFrame?.sm_states?.[smId]);
  
  if (!smData) return null;

  const utilPercent = (smData.utilization * 100).toFixed(0);
  const isTensor = smData.tensor_active;

  return (
    <Html 
      position={localPosition} 
      center 
      pointerEvents="none" 
      zIndexRange={[100, 0]}
    >
      <div className="bg-[#1A1614]/80 backdrop-blur-md border border-white/10 rounded px-3 py-2 flex flex-col gap-1 w-32 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        <div className="flex justify-between items-center border-b border-white/5 pb-1 mb-1">
          <span className="text-[10px] text-muted uppercase tracking-widest font-display">SM_{smId}</span>
          <div className={`w-2 h-2 rounded-full ${isTensor ? 'bg-[#FFE8D6] shadow-[0_0_5px_#FFE8D6]' : 'bg-[#2C2620]'}`} title="Tensor Core Active" />
        </div>
        
        <div className="flex justify-between items-baseline">
          <span className="text-xs text-muted">Util</span>
          <span className={`font-mono text-sm ${smData.utilization > 0.8 ? 'text-[#FF4470]' : 'text-primary'}`}>
            {utilPercent}%
          </span>
        </div>


        <div className="flex justify-between items-baseline">
          <span className="text-xs text-muted">Threads</span>
          <span className="font-mono text-xs text-text">
            {Math.floor(smData.utilization * 2048)}
          </span>
        </div>
      </div>
    </Html>
  );
};

export default function InstancedSMGrid({ smCount = 128 }) {
  const groupRef = useRef();
  const aluRef = useRef();
  const tensorRef = useRef();
  const cacheRef = useRef();

  const [hoveredSM, setHoveredSM] = useState(null);

  const idleColor = useMemo(() => new THREE.Color('#2A2726'), []);
  const aluActiveColor = useMemo(() => new THREE.Color('#FF6A00'), []);
  const tensorActiveColor = useMemo(() => new THREE.Color('#FFE8D6'), []);

  const currentAluColors = useMemo(() => Array.from({ length: smCount }, () => new THREE.Color('#2A2726')), [smCount]);
  const currentTensorColors = useMemo(() => Array.from({ length: smCount }, () => new THREE.Color('#2A2726')), [smCount]);
  
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const tempColor = useMemo(() => new THREE.Color(), []);


  const positions = useMemo(() => {
    const cols = Math.ceil(Math.sqrt(smCount * 1.2)); 
    const rows = Math.ceil(smCount / cols);
    const spacing = 1.3; 
    const offsetZ = ((rows - 1) * spacing) / 2;
    const offsetX = ((cols - 1) * spacing) / 2;
    
    const posArray = [];
    for (let i = 0; i < smCount; i++) {
      const row = Math.floor(i / cols);
      const col = i % cols;
      posArray.push({
        x: col * spacing - offsetX,
        z: row * spacing - offsetZ
      });
    }
    return posArray;
  }, [smCount]);

  useEffect(() => {
    if (!aluRef.current || !tensorRef.current || !cacheRef.current) return;

    for (let i = 0; i < smCount; i++) {
      dummy.position.set(positions[i].x, 0, positions[i].z);
      dummy.updateMatrix();

      aluRef.current.setMatrixAt(i, dummy.matrix);
      tensorRef.current.setMatrixAt(i, dummy.matrix);
      cacheRef.current.setMatrixAt(i, dummy.matrix);

      aluRef.current.setColorAt(i, idleColor);
      tensorRef.current.setColorAt(i, idleColor);
      cacheRef.current.setColorAt(i, idleColor);
    }

    aluRef.current.instanceMatrix.needsUpdate = true;
    tensorRef.current.instanceMatrix.needsUpdate = true;
    cacheRef.current.instanceMatrix.needsUpdate = true;
    
    aluRef.current.instanceColor.needsUpdate = true;
    tensorRef.current.instanceColor.needsUpdate = true;
    cacheRef.current.instanceColor.needsUpdate = true;
  }, [smCount, idleColor, dummy, positions]);

  useFrame(() => {
    if (!aluRef.current || !tensorRef.current || !groupRef.current) return;

    const isExploded = useTelemetryStore.getState().isExplodedView;
    groupRef.current.position.y = lerp(groupRef.current.position.y, isExploded ? 2.0 : 0, 0.08);

    const frame = useTelemetryStore.getState().currentFrame;

    for (let i = 0; i < smCount; i++) {
      const smData = frame?.sm_states?.[i];
      const util = smData?.utilization || 0; 
      const isTensor = smData?.tensor_active || false;

      const targetAluColor = util > 0.05 ? aluActiveColor : idleColor;
      currentAluColors[i].lerp(targetAluColor, 0.15); 

      const aluIntensity = 1.0 + (util * 4.0); 
      tempColor.copy(currentAluColors[i]).multiplyScalar(aluIntensity);
      aluRef.current.setColorAt(i, tempColor);


      const targetTensorColor = (util > 0.05 && isTensor) ? tensorActiveColor : idleColor;
      currentTensorColors[i].lerp(targetTensorColor, 0.15);

      const tensorIntensity = 1.0 + (util * 5.0); 
      tempColor.copy(currentTensorColors[i]).multiplyScalar(tensorIntensity);
      tensorRef.current.setColorAt(i, tempColor);
    }

    aluRef.current.instanceColor.needsUpdate = true;
    tensorRef.current.instanceColor.needsUpdate = true;
  });

 
  const handlePointerMove = (e) => {
    e.stopPropagation();
    if (hoveredSM?.id !== e.instanceId) {
      document.body.style.cursor = 'crosshair';
  
      const pos = [positions[e.instanceId].x, 0.9, positions[e.instanceId].z];
      setHoveredSM({ id: e.instanceId, position: pos });
    }
  };

  const handlePointerOut = (e) => {
    e.stopPropagation();
    document.body.style.cursor = 'default';
    setHoveredSM(null);
  };

  return (
    <group ref={groupRef}>

      {hoveredSM && (
        <SMTooltip smId={hoveredSM.id} localPosition={hoveredSM.position} />
      )}

      <instancedMesh ref={cacheRef} args={[null, null, smCount]} castShadow receiveShadow>
        <boxGeometry args={[1.0, 0.05, 1.0]} />
        <meshStandardMaterial color="#110E0D" roughness={0.8} metalness={0.2} />
      </instancedMesh>

    <instancedMesh 
        ref={aluRef} 
        args={[null, null, smCount]} 
        position={[0, 0.15, -0.15]} 
        castShadow 
        receiveShadow
        onPointerMove={handlePointerMove}
        onPointerOut={handlePointerOut}
      >
        <boxGeometry args={[0.85, 0.25, 0.55]} />
        <meshStandardMaterial 
          roughness={0.2}         
          metalness={0.8}          
          toneMapped={false} 
        />
      </instancedMesh>

      <instancedMesh ref={tensorRef} args={[null, null, smCount]} position={[0, 0.15, 0.3]} castShadow receiveShadow>
        <boxGeometry args={[0.85, 0.25, 0.25]} />
        <meshStandardMaterial 
          roughness={0.2}
          metalness={0.8}
          toneMapped={false}
        />
      </instancedMesh>
    </group>
  );
}