/* ==========================================================================
   AQUILA - Digital Twin 3D WebGL Engine (Three.js)
   Real-World Benchmark: University of Lille (Polytech'Lille) Campus Network
   ========================================================================== */

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

/* ---------- Topology Network Definition (Polytech'Lille Benchmark) ---------- */
const N = [], E = [], V = THREE.Vector3;

const addN = (x, y, z, id, name, isQuality = false) => {
  const n = {
    p: new V(x, y, z),
    id,
    name,
    isQuality,
    adj: [],
    trust: 100,
    tt: 100,
    st: 'ok',
    pr: 58 + Math.random() * 8,
    cl: 0.85
  };
  N.push(n);
  return N.length - 1;
};

const addE = (a, b) => {
  E.push({ a, b, m: 'ok' });
  N[a].adj.push(b);
  N[b].adj.push(a);
};

// 25 Real-World Campus Nodes (Matching University of Lille diagram)
// 0: Main Municipal Water Supply Intake (North)
addN(1.8, 1.8, -9.5, 'RES', "North Metro Supply Intake & Reservoir");

// Outer Loop Perimeter
addN(-3.8, 0.6, -8.0, 'S1', "North-West Loop (Av. Poincaré)");
addN(-7.6, 0.3, -5.2, 'S2', "Faculty of Biology & Earth Sciences");
addN(-8.9, 0.1, -1.2, 'S3', "West Ring (Av. Paul Langevin)");
addN(-8.0, -0.2, 3.4, 'S4', "Polytech'Lille West Service Branch");
addN(-5.8, -0.4, 6.8, 'S5', "Polytech'Lille South Feeder");

// 6: Polytech'Lille Main Engineering Hall (WATER QUALITY SENSOR)
addN(-3.6, 0.4, 2.4, 'S6', "Polytech'Lille (Water Quality Sensor)", true);

// 7: North-East Ring
addN(6.2, 0.5, -4.0, 'S7', "North-East Loop (Av. Mendeleïev)");

// 8: Barrois Restaurant (WATER QUALITY SENSOR)
addN(3.8, 0.8, -6.2, 'S8', "Barrois Restaurant (Water Quality Sensor)", true);

// 9-11: East and South Outer Loop
addN(8.6, 0.1, 0.5, 'S9', "East Campus Gate & Main Arterial");
addN(6.8, -0.3, 5.2, 'S10', "South-East Residential Sector");
addN(0.8, -0.5, 7.9, 'S11', "South Campus Perimeter Loop");

// 12-24: Interior Campus Hubs & Academic Wings
addN(1.6, 0.5, 0.4, 'S12', "LILLIAD Central Library & Roundabout");
addN(-1.2, 0.3, -1.8, 'S13', "Campus Health Center & Clinic");
addN(-4.6, 0.2, -1.8, 'S14', "Computer Science & Robotics (M3)");
addN(-2.2, 0.4, -4.6, 'S15', "Chemistry Research Wing (C1-C5)");
addN(1.2, 0.6, -4.0, 'S16', "North Dining & Student Hall");
addN(-3.2, -0.2, 5.4, 'S17', "Materials Research Center (IEMN)");
addN(5.0, 0.2, 2.2, 'S18', "East Residence Village (Bachelard)");
addN(3.5, -0.2, 4.8, 'S19', "Sports Pavilion & Student Union");
addN(-0.6, 0.1, 3.6, 'S20', "Applied Mathematics Tower (M1-M2)");
addN(-1.6, -0.4, 6.6, 'S21', "Care Clinic & South Infirmary");
addN(-4.8, -0.6, 9.4, 'S22', "South Campus Extension");
addN(-4.0, -0.8, 11.2, 'S23', "Ascq Distribution Outfall");
addN(-5.2, 0.6, -9.8, 'S24', "North-West Outer Branch");

// Campus Conduits (Pipes)
addE(0, 1); addE(1, 2); addE(2, 3); addE(3, 4); addE(4, 5);
addE(5, 11); addE(11, 10); addE(10, 9); addE(9, 7); addE(7, 8); addE(8, 0);
addE(0, 8); addE(0, 16); addE(8, 16); addE(8, 7);
addE(12, 16); addE(12, 9); addE(12, 18); addE(12, 13); addE(12, 20);
addE(6, 4); addE(6, 5); addE(6, 17); addE(6, 20); addE(6, 14);
addE(14, 3); addE(14, 15); addE(15, 2); addE(15, 16); addE(13, 15);
addE(13, 20); addE(17, 21); addE(21, 11); addE(20, 19); addE(19, 10);
addE(18, 19); addE(18, 9);
addE(5, 22); addE(22, 23); addE(1, 24);

