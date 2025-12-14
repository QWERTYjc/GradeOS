'use client';

import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { useConsoleStore } from '@/store/consoleStore';

// Shader for the particles - Spherical Distribution & Gentle Motion
const particleVertexShader = `
  uniform float uTime;
  uniform float uSpeed;
  uniform float uExpansion;
  
  attribute float aScale;
  attribute vec3 aRandom;
  attribute vec3 aColor;
  
  varying vec3 vColor;
  
  void main() {
    vec3 pos = position;
    
    // Gentle breathing/expansion effect
    float breath = sin(uTime * 0.5) * 0.05 + 1.0;
    pos *= breath * uExpansion;
    
    // Subtle rotation based on y-axis
    float angle = uTime * 0.1 * uSpeed;
    float s = sin(angle);
    float c = cos(angle);
    mat2 rot = mat2(c, -s, s, c);
    pos.xz = rot * pos.xz;
    
    // Add some noise/turbulence
    pos.x += sin(pos.y * 2.0 + uTime) * 0.1;
    pos.z += cos(pos.x * 2.0 + uTime) * 0.1;

    vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mvPosition;
    
    // Size attenuation
    gl_PointSize = aScale * (400.0 / -mvPosition.z);
    
    vColor = aColor;
  }
`;

const particleFragmentShader = `
  varying vec3 vColor;
  
  void main() {
    // Soft circular particle
    float r = distance(gl_PointCoord, vec2(0.5));
    if (r > 0.5) discard;
    
    // Soft edge
    float alpha = 1.0 - smoothstep(0.3, 0.5, r);
    gl_FragColor = vec4(vColor, alpha * 0.8);
  }
`;

const Particles = () => {
    const mesh = useRef<THREE.Points>(null);
    const { status } = useConsoleStore();

    // Google Blue palette and variations
    const colors = ['#4285F4', '#8AB4F8', '#D2E3FC', '#1967D2'];
    const count = 4000;

    const uniforms = useMemo(() => ({
        uTime: { value: 0 },
        uSpeed: { value: 1.0 },
        uExpansion: { value: 1.0 },
    }), []);

    const particles = useMemo(() => {
        const tempPositions = new Float32Array(count * 3);
        const tempScales = new Float32Array(count);
        const tempRandoms = new Float32Array(count * 3);
        const tempColors = new Float32Array(count * 3);

        const colorObj = new THREE.Color();

        for (let i = 0; i < count; i++) {
            const i3 = i * 3;

            // Spherical distribution
            const r = 10 * Math.cbrt(Math.random()); // Cube root for uniform distribution in sphere
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);

            const x = r * Math.sin(phi) * Math.cos(theta);
            const y = r * Math.sin(phi) * Math.sin(theta);
            const z = r * Math.cos(phi);

            tempPositions[i3] = x;
            tempPositions[i3 + 1] = y;
            tempPositions[i3 + 2] = z;

            tempScales[i] = Math.random() * 0.8 + 0.2;

            tempRandoms[i3] = Math.random();
            tempRandoms[i3 + 1] = Math.random();
            tempRandoms[i3 + 2] = Math.random();

            // Pick random blue color
            colorObj.set(colors[Math.floor(Math.random() * colors.length)]);
            tempColors[i3] = colorObj.r;
            tempColors[i3 + 1] = colorObj.g;
            tempColors[i3 + 2] = colorObj.b;
        }
        return { positions: tempPositions, scales: tempScales, randoms: tempRandoms, colors: tempColors };
    }, [count]);

    useFrame((state) => {
        if (mesh.current) {
            const material = mesh.current.material as THREE.ShaderMaterial;
            if (material.uniforms) {
                material.uniforms.uTime.value = state.clock.elapsedTime;

                // React to state
                if (status === 'RUNNING') {
                    // Faster rotation, slight contraction
                    material.uniforms.uSpeed.value = THREE.MathUtils.lerp(material.uniforms.uSpeed.value, 3.0, 0.05);
                    material.uniforms.uExpansion.value = THREE.MathUtils.lerp(material.uniforms.uExpansion.value, 0.8, 0.05);
                } else if (status === 'UPLOADING') {
                    // Slow down, expand slightly
                    material.uniforms.uSpeed.value = THREE.MathUtils.lerp(material.uniforms.uSpeed.value, 0.2, 0.05);
                    material.uniforms.uExpansion.value = THREE.MathUtils.lerp(material.uniforms.uExpansion.value, 1.2, 0.05);
                } else {
                    // Idle state
                    material.uniforms.uSpeed.value = THREE.MathUtils.lerp(material.uniforms.uSpeed.value, 1.0, 0.05);
                    material.uniforms.uExpansion.value = THREE.MathUtils.lerp(material.uniforms.uExpansion.value, 1.0, 0.05);
                }
            }
        }
    });

    return (
        <points ref={mesh}>
            <bufferGeometry>
                <bufferAttribute
                    attach="attributes-position"
                    args={[particles.positions, 3]}
                />
                <bufferAttribute
                    attach="attributes-aScale"
                    args={[particles.scales, 1]}
                />
                <bufferAttribute
                    attach="attributes-aRandom"
                    args={[particles.randoms, 3]}
                />
                <bufferAttribute
                    attach="attributes-aColor"
                    args={[particles.colors, 3]}
                />
            </bufferGeometry>
            <shaderMaterial
                depthWrite={false}
                vertexColors
                transparent
                vertexShader={particleVertexShader}
                fragmentShader={particleFragmentShader}
                uniforms={uniforms}
            />
        </points>
    );
};

const CameraController = () => {
    const { camera } = useThree();
    const { status, view } = useConsoleStore();

    useFrame((state) => {
        const t = state.clock.elapsedTime;

        if (view === 'LANDING') {
            // Centered, rotating around the sphere
            camera.position.x = Math.sin(t * 0.1) * 20;
            camera.position.z = Math.cos(t * 0.1) * 20 + 10;
            camera.position.y = Math.sin(t * 0.05) * 5;
            camera.lookAt(0, 0, 0);
        } else {
            // CONSOLE VIEW
            // Pushed back to Z=40 to avoid text overlap, steady view
            const targetZ = status === 'RUNNING' ? 30 : 45;

            camera.position.x = THREE.MathUtils.lerp(camera.position.x, 0, 0.05);
            camera.position.y = THREE.MathUtils.lerp(camera.position.y, 0, 0.05);
            camera.position.z = THREE.MathUtils.lerp(camera.position.z, targetZ, 0.02);
            camera.lookAt(0, 0, 0);
        }
    });

    return null;
};

export default function AntiGravityScene() {
    return (
        <div className="fixed inset-0 -z-10 bg-white">
            <Canvas dpr={[1, 2]} camera={{ position: [0, 0, 25], fov: 45 }}>
                {/* Pure white fog to blend distant particles */}
                <fog attach="fog" args={['#ffffff', 15, 40]} />
                <ambientLight intensity={0.8} />
                <Particles />
                <CameraController />
            </Canvas>
        </div>
    );
}
