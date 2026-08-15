import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

/* ============================================================
   LearningCore — the AI Digital Tutor signature 3D identity.

   A "knowledge atom": a gold wireframe nucleus with inner glow,
   tilted knowledge orbits carrying learning nodes (gold / teal /
   warm white), and a sparse drifting particle halo. Slow ambient
   rotation, gentle float, subtle mouse parallax. Built entirely
   from basic materials (no lighting cost) with additive blending
   so it renders crisp on ink backgrounds.

   Accessibility & performance:
   - prefers-reduced-motion  → static scene (no rotation/parallax)
   - mobile                  → fewer particles, capped DPR
   - lazy-loaded by the Landing page (never in the main bundle)
   ============================================================ */

const GOLD = '#d9b86e';
const GOLD_LIGHT = '#ecd9a8';
const TEAL = '#5fd9ce';
const WARM = '#f2e8cf';

function usePrefersReducedMotion() {
  return useMemo(
    () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches,
    []
  );
}

/* Central nucleus: gold wireframe icosahedron + soft warm glow */
function Nucleus({ slow }) {
  const coreRef = useRef(null);
  const glowRef = useRef(null);

  useFrame(({ clock }) => {
    if (slow) return;
    const t = clock.getElapsedTime();
    coreRef.current.rotation.x = t * 0.16;
    coreRef.current.rotation.y = t * 0.22;
    const breathe = 1 + Math.sin(t * 0.9) * 0.015;
    coreRef.current.scale.setScalar(breathe);
    if (glowRef.current) {
      glowRef.current.scale.setScalar(1 + Math.sin(t * 0.9 + 1.2) * 0.05);
      glowRef.current.material.opacity = 0.1 + Math.sin(t * 0.9) * 0.03;
    }
  });

  return (
    <group>
      <mesh ref={coreRef}>
        <icosahedronGeometry args={[0.82, 1]} />
        <meshBasicMaterial color={GOLD} wireframe transparent opacity={0.85} />
      </mesh>
      <mesh ref={glowRef}>
        <sphereGeometry args={[0.95, 24, 24]} />
        <meshBasicMaterial
          color={WARM}
          transparent
          opacity={0.1}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

/* One knowledge orbit: ring + traveling nodes + faint counter-node */
function Orbit({ radius, tilt, color, speed, phase, nodeCount = 7, nodeColors, slow }) {
  const ringRef = useRef(null);
  const nodeRefs = useRef([]);

  useFrame(({ clock }) => {
    if (slow) return;
    const t = clock.getElapsedTime();
    ringRef.current.rotation.z += speed * 0.02;
    nodeRefs.current.forEach((n, i) => {
      if (!n) return;
      const a = phase + (i / nodeCount) * Math.PI * 2 + t * speed;
      n.position.set(Math.cos(a) * radius, Math.sin(a) * radius, Math.sin(a * 1.7) * radius * 0.35);
    });
  });

  return (
    <group rotation={tilt}>
      <mesh ref={ringRef}>
        <torusGeometry args={[radius, 0.012, 8, 96]} />
        <meshBasicMaterial color={color} transparent opacity={0.16} />
      </mesh>
      {Array.from({ length: nodeCount }).map((_, i) => (
        <mesh
          key={i}
          ref={(el) => (nodeRefs.current[i] = el)}
          position={[Math.cos(phase + (i / nodeCount) * Math.PI * 2) * radius, Math.sin(phase + (i / nodeCount) * Math.PI * 2) * radius, 0]}
        >
          <sphereGeometry args={[i % 3 === 0 ? 0.085 : 0.06, 12, 12]} />
          <meshBasicMaterial
            color={nodeColors[i % nodeColors.length]}
            transparent
            opacity={0.95}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ))}
    </group>
  );
}

/* Sparse drifting particle halo — information dust */
function ParticleHalo({ count, slow }) {
  const pointsRef = useRef(null);
  const { positions, colors } = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);
    const palette = [GOLD_LIGHT, TEAL, WARM];
    const gold = new THREE.Color(GOLD_LIGHT);
    const teal = new THREE.Color(TEAL);
    const warm = new THREE.Color(WARM);
    for (let i = 0; i < count; i++) {
      const r = 4.2 + Math.random() * 2.6;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.75;
      pos[i * 3 + 2] = r * Math.cos(phi);
      const c = palette[i % palette.length] === TEAL ? teal : i % 2 ? gold : warm;
      c.toArray(col, i * 3);
    }
    return { positions: pos, colors: col };
  }, [count]);

  useFrame(({ clock }) => {
    if (slow) return;
    pointsRef.current.rotation.y = clock.getElapsedTime() * 0.028;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.028}
        vertexColors
        transparent
        opacity={0.4}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

/* Whole assembly: float + parallax + slow rotation */
function CoreAssembly({ slow, isMobile }) {
  const groupRef = useRef(null);

  useFrame(({ clock, pointer }) => {
    if (slow) return;
    const t = clock.getElapsedTime();
    groupRef.current.rotation.y = t * 0.12;
    groupRef.current.position.y = Math.sin(t * 0.7) * 0.16;
    // Mouse parallax — damped toward the pointer
    groupRef.current.rotation.x += (pointer.y * 0.22 - groupRef.current.rotation.x) * 0.04;
    groupRef.current.rotation.z += (pointer.x * -0.08 - groupRef.current.rotation.z) * 0.04;
  });

  return (
    <group ref={groupRef}>
      <Nucleus slow={slow} />
      <Orbit radius={2.05} tilt={[Math.PI / 2.6, 0.35, 0]} color={GOLD} speed={0.5} phase={0.6} nodeCount={7} nodeColors={[GOLD_LIGHT, WARM]} slow={slow} />
      <Orbit radius={2.7} tilt={[Math.PI / 1.9, -0.4, 0.5]} color={TEAL} speed={-0.36} phase={2.1} nodeCount={6} nodeColors={[TEAL, GOLD_LIGHT]} slow={slow} />
      <Orbit radius={3.35} tilt={[Math.PI / 2.2, 0.9, -0.3]} color={GOLD} speed={0.27} phase={4.2} nodeCount={5} nodeColors={[WARM, TEAL]} slow={slow} />
      <ParticleHalo count={isMobile ? 55 : 110} slow={slow} />
    </group>
  );
}

export default function LearningCore({ className = '', style }) {
  const slow = usePrefersReducedMotion();
  const isMobile = useMemo(
    () => typeof window !== 'undefined' && window.innerWidth < 768,
    []
  );

  return (
    <div className={className} style={style} aria-hidden="true">
      <Canvas
        camera={{ position: [0, 0, 8.4], fov: 42 }}
        dpr={[1, isMobile ? 1.25 : 1.75]}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        style={{ background: 'transparent' }}
      >
        <CoreAssembly slow={slow} isMobile={isMobile} />
      </Canvas>
    </div>
  );
}