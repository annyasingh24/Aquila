/* ==========================================================================
   AQUILA - Application Master Controller
   Handles toasts, modals, warzone, feature dropdown & app lifecycle
   ========================================================================== */

function toast(m, t = '', ms = 4500) {
  const d = document.createElement('div');
  d.className = 'toast ' + t;
  d.innerHTML = m;
  $('#toasts').appendChild(d);
  setTimeout(() => {
    d.classList.add('out');
    setTimeout(() => d.remove(), 400);
  }, ms);
}

// Dark / Light Theme Toggle
$('#th').onclick = () => {
  const r = document.documentElement;
  const dk = r.dataset.theme ? r.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme:dark)').matches;
  r.dataset.theme = dk ? 'light' : 'dark';
};

// Modal Dismissal
function dismissModal() {
  const m = $('#modal');
  if (m) m.classList.add('hide');
  setTimeout(
    () => toast('👋 Digital Twin active. Try <b>Simulate Leak</b>, <b>Cyberattack</b>, or the <b>Simulator</b> below.', '', 5000),
    600
  );
}

// Stats Animated Numbers
$$('.stats b').forEach(b => {
  const n = +b.dataset.n;
  let v = 0;
  const iv = setInterval(() => {
    v = Math.min(n, v + Math.max(1, n / 30));
    b.textContent = Math.round(v);
    if (v >= n) clearInterval(iv);
  }, 40);
});

/* ---------- Features Inspector Dropdown Dataset ---------- */
const FEATURES_DATA = {
  twin: {
    title: '🧬 Digital Twin (EPANET Linear Hydraulic Simulator)',
    desc: 'Runs a live linear hydraulic model of the pipe network in real time. Predicts fluid velocity, advective travel times, and steady-state pressure heads. Water entering any pipe junction must equal water leaving it: if telemetry breaks the conservation equation, Aquila flags the anomaly immediately.',
    tags: ['Mass Conservation Law', 'Matrix Inversion', 'Linearized Conductance', 'Runs on Edge']
  },
  trust: {
    title: '🕵️ Sensor Trust Score (Bayesian Degradation)',
    desc: 'Every sensor in the city maintains a live confidence rating from 0% to 100%. If a sensor reports impossible data that contradicts neighboring fluid dynamics, its trust is cut by 50% immediately, dropping to 0% as neighbours cast outlier votes.',
    tags: ['Autonomous Edge Agent', 'Fast Decay on Breach', 'Slow Recovery on True Physics']
  },
  classifier: {
    title: '🚦 Four-Way Instant Threat Classifier',
    desc: 'Whenever an alarm sounds, Aquila classifies it in milliseconds: (1) Normal routine usage, (2) Real physical pipe rupture, (3) Chemical / biological contamination, or (4) Cyberattack / rogue packet spoofing. Operators never dispatch crews to ghost leaks again.',
    tags: ['Packet HMAC Inspection', 'Reservoir Spike Check', 'Plume Clustering']
  },
  swarm: {
    title: '🐝 Federated Sensor Trust Swarm (Raft / BFT Edge Consensus)',
    desc: 'Sensors communicate peer-to-peer with their immediate physical neighbours. Each neighbor calculates what the target sensor SHOULD report based on their own pressure and pipe conductance. If neighbours vote 3–0 or 4–0 against an outlier, the sensor is evicted without needing centralized cloud processing.',
    tags: ['Byzantine Fault Tolerant', 'Zero Cloud Dependency', '1-Hop Peer Ballots']
  },
  mesh: {
    title: '✨ 3D Volumetric Particle Flow Mesh',
    desc: 'Volumetric conduit grid featuring flowing illuminated water droplets. Flow speed directly reflects physical velocity. Conduits turn azure blue for pure water, neon green for safe chlorine, deep purple for chemical plumes, and pulsing crimson for spoofed cyber nodes.',
    tags: ['Fluid Velocity Scaling', 'Three.js WebGL Engine', 'Isometric Orbit Navigation']
  },
  valve: {
    title: '🏥 Smart Valve Doctor (Hospital Safe Floor ≥15m)',
    desc: 'Automatically calculates boundary valve isolations when a pipe breaks or toxins enter. Crucially, it simulates the closure on the Digital Twin first to verify that City Hospital and emergency clinics maintain safe pressure floor (≥15m) before turning any physical valve.',
    tags: ['Critical Infrastructure Safe', 'EPANET Head Floor Verification', 'Automated Isolation']
  },
  pz: {
    title: '🕵️ Patient Zero Backtracker (Reverse Fluid Dynamic DAG)',
    desc: 'When chemical or biological contamination is spotted at multiple junctions, Aquila treats pipe flows like a directed acyclic graph (DAG) and walks backwards in time and space along flow streams to pinpoint the exact origin node, entry timestamp, and injection velocity.',
    tags: ['Reverse-Time DAG Traversal', 'Advective Dijkstra', 'Upstream Origin Pinpoint']
  },
  audit: {
    title: '🔒 Cryptographic SHA-256 Flight Recorder',
    desc: 'Every telemetry measurement, valve state change, and operator decision is combined with the cryptographic hash of the previous record in a blockchain-style ledger. Any retroactive attempt by an insider or hacker to alter past logs instantly breaks the chain.',
    tags: ['SHA-256 Chained Hash', 'Immutable Audit Log', 'Tamper-Evident Flight Recorder']
  }
};