/* Floating 3D Interactive Landmark Icon Pins */
const PIN_ICONS = {
  0: { icon: '💧', label: 'Supply Intake', color: '#0284c7' },
  6: { icon: '🔬', label: "Polytech'Lille Quality", color: '#ff2d55', isSpecial: true },
  8: { icon: '🍽️', label: 'Barrois Quality', color: '#ff2d55', isSpecial: true },
  12: { icon: '📚', label: 'LILLIAD Hub', color: '#06b6d4', isSpecial: true },
  13: { icon: '🏥', label: 'Health Clinic', color: '#10b981' },
  14: { icon: '🤖', label: 'CompSci (M3)', color: '#38bdf8' },
  15: { icon: '🧪', label: 'Chemistry (C1)', color: '#38bdf8' },
  17: { icon: '⚡', label: 'IEMN Research', color: '#38bdf8' },
  18: { icon: '🏡', label: 'Student Dorms', color: '#38bdf8' },
  19: { icon: '🏅', label: 'Sports Union', color: '#38bdf8' },
  20: { icon: '📐', label: 'Math Tower (M1)', color: '#38bdf8' },
  21: { icon: '🚑', label: 'Care Clinic', color: '#10b981' }
};

const pinsContainer = $('#pinsContainer');
if (pinsContainer) {
  pinsContainer.innerHTML = '';
  N.forEach((n, i) => {
    const info = PIN_ICONS[i] || { icon: '💧', label: n.id, color: '#0284c7', isSmall: true };
    const pin = document.createElement('div');
    pin.className = 'pin' + (info.isSpecial ? ' special' : '') + (info.isSmall ? ' small' : '');
    pin.dataset.i = i;
    pin.innerHTML = `
      <div class="pin-badge" style="background:${info.color}; border:2px solid #ffffffdd; box-shadow:0 0 12px ${info.color};">
        ${info.icon}
      </div>
      <div class="pin-label">${info.label}</div>
    `;
    pin.onclick = (e) => {
      e.stopPropagation();
      showCard(i);
      const p = n.p;
      targetTh = Math.atan2(p.x, p.z) + 0.35;
      targetPh = 0.95;
      targetRad = 20;
      idle = 0;
    };
    pinsContainer.appendChild(pin);
    n.pinEl = pin;
  });
}

/* ---------- Three.js Scene Setup ---------- */
const stage = $('#stage');
const R = new THREE.WebGLRenderer({ antialias: true, alpha: true });
R.setPixelRatio(Math.min(devicePixelRatio, 2));
stage.prepend(R.domElement);

const sc = new THREE.Scene();
sc.fog = new THREE.FogExp2(0x030711, 0.014);
const cam = new THREE.PerspectiveCamera(48, 1, 0.1, 200);

// Campus Lighting for 3D Buildings
const ambLight = new THREE.AmbientLight(0xffffff, 0.9);
sc.add(ambLight);
const dirLight = new THREE.DirectionalLight(0xfff5e6, 0.7);
dirLight.position.set(12, 24, 18);
sc.add(dirLight);

const grid = new THREE.GridHelper(46, 46, 0x0e4a6e, 0x0a2236);
grid.position.y = -3.6;
sc.add(grid);

