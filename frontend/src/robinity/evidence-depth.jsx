import React, { useEffect, useRef } from "react";
import * as THREE from "three";

export default function EvidenceDepth() {
  const host = useRef(null);
  useEffect(() => {
    const element = host.current;
    if (!element || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let renderer;
    try { renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" }); } catch { return; }
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 20);
    camera.position.set(0, 0, 4.2);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.4));
    renderer.setClearColor(0x000000, 0);
    element.appendChild(renderer.domElement);
    const count = 84;
    const positions = new Float32Array(count * 3), colors = new Float32Array(count * 3), base = new Float32Array(count * 3);
    const blue = new THREE.Color(0x9bb6cb), apricot = new THREE.Color(0xddae8b);
    for (let index = 0; index < count; index++) {
      const column = index % 12, row = Math.floor(index / 12), point = index * 3;
      const x = (column / 11 - 0.5) * 4.2 + Math.sin(row * 1.7 + column) * 0.11;
      const y = (row / 6 - 0.5) * 2.7 + Math.cos(column * 1.3) * 0.08;
      const z = Math.sin(column * 0.72 + row * 1.15) * 0.42;
      base[point] = positions[point] = x; base[point + 1] = positions[point + 1] = y; base[point + 2] = positions[point + 2] = z;
      const color = row === 3 || column === 7 ? apricot : blue;
      colors[point] = color.r; colors[point + 1] = color.g; colors[point + 2] = color.b;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const points = new THREE.Points(geometry, new THREE.PointsMaterial({ size: 0.058, vertexColors: true, transparent: true, opacity: 0.82, depthWrite: false }));
    scene.add(points);
    const lineVertices = [];
    for (let row = 0; row < 7; row++) for (let column = 0; column < 11; column++) {
      const a = (row * 12 + column) * 3, b = (row * 12 + column + 1) * 3;
      lineVertices.push(base[a], base[a + 1], base[a + 2], base[b], base[b + 1], base[b + 2]);
    }
    const linesGeometry = new THREE.BufferGeometry();
    linesGeometry.setAttribute("position", new THREE.Float32BufferAttribute(lineVertices, 3));
    const lines = new THREE.LineSegments(linesGeometry, new THREE.LineBasicMaterial({ color: 0x9bb6cb, transparent: true, opacity: 0.18 }));
    scene.add(lines);
    const pointer = new THREE.Vector2(); let target = new THREE.Vector2(); let visible = true; let frame = 0;
    const onMove = event => { const bounds = element.getBoundingClientRect(); target = new THREE.Vector2(((event.clientX - bounds.left) / bounds.width - 0.5) * 2, -((event.clientY - bounds.top) / bounds.height - 0.5) * 2); };
    const resize = () => { const width = element.clientWidth, height = element.clientHeight; if (!width || !height) return; renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix(); };
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; }, { threshold: 0.01 });
    const draw = time => { frame = requestAnimationFrame(draw); if (!visible || document.hidden) return; pointer.lerp(target, 0.04); points.rotation.y = pointer.x * 0.09; points.rotation.x = pointer.y * 0.05; lines.rotation.copy(points.rotation); const data = geometry.attributes.position.array; for (let index = 0; index < count; index++) data[index * 3 + 2] = base[index * 3 + 2] + Math.sin(time * 0.00038 + index * 0.43) * 0.08; geometry.attributes.position.needsUpdate = true; renderer.render(scene, camera); };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(element); observer.observe(element); element.addEventListener("pointermove", onMove, { passive: true }); resize(); draw(0);
    return () => { cancelAnimationFrame(frame); resizeObserver.disconnect(); observer.disconnect(); element.removeEventListener("pointermove", onMove); geometry.dispose(); linesGeometry.dispose(); points.material.dispose(); lines.material.dispose(); renderer.dispose(); renderer.domElement.remove(); };
  }, []);
  return <div className="ri-evidence-depth" ref={host} aria-hidden="true" />;
}
