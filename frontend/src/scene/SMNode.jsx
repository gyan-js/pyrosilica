import React, { useRef, memo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useTelemetryStore } from '../stores/telemetryStore';
import { lerp } from '../lib/interpolation';

const SMNode = memo(({ id, position }) => {
  const coreMaterialRef = useRef();
  const idleColor = new THREE.Color('#2A2726'); 
  const aluColor = new THREE.Color('#FF6A00');  
  const tensorColor = new THREE.Color('#FFE8D6 '); 
  const currentColor = new THREE.Color();

  useFrame(() => {
    if (!coreMaterialRef.current) return;

    const frame = useTelemetryStore.getState().currentFrame;
    const smData = frame?.sm_states?.[id];
    
    const util = smData?.utilization || 0; 
    const tensorActive = smData?.tensor_active || false;

    currentColor.copy(tensorActive ? tensorColor : aluColor);

    coreMaterialRef.current.color.lerp(util > 0.05 ? currentColor : idleColor, 0.15);
    coreMaterialRef.current.emissive.lerp(currentColor, 0.2);

    const targetIntensity = util * 1.5; 
    coreMaterialRef.current.emissiveIntensity = lerp(
      coreMaterialRef.current.emissiveIntensity, 
      targetIntensity, 
      0.15
    );
  });

  return (
    <group position={position}>
      

      <mesh position={[0, -0.25, 0]}>
        <boxGeometry args={[1.0, 0.05, 1.0]} />
        <meshStandardMaterial 
          color="#110E0D" 
          roughness={0.8} 
          metalness={0.2} 
        />
      </mesh>
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[0.85, 0.4, 0.85]} />
        <meshStandardMaterial 
          ref={coreMaterialRef}
          color={idleColor} 
          emissive={aluColor}
          emissiveIntensity={0}
          roughness={0.2}
          metalness={0.8}
          toneMapped={false} 
        />
      </mesh>
      
    </group>
  );
});

export default SMNode;