/* Real-Life Campus Buildings (Extruded Volumes matching the Lille map) */
const BUILDINGS = [
  // Polytech'Lille Complex (linked to node 6: Water Quality Station)
  { x: -3.8, z: 2.5, w: 2.8, d: 1.6, h: 0.9, rot: 0.15, node: 6 },
  { x: -4.5, z: 3.5, w: 1.8, d: 1.2, h: 0.75, rot: 0.15, node: 6 },
  { x: -2.8, z: 2.8, w: 1.2, d: 1.8, h: 0.8, rot: 0.15, node: 6 },
  // Barrois Restaurant (linked to node 8: Water Quality Station)
  { x: 3.8, z: -5.8, w: 1.9, d: 1.7, h: 0.75, rot: -0.2, node: 8 },
  // LILLIAD Learning Center Innovation (linked to node 12: Central Hub)
  { x: 1.6, z: 0.4, w: 2.0, d: 2.0, h: 0.95, isCyl: true, node: 12 },
  // Computer Science & Automation (M3, linked to node 14)
  { x: -4.8, z: -1.6, w: 2.4, d: 1.3, h: 0.85, rot: 0.1, node: 14 },
  // Chemistry & Materials Labs (linked to node 15 / 17)
  { x: -2.2, z: -4.5, w: 2.2, d: 1.4, h: 0.8, rot: -0.1, node: 15 },
  { x: -4.2, z: -3.8, w: 1.6, d: 1.2, h: 0.7, rot: 0.2, node: 15 },
  { x: -0.8, z: -5.5, w: 1.5, d: 1.1, h: 0.75, rot: -0.15, node: 16 },
  // Mathematics & Physics Wings (linked to node 20)
  { x: -0.5, z: 3.6, w: 1.8, d: 1.5, h: 0.85, rot: 0.05, node: 20 },
  // East Student Village & Dormitories (linked to node 18)
  { x: 5.6, z: 1.8, w: 1.2, d: 2.2, h: 1.1, rot: 0.3, node: 18 },
  { x: 6.2, z: 3.8, w: 1.1, d: 1.8, h: 0.95, rot: 0.35, node: 18 },
  { x: 4.8, z: -2.2, w: 1.4, d: 1.3, h: 0.8, rot: -0.1, node: 7 },
  // North Facilities & Metro (linked to node 0)
  { x: 1.5, z: -7.5, w: 2.0, d: 1.2, h: 0.65, rot: 0, node: 0 },
  { x: -1.5, z: -8.0, w: 1.5, d: 1.4, h: 0.7, rot: 0.1, node: 1 },
  // South Sports Complex & Research (linked to node 17 / 19)
  { x: -2.8, z: 7.2, w: 2.2, d: 1.6, h: 0.75, rot: 0.2, node: 17 },
  { x: 3.2, z: 6.0, w: 1.8, d: 1.3, h: 0.7, rot: -0.2, node: 19 }
];

const bMat = new THREE.MeshLambertMaterial({ color: 0xdfb17b, transparent: true, opacity: 0.78 });
const bWireMat = new THREE.LineBasicMaterial({ color: 0xf5d4a6, transparent: true, opacity: 0.45 });
const clickableObjects = [];

BUILDINGS.forEach(b => {
  let geo = b.isCyl
    ? new THREE.CylinderGeometry(b.w / 2, b.w / 2, b.h, 24)
    : new THREE.BoxGeometry(b.w, b.h, b.d);
  const mesh = new THREE.Mesh(geo, bMat);
  mesh.position.set(b.x, b.h / 2 - 0.2, b.z);
  if (b.rot) mesh.rotation.y = b.rot;
  mesh.userData.i = b.node;
  mesh.userData.isBuilding = true;
  sc.add(mesh);
  clickableObjects.push(mesh);
  const edges = new THREE.EdgesGeometry(geo);
  mesh.add(new THREE.LineSegments(edges, bWireMat));
});

const Y = new V(0, 1, 0), pm = [], gm = [];

E.forEach(e => {
  const a = N[e.a].p, b = N[e.b].p, d = b.clone().sub(a), L = d.length();
  const q = new THREE.Quaternion().setFromUnitVectors(Y, d.clone().normalize());
  const mid = a.clone().add(b).multiplyScalar(0.5);

  const m1 = new THREE.Mesh(
    new THREE.CylinderGeometry(0.08, 0.08, L, 8),
    new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.6 })
  );
  const m2 = new THREE.Mesh(
    new THREE.CylinderGeometry(0.22, 0.22, L, 8),
    new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.08, blending: THREE.AdditiveBlending, depthWrite: false })
  );

  [m1, m2].forEach(m => {
    m.position.copy(mid);
    m.quaternion.copy(q);
    sc.add(m);
  });
  pm.push(m1);
  gm.push(m2);
});

