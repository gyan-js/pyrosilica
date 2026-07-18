import React, { useRef, useState, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useTelemetryStore } from '../stores/telemetryStore';

export default function BankConflictFlash({ smId }) {
  const meshRef = useRef();
  const [isFlashing, setIsFlashing] = useState(false);
  const opacityRef = useRef(0);

  useEffect(() => {
   
    const unsub = useTelemetryStore.subscribe((state) => {
      const frame = state.currentFrame;
      if (frame?.bank_conflicts?.includes(smId)) {
        setIsFlashing(true);
        opacityRef.current = 1.0; 
      }
    });
    return () => unsub();
  }, [smId]);

  useFrame(() => {
    if (!meshRef.current) return;

    if (isFlashing) {

      opacityRef.current -= 0.1; 
      if (opacityRef.current <= 0) {
        opacityRef.current = 0;
        setIsFlashing(false);
      }
      meshRef.current.material.opacity = opacityRef.current;
    }
  });

  return (
    <mesh ref={meshRef} position={[0, 0.25, 0]} visible={isFlashing}>

      <boxGeometry args={[1.0, 0.35, 1.0]} />
      <meshBasicMaterial 
        color="#FF4470"
        transparent
        opacity={0}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
  );
}
