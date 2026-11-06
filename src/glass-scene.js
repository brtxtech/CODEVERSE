import { languageColor } from "./model.js";
import * as THREE from "three";
export function stackMetrics(repo) {
  return {
    layers:
      repo.commits == null
        ? 4
        : Math.min(
            42,
            3 + Math.floor(Math.log2(1 + Math.max(0, repo.commits)) * 2.6),
          ),
    width:
      1.25 +
      Math.min(
        2.5,
        Math.log10(1 + Math.max(0, repo.stars || repo.stargazers_count || 0)) *
          0.58,
      ),
    unknown: repo.commits == null,
  };
}
export function createGlassScene(canvas, onSelect) {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scene = new THREE.Scene();
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    preserveDrawingBuffer: true,
  });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.8));
  renderer.setClearColor(0x071017, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.4;
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 150);
  camera.position.set(17, 18, 24);
  camera.lookAt(0, 4, 0);
  scene.add(new THREE.HemisphereLight(0xc9ffff, 0x202c48, 3));
  const light = new THREE.DirectionalLight(0xc0ffec, 5);
  light.position.set(-5, 20, 10);
  scene.add(light);
  const pink = new THREE.PointLight(0xff2b9d, 70, 32);
  pink.position.set(-8, 4, 3);
  scene.add(pink);
  const group = new THREE.Group();
  scene.add(group);
  const ray = new THREE.Raycaster(),
    pointer = new THREE.Vector2();
  let objects = [],
    start = performance.now(),
    raf;
  const colors = [0x5fffd5, 0x84b7ff, 0xbda4ff, 0x74dfed, 0xfb96bb, 0xf5cc86];
  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(13, 96),
    new THREE.MeshStandardMaterial({
      color: 0x10262c,
      metalness: 0.6,
      roughness: 0.24,
      transparent: true,
      opacity: 0.6,
    }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.scale.y = 0.8;
  scene.add(floor);
  const grid = new THREE.GridHelper(24, 24, 0x25585c, 0x163036);
  grid.position.y = 0.02;
  scene.add(grid);
  const starsGeo = new THREE.BufferGeometry();
  const points = Array.from({ length: 240 }, (_, i) => Math.sin(i * 7919) * 23);
  starsGeo.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(points, 3),
  );
  const particles = new THREE.Points(
    starsGeo,
    new THREE.PointsMaterial({
      color: 0x78dcca,
      size: 0.035,
      transparent: true,
      opacity: 0.5,
    }),
  );
  scene.add(particles);
  function clear() {
    group.children.slice().forEach((o) => {
      o.traverse((v) => {
        v.geometry?.dispose();
        if (Array.isArray(v.material)) v.material.forEach((m) => m.dispose());
        else {
          v.material?.map?.dispose();
          v.material?.dispose();
        }
      });
      group.remove(o);
    });
    objects = [];
  }
  function build(repos) {
    clear();
    const items = repos.slice(0, 24),
      cols = Math.ceil(Math.sqrt(items.length));
    items.forEach((repo, i) => {
      const m = stackMetrics(repo),
        stack = new THREE.Group(),
        x = ((i % cols) - (cols - 1) / 2) * 3.55,
        z =
          (Math.floor(i / cols) - (Math.ceil(items.length / cols) - 1) / 2) *
          3.55;
      stack.position.set(x, 0, z);
      stack.userData.offset = i * 0.06;
      group.add(stack);
      const color = languageColor(repo.language || "Unknown"),
        geo = new THREE.BoxGeometry(m.width, 0.17, m.width),
        edges = new THREE.EdgesGeometry(geo);
      for (let j = 0; j < m.layers; j++) {
        const mix = new THREE.Color(j < m.layers * 0.24 ? 0xdf348f : color);
        const mat = new THREE.MeshPhysicalMaterial({
          color: mix,
          metalness: 0.28,
          roughness: 0.1,
          transparent: true,
          opacity: 0.65,
          transmission: 0.18,
          thickness: 0.5,
          clearcoat: 1,
          emissive: mix,
          emissiveIntensity: 0.13,
          depthWrite: false,
        });
        const slab = new THREE.Mesh(geo, mat);
        slab.position.y = 0.3 + j * 0.25;
        slab.userData.repo = repo;
        stack.add(slab);
        objects.push(slab);
        const line = new THREE.LineSegments(
          edges,
          new THREE.LineBasicMaterial({
            color: mix,
            transparent: true,
            opacity: 0.68,
          }),
        );
        line.position.copy(slab.position);
        stack.add(line);
      }
      const cap = new THREE.Mesh(
        new THREE.BoxGeometry(m.width + 0.04, 0.1, m.width + 0.04),
        new THREE.MeshPhysicalMaterial({
          color: 0xa6eee0,
          metalness: 0.55,
          roughness: 0.1,
          transparent: true,
          opacity: 0.75,
          clearcoat: 1,
        }),
      );
      cap.position.y = 0.45 + m.layers * 0.25;
      stack.add(cap);
      const textCanvas = document.createElement("canvas");
      textCanvas.width = 512;
      textCanvas.height = 128;
      const ctx = textCanvas.getContext("2d");
      ctx.textAlign = "center";
      ctx.fillStyle = "#c6ffef";
      ctx.font = "48px sans-serif";
      ctx.fillText(String(repo.commits ?? "?"), 256, 55);
      ctx.fillStyle = "#9bbeb8";
      ctx.font = "22px sans-serif";
      ctx.fillText(repo.name.slice(0, 24), 256, 100);
      const texture = new THREE.CanvasTexture(textCanvas);
      const label = new THREE.Sprite(
        new THREE.SpriteMaterial({
          map: texture,
          transparent: true,
          depthWrite: false,
        }),
      );
      label.position.set(0, m.layers * 0.25 + 1.1, 0);
      label.scale.set(3.5, 0.875, 1);
      stack.add(label);
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(m.width * 0.52, m.width * 0.58, 4),
        new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          opacity: 0.4,
          side: THREE.DoubleSide,
        }),
      );
      ring.rotation.x = -Math.PI / 2;
      ring.rotation.z = Math.PI / 4;
      ring.position.y = 0.04;
      stack.add(ring);
    });
    start = performance.now();
  }
  const obs = new ResizeObserver(() => {
    const w = canvas.clientWidth,
      h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  });
  obs.observe(canvas);
  canvas.addEventListener("click", (e) => {
    if (moved) {
      moved = false;
      return;
    }
    const r = canvas.getBoundingClientRect();
    pointer.set(
      ((e.clientX - r.left) / r.width) * 2 - 1,
      (-(e.clientY - r.top) / r.height) * 2 + 1,
    );
    ray.setFromCamera(pointer, camera);
    const hit = ray.intersectObjects(objects)[0];
    if (hit) onSelect?.(hit.object.userData.repo);
  });
  let drag = false,
    oldX = 0,
    moved = false;
  canvas.addEventListener("pointerdown", (e) => {
    drag = true;
    oldX = e.clientX;
    moved = false;
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const d = e.clientX - oldX;
    if (Math.abs(d) > 2) moved = true;
    group.rotation.y += d * 0.005;
    oldX = e.clientX;
  });
  window.addEventListener("pointerup", () => (drag = false));
  function frame(now) {
    raf = requestAnimationFrame(frame);
    const t = (now - start) / 1000;
    group.children.forEach((s) => {
      const progress = reduced
        ? 1
        : Math.min(1, Math.max(0.01, (t - s.userData.offset) * 1.3));
      s.scale.y = 1 - Math.pow(1 - progress, 3);
    });
    if (!reduced) particles.rotation.y = now * 0.000015;
    renderer.render(scene, camera);
  }
  raf = requestAnimationFrame(frame);
  return {
    build,
    download() {
      const a = document.createElement("a");
      a.download = "codeverse-glass-stacks.png";
      a.href = canvas.toDataURL("image/png");
      a.click();
    },
    destroy() {
      cancelAnimationFrame(raf);
      obs.disconnect();
      clear();
      renderer.dispose();
    },
  };
}