const sm = [];
N.forEach((n, i) => {
  const isWQ = n.isQuality;
  const col = isWQ ? 0xff2d55 : (i ? 0x22d3ee : 0x38bdf8);
  const geo = i
    ? new THREE.SphereGeometry(isWQ ? 0.46 : 0.34, 20, 20)
    : new THREE.IcosahedronGeometry(0.85, 1);
  const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: col, wireframe: !i }));
  m.position.copy(n.p);
  m.userData.i = i;
  sc.add(m);
  sm.push(m);
  clickableObjects.push(m);

  // Generous invisible hit target (easy clicking on any device)
  const hit = new THREE.Mesh(new THREE.SphereGeometry(1.8, 12, 12), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }));
  hit.position.copy(n.p);
  hit.userData.i = i;
  sc.add(hit);
  clickableObjects.push(hit);

  if (i) {
    const h = new THREE.Mesh(
      new THREE.RingGeometry(isWQ ? 0.58 : 0.46, isWQ ? 0.68 : 0.54, 32),
      new THREE.MeshBasicMaterial({
        color: col,
        transparent: true,
        opacity: isWQ ? 0.65 : 0.35,
        side: THREE.DoubleSide
      })
    );
    h.position.copy(n.p);
    h.lookAt(cam.position);
    n.halo = h;
    h.userData.i = i;
    sc.add(h);
    clickableObjects.push(h);
  }
});

// Selection pulsing halo in 3D
const selMesh = new THREE.Group();
const selRing1 = new THREE.Mesh(new THREE.RingGeometry(0.75, 1.0, 32), new THREE.MeshBasicMaterial({ color: 0x38bdf8, side: 2, transparent: true, opacity: 0.9 }));
const selRing2 = new THREE.Mesh(new THREE.RingGeometry(1.2, 1.45, 32), new THREE.MeshBasicMaterial({ color: 0x22d3ee, side: 2, transparent: true, opacity: 0.55 }));
selRing1.rotation.x = Math.PI / 2;
selRing2.rotation.x = Math.PI / 2;
selMesh.add(selRing1);
selMesh.add(selRing2);
selMesh.visible = false;
sc.add(selMesh);

const qr = new THREE.Mesh(
  new THREE.TorusGeometry(1.1, 0.06, 8, 40),
  new THREE.MeshBasicMaterial({ color: 0xff2d55 })
);
qr.rotation.x = Math.PI / 2;
qr.visible = false;
sc.add(qr);

/* Particle Flow Mesh */
const cv = document.createElement('canvas');
cv.width = cv.height = 64;
const cx = cv.getContext('2d'), g = cx.createRadialGradient(32, 32, 0, 32, 32, 32);
g.addColorStop(0, '#fff');
g.addColorStop(0.4, '#fff9');
g.addColorStop(1, '#fff0');
cx.fillStyle = g;
cx.fillRect(0, 0, 64, 64);

const P = [];
E.forEach((e, i) => {
  for (let j = 0; j < 8; j++) {
    P.push({ e: i, t: Math.random(), s: 0.12 + Math.random() * 0.1, c: j % 2 });
  }
});

const pg = new THREE.BufferGeometry();
pg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(P.length * 3), 3));
pg.setAttribute('color', new THREE.BufferAttribute(new Float32Array(P.length * 3), 3));
sc.add(
  new THREE.Points(
    pg,
    new THREE.PointsMaterial({
      size: 0.5,
      map: new THREE.CanvasTexture(cv),
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    })
  )
);

const C = {
  ok: [new THREE.Color(0x38bdf8), new THREE.Color(0x4ade80)],
  leak: [new THREE.Color(0xfb923c), new THREE.Color(0xfbbf24)],
  contam: [new THREE.Color(0xa855f7), new THREE.Color(0xd946ef)],
  spoof: [new THREE.Color(0xff2d55), new THREE.Color(0xff8fa3)]
};
const SP = { ok: 1, leak: 2.2, contam: 0.5, spoof: 1 };

/* ---------- Camera Damping & Generous Interactive Picking ---------- */
let th = 0.8, ph = 1.05, rad = 26;
let targetTh = th, targetPh = ph, targetRad = rad;
let drag = 0, lx = 0, ly = 0, downX = 0, downY = 0, isDrag = false, idle = 0;
const cvs = R.domElement;

function zoomIn() {
  targetRad = Math.max(12, targetRad - 4);
  idle = 0;
}
function zoomOut() {
  targetRad = Math.min(42, targetRad + 4);
  idle = 0;
}

cvs.addEventListener('pointerdown', e => {
  downX = lx = e.clientX;
  downY = ly = e.clientY;
  isDrag = false;
  drag = 1;
  cvs.style.cursor = 'grabbing';
});

