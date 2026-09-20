import React, { useEffect, useRef } from "react";

const COUNT = 70;
const BLUE = alpha => `rgba(155,182,203,${alpha})`;
const ORANGE = alpha => `rgba(221,174,139,${alpha})`;

export default function BackdropParticles() {
  const canvasRef = useRef(null);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    let width = 0, height = 0, frame = 0, last = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    const particles = [];
    const ripples = [];

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const spawn = particle => {
      particle.x = Math.random() * width;
      particle.y = Math.random() * height;
    };
    for (let index = 0; index < COUNT; index++) {
      particles.push({
        x: 0, y: 0,
        size: 1.5 + Math.random() * 1.5,
        color: Math.random() < 0.7 ? BLUE(0.12) : ORANGE(0.08),
        vx: Math.random() * 0.3 - 0.15,
        vy: -(0.1 + Math.random() * 0.2),
        mx: 0, my: 0,
        spawn
      });
      spawn(particles[index]);
    }
    const onPointer = event => {
      const x = event.clientX, y = event.clientY;
      ripples.push({ x, y, radius: 0, elapsed: 0, duration: 600, maxRadius: 180 });
      for (const particle of particles) {
        const dx = particle.x - x, dy = particle.y - y;
        const distance = Math.hypot(dx, dy);
        if (distance < 200 && distance > 0) {
          const force = ((200 - distance) / 200) * 3;
          particle.mx += (dx / distance) * force;
          particle.my += (dy / distance) * force;
        }
      }
    };
    const draw = () => {
      frame = requestAnimationFrame(draw);
      const now = performance.now();
      if (now - last < 1000 / 30) return;
      last = now;
      if (document.hidden) return;
      context.clearRect(0, 0, width, height);
      for (const particle of particles) {
        particle.mx *= 0.97;
        particle.my *= 0.97;
        particle.x += particle.vx + particle.mx;
        particle.y += particle.vy + particle.my;
        if (particle.y < -12) { particle.y = height + 12; particle.x = Math.random() * width; }
        if (particle.x < -12) particle.x = width + 12;
        else if (particle.x > width + 12) particle.x = -12;
        context.beginPath();
        context.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
        context.fillStyle = particle.color;
        context.fill();
      }
      for (let index = ripples.length - 1; index >= 0; index--) {
        const ripple = ripples[index];
        ripple.elapsed += 1000 / 30;
        if (ripple.elapsed >= ripple.duration) { ripples.splice(index, 1); continue; }
        ripple.radius = (ripple.elapsed / ripple.duration) * ripple.maxRadius;
        const alpha = 0.22 * (1 - ripple.elapsed / ripple.duration);
        context.beginPath();
        context.arc(ripple.x, ripple.y, ripple.radius, 0, Math.PI * 2);
        context.strokeStyle = BLUE(alpha);
        context.lineWidth = 1.2;
        context.stroke();
      }
    };
    resize();
    document.addEventListener("pointerdown", onPointer);
    window.addEventListener("resize", resize);
    frame = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("resize", resize);
    };
  }, []);
  return <canvas className="ri-backdrop-particles" ref={canvasRef} aria-hidden="true" />;
}