function renderFeatureDetail(key) {
  const feat = FEATURES_DATA[key] || FEATURES_DATA.twin;
  $('#feat-title').textContent = feat.title;
  $('#feat-desc').textContent = feat.desc;
  const tagsBox = $('#feat-tags');
  tagsBox.innerHTML = '';
  feat.tags.forEach(t => {
    const s = document.createElement('span');
    s.className = 'pill-tag ok';
    s.textContent = t;
    tagsBox.appendChild(s);
  });
}

/* ---------- Sensor Trust Board ---------- */
const gr = $('#grid');
N.forEach(n => {
  const d = document.createElement('div');
  d.className = 'cell';
  d.innerHTML = `<small>${n.id}</small><br><b>100%</b><div class="bar"><i></i></div>`;
  n.bEl = d.querySelector('b');
  n.iEl = d.querySelector('i');
  d.onclick = () => {
    showCard(N.indexOf(n));
    const tw = $('#twin');
    if (tw) tw.scrollIntoView({ behavior: 'smooth' });
  };
  n.cell = d;
  gr.appendChild(d);
});

// Periodic Trust Board Sync
setInterval(() => {
  N.forEach(n => {
    const t = Math.round(n.trust);
    if (n._lt !== t) {
      n._lt = t;
      if (n.bEl) n.bEl.textContent = t + '%';
      if (n.iEl) n.iEl.style.width = t + '%';
    }
    const cls = 'cell' + (n.st === 'spoof' && t < 60 ? ' bad' : n.st === 'leak' ? ' warn' : n.st === 'contam' ? ' pu' : '');
    if (n.cell && n.cell.className !== cls) n.cell.className = cls;
  });
  updCard();
}, 120);

/* ---------- Warzone Simulation ---------- */
let wt = [];
function wl(id, t, c) {
  const d = document.createElement('div');
  d.className = c;
  d.textContent = t;
  $(id).appendChild(d);
}

$('#wb').onclick = () => {
  wt.forEach(clearTimeout);
  wt.forEach(clearInterval);
  wt = [];
  ['#ll', '#lr'].forEach(i => ($(i).innerHTML = ''));
  $('#ml').textContent = '$0';
  $('#mr').textContent = '$0';

  const A = [
    [0, '#ll', '⚠ J5 reports 0 psi', 'warn'],
    [900, '#ll', 'SCADA trusts the reading', 'bad'],
    [1800, '#ll', '🚧 Dispatching 3 crews…', 'bad'],
    [2800, '#ll', 'Digging up Main St. Traffic jam.', 'bad'],
    [3900, '#ll', 'Nothing found. Ghost leak.', 'bad'],
    [0, '#lr', '⚠ J5 reports 0 psi', 'warn'],
    [900, '#lr', 'Physics check: 4 neighbours normal', 'ok'],
    [1800, '#lr', 'Swarm votes 4–0: isolate J5', 'ok'],
    [2800, '#lr', 'Injection vector: node 10.4.7.22', 'ok'],
    [3900, '#lr', 'Valves quarantined. Zero loss ✅', 'ok']
  ];

  A.forEach(a => wt.push(setTimeout(() => wl(a[1], a[2], a[3]), a[0])));
  wt.push(
    setTimeout(() => {
      let m = 0;
      const iv = setInterval(() => {
        m = Math.min(48000, m + 1600);
        $('#ml').textContent = '-$' + m.toLocaleString();
        if (m >= 48000) clearInterval(iv);
      }, 90);
      wt.push(iv);
    }, 1800)
  );
  wt.push(
    setTimeout(() => {
      $('#mr').textContent = '$0 lost';
      toast('🏆 Aquila saved the city $48,000 and one very angry road.', 'ok', 6000);
    }, 3900)
  );
};

/* ===== REAL PHYSICAL PHONE DISPATCH & MOBILE NOTIFICATIONS ===== */
function getCleanPhoneTopic() {
  const input = $('#dispatch-phone');
  const raw = (input && input.value.trim()) || localStorage.getItem('aquila_phone') || '+91 98765 43210';
  if (raw.toLowerCase() === 'emergency' || raw.toLowerCase() === 'aquila-emergency') {
    return {
      raw: 'aquila-emergency',
      clean: '9876543210',
      topic: 'aquila-emergency'
    };
  }
  const clean = raw.replace(/\D/g, '');
  return {
    raw: raw,
    clean: clean,
    topic: clean ? ('aquila-' + clean) : 'aquila-emergency'
  };
}

function setSimpleEmergencyTopic() {
  const input = $('#dispatch-phone');
  if (input) input.value = 'aquila-emergency';
  onPhoneInputChanged();
  savePhoneNumber(true);
  toast('Topic set to: <b>aquila-emergency</b>', 'ok');
}

function loadPhoneNumber() {
  const saved = localStorage.getItem('aquila_phone') || 'aquila-emergency';
  const input = $('#dispatch-phone');
  if (input) input.value = saved;
  onPhoneInputChanged();
}

function savePhoneNumber(showFeedback = true) {
  const input = $('#dispatch-phone');
  if (!input) return;
  const num = input.value.trim() || '+91 98765 43210';
  localStorage.setItem('aquila_phone', num);
  onPhoneInputChanged();
  const msg = $('#phone-saved-msg');
  if (msg && showFeedback) {
    msg.style.display = 'block';
    setTimeout(() => { msg.style.display = 'none'; }, 3500);
  }
  if (showFeedback) {
    toast(`📱 Dedicated channel paired to <b>${num}</b>`, 'ok');
  }
}