cvs.addEventListener('pointermove', e => {
  if (drag) {
    const dx = e.clientX - lx, dy = e.clientY - ly;
    if (Math.hypot(e.clientX - downX, e.clientY - downY) > 7) isDrag = true;
    targetTh -= dx * 0.005;
    targetPh = Math.max(0.2, Math.min(1.48, targetPh - dy * 0.004));
    lx = e.clientX;
    ly = e.clientY;
    idle = 0;
    return;
  }
  const r = cvs.getBoundingClientRect();
  mp.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  rc.setFromCamera(mp, cam);
  const hits = rc.intersectObjects(clickableObjects, true);
  let found = null;
  if (hits.length > 0) {
    for (let h of hits) {
      let obj = h.object;
      while (obj && obj.userData.i === undefined && obj.parent) obj = obj.parent;
      if (obj && obj.userData.i !== undefined) { found = obj.userData.i; break; }
    }
  }
  const hb = $('#hoverBadge');
  if (found !== null) {
    cvs.style.cursor = 'pointer';
    if (hb) {
      hb.innerHTML = `📍 <b>${N[found].id}</b>: ${N[found].name || 'Sensor'}<br><span style="font-size:10.5px;color:#9bb7d0">Click to inspect</span>`;
      hb.style.display = 'block';
      hb.style.left = Math.min(r.width - 220, Math.max(10, e.clientX - r.left + 16)) + 'px';
      hb.style.top = Math.max(10, e.clientY - r.top - 42) + 'px';
    }
  } else {
    cvs.style.cursor = 'grab';
    if (hb) hb.style.display = 'none';
  }
});

cvs.addEventListener('pointerup', e => {
  drag = 0;
  cvs.style.cursor = 'grab';
  if (!isDrag && Math.hypot(e.clientX - downX, e.clientY - downY) < 18) {
    pick(e);
  }
});

cvs.addEventListener('click', e => {
  if (!isDrag && Math.hypot(e.clientX - downX, e.clientY - downY) < 18) {
    pick(e);
  }
});

// Allow natural window scroll unless Ctrl is held down
cvs.addEventListener(
  'wheel',
  e => {
    if (e.ctrlKey || drag) {
      e.preventDefault();
      targetRad = Math.max(12, Math.min(42, targetRad + e.deltaY * 0.02));
      idle = 0;
    }
  },
  { passive: false }
);

const rc = new THREE.Raycaster(), mp = new THREE.Vector2();

function pick(e) {
  const r = cvs.getBoundingClientRect();
  mp.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  rc.setFromCamera(mp, cam);
  const hits = rc.intersectObjects(clickableObjects, true);
  let targetIdx = -1;
  if (hits.length > 0) {
    for (let h of hits) {
      let obj = h.object;
      while (obj && obj.userData.i === undefined && obj.parent) obj = obj.parent;
      if (obj && obj.userData.i !== undefined && obj.userData.i >= 0) {
        targetIdx = obj.userData.i;
        break;
      }
    }
  }
  if (targetIdx >= 0) {
    showCard(targetIdx);
    const p = N[targetIdx].p;
    targetTh = Math.atan2(p.x, p.z) + 0.35;
    targetPh = 0.95;
    targetRad = 20;
    idle = 0;
  }
}

let sel = -1;

function showCard(i) {
  sel = i;
  $('#card').classList.add('show');
  const n = N[i];
  $('#cn').textContent = n.name || ((i ? 'Sensor ' : '') + n.id + (i ? '' : ' · Supply Reservoir'));
  updCard();
  if (selMesh && N[i]) {
    selMesh.visible = true;
    selMesh.position.copy(N[i].p);
    selMesh.position.y += 0.04;
  }
  if (typeof toast === 'function') {
    toast(`Selected <b>${n.id}</b>: ${n.name || 'Sensor'} · Telemetry synced`, 'ok', 3000);
  }
}

$('#cx').onclick = () => {
  sel = -1;
  $('#card').classList.remove('show');
  if (selMesh) selMesh.visible = false;
};

function verdict(n) {
  return n.st === 'leak'
    ? ['Real leak nearby', 'Neighbours agree: pressure falling, flow rising.']
    : n.st === 'contam'
    ? ['Contamination', 'Chlorine dropping; zone flagged.']
    : n.st === 'spoof'
    ? ['Spoofed / faulty', 'Neighbours disagree. Physics fails. Isolated.']
    : ['Healthy', n.isQuality ? 'Physical Water Quality sensor station: baseline chlorine & turbidity normal.' : 'Readings match neighbouring sensors.'];
}

