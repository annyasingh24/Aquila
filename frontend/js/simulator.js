/* ==========================================================================
   AQUILA - Attack Simulator & Edge Byzantine Swarm Consensus
   Simulates cyber spoofs, toxic plumes, bursts & edge voting
   ========================================================================== */

const nm = i => (N[i].name ? `${N[i].id} (${N[i].name.split('(')[0].trim()})` : N[i].id);
const rnd = () => Math.floor(1 + Math.random() * (N.length - 1));

function setAlert(k) {
  $$('.chip').forEach(c => c.classList.toggle('on', c.dataset.k === k));
}

$$('.chip').forEach(c => {
  c.onclick = () => {
    const k = c.dataset.k;
    if (k === 'ok') reset();
    else if (k === 'leak') leak();
    else if (k === 'contam') contam();
    else if (k === 'spoof') attack();
  };
});

function reset(q) {
  N.forEach(n => {
    n.tt = 100;
    n.st = 'ok';
    n.pr = 58 + Math.random() * 8;
    n.cl = 0.85;
  });
  E.forEach(e => (e.m = 'ok'));
  qr.visible = false;
  setAlert('ok');
  if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
  if (typeof setPhoneStandby === 'function') setPhoneStandby();
  if (!q) toast('✅ Network restored. All sensors trusted.', 'ok');
}

function leak() {
  reset(1);
  const c = rnd();
  N[c].st = 'leak';
  N[c].pr = 18;
  N[c].adj.forEach(a => {
    N[a].pr = 38;
    N[a].adj.forEach(b => {
      if (b !== c) N[b].pr = Math.min(N[b].pr, 50);
    });
  });
  E.forEach(e => {
    if (e.a === c || e.b === c) e.m = 'leak';
  });
  setAlert('leak');
  showCard(c);
  if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
  toast(`💧 <b>${nm(c)}</b> pressure falling`, 'warn');
  setTimeout(
    () =>
      toast(
        `${N[c].adj.length} neighbours also feel the drop. <b>Physics agrees: REAL LEAK.</b> Crew dispatched.`,
        'warn'
      ),
    1400
  );
  if (typeof triggerPhoneAlert === 'function') {
    triggerPhoneAlert({
      kind: 'REAL_LEAK',
      title: '💧 CRITICAL: PHYSICAL PIPE BURST',
      body: `Sensor ${nm(c)} dropped to 18 psi. Inflow meter spiked +25 L/s. All ${N[c].adj.length} neighbours agree. Orifice law verified.`,
      targetNode: nm(c),
      priority: 5,
      valves: 'Smart Valve Doctor Isolating'
    });
  }
}

function contam() {
  reset(1);
  const c = rnd();
  [c, ...N[c].adj].forEach(i => {
    N[i].st = 'contam';
    N[i].pr = 55;
    N[i].cl = 0.08;
  });
  E.forEach(e => {
    if (N[e.a].st === 'contam' && N[e.b].st === 'contam') e.m = 'contam';
  });
  setAlert('contam');
  showCard(c);
  if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
  toast(`☣ Chlorine dropped near <b>${nm(c)}</b>`, 'pu');
  setTimeout(() => toast('Downstream zone quarantined. Public alert drafted.', 'pu'), 1400);
  if (typeof triggerPhoneAlert === 'function') {
    triggerPhoneAlert({
      kind: 'CONTAMINATION',
      title: '☣️ CRITICAL: CHEMICAL CONTAMINATION',
      body: `Toxic plume detected near ${nm(c)}. Chlorine dropped to 0.08 mg/L. Patient Zero DAG backtracking activated.`,
      targetNode: nm(c),
      priority: 5,
      valves: 'Downstream Quarantine Valves Queued'
    });
  }
}

function attack() {
  reset(1);
  const c = rnd();
  N[c].st = 'spoof';
  N[c].pr = 0;
  E.forEach(e => {
    if (e.a === c || e.b === c) e.m = 'spoof';
  });
  setAlert('spoof');
  showCard(c);
  if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
  toast(`🚨 <b>${nm(c)}</b> screams: “Pressure 0 psi, pipe burst!”`, 'bad');
  setTimeout(() => {
    toast(`Checking ${N[c].adj.length} neighbours… all normal. Physics doesn’t add up.`, 'warn');
  }, 1500);
  setTimeout(() => {
    N[c].tt = 0;
    if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
    toast(`🐝 Swarm vote ${N[c].adj.length}–0: isolate <b>${nm(c)}</b>. Trust → 0%`, 'bad');
  }, 3000);
  setTimeout(() => {
    qr.position.copy(N[c].p);
    qr.visible = true;
    toast('🔒 Valves quarantined. <b>FAKE ALARM. $0 lost.</b>', 'ok', 6000);
  }, 4500);
  if (typeof triggerPhoneAlert === 'function') {
    triggerPhoneAlert({
      kind: 'CYBERATTACK',
      title: '🛑 CRITICAL: SENSOR PACKET SPOOF',
      body: `Sensor ${nm(c)} forged 0 psi packet. Swarm voted ${N[c].adj.length}-0 liar. IP firewalled & synthetic Ghost sensor engaged.`,
      targetNode: nm(c),
      priority: 4,
      valves: 'Sensor Quarantined'
    });
  }
}