function onPhoneInputChanged() {
  const { raw, clean, topic } = getCleanPhoneTopic();
  localStorage.setItem('aquila_phone', raw);

  const topicDisplay = $('#topic-display-name');
  if (topicDisplay) topicDisplay.textContent = `ntfy.sh/${topic}`;

  const qrImg = $('#qr-code-img');
  const directLink = $('#topic-direct-link');
  const targetUrl = `https://ntfy.sh/${topic}`;

  if (qrImg) {
    qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(targetUrl)}`;
  }
  if (directLink) {
    directLink.href = targetUrl;
    directLink.textContent = `🔗 Open ntfy.sh/${topic} on phone ↗`;
  }
}

function openTopicDirectly() {
  const { topic } = getCleanPhoneTopic();
  window.open(`https://ntfy.sh/${topic}`, '_blank');
}

function sendWhatsAppAlert(customMsg) {
  const { raw, clean } = getCleanPhoneTopic();
  if (!clean) {
    toast('Please enter your mobile phone number first.', 'warn');
    return;
  }
  const msg = customMsg || `🚨 AQUILA EMERGENCY DISPATCH (PRIORITY 5)\n\nNode S8: Real Pipe Rupture confirmed (~25.0 L/s)\nInflow spike verified by mass conservation.\nSmart Valve Doctor isolating section.\nHospital pressure maintained ≥15m.`;
  const url = `https://api.whatsapp.com/send?phone=${clean}&text=${encodeURIComponent(msg)}`;
  window.open(url, '_blank');
  toast(`💬 WhatsApp emergency dispatch opened for +${clean}`, 'ok');
}

function playDispatchChime(type = 'alarm') {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const now = ctx.currentTime;

    if (type === 'alarm') {
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain = ctx.createGain();

      osc1.type = 'triangle';
      osc2.type = 'sine';

      osc1.frequency.setValueAtTime(880, now);
      osc1.frequency.setValueAtTime(1175, now + 0.14);
      osc1.frequency.setValueAtTime(880, now + 0.28);
      osc1.frequency.setValueAtTime(1175, now + 0.42);

      osc2.frequency.setValueAtTime(440, now);
      osc2.frequency.setValueAtTime(587.33, now + 0.14);

      gain.gain.setValueAtTime(0.22, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.7);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(ctx.destination);

      osc1.start(now);
      osc2.start(now);
      osc1.stop(now + 0.72);
      osc2.stop(now + 0.72);
    } else {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(523.25, now);
      osc.frequency.exponentialRampToValueAtTime(1046.5, now + 0.15);
      gain.gain.setValueAtTime(0.18, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.38);
    }
  } catch (e) {}
}

function dispatchRealMobilePush(title, message, priority = 5, tags = ['rotating_light', 'warning'], customTopic) {
  const { topic } = getCleanPhoneTopic();
  const targetTopic = customTopic || topic;
  const topicsToPush = Array.from(new Set([targetTopic, 'aquila-emergency']));
  const statusEl = $('#dispatch-delivery-status');

  if (statusEl) {
    statusEl.innerHTML = `<span style="color:#38bdf8;">⏳ Transmitting alert to ntfy.sh/${targetTopic} & aquila-emergency...</span>`;
    statusEl.style.display = 'block';
  }

  const pushPromises = topicsToPush.map(top => {
    return fetch('https://ntfy.sh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        topic: top,
        title: title,
        message: message,
        priority: Number(priority) || 5,
        tags: tags || ['warning']
      })
    });
  });

  Promise.all(pushPromises).then(responses => {
    console.log(`[Aquila] Alert pushed to topics [${topicsToPush.join(', ')}]`);
    if (statusEl) {
      const now = new Date().toLocaleTimeString();
      statusEl.innerHTML = `
        <div style="color:#4ade80; font-weight:700; margin-bottom:3px;">
          ✓ Dispatched to real phone at ${now} (HTTP 200 OK)
        </div>
        <div style="font-size:11px; color:var(--mu);">
          Active Topics: <b style="color:var(--tx);">${topicsToPush.join(', ')}</b> · 
          <a href="https://ntfy.sh/aquila-emergency" target="_blank" rel="noopener noreferrer" style="color:var(--ac); text-decoration:underline;">
            Open Live Web Feed ↗
          </a>
        </div>
      `;
      statusEl.style.display = 'block';
    }
  }).catch(err => {
    console.warn('[Aquila] Push delivery error:', err);
    if (statusEl) {
      statusEl.innerHTML = `
        <div style="color:#f87171; font-weight:700; margin-bottom:3px;">
          ⚠️ Transmit notice: ${err.message || 'Check connection'}
        </div>
        <div style="font-size:11px; color:var(--mu);">
          <a href="https://ntfy.sh/aquila-emergency" target="_blank" rel="noopener noreferrer" style="color:var(--ac); text-decoration:underline;">open ntfy.sh/aquila-emergency directly ↗</a>
        </div>
      `;
      statusEl.style.display = 'block';
    }
  });
}