function updCard() {
  if (sel < 0) return;
  const n = N[sel], v = verdict(n);
  $('#cs').textContent = 'Status: ' + v[0];
  $('#cb').style.width = n.trust + '%';
  $('#cd').innerHTML = `Trust <b>${Math.round(n.trust)}%</b><br>Reported pressure <b>${n.st === 'spoof' ? 0 : Math.round(n.pr)} psi</b><br><small>${v[1]}</small>`;
}

/* ---------- Render Loop ---------- */
function rs() {
  const w = stage.clientWidth, h = stage.clientHeight;
  R.setSize(w, h);
  cam.aspect = w / h;
  cam.updateProjectionMatrix();
}
new ResizeObserver(rs).observe(stage);

const pa = pg.attributes.position, ca = pg.attributes.color, tmp = new V();
let last = performance.now(), tick = 0;

function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  tick += dt;
  idle += dt;

  if (!drag && idle > 3) targetTh += dt * 0.08;

  // Damping for silky motion
  th += (targetTh - th) * 0.12;
  ph += (targetPh - ph) * 0.12;
  rad += (targetRad - rad) * 0.12;

  cam.position.set(
    Math.sin(th) * Math.sin(ph) * rad,
    Math.cos(ph) * rad,
    Math.cos(th) * Math.sin(ph) * rad
  );
  cam.lookAt(0, 0, 0);

  const fl = Math.sin(tick * 12) > 0;

  E.forEach((e, i) => {
    const c = C[e.m][0];
    pm[i].material.color.copy(c);
    gm[i].material.color.copy(c);
  });

  P.forEach((p, i) => {
    const e = E[p.e];
    p.t = (p.t + p.s * dt * SP[e.m]) % 1;
    tmp.lerpVectors(N[e.a].p, N[e.b].p, p.t);
    pa.setXYZ(i, tmp.x, tmp.y, tmp.z);
    const c = (e.m === 'spoof' && fl) ? C.spoof[1] : C[e.m][p.c];
    ca.setXYZ(i, c.r, c.g, c.b);
  });
  pa.needsUpdate = ca.needsUpdate = true;

  N.forEach((n, i) => {
    n.trust += (n.tt - n.trust) * 0.06;
    const isWQ = n.isQuality;
    const col = n.st === 'leak'
      ? 0xfb923c
      : n.st === 'contam'
      ? 0xa855f7
      : (n.st === 'spoof'
        ? (fl ? 0xff2d55 : 0xffb3c0)
        : (isWQ ? 0xff2d55 : 0x22d3ee));
    sm[i].material.color.setHex(col);
    if (n.halo) {
      n.halo.material.color.setHex(col);
      n.halo.lookAt(cam.position);
      n.halo.scale.setScalar(1 + (isWQ ? 0.22 : 0.15) * Math.sin(tick * 3 + i));
    }
    sm[i].scale.setScalar(sel === i ? 1.5 : 1);
  });

  if (selMesh && selMesh.visible) {
    const s = 1 + 0.16 * Math.sin(tick * 6);
    selRing1.scale.set(s, s, s);
    selRing2.scale.set(1 / s, 1 / s, 1 / s);
  }

  if (qr.visible) qr.rotation.z += dt * 2;
  sm[0].rotation.y += dt * 0.6;

  // Project 3D floating landmark pins to screen coordinates
  const stageW = stage.clientWidth, stageH = stage.clientHeight;
  const wp = new THREE.Vector3();
  N.forEach((n, i) => {
    if (n.pinEl) {
      wp.copy(n.p);
      wp.y += (n.isQuality ? 0.95 : 0.72);
      wp.project(cam);
      if (wp.z < 1) {
        const px = (wp.x * 0.5 + 0.5) * stageW;
        const py = (-(wp.y * 0.5) + 0.5) * stageH;
        n.pinEl.style.transform = `translate(-50%, -100%) translate(${px.toFixed(1)}px, ${py.toFixed(1)}px)`;
        n.pinEl.style.display = 'flex';
        n.pinEl.classList.toggle('selected', sel === i);
      } else {
        n.pinEl.style.display = 'none';
      }
    }
  });

  R.render(sc, cam);
}

rs();
requestAnimationFrame(frame);
