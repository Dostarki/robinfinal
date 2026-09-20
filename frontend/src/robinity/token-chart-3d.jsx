import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";

const COLORS = { blue: 0x8faac4, orange: 0xdca782, muted: 0xa2a6ad, text: 0xe8e5df };

const RINGS = [
  { name: "Presale allocation", amount: "200M", percent: "20%", color: COLORS.blue, radius: 1.42, tube: 0.032, tiltX: 0.3, tiltZ: 0.15, orbit: 0.28, glow: 0.052 },
  { name: "Engagement Rewards", amount: "50M", percent: "5%", color: COLORS.orange, radius: 1.86, tube: 0.021, tiltX: 1.1, tiltZ: -0.3, orbit: 0.4, glow: 0.04 },
  { name: "Remaining allocation", amount: "750M", percent: "75%", color: COLORS.muted, radius: 2.24, tube: 0.048, tiltX: 0.7, tiltZ: 0.5, orbit: 0.22, glow: 0.075 }
];

export default function TokenChart3D() {
  const host = useRef(null);
  const [label, setLabel] = useState(null);
  const currentHit = useRef(-1);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let renderer;
    try { renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" }); } catch { return; }
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 30);
    camera.position.set(0, 1.05, 8.8);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.4));
    renderer.setClearColor(0x000000, 0);
    element.appendChild(renderer.domElement);

    const rig = new THREE.Group();
    rig.position.y = 0.12;
    scene.add(rig);
    scene.add(new THREE.AmbientLight(COLORS.text, 0.92));
    const key = new THREE.PointLight(COLORS.blue, 5.8, 15);
    key.position.set(3.2, 3.4, 3);
    const warm = new THREE.PointLight(COLORS.orange, 3.8, 13);
    warm.position.set(-3.6, -2.7, -1.8);
    const rim = new THREE.DirectionalLight(0xdcecff, 3.2);
    rim.position.set(-3.8, 2.1, -4.5);
    scene.add(key, warm, rim);

    const core = new THREE.Mesh(new THREE.SphereGeometry(0.7, 64, 64), new THREE.MeshPhysicalMaterial({ color: 0xd8d8d2, roughness: 0.16, metalness: 0.34, clearcoat: 0.8, clearcoatRoughness: 0.18, transmission: 0.06, thickness: 0.35, emissive: 0x8faac4, emissiveIntensity: 0.035, transparent: true, opacity: 0.96 }));
    const innerGlow = new THREE.Mesh(new THREE.SphereGeometry(0.77, 48, 48), new THREE.MeshBasicMaterial({ color: 0xb2c4d5, transparent: true, opacity: 0.1, blending: THREE.AdditiveBlending, depthWrite: false }));
    const rimGlow = new THREE.Mesh(new THREE.SphereGeometry(0.9, 48, 48), new THREE.MeshBasicMaterial({ color: 0x9bb6cb, transparent: true, opacity: 0.065, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.BackSide }));
    rig.add(core, innerGlow, rimGlow);
    const disposables = [core.geometry, innerGlow.geometry, rimGlow.geometry, core.material, innerGlow.material, rimGlow.material];

    const ringMeshes = [];
    const ringGlowMeshes = [];
    RINGS.forEach((data, index) => {
      const material = new THREE.MeshStandardMaterial({ color: data.color, emissive: data.color, emissiveIntensity: 0.3, transparent: true, opacity: 0.8, metalness: 0.42, roughness: 0.32, side: THREE.DoubleSide });
      const ring = new THREE.Mesh(new THREE.TorusGeometry(data.radius, data.tube, 48, 28), material);
      ring.rotation.x = data.tiltX;
      ring.rotation.z = data.tiltZ;
      ring.userData.ringIndex = index;
      const glowMaterial = new THREE.MeshBasicMaterial({ color: data.color, transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
      const ringGlow = new THREE.Mesh(new THREE.TorusGeometry(data.radius, data.glow, 48, 28), glowMaterial);
      ringGlow.rotation.copy(ring.rotation);
      const satellite = new THREE.Mesh(new THREE.SphereGeometry(0.04, 16, 16), new THREE.MeshBasicMaterial({ color: data.color, transparent: true, opacity: 0.92 }));
      ring.add(satellite);
      rig.add(ringGlow, ring);
      ringMeshes.push(ring);
      ringGlowMeshes.push(ringGlow);
      disposables.push(ring.geometry, ring.material, ringGlow.geometry, ringGlow.material, satellite.geometry, satellite.material);
    });

    const dustCount = 30;
    const dustPositions = new Float32Array(dustCount * 3);
    for (let index = 0; index < dustCount; index++) {
      const radius = 2 + Math.random() * 1.2;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      dustPositions[index * 3] = radius * Math.sin(phi) * Math.cos(theta);
      dustPositions[index * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      dustPositions[index * 3 + 2] = radius * Math.cos(phi);
    }
    const dustGeometry = new THREE.BufferGeometry();
    dustGeometry.setAttribute("position", new THREE.BufferAttribute(dustPositions, 3));
    const dust = new THREE.Points(dustGeometry, new THREE.PointsMaterial({ size: 0.02, color: 0x9bb6cb, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false }));
    rig.add(dust);
    disposables.push(dustGeometry, dust.material);

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0, visible = true, contextLost = false;
    const pointer = new THREE.Vector2(), target = new THREE.Vector2();
    const raycaster = new THREE.Raycaster();
    const onMove = event => {
      const bounds = element.getBoundingClientRect();
      if (!bounds.width || !bounds.height) return;
      target.set(((event.clientX - bounds.left) / bounds.width - 0.5) * 2, -((event.clientY - bounds.top) / bounds.height - 0.5) * 2);
      scene.updateMatrixWorld();
      raycaster.setFromCamera(target, camera);
      const hit = raycaster.intersectObjects(ringMeshes, true)[0];
      const ring = hit ? ringMeshes.find(r => hit.object === r || hit.object.parent === r) : null;
      const next = ring ? ring.userData.ringIndex : -1;
      if (next === currentHit.current) return;
      currentHit.current = next;
      setLabel(next >= 0 ? RINGS[next] : null);
    };
    const onLeave = () => { currentHit.current = -1; setLabel(null); };
    const resize = () => { const width = element.clientWidth, height = element.clientHeight; if (!width || !height) return; renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix(); };
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; }, { threshold: 0.01 });
    const onContextLost = event => { event.preventDefault(); contextLost = true; };
    const draw = time => {
      frame = requestAnimationFrame(draw);
      if (!visible || document.hidden || contextLost) return;
      const elapsed = time * 0.001;
      pointer.lerp(target, 0.045);
      rig.rotation.y = elapsed * 0.12 + pointer.x * 0.28;
      rig.rotation.x = 0.14 + pointer.y * 0.18;
      rig.rotation.z = 0.04 - pointer.x * 0.08;
      rig.position.y = 0.12 + Math.sin(elapsed * 0.6) * 0.05;
      ringMeshes.forEach((ring, index) => {
        const angle = elapsed * RINGS[index].orbit;
        ring.children[0].position.set(Math.cos(angle) * RINGS[index].radius, Math.sin(angle) * RINGS[index].radius, 0);
      });
      dust.rotation.y = elapsed * 0.045;
      innerGlow.scale.setScalar(1 + Math.sin(elapsed * 0.8) * 0.05);
      rimGlow.scale.setScalar(1.02 + Math.sin(elapsed * 0.65) * 0.03);
      rig.updateMatrixWorld();
      ringMeshes.forEach((ring, index) => {
        const world = ring.getWorldPosition(new THREE.Vector3());
        const depth = THREE.MathUtils.clamp((world.z + 2.6) / 5.2, 0, 1);
        ring.material.opacity = 0.44 + depth * 0.42;
        ring.material.emissiveIntensity = 0.12 + depth * 0.32;
        ringGlowMeshes[index].material.opacity = 0.04 + depth * 0.16;
      });
      renderer.render(scene, camera);
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(element);
    observer.observe(element);
    element.addEventListener("pointermove", onMove, { passive: true });
    element.addEventListener("pointerleave", onLeave);
    element.addEventListener("webglcontextlost", onContextLost);
    resize();
    if (reduced) { rig.rotation.y = 0.6; rig.rotation.x = 0.16; renderer.render(scene, camera); } else { draw(0); }
    return () => {
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      observer.disconnect();
      element.removeEventListener("pointermove", onMove);
      element.removeEventListener("pointerleave", onLeave);
      element.removeEventListener("webglcontextlost", onContextLost);
      disposables.forEach(item => { try { item.dispose?.(); } catch {} });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);
  return <div className="ri-token-chart-host" ref={host} aria-hidden="true">{label && <div className="ri-token-chart-label"><b>{label.name}</b><small>{label.amount} · {label.percent}</small></div>}</div>;
}