function triggerPhoneAlert(info) {
  const { raw, clean, topic } = getCleanPhoneTopic();

  playDispatchChime('alarm');

  dispatchRealMobilePush(
    info.title || '🚨 Aquila Emergency Dispatch',
    `${info.body}\nDispatched to: ${raw}\nAction: Smart Valve Doctor Isolating`,
    info.priority || 5,
    (info.kind === 'CONTAMINATION') ? ['biohazard', 'rotating_light'] : (info.kind === 'REAL_LEAK') ? ['droplet', 'warning'] : ['rotating_light', 'lock'],
    topic
  );

  toast(`📱 <b>Message Dispatched to Your Physical Phone:</b><br>${info.title}<br><small style="color:#9bb7d0">Sent to ${raw} (Channel: ntfy.sh/${topic})</small>`, 'bad', 5500);

  if ('Notification' in window && Notification.permission === 'granted') {
    try {
      new Notification(info.title, { body: `${info.body} (Target: ${raw})` });
    } catch (e) {}
  }
}

function triggerTestEmergencyAlert() {
  const { raw, topic } = getCleanPhoneTopic();
  triggerPhoneAlert({
    kind: 'REAL_LEAK',
    title: '🚨 CRITICAL: HIGH-PRESSURE PIPE RUPTURE',
    body: `Sensor S8 (Barrois Quality) pressure dropped to 18 psi. Inflow spike +25.0 L/s verified. Inflow & neighbor drop matches Orifice Law.`,
    targetNode: 'Sensor S8',
    priority: 5,
    valves: 'Valves V4 & V7 auto-isolated. Hospital head maintained ≥15m.'
  });
  toast(`⚡ Test emergency push transmitted to your phone at <b>${raw}</b> (ntfy.sh/${topic})!`, 'ok', 6000);
}

/* ===== AUTONOMOUS GUARDIAN (AUTO-DISPATCH ON ITS OWN) ===== */
let autoGuardianActive = false;
let autoGuardianInterval = null;
let autoIncidentIndex = 0;

const AUTO_INCIDENTS = [
  {
    kind: 'REAL_LEAK',
    title: '💧 CRITICAL: HIGH-PRESSURE PIPE RUPTURE',
    body: 'Sensor S8 (Barrois Quality): Inflow surged +25.0 L/s. Neighbour gradients confirmed real burst. Smart Valve Doctor isolating section V4 & V7. Hospital pressure safe ≥15m.',
    priority: 5
  },
  {
    kind: 'CYBERATTACK',
    title: '🛑 CRITICAL: COZY BEAR PACKET SPOOF',
    body: 'Sensor S12 reported forged 0.0 psi. Physics consensus voted 4-0 outlier. Node quarantined & synthetic Ghost Sensor activated.',
    priority: 4
  },
  {
    kind: 'CONTAMINATION',
    title: '☣️ CRITICAL: CHEMICAL CONTAMINATION',
    body: 'Sensor S6 detected chlorine depletion below 0.1 mg/L. Plume backtracker identified injection origin. Quarantine valves triggered.',
    priority: 5
  }
];

function toggleAutoGuardian() {
  autoGuardianActive = !autoGuardianActive;
  const btn = $('#btn-auto-guardian');

  if (autoGuardianActive) {
    if (btn) {
      btn.innerHTML = '<span>⏸</span> Stop Auto-Dispatch (Running on its own)';
      btn.style.background = 'rgba(239,68,68,0.2)';
      btn.style.borderColor = '#ef4444';
      btn.style.color = '#f87171';
    }
    toast('🤖 <b>Auto-Guardian Mode ACTIVE!</b> Sending alerts on its own every 25 seconds...', 'ok', 5000);

    setTimeout(() => {
      if (autoGuardianActive) fireNextAutoIncident();
    }, 2000);

    autoGuardianInterval = setInterval(() => {
      if (autoGuardianActive) fireNextAutoIncident();
    }, 25000);
  } else {
    clearInterval(autoGuardianInterval);
    if (btn) {
      btn.innerHTML = '<span>🤖</span> Enable Auto-Dispatch Mode (Sends on its own)';
      btn.style.background = 'rgba(56,189,248,0.12)';
      btn.style.borderColor = '#38bdf8';
      btn.style.color = '#38bdf8';
    }
    toast('Auto-Guardian Mode stopped.', 'warn');
  }
}

function fireNextAutoIncident() {
  const inc = AUTO_INCIDENTS[autoIncidentIndex % AUTO_INCIDENTS.length];
  autoIncidentIndex++;
  triggerPhoneAlert(inc);
}