$$('.ctl button[data-s]').forEach(b => (b.onclick = () => ({ leak, attack, contam, reset })[b.dataset.s]()));

/* ---------- Custom Attack Simulator Controls ---------- */
let currentSimMode = 'cyber';
/* ===== PRESSURE ZONES DEFINITION ===== */
const PRESSURE_ZONES = {
  'hospital': {
    name: 'Zone 1: City Hospital Life-Safety District',
    nodes: [13, 18, 19],
    desc: 'Critical medical facilities. Smart Valve Doctor enforces minimum 15m pressure floor (≥48 psi).',
    head: '52.4 psi',
    badge: '🏥 Hospital Priority 1'
  },
  'polytech': {
    name: 'Zone 2: Polytech & Sciences Research Quad',
    nodes: [6, 7, 11, 16],
    desc: 'Engineering labs & cleanrooms. Monitored by Water Quality Station S6 for chemical intrusion.',
    head: '58.6 psi',
    badge: '🔬 Research Quad'
  },
  'barrois': {
    name: 'Zone 3: Barrois Dining & Commercial District',
    nodes: [8, 9, 14],
    desc: 'Student restaurant & commercial plaza. Monitored by Water Quality Sensor Station S8 with high diurnal demand.',
    head: '57.8 psi',
    badge: '🍽️ Commercial Hub'
  },
  'lilliad': {
    name: 'Zone 4: LILLIAD Central Innovation Hub',
    nodes: [2, 3, 12],
    desc: 'Central campus library & SCADA Edge RTU relay station.',
    head: '60.2 psi',
    badge: '🏢 Central Hub'
  },
  'eastern': {
    name: 'Zone 5: Eastern Arterial & Nanotech Sector',
    nodes: [4, 5, 10, 15, 20],
    desc: 'IEMN Nanotechnology research wing and eastern distribution trunks.',
    head: '56.5 psi',
    badge: '⚡ High Pressure Arterial'
  },
  'reservoir': {
    name: 'Zone 6: Mountain Reservoir & Bulk Feeder',
    nodes: [1, 21, 22, 23],
    desc: 'Elevated storage tank (Z = 55m) and bulk mechanical inflow turbine meter (14.2 L/s).',
    head: '62.0 psi',
    badge: '🏔️ Elevated Gravity Source'
  },
  'blacksky': {
    name: 'Zone 7: Whole-Grid Multi-Sector Stress Test',
    nodes: Array.from({length: 24}, (_, i) => i + 1),
    desc: 'Simultaneous grid-wide cyber-physical stress test evaluating Byzantine swarm consensus under 100% adversary load.',
    head: 'Grid Wide',
    badge: '🌪️ Coordinated 24-Node'
  }
};

let currentZoneKey = 'hospital';
let targetMode = 'single';
let multiSelectedNodes = [6, 8];

function setTargetMode(mode) {
  targetMode = mode;
  const btnSingle = $('#btn-mode-single');
  const btnZone = $('#btn-mode-zone');
  const btnMulti = $('#btn-mode-multi');
  if (btnSingle) btnSingle.classList.toggle('active', mode === 'single');
  if (btnZone) btnZone.classList.toggle('active', mode === 'zone');
  if (btnMulti) btnMulti.classList.toggle('active', mode === 'multi');

  const sBox = $('#single-target-box');
  const zBox = $('#zone-target-box');
  const mBox = $('#multi-target-box');
  const presets = $('#multi-presets');

  if (sBox) sBox.style.display = (mode === 'single') ? 'block' : 'none';
  if (zBox) zBox.style.display = (mode === 'zone') ? 'block' : 'none';
  if (mBox) mBox.style.display = (mode === 'multi') ? 'block' : 'none';
  if (presets) presets.style.display = (mode === 'multi') ? 'flex' : 'none';

  if (mode === 'zone') {
    const sel = $('#sim-zone-select');
    const val = sel ? sel.value : 'hospital';
    onZoneSelectChange(val);
  } else if (mode === 'multi') {
    renderMultiChips();
  }
}

