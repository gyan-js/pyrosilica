import React, { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Environment } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import { useTelemetryStore } from '../stores/telemetryStore';
import InstancedSMGrid from './InstancedSMGrid';
import MemoryFlowParticles from './MemoryFlowParticles';
import { lerp } from '../lib/interpolation';


export function L2CacheLayer({ smCount = 128 }) {
  const layerRef = useRef();
  
  useFrame(() => {
    const isExploded = useTelemetryStore.getState().isExplodedView;
  
    layerRef.current.position.y = lerp(layerRef.current.position.y, isExploded ? -1.5 : -0.1, 0.08);
  });


  const cols = Math.ceil(Math.sqrt(smCount * 1.2)); 
  const rows = Math.ceil(smCount / cols);
  
  return (
    <group ref={layerRef}>
      <mesh receiveShadow castShadow position={[0, -0.1, 0]}>
        <boxGeometry args={[cols * 1.4, 0.2, rows * 1.4]} />
        <meshStandardMaterial color="#0A0807" roughness={0.8} metalness={0.6} />
      </mesh>
    
      <mesh position={[0, 0.01, 0]}>
        <boxGeometry args={[cols * 1.35, 0.21, rows * 1.35]} />
        <meshStandardMaterial color="#00a1ff" wireframe transparent opacity={0.15} toneMapped={false} />
      </mesh>
    </group>
  );
}

export function HBMStacks({ smCount = 128 }) {
  const layerRef = useRef();
  
  useFrame(() => {
    const isExploded = useTelemetryStore.getState().isExplodedView;

    layerRef.current.position.y = lerp(layerRef.current.position.y, isExploded ? -3.0 : -0.2, 0.08);
  });

  const cols = Math.ceil(Math.sqrt(smCount * 1.2)); 
  const offsetX = (cols * 1.4) / 2 + 2; 

  return (
    <group ref={layerRef}>
      <mesh position={[-offsetX, 0.5, -3]} castShadow receiveShadow>
        <boxGeometry args={[2, 1.4, 3]} />
        <meshStandardMaterial color="#141110" roughness={0.5} metalness={0.9} />
      </mesh>
      <mesh position={[-offsetX, 0.5, 3]} castShadow receiveShadow>
        <boxGeometry args={[2, 1.4, 3]} />
        <meshStandardMaterial color="#141110" roughness={0.5} metalness={0.9} />
      </mesh>

      {/* Right Stacks */}
      <mesh position={[offsetX, 0.5, -3]} castShadow receiveShadow>
        <boxGeometry args={[2, 1.4, 3]} />
        <meshStandardMaterial color="#141110" roughness={0.5} metalness={0.9} />
      </mesh>
      <mesh position={[offsetX, 0.5, 3]} castShadow receiveShadow>
        <boxGeometry args={[2, 1.4, 3]} />
        <meshStandardMaterial color="#141110" roughness={0.5} metalness={0.9} />
      </mesh>
    </group>
  );
}

export default function GPUDieScene() {
  const activeGpuProfile = useTelemetryStore((state) => state.activeGpuProfile);
  const smCount = activeGpuProfile?.smCount || 64; 

  return (
    <Canvas shadows camera={{ position: [15, 15, 18], fov: 35 }}>
      <color attach="background" args={['#0D0B0A']} />
      <Environment preset="city" />
      
      <ambientLight intensity={0.1} color="#FF6A00" />
      
  
      <directionalLight 
        castShadow
        position={[15, 25, 10]} 
        intensity={2.5} 
        color="#F0E6DC"
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0001}
      >
      
        <orthographicCamera attach="shadow-camera" args={[-20, 20, 20, -20, 0.1, 50]} />
      </directionalLight>

      <MemoryFlowParticles />

      <group position={[0, 0, 0]}>
        <HBMStacks smCount={smCount} />
        <L2CacheLayer smCount={smCount} />
        <InstancedSMGrid smCount={smCount} />
      </group> 

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -4, 0]} receiveShadow>
        <planeGeometry args={[100, 100]} />
        <shadowMaterial transparent opacity={0.5} /> 
      </mesh>

      <OrbitControls enableDamping dampingFactor={0.05} maxPolarAngle={Math.PI / 2.2} />
      
      <EffectComposer disableNormalPass multisampling={4}>
        <Bloom luminanceThreshold={1.0} luminanceSmoothing={0.5} mipmapBlur intensity={0.8} />
      </EffectComposer>
    </Canvas>
  );
}