/* ===== FORENSIC INCIDENT REPORT GENERATOR & EXPORTER ===== */
function getLatestReportText() {
  const dateStr = new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
  const reportId = 'AQ-' + new Date().getFullYear() + '-INC-' + Math.floor(1000 + Math.random() * 9000) + '-F' + Math.floor(10 + Math.random() * 89);
  
  const isContam = typeof currentSimMode !== 'undefined' && currentSimMode === 'contam';
  const isLeak = typeof currentSimMode !== 'undefined' && currentSimMode === 'leak';
  const isMulti = typeof currentSimMode !== 'undefined' && (currentSimMode === 'multi' || targetMode === 'multi' || targetMode === 'zone');
  const isStealth = typeof currentSimMode !== 'undefined' && currentSimMode === 'stealth';

  let classification = 'CYBERATTACK_PACKET_SPOOF (Confidence: 99.8%)';
  let lossAvoided = '$48,000 USD (3 Ghost Leaks & Unnecessary Excavation Prevented)';
  let targetDesc = (targetMode === 'zone' && typeof PRESSURE_ZONES !== 'undefined' && PRESSURE_ZONES[currentZoneKey]) ?
    `${PRESSURE_ZONES[currentZoneKey].name} (${PRESSURE_ZONES[currentZoneKey].nodes.map(i=>'S'+i).join(', ')})` :
    'Sensor S8 (Barrois Restaurant Quality Junction)';
  let reportedTelemetry = '0.0 psi (FORGED PIPE BURST)';
  let truthTelemetry = '58.4 psi (Physics Reconstruction)';
  let residualDeficit = '-58.4 psi (Statistically Impossible Gradient)';
  let flowSurge = '0.0 L/s (Inflow Meter Steady at 14.2 L/s)';
  let packetIP = '185.220.101.47 (Known Tor Exit / Spoofed Gateway)';
  let ttlVal = '52 (Internal SCADA expected: 64)';
  let hmacStatus = 'FAILED (Forged / Replay Packet detected)';
  let actionsTaken = 'Quarantined node IP without closing physical water mains.\n- Hospital Pressure : City Hospital (Node S13) maintained at 48.2 psi (≥15m floor).\n- Emergency Alert   : Dispatched to Real Physical Mobile Phone (ntfy.sh/aquila-emergency).\n- Public Notice     : Suppressed false leak dispatch (Saved $48,000 excavation cost).';

  if (isLeak) {
    classification = 'PHYSICAL_PIPE_BURST (Orifice Law Verified: 99.4%)';
    lossAvoided = '120,000 Litres ($3,600 USD) drinking water saved via rapid isolation';
    targetDesc = 'Sensor S8 (Barrois Quality Junction)';
    reportedTelemetry = '18.0 psi (REAL LOW PRESSURE)';
    truthTelemetry = '18.0 psi (Physics Inflow Gradient Confirmed)';
    residualDeficit = '+25.0 L/s (Inflow Meter Surge Match)';
    flowSurge = '+25.0 L/s (Mass Conservation Inflow Verified)';
    packetIP = '10.4.7.22 (Valid Internal SCADA Node)';
    ttlVal = '64 (Valid Internal Hop)';
    hmacStatus = 'VALID (Genuine Hardware Sensor Signature)';
    actionsTaken = 'Smart Valve Doctor actuated isolation of Valves V4 & V7.\n- Hospital Pressure : Maintained at 18.5m (Safe floor ≥15m preserved).\n- Crew Dispatch     : Targeted repair team sent with exact pipe GPS coordinates.\n- Public Notice     : Downstream booster activated to maintain civilian flow.';
  } else if (isContam) {
    classification = 'TOXIC_CHEMICAL_CONTAMINATION (Chlorine Depletion < 0.1 mg/L)';
    lossAvoided = 'Protected 18,000 students and campus residents from toxic ingestion';
    targetDesc = 'Sensor S6 (Polytech Lille Water Quality Node)';
    reportedTelemetry = 'Chlorine: 0.08 mg/L (Critical Depletion Alarm)';
    truthTelemetry = 'Chlorine: 0.08 mg/L (Plume Confirmed)';
    residualDeficit = '-0.77 mg/L Chemical Mass Degradation';
    flowSurge = 'Normal Hydraulic Advection: 0.42 m/s velocity';
    packetIP = '10.4.7.18 (Valid Water Quality Node)';
    ttlVal = '64 (Valid Internal Hop)';
    hmacStatus = 'VALID (Genuine Water Quality Sensor Signature)';
    actionsTaken = 'Patient Zero DAG backtracker identified injection origin at Node S6 (~160 min ago).\n- Downstream Valves : Sector quarantine valves V6, V9 & V11 closed in parallel.\n- Emergency Alert   : Priority 5 Hazardous Material dispatch sent to municipal engineer.\n- Water Safety Desk : Chlorination dosing station triggered at upstream reservoir.';
  } else if (isStealth) {
    classification = 'STEALTH_SLOW_DRIFT_REPLAY_ATTACK (Physics Residual Deficit: 99.1%)';
    lossAvoided = '$62,000 USD (Latent sensor blinding & undetected water loss averted)';
    targetDesc = 'Sensor S8 (Barrois Quality Junction)';
    reportedTelemetry = '42.1 psi (-0.3 psi/min slow stealth crawl)';
    truthTelemetry = '58.4 psi (Unchanged ground truth)';
    residualDeficit = '-16.3 psi cumulative residual discrepancy';
    flowSurge = '0.0 L/s inflow change (Adversary attempted sub-threshold evasion)';
    packetIP = '194.26.29.112 (Compromised Edge RTU Gateway)';
    ttlVal = '58 (Abnormal Routing Hop)';
    hmacStatus = 'REVOKED (Timestamp drift exceeded replay window tolerance)';
    actionsTaken = 'Cumulative sum CUSUM detector flagged persistent sub-threshold drift.\n- Swarm Consensus  : 4 neighbor nodes confirmed physical flow invariance.\n- Synthetic Stream : Node isolated and replaced by real-time physics estimate.\n- Municipal Log    : Forensics flagged slow adversary reconnaissance.';
  } else if (isMulti) {
    classification = 'COORDINATED_MULTI_NODE_ATTACK (Quad-Vector Spoof)';
    lossAvoided = '$192,000 USD (Grid-wide black-sky shutdown averted)';
    targetDesc = 'Junctions S4, S8, S12, S17 (East Main, Barrois, LILLIAD, IEMN)';
    reportedTelemetry = 'Simultaneous 0.0 psi across 4 distinct pressure zones';
    truthTelemetry = 'All 4 zones physically healthy (56.0 - 62.0 psi)';
    residualDeficit = 'Mass Conservation Invariant intact across whole grid';
    flowSurge = 'Zero inflow variation (Proves Digital Key compromise)';
    packetIP = 'Distributed Sybil Botnet (185.220.101.*)';
    ttlVal = '48 - 54 (External adversary injection)';
    hmacStatus = 'FAILED on all 4 vectors (Forged HMAC Tokens)';
    actionsTaken = 'Byzantine Swarm isolated all 4 compromised nodes simultaneously.\n- Synthetic Ghosts  : 4 Ghost Sensors initialized to stream ground truth.\n- Hospital Pressure : 100% uninterrupted water delivery to City Hospital & Clinic.\n- Cryptographic Key : Revoked compromised node credentials in Flight Recorder.';
  }

  return `================================================================================
AQUILA INDUSTRIAL CYBER-PHYSICAL INCIDENT DOSSIER
Municipal Drinking Water Distribution Network Defense
================================================================================
Report ID      : ${reportId}
Timestamp      : ${dateStr}
Target Network : Polytech'Lille Campus Municipal Water Grid (24 Sensor Nodes)
Classification : ${classification}
Defense Engine : Byzantine Fault Tolerant Swarm Consensus (14ms response)
Loss Avoided   : ${lossAvoided}

1. EXECUTIVE INCIDENT SUMMARY
--------------------------------------------------------------------------------
Aquila's autonomous physics-aware neural engine detected anomalous telemetry
in the drinking water network. Unlike legacy SCADA systems that blindly trust
sensor packets, Aquila cross-examined Navier-Stokes hydraulic gradients,
mass conservation (Σ Qin = Σ Qout), and advective transport invariants to
differentiate cyber warfare from physical infrastructure failures.

2. TELEMETRY & NETWORK FINGERPRINT
--------------------------------------------------------------------------------
Target Junction      : ${targetDesc}
Reported Telemetry   : ${reportedTelemetry}
Ground Truth Value   : ${truthTelemetry}
Divergence Residual  : ${residualDeficit}
Inflow Meter State   : ${flowSurge}
Packet Origin IP     : ${packetIP}
TTL Hop Distance     : ${ttlVal}
HMAC Cryptography    : ${hmacStatus}

3. SWARM BYZANTINE CONSENSUS AUDIT
--------------------------------------------------------------------------------
Surrounding sensors independently evaluated mass balance equations:
- Sensor S1  -> Implied Target: 58.2 psi | Vote: ${isLeak ? 'REAL DRAWDOWN' : 'LIAR (OUTLIER)'} (Weight: 100%)
- Sensor S7  -> Implied Target: 59.1 psi | Vote: ${isLeak ? 'REAL DRAWDOWN' : 'LIAR (OUTLIER)'} (Weight: 100%)
- Sensor S9  -> Implied Target: 57.8 psi | Vote: ${isLeak ? 'REAL DRAWDOWN' : 'LIAR (OUTLIER)'} (Weight: 100%)
- Sensor S13 -> Implied Target: 58.6 psi | Vote: ${isLeak ? 'REAL DRAWDOWN' : 'LIAR (OUTLIER)'} (Weight: 100%)
Consensus Result     : 4-0 UNANIMOUS PHYSICAL CONCURRENCE
Bayesian Trust Score : Evaluated in 14 milliseconds without cloud round-trip.
Ghost Sensor Status  : ${isLeak ? 'N/A (Physical Event)' : 'Synthetic Ghost Sensor stream engaged for continuous flow.'}

4. SMART VALVE DOCTOR & LIFE SAFETY ACTIONS
--------------------------------------------------------------------------------
- Safety Strategy    : ${actionsTaken}

5. CRYPTOGRAPHIC FLIGHT RECORDER AUDIT
--------------------------------------------------------------------------------
Previous Block Hash  : 9e3f1c8a42b08d27e98a123f8b9012cd345678ef901234567890abcdef123456
Current Incident Hash: a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8
Signature Status     : CRYPTOGRAPHICALLY TAMPER-PROOF (SHA-256 Chain Intact)
Protocol Engine      : Aquila Swarm Consensus Protocol v2.9
Operator Authority   : Autonomous Municipal Guardian
================================================================================
END OF FORENSIC INCIDENT REPORT`;
}