function onZoneSelectChange(zoneKey) {
  currentZoneKey = zoneKey;
  const z = PRESSURE_ZONES[zoneKey] || PRESSURE_ZONES['hospital'];
  multiSelectedNodes = [...z.nodes];

  const titleEl = $('#zone-info-title');
  const descEl = $('#zone-info-desc');
  const nodesEl = $('#zone-info-nodes');
  const headEl = $('#zone-info-head');
  const badgeEl = $('#zone-badge');

  if (titleEl) titleEl.textContent = z.name;
  if (descEl) descEl.textContent = z.desc;
  if (nodesEl) nodesEl.textContent = z.nodes.map(i => (N[i] ? N[i].id : `S${i}`)).join(', ');
  if (headEl) headEl.textContent = z.head;
  if (badgeEl) badgeEl.textContent = z.badge;

  if (z.nodes.length > 0 && typeof N !== 'undefined') {
    const firstNode = N[z.nodes[0]];
    if (firstNode && firstNode.p) {
      targetTh = Math.atan2(firstNode.p.x, firstNode.p.z) + 0.3;
      targetPh = 0.95;
      targetRad = z.nodes.length > 5 ? 30 : 20;
      idle = 0;
    }
  }

  toast(`📍 Pressure Zone Selected: <b>${z.name}</b> (${z.nodes.length} Sensors)`, 'ok', 3500);
}

function renderMultiChips() {
  const grid = $('#multi-chip-grid');
  if (!grid) return;
  grid.innerHTML = '';
  for (let i = 1; i < N.length; i++) {
    const chip = document.createElement('div');
    const isSel = multiSelectedNodes.includes(i);
    chip.className = 'node-chip' + (isSel ? ' selected' : '');
    chip.textContent = `${isSel ? '✓ ' : ''}${N[i].id}`;
    chip.title = `${N[i].id}: ${N[i].name || 'Sensor'}`;
    chip.onclick = () => {
      if (multiSelectedNodes.includes(i)) {
        if (multiSelectedNodes.length > 1) {
          multiSelectedNodes = multiSelectedNodes.filter(x => x !== i);
        }
      } else {
        multiSelectedNodes.push(i);
      }
      renderMultiChips();
    };
    grid.appendChild(chip);
  }
  const countEl = $('#multi-count');
  if (countEl) countEl.textContent = multiSelectedNodes.length;
}

function loadMultiPreset(preset) {
  if (preset === 'quality') multiSelectedNodes = [6, 8];
  else if (preset === 'quad') multiSelectedNodes = [4, 8, 12, 17];
  else if (preset === 'tri') multiSelectedNodes = [6, 15, 20];
  else if (preset === 'botnet') multiSelectedNodes = [2, 6, 8, 14, 19];
  renderMultiChips();
  if (typeof toast === 'function') toast(`⚡ Loaded multi-attack preset: <b>${multiSelectedNodes.map(i => N[i].id).join(', ')}</b>`, 'ok', 3000);
}

function toggleAllMulti(selectAll) {
  if (selectAll) {
    multiSelectedNodes = [];
    for (let i = 1; i < N.length; i++) multiSelectedNodes.push(i);
  } else {
    multiSelectedNodes = [6];
  }
  renderMultiChips();
}

function randomMulti(count) {
  const all = [];
  for (let i = 1; i < N.length; i++) all.push(i);
  all.sort(() => Math.random() - 0.5);
  multiSelectedNodes = all.slice(0, count);
  renderMultiChips();
  if (typeof toast === 'function') toast(`Selected ${count} random targets: <b>${multiSelectedNodes.map(i => N[i].id).join(', ')}</b>`, 'ok', 3000);
}

