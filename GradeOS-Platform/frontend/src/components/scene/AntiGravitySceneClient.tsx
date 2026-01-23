'use client';

import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { useConsoleStore } from '@/store/consoleStore';

// Shader for soft circles
const circleVertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const circleFragmentShader = `
  varying vec2 vUv;
  uniform vec3 uColor;
  uniform float uOpacity;
  
  void main() {
    float dist = distance(vUv, vec2(0.5));
    // Soft edge gradient: solid until 0.3, then fades to 0.5
    float alpha = 1.0 - smoothstep(0.3, 0.5, dist);
    
    if (dist > 0.5) discard; // Clip to circle
    
    gl_FragColor = vec4(uColor, alpha * uOpacity);
  }
`;

// Floating Circles Component
const FloatingCircles = () => {
    const config = useMemo(() => [
        { radius: 3.5, opacity: 0.03, speed: 0.05 * 0.7 },
        { radius: 5.0, opacity: 0.06, speed: 0.03 * 0.7 },
        { radius: 2.0, opacity: 0.10, speed: 0.07 * 0.7 },
        { radius: 4.5, opacity: 0.10, speed: 0.04 * 0.3 },
        { radius: 1.5, opacity: 0.15, speed: 0.08 * 0.3 },
        { radius: 6.0, opacity: 0.04, speed: 0.02 * 0.3 },
    ], []);

    const meshRefs = useRef<(THREE.Mesh | null)[]>([]);

    // Initialize random positions and directions
    const stateRef = useRef(config.map(c => {
        const angle = Math.random() * Math.PI * 2;
        return {
            x: (Math.random() - 0.5) * 20,
            y: (Math.random() - 0.5) * 20,
            vx: Math.cos(angle) * c.speed,
            vy: Math.sin(angle) * c.speed
        };
    }));

    useFrame((state) => {
        const { width, height } = state.viewport;
        const halfWidth = width / 2;
        const halfHeight = height / 2;

        meshRefs.current.forEach((mesh, i) => {
            if (!mesh) return;

            const s = stateRef.current[i];
            const c = config[i];

            // Update position
            s.x += s.vx;
            s.y += s.vy;

            // Bounce logic
            if (s.x + c.radius > halfWidth) {
                s.x = halfWidth - c.radius;
                s.vx = -Math.abs(s.vx);
            } else if (s.x - c.radius < -halfWidth) {
                s.x = -halfWidth + c.radius;
                s.vx = Math.abs(s.vx);
            }

            if (s.y + c.radius > halfHeight) {
                s.y = halfHeight - c.radius;
                s.vy = -Math.abs(s.vy);
            } else if (s.y - c.radius < -halfHeight) {
                s.y = -halfHeight + c.radius;
                s.vy = Math.abs(s.vy);
            }

            mesh.position.set(s.x, s.y, 0);
        });
    });

    // Baby Blue Color
    const color = new THREE.Color('#AEC9D6');

    return (
        <>
            {config.map((c, i) => (
                <mesh key={i} ref={el => { meshRefs.current[i] = el; }}>
                    <planeGeometry args={[c.radius * 2, c.radius * 2]} />
                    <shaderMaterial
                        vertexShader={circleVertexShader}
                        fragmentShader={circleFragmentShader}
                        uniforms={{
                            uColor: { value: color },
                            uOpacity: { value: c.opacity }
                        }}
                        transparent
                        depthWrite={false}
                    />
                </mesh>
            ))}
        </>
    );
};

const CameraController = () => {
    const { camera } = useThree();
    const status = useConsoleStore((state) => state.status);

    useFrame((state) => {
        const t = state.clock.elapsedTime;

        // Very subtle movement
        camera.position.x = Math.sin(t * 0.05) * 0.5;
        camera.position.y = Math.cos(t * 0.05) * 0.5;

        // Zoom based on status
        const targetZ = status === 'RUNNING' ? 25 : 30;
        camera.position.z = THREE.MathUtils.lerp(camera.position.z, targetZ, 0.02);

        camera.lookAt(0, 0, 0);
    });

    return null;
};

export default function AntiGravitySceneClient() {
    return (
        <div className="fixed inset-0 -z-10 bg-white">
            <Canvas dpr={[1, 2]} camera={{ position: [0, 0, 30], fov: 45 }}>
                <FloatingCircles />
                <CameraController />
            </Canvas>
        </div>
    );
}