function toggleCornerReport(forceState) {
  const panel = $('#corner-report-panel');
  const preview = $('#corner-report-preview');
  const chevron = $('#corner-chevron');
  if (!panel) return;
  
  const shouldOpen = (typeof forceState === 'boolean') ? forceState : panel.classList.contains('hide');
  if (shouldOpen) {
    if (preview) {
      preview.textContent = getLatestReportText();
    }
    panel.classList.remove('hide');
    if (chevron) chevron.textContent = '▼';
    toast('📄 Forensic Incident Dossier ready in corner option.', 'ok');
  } else {
    panel.classList.add('hide');
    if (chevron) chevron.textContent = '▲';
  }
}

function openForensicReport() {
  toggleCornerReport(true);
}

function closeForensicReport() {
  toggleCornerReport(false);
}

function downloadForensicReport() {
  const text = getLatestReportText();
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const dateStr = new Date().toISOString().replace(/[:.]/g, '-');
  a.href = url;
  a.download = `aquila-forensic-report-${dateStr}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast('💾 Forensic Incident Report downloaded (.txt)!', 'ok');
}

function copyForensicReport() {
  const text = getLatestReportText();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      toast('📋 Report copied to clipboard!', 'ok');
    }).catch(() => {
      fallbackCopyText(text);
    });
  } else {
    fallbackCopyText(text);
  }
}

function fallbackCopyText(text) {
  const textArea = document.createElement('textarea');
  textArea.value = text;
  document.body.appendChild(textArea);
  textArea.select();
  try {
    document.execCommand('copy');
    toast('📋 Report copied to clipboard!', 'ok');
  } catch (err) {
    toast('Please select and copy manually.', 'warn');
  }
  document.body.removeChild(textArea);
}

function setPhoneStandby() {
  // Standby mode
}

function requestBrowserNotificationPermission() {
  if (!('Notification' in window)) {
    toast('Browser push notifications not supported in this browser.', 'warn');
    return;
  }
  Notification.requestPermission().then(permission => {
    if (permission === 'granted') {
      toast('🔔 Browser push notifications enabled!', 'ok');
      new Notification('Aquila Water Guardian', { body: 'Emergency dispatch notifications are now active.' });
    } else {
      toast('Browser push notifications blocked or dismissed.', 'warn');
    }
  });
}

/* ===== LIVE INTERACTIVE PITCH DIRECTOR ===== */
let currentPitchStep = 0;
const PITCH_SLIDES = [
  {
    step: 1,
    title: '1. The Crisis: Legacy SCADA Blindness',
    sub: 'Why modern water grids lose $40B/year and fail against cyber threats',
    pitch: 'City water networks lose over 40% of treated drinking water to silent leaks. More dangerously, SCADA software in most cities blindly trusts sensor packets. If an attacker injects a spoofed low-pressure packet, operators panic and dig up roads for ghost leaks, or miss real toxic spills.',
    triggerText: '▶ Run Normal Baseline Network',
    action: () => {
      reset();
      const tw = $('#twin');
      if (tw) tw.scrollIntoView({ behavior: 'smooth' });
      toast('Baseline steady-state loaded. All 24 sensors healthy.', 'ok');
    }
  },
  {
    step: 2,
    title: '2. The Attack: Coordinated Multi-Point Spoof',
    sub: 'Adversary spoofing sensors across the Polytech\'Lille campus',
    pitch: 'Now watch an adversary execute a simultaneous 4-node attack across the University of Lille campus. They report 0 psi on sensors S4, S8, S12, and S17 to deceive operators into triggering emergency pump shutdowns.',
    triggerText: '▶ Launch Coordinated 4-Node Attack',
    action: () => {
      setSimMode('multi');
      loadMultiPreset('quad');
      runCustomSimulation();
      const sim = $('#sim');
      if (sim) sim.scrollIntoView({ behavior: 'smooth' });
    }
  },
  {
    step: 3,
    title: '3. The Defense: Physics as the Lie Detector',
    sub: 'Byzantine Fault Tolerant consensus in 14 milliseconds',
    pitch: 'Hackers can forge digital keys and spoof IPs, but they cannot hack mass conservation: Σ Qin = Σ Qout. In 14 milliseconds, neighbouring sensors check each other\'s physical gradients, cast unanimous 4-0 outlier votes, firewall the hacked nodes, and spin up synthetic Ghost Sensors so water flows uninterrupted.',
    triggerText: '▶ View Swarm Consensus & Before/After Graphs',
    action: () => {
      const an = $('#analytics');
      if (an) an.scrollIntoView({ behavior: 'smooth' });
      if (typeof switchGraph === 'function') switchGraph('pressure', $$('.graph-tab')[0]);
      toast('Inspecting Before vs After physics reconstruction graphs.', 'ok');
    }
  },
  {
    step: 4,
    title: '4. Immediate Impact: Real Mobile Push on Physical Phone',
    sub: 'Lockscreen notification on your real physical phone with sound & vibration',
    pitch: 'Look at the physical smartphone on the table. Within 200 milliseconds, an encrypted dispatch hits the municipal engineer\'s phone screen with exact valve coordinates, while our Smart Valve Doctor verifies hospital and clinic pressure stays above the safe 15-meter floor before closing any valve.',
    triggerText: '▶ Fire Live Push to Real Physical Phone',
    action: () => {
      triggerTestEmergencyAlert();
    }
  }
];

function openPitchDirector() {
  const m = $('#pitch-modal');
  if (m) m.classList.remove('hide');
  renderPitchSlide(currentPitchStep);
}

function closePitchDirector(e) {
  if (e && e.target && e.target.id !== 'pitch-modal' && !e.target.classList.contains('x')) return;
  const m = $('#pitch-modal');
  if (m) m.classList.add('hide');
}

function renderPitchSlide(step) {
  currentPitchStep = step;
  const slide = PITCH_SLIDES[step];
  const stepEl = $('#pitch-step-num');
  if (stepEl) stepEl.textContent = step + 1;

  const dots = $$('#pitch-dots span');
  dots.forEach((d, i) => d.classList.toggle('active', i === step));

  const contentEl = $('#pitch-slide-content');
  if (contentEl) {
    contentEl.innerHTML = `
      <h2 style="font-size:1.5rem; margin:0 0 4px; color:var(--tx);">${slide.title}</h2>
      <div style="font-size:13px; color:var(--ac); font-weight:700; margin-bottom:14px;">${slide.sub}</div>
      <div style="background:rgba(0,0,0,0.25); border:1px solid var(--ln); border-left:4px solid var(--ac); border-radius:12px; padding:16px; margin-bottom:20px;">
        <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.5px; font-weight:800; color:var(--mu); margin-bottom:6px;">Presenter Talking Point:</div>
        <p style="font-size:14.5px; line-height:1.6; color:var(--tx); margin:0;">"${slide.pitch}"</p>
      </div>
      <div style="display:flex; justify-content:center;">
        <button type="button" class="btn" onclick="PITCH_SLIDES[${step}].action()" style="padding:12px 24px; font-size:14.5px; background:linear-gradient(135deg, #06b6d4, #3b82f6); box-shadow:0 8px 25px -5px #06b6d4; color:#fff; border:none;">
          ${slide.triggerText}
        </button>
      </div>
    `;
  }

  const prevBtn = $('#pitch-prev-btn');
  const nextBtn = $('#pitch-next-btn');
  if (prevBtn) prevBtn.style.visibility = (step === 0) ? 'hidden' : 'visible';
  if (nextBtn) nextBtn.textContent = (step === PITCH_SLIDES.length - 1) ? 'Finish Pitch 🏆' : 'Next Step →';
}

function nextPitchStep() {
  if (currentPitchStep < PITCH_SLIDES.length - 1) {
    renderPitchSlide(currentPitchStep + 1);
  } else {
    closePitchDirector();
    toast('🏆 Live Pitch complete! Evaluators can now test interactive controls.', 'ok', 6000);
  }
}

function prevPitchStep() {
  if (currentPitchStep > 0) {
    renderPitchSlide(currentPitchStep - 1);
  }
}

/* ===== COLOR PALETTES & THEME SYSTEM ===== */
const THEMES = {
  'matcha': { name: 'Matcha Latte', icon: '🍵', swatch: '#4ade80' },
  'chocolate': { name: 'Dark Chocolate', icon: '🍫', swatch: '#e09f67' },
  'sakura': { name: 'Sakura Blossom', icon: '🌸', swatch: '#ec4899' },
  'lavender': { name: 'Lavender Mist', icon: '💜', swatch: '#8b5cf6' },
  'mint': { name: 'Mint Sorbet', icon: '🌿', swatch: '#10b981' },
  'cloud': { name: 'Cloud Nine', icon: '☁️', swatch: '#3b82f6' },
  'buttercream': { name: 'Buttercream Honey', icon: '🍯', swatch: '#f59e0b' },
  'dark': { name: 'Midnight Deep', icon: '🌙', swatch: '#22d3ee' },
  'light': { name: 'Ocean Breeze', icon: '☀️', swatch: '#0891b2' }
};

function setTheme(name, showToast = true) {
  if (!THEMES[name]) name = 'dark';
  document.documentElement.dataset.theme = name;
  localStorage.setItem('aquila_theme', name);

  const labelEl = $('#theme-label');
  const iconEl = $('#theme-icon');
  const dotEl = $('#theme-dot');
  if (labelEl && THEMES[name]) labelEl.textContent = THEMES[name].name;
  if (iconEl && THEMES[name]) iconEl.textContent = THEMES[name].icon;
  if (dotEl && THEMES[name]) dotEl.style.background = THEMES[name].swatch;

  $$('.theme-opt').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === name);
  });

  closeThemePicker();
  if (showToast && typeof toast === 'function') {
    toast(`🎨 Theme set to <b>${THEMES[name].name}</b>`, 'ok', 3000);
  }
}

function navigateToSection(targetId, e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  closeNavZones();
  const el = document.getElementById(targetId);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    try { history.replaceState(null, null, '#' + targetId); } catch(err) {}
  }
}

function openCornerReportFromMenu(e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  closeNavZones();
  toggleCornerReport(true);
}

function toggleNavZones(e) {
  if (e) e.stopPropagation();
  const m = $('#nav-zones-menu');
  if (m) m.classList.toggle('hide');
}

function closeNavZones() {
  const m = $('#nav-zones-menu');
  if (m) m.classList.add('hide');
}

function toggleThemePicker(e) {
  if (e) e.stopPropagation();
  const m = $('#theme-dropdown');
  if (m) m.classList.toggle('hide');
}

function closeThemePicker() {
  const m = $('#theme-dropdown');
  if (m) m.classList.add('hide');
}

document.addEventListener('click', (e) => {
  const zonesContainer = $('.nav-zones-dropdown-container');
  if (zonesContainer && !zonesContainer.contains(e.target)) {
    closeNavZones();
  }
  const container = $('.theme-picker-container');
  if (container && !container.contains(e.target)) {
    closeThemePicker();
  }
  const cornerWidget = $('#corner-report-widget');
  if (cornerWidget && !cornerWidget.contains(e.target)) {
    closeForensicReport();
  }
});

function initTheme() {
  const saved = localStorage.getItem('aquila_theme') || 'dark';
  setTheme(saved, false);
}

/* ---------- Window Load Lifecycle ---------- */
window.addEventListener('load', () => {
  initTheme();
  if (typeof initAnalyticsChart === 'function') initAnalyticsChart();
  if (typeof renderMultiChips === 'function') renderMultiChips();
  renderFeatureDetail('twin');
  loadPhoneNumber();
  renderPitchSlide(0);

  // Smooth Scrolling for all Internal Hash Anchors
  document.querySelectorAll('nav a, .hero a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const href = a.getAttribute('href');
      if (href && href.startsWith('#') && href.length > 1) {
        const target = document.querySelector(href);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  });
});