function setSimMode(m, btn) {
  $$('.sim-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentSimMode = m;
  const pBox = $('#sim-param-box');
  if (m === 'cyber') {
    pBox.innerHTML =
      '<label>Spoofed Pressure Value (Reported)</label><select id="sim-spoof-val"><option value="0">0.0 psi (Fake Catastrophic Burst)</option><option value="12">12.0 psi (Low Pressure Alarm)</option><option value="95">95.0 psi (Fake Surge)</option></select>';
  } else if (m === 'contam') {
    pBox.innerHTML =
      '<label>Contaminant Strength (Toxin)</label><select id="sim-spoof-val"><option value="0.05">0.05 mg/L (High Toxicity / Cyanide)</option><option value="0.02">0.02 mg/L (Turbidity Spike)</option></select>';
  } else if (m === 'stealth') {
    pBox.innerHTML =
      '<label>Replay Attack Strategy</label><select id="sim-spoof-val"><option value="replay">Hide 30 L/s Leak with Yesterday Data</option></select>';
  } else if (m === 'leak') {
    pBox.innerHTML =
      '<label>Physical Rupture Flow Rate</label><select id="sim-spoof-val"><option value="25">25.0 L/s (Medium Rupture)</option><option value="50">50.0 L/s (Main Trunk Burst)</option></select>';
  } else if (m === 'multi') {
    setTargetMode('multi');
    pBox.innerHTML =
      '<label>Multi-Attack Threat Vector</label><select id="sim-spoof-val"><option value="botnet">Distributed Botnet Spoof (0 psi fake leaks)</option><option value="multileak">Simultaneous Multi-Pipe Physical Ruptures</option><option value="contam">Multi-Sector Toxic Contamination</option><option value="hybrid">Hybrid Warzone (Cyber Spoof + Real Leak)</option></select>';
  }
}

function runCustomSimulation() {
  const isMulti = (targetMode === 'multi' || targetMode === 'zone' || currentSimMode === 'multi');
  const targetIds = isMulti ? [...multiSelectedNodes] : [parseInt($('#sim-target').value) || 8];
  if (targetIds.length === 0) targetIds.push(8);

  reset(1);
  showCard(targetIds[0]);

  if (targetIds.length === 1) {
    const targetNode = N[targetIds[0]];
    const targetPos = targetNode.p;
    targetTh = Math.atan2(targetPos.x, targetPos.z) + 0.35;
    targetPh = 0.95;
    targetRad = 19;
  } else {
    targetTh = 0.8;
    targetPh = 1.05;
    targetRad = 29;
  }
  idle = 0;

  const nodeLabels = targetIds.map(i => N[i].id).join(', ');
  if (targetMode === 'zone' && PRESSURE_ZONES[currentZoneKey]) {
    $('#hud-node').textContent = `${PRESSURE_ZONES[currentZoneKey].name} (${targetIds.length} Nodes)`;
  } else {
    $('#hud-node').textContent = isMulti ? `${nodeLabels} (${targetIds.length} Nodes)` : N[targetIds[0]].id;
  }

  const spoofValEl = $('#sim-spoof-val');
  const paramVal = spoofValEl ? spoofValEl.value : '0';

  if (isMulti || currentSimMode === 'multi') {
    const isLeakVector = (paramVal === 'multileak' || currentSimMode === 'leak');
    const isContamVector = (paramVal === 'contam' || currentSimMode === 'contam');
    const isHybridVector = (paramVal === 'hybrid');

    if (isContamVector) {
      const allPlume = new Set(targetIds);
      targetIds.forEach(tId => N[tId].adj.forEach(a => allPlume.add(a)));
      allPlume.forEach(i => { N[i].st = 'contam'; N[i].pr = 55; N[i].cl = 0.05; });
      E.forEach(e => { if (allPlume.has(e.a) && allPlume.has(e.b)) e.m = 'contam'; });
      setAlert('contam');

      $('#hud-reported').className = 'pill-tag pu';
      $('#hud-reported').textContent = `Toxic Contamination across ${allPlume.size} nodes (0.05 mg/L)`;
      $('#hud-packet').textContent = `Injection Vectors: ${nodeLabels}`;
      $('#hud-hmac').className = 'pill-tag ok';
      $('#hud-hmac').textContent = 'AUTHENTIC SENSORS';
      $('#hud-ghost').className = 'pill-tag pu';
      $('#hud-ghost').textContent = 'Chlorine Depletion Confirmed';
      $('#hud-action').className = 'pill-tag pu';
      $('#hud-action').textContent = `${targetIds.length} SECTOR QUARANTINE VALVES CLOSING`;

      $('#patient-zero-box').style.display = 'block';
      $('#pz-path').textContent = `Multi-Point Outbreak: ${nodeLabels} confirmed via DAG backtracker.`;

      const tbody = $('#sim-votes-body');
      tbody.innerHTML = '';
      targetIds.forEach(tId => {
        N[tId].adj.forEach(nbrId => {
          if (!targetIds.includes(nbrId)) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${N[nbrId].id} ➔ ${N[tId].id}</td><td>Depleted Cl</td><td><span class="pill-tag pu">AGREES: TOXIN PLUME</span></td><td>100%</td>`;
            tbody.appendChild(tr);
          }
        });
      });

      toast(`☣️ <b>Coordinated Contamination:</b> Poison detected at ${targetIds.length} nodes simultaneously (${nodeLabels})!`, 'pu');
      setTimeout(() => {
        toast(`🛡️ Backtracker confirmed ${targetIds.length} injection origins. Emergency quarantine engaged!`, 'pu', 6000);
        if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
      }, 1800);
      if (typeof triggerPhoneAlert === 'function') {
        triggerPhoneAlert({
          kind: 'CONTAMINATION',
          title: `☣️ CRITICAL: MULTI-POINT CONTAMINATION (${targetIds.length} NODES)`,
          body: `Chemical contamination verified across ${nodeLabels}. Patient Zero backtracker mapped injection DAG.`,
          targetNode: nodeLabels,
          priority: 5,
          valves: 'Sector Quarantine Actuated'
        });
      }

    } else if (isLeakVector) {
      targetIds.forEach(i => {
        N[i].st = 'leak';
        N[i].pr = 20;
        N[i].adj.forEach(a => { if (!targetIds.includes(a)) N[a].pr = 38; });
      });
      E.forEach(e => { if (targetIds.includes(e.a) || targetIds.includes(e.b)) e.m = 'leak'; });
      setAlert('leak');

      $('#hud-reported').className = 'pill-tag warn';
      $('#hud-reported').textContent = `Simultaneous Pipe Bursts across ${targetIds.length} sectors`;
      $('#hud-packet').textContent = `Total Inflow Surge: +${(targetIds.length * 25).toFixed(1)} L/s`;
      $('#hud-hmac').className = 'pill-tag ok';
      $('#hud-hmac').textContent = 'GENUINE SENSORS';
      $('#hud-ghost').className = 'pill-tag warn';
      $('#hud-ghost').textContent = 'Physics Agrees: Mass Conservation Deficit';
      $('#hud-action').className = 'pill-tag ok';
      $('#hud-action').textContent = `PARALLEL VALVE ISOLATION (${targetIds.length} CREWS QUEUED)`;
      $('#patient-zero-box').style.display = 'none';

      const tbody = $('#sim-votes-body');
      tbody.innerHTML = '';
      targetIds.forEach(tId => {
        N[tId].adj.forEach(nbrId => {
          if (!targetIds.includes(nbrId)) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${N[nbrId].id} ➔ ${N[tId].id}</td><td>38.0 psi</td><td><span class="pill-tag warn">VOTE: REAL DRAWDOWN</span></td><td>100%</td>`;
            tbody.appendChild(tr);
          }
        });
      });

      toast(`💧 <b>Multiple Pipe Bursts Confirmed:</b> Ruptures at ${nodeLabels}. Total loss: ${(targetIds.length * 25).toFixed(0)} L/s!`, 'warn');
      setTimeout(() => {
        toast(`🔧 Smart Valve Doctor isolates all ${targetIds.length} bursts in parallel. Hospital pressure protected ≥15m!`, 'ok', 6000);
        if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
      }, 1800);
      if (typeof triggerPhoneAlert === 'function') {
        triggerPhoneAlert({
          kind: 'REAL_LEAK',
          title: `💧 CRITICAL: MULTI-BURST EVENT (${targetIds.length} NODES)`,
          body: `Physical ruptures confirmed at ${nodeLabels}. Inflow surged by +${(targetIds.length * 25).toFixed(0)} L/s. Repair crews dispatched.`,
          targetNode: nodeLabels,
          priority: 5,
          valves: 'Hospital Floor Protected ≥15m'
        });
      }

    } else if (isHybridVector) {
      const cyberNodes = targetIds.slice(0, Math.ceil(targetIds.length / 2));
      const leakNodes = targetIds.slice(Math.ceil(targetIds.length / 2));

      cyberNodes.forEach(i => { N[i].st = 'spoof'; N[i].pr = 0; });
      leakNodes.forEach(i => { N[i].st = 'leak'; N[i].pr = 20; N[i].adj.forEach(a => { if (!targetIds.includes(a)) N[a].pr = 38; }); });
      E.forEach(e => {
        if (cyberNodes.includes(e.a) || cyberNodes.includes(e.b)) e.m = 'spoof';
        else if (leakNodes.includes(e.a) || leakNodes.includes(e.b)) e.m = 'leak';
      });
      setAlert('spoof');

      $('#hud-reported').className = 'pill-tag bad';
      $('#hud-reported').textContent = `Hybrid Warzone: ${cyberNodes.length} Spoofed + ${leakNodes.length} Real Leaks`;
      $('#hud-packet').textContent = `Cyber: S${cyberNodes.join(', S')} | Leaks: S${leakNodes.join(', S')}`;
      $('#hud-hmac').className = 'pill-tag bad';
      $('#hud-hmac').textContent = 'MIXED (CYBER HMAC FORGED)';
      $('#hud-ghost').className = 'pill-tag ok';
      $('#hud-ghost').textContent = 'AQUILA SEPARATES LIARS FROM REAL BURSTS';
      $('#hud-action').className = 'pill-tag ok';
      $('#hud-action').textContent = 'ISOLATE ONLY REAL BURSTS · $0 ON SPOOFS';
      $('#patient-zero-box').style.display = 'none';

      const tbody = $('#sim-votes-body');
      tbody.innerHTML = '';
      cyberNodes.forEach(cId => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>Swarm ➔ ${N[cId].id}</td><td>0 psi</td><td><span class="pill-tag bad">EVICT (FORGED / NO FLOW)</span></td><td>100%</td>`;
        tbody.appendChild(tr);
      });
      leakNodes.forEach(lId => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>Swarm ➔ ${N[lId].id}</td><td>20 psi</td><td><span class="pill-tag warn">CONFIRMED REAL LEAK</span></td><td>100%</td>`;
        tbody.appendChild(tr);
      });

      toast(`⚔️ <b>Hybrid Attack Launched:</b> Adversary launches fake alarms (${cyberNodes.map(i=>N[i].id).join(',')}) while masking real leaks (${leakNodes.map(i=>N[i].id).join(',')})!`, 'bad');
      setTimeout(() => {
        toast(`⚖️ <b>Aquila Lie Detector:</b> Physics exposes the ${cyberNodes.length} liars while dispatching crews only to the ${leakNodes.length} real leaks!`, 'ok', 6000);
        cyberNodes.forEach(i => { N[i].tt = 0; });
        if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
      }, 1800);
      if (typeof triggerPhoneAlert === 'function') {
        triggerPhoneAlert({
          kind: 'CYBERATTACK',
          title: `⚔️ HYBRID WARZONE: CYBER SPOOF + REAL LEAK`,
          body: `Adversary spoofed ${cyberNodes.length} nodes to distract from real ruptures. Aquila isolated liars and routed crews only to true leaks.`,
          targetNode: nodeLabels,
          priority: 5,
          valves: 'Surgical Isolation Active'
        });
      }

    } else {
      // Default: Distributed Botnet Cyber Spoof on all targets
      targetIds.forEach(i => { N[i].st = 'spoof'; N[i].pr = 0; });
      E.forEach(e => { if (targetIds.includes(e.a) || targetIds.includes(e.b)) e.m = 'spoof'; });
      setAlert('spoof');

      $('#hud-reported').className = 'pill-tag bad';
      $('#hud-reported').textContent = `Multiple 0.0 psi Alarms across ${targetIds.length} nodes`;
      $('#hud-packet').textContent = `Botnet IPs: 185.220.101.40-${40 + targetIds.length} (ALL FORGED)`;
      $('#hud-hmac').className = 'pill-tag bad';
      $('#hud-hmac').textContent = 'ALL HMAC SIGNATURES INVALID';
      $('#hud-ghost').className = 'pill-tag ok';
      $('#hud-ghost').textContent = `${targetIds.length} Ghost Sensors Active (58.6 psi)`;
      $('#hud-action').className = 'pill-tag ok';
      $('#hud-action').textContent = `ALL ${targetIds.length} ROGUE IPs BLOCKED · ZERO FALSE CREWS`;
      $('#patient-zero-box').style.display = 'none';

      const tbody = $('#sim-votes-body');
      tbody.innerHTML = '';
      targetIds.forEach(tId => {
        const tNode = N[tId];
        tNode.adj.forEach(nbrId => {
          if (!targetIds.includes(nbrId)) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${N[nbrId].id} ➔ ${tNode.id}</td><td>${(57 + Math.random() * 3).toFixed(1)} psi</td><td><span class="pill-tag bad">VOTE: OUTLIER / LIAR</span></td><td>100%</td>`;
            tbody.appendChild(tr);
          }
        });
      });

      toast(`🚨 <b>Distributed Botnet Attack:</b> Adversary forges 0 psi packets across ${targetIds.length} nodes (${nodeLabels})!`, 'bad');
      setTimeout(() => {
        toast(`🐝 <b>Byzantine Edge Swarm:</b> Fluid dynamics proves zero drop across unaffected neighbours. Voting 100% to evict all ${targetIds.length} compromised sensors!`, 'warn');
        targetIds.forEach(i => { N[i].tt = 0; });
        qr.position.copy(N[targetIds[0]].p);
        qr.visible = true;
        if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
      }, 1600);
      setTimeout(() => {
        toast(`🛡️ <b>Aquila Guardian:</b> All ${targetIds.length} nodes quarantined. <b>$${(targetIds.length * 48000).toLocaleString()} saved in ghost dispatches!</b>`, 'ok', 6000);
      }, 3400);
      if (typeof triggerPhoneAlert === 'function') {
        triggerPhoneAlert({
          kind: 'CYBERATTACK',
          title: `🚨 CRITICAL: BOTNET ATTACK (${targetIds.length} NODES)`,
          body: `Synchronized 0 psi packets forged across ${nodeLabels}. Swarm voted 100% liar. ${targetIds.length} Ghost Sensors engaged.`,
          targetNode: nodeLabels,
          priority: 4,
          valves: 'IPs Firewalled · $0 Lost'
        });
      }
    }

  } else {
    // Single Target modes
    const targetId = targetIds[0];
    const targetNode = N[targetId];
    const nodeLabel = targetNode.id;

    if (currentSimMode === 'cyber') {
      targetNode.st = 'spoof';
      targetNode.pr = 0;
      E.forEach(e => {
        if (e.a === targetId || e.b === targetId) e.m = 'spoof';
      });
      setAlert('spoof');

      $('#hud-reported').className = 'pill-tag bad';
      $('#hud-reported').textContent = '0.0 psi (CRITICAL ALARM)';
      $('#hud-packet').textContent = 'IP: 185.220.101.47 | TTL: 52 (FORGED)';
      $('#hud-hmac').className = 'pill-tag bad';
      $('#hud-hmac').textContent = 'INVALID (HMAC FAILED)';
      $('#hud-ghost').className = 'pill-tag ok';
      $('#hud-ghost').textContent = '58.6 psi (DERIVED BY SWARM)';
      $('#hud-action').className = 'pill-tag ok';
      $('#hud-action').textContent = 'ROGUE IP BLOCKED · GHOST ENGAGED';
      $('#patient-zero-box').style.display = 'none';

      const tbody = $('#sim-votes-body');
      tbody.innerHTML = '';
      targetNode.adj.forEach(nbrId => {
        const nbr = N[nbrId];
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${nbr.id}</td><td>${(57 + Math.random() * 3).toFixed(1)} psi</td><td><span class="pill-tag bad">VOTE: OUTLIER / LIAR</span></td><td>100%</td>`;
        tbody.appendChild(tr);
      });

      toast(`🚨 <b>${nodeLabel}</b> sends forged 0 psi packet from rogue IP 185.220.101.47!`, 'bad');
      setTimeout(() => {
        toast(
          `🐝 ${targetNode.adj.length} neighbours test physics: residual broken at liar ONLY. Swarm votes 100% to evict.`,
          'warn'
        );
        targetNode.tt = 0;
        qr.position.copy(targetNode.p);
        qr.visible = true;
        if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
      }, 1600);
      setTimeout(() => {
        toast(`👻 Ghost sensor spawned (${nodeLabel} = 58.6 psi). <b>Zero false alarms. $0 wasted.</b>`, 'ok', 6000);
      }, 3200);
      if (typeof triggerPhoneAlert === 'function') {
        triggerPhoneAlert({
          kind: 'CYBERATTACK',
          title: '🚨 CRITICAL: SENSOR PACKET FORGERY',
          body: `Sensor ${nodeLabel} forged 0.0 psi alarm from rogue IP 185.220.101.47. Byzantine swarm voted 4-0 outlier. Ghost sensor active.`,
          targetNode: nodeLabel,
          priority: 4,
          valves: 'IP Blocked · Grid Protected'
        });
      }

    } else if (currentSimMode === 'contam') {
      const plumeNodes = [targetId, ...targetNode.adj];
      plumeNodes.forEach(i => {
        N[i].st = 'contam';
        N[i].pr = 55;
        N[i].cl = 0.05;
      });
      E.forEach(e => {
        if (plumeNodes.includes(e.a) && plumeNodes.includes(e.b)) e.m = 'contam';
      });
      setAlert('contam');

      $('#hud-reported').className = 'pill-tag pu';
      $('#hud-reported').textContent = 'Chlorine: 0.05 mg/L (TOXIN)';
      $('#hud-packet').textContent = `Sensors S${targetId}, S${targetNode.adj.join(', S')}`;
      $('#hud-hmac').className = 'pill-tag ok';
      $('#hud-hmac').textContent = 'AUTHENTIC SENSORS';
      $('#hud-ghost').className = 'pill-tag pu';
      $('#hud-ghost').textContent = 'Chlorine Depletion Confirmed';
      $('#hud-action').className = 'pill-tag pu';
      $('#hud-action').textContent = 'QUARANTINE VALVES CLOSING';

      $('#patient-zero-box').style.display = 'block';
      $('#pz-path').textContent = `${nodeLabel} (~140 min ago, 99.9% fit). Upstream DAG confirmed.`;

      const tbody = $('#sim-votes-body');
      tbody.innerHTML = '';
      targetNode.adj.forEach(nbrId => {
        const nbr = N[nbrId];
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${nbr.id}</td><td>Depleted Cl</td><td><span class="pill-tag pu">AGREES: TOXIN PLUME</span></td><td>100%</td>`;
        tbody.appendChild(tr);
      });

      toast(`☣️ Chemical contamination detected across ${plumeNodes.length} nodes!`, 'pu');
      setTimeout(() => {
        toast(
          `🕵️ <b>Patient Zero Backtracker:</b> Poison entered at <b>${nodeLabel}</b>. Quarantine valves queued!`,
          'pu',
          6000
        );
        if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
      }, 1800);
      if (typeof triggerPhoneAlert === 'function') {
        triggerPhoneAlert({
          kind: 'CONTAMINATION',
          title: '☣️ CRITICAL: CHEMICAL CONTAMINATION',
          body: `Chemical contamination detected at ${nodeLabel}. Upstream DAG identified Patient Zero. Quarantine valves queued.`,
          targetNode: nodeLabel,
          priority: 5,
          valves: 'Quarantine Valves Closing'
        });
      }

    } else if (currentSimMode === 'stealth') {
      targetNode.st = 'spoof';
      targetNode.pr = 59;
      setAlert('spoof');

      $('#hud-reported').className = 'pill-tag ok';
      $('#hud-reported').textContent = '59.0 psi (SPOOFED NORMAL REPLAY)';
      $('#hud-packet').textContent = 'IP: 185.220.101.47 | Replay Attack';
      $('#hud-hmac').className = 'pill-tag bad';
      $('#hud-hmac').textContent = 'TIMESTAMP STALE';
      $('#hud-ghost').className = 'pill-tag bad';
      $('#hud-ghost').textContent = 'PHYSICS SEES 30 L/s REAL LEAK';
      $('#hud-action').className = 'pill-tag ok';
      $('#hud-action').textContent = 'STEALTH ATTACK UNMASKED';
      $('#patient-zero-box').style.display = 'none';

      toast(`🦹 Attacker hides a 30 L/s leak at <b>${nodeLabel}</b> by replaying yesterday's normal pressure!`, 'bad');
      setTimeout(() => {
        toast(`⚖️ Reservoir meter spiked + neighbours feel suction. Mass conservation exposes the liar!`, 'warn');
        targetNode.tt = 20;
        if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
      }, 1600);
      if (typeof triggerPhoneAlert === 'function') {
        triggerPhoneAlert({
          kind: 'CYBERATTACK',
          title: '🦹 HIGH: STEALTH REPLAY ATTACK UNMASKED',
          body: `Adversary replayed stale telemetry at ${nodeLabel} to mask 30 L/s leak. Reservoir mass conservation unmasked fraud.`,
          targetNode: nodeLabel,
          priority: 4,
          valves: 'Isolating Leaking Branch'
        });
      }

    } else if (currentSimMode === 'leak') {
      targetNode.st = 'leak';
      targetNode.pr = 20;
      targetNode.adj.forEach(a => {
        N[a].pr = 38;
      });
      E.forEach(e => {
        if (e.a === targetId || e.b === targetId) e.m = 'leak';
      });
      setAlert('leak');

      $('#hud-reported').className = 'pill-tag warn';
      $('#hud-reported').textContent = '20.0 psi (GENUINE LEAK)';
      $('#hud-packet').textContent = 'Inflow Spike: +25.0 L/s Verified';
      $('#hud-hmac').className = 'pill-tag ok';
      $('#hud-hmac').textContent = 'GENUINE SENSOR';
      $('#hud-ghost').className = 'pill-tag warn';
      $('#hud-ghost').textContent = 'Inflow & Neighbor Drop Matches Orifice Law';
      $('#hud-action').className = 'pill-tag ok';
      $('#hud-action').textContent = 'SMART VALVE DOCTOR ISOLATING';
      $('#patient-zero-box').style.display = 'none';

      toast(`💧 Genuine pipe rupture at <b>${nodeLabel}</b>. Inflow meter spiked!`, 'warn');
      setTimeout(() => {
        toast(
          `🏥 Smart Valve Doctor verifies hospital pressure remains ≥15m before turning valves. Crew dispatched!`,
          'ok',
          6000
        );
        if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
      }, 1800);
      if (typeof triggerPhoneAlert === 'function') {
        triggerPhoneAlert({
          kind: 'REAL_LEAK',
          title: '💧 CRITICAL: HIGH-PRESSURE PIPE RUPTURE',
          body: `Genuine 25 L/s rupture at ${nodeLabel}. Inflow spike confirmed. Smart Valve Doctor isolating while protecting hospital ≥15m.`,
          targetNode: nodeLabel,
          priority: 5,
          valves: 'Hospital Head Safe Floor Verified'
        });
      }
    }
  }

  if (typeof updateAnalyticsChart === 'function') updateAnalyticsChart();
}

// Populate simulator target dropdown
const simTarget = $('#sim-target');
if (simTarget) {
  simTarget.innerHTML = '';
  N.forEach((n, i) => {
    if (i > 0) {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = `${n.id}: ${n.name || 'Junction ' + i}`;
      simTarget.appendChild(opt);
    }
  });
  simTarget.value = 8;
}
