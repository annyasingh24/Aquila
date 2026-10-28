/* ==========================================================================
   AQUILA - Before vs After Attack Analytics & Visualizations
   Dynamic comparative charts powered by Chart.js
   ========================================================================== */

let analyticsChart = null;
let currentGraphType = 'pressure';

function initAnalyticsChart() {
  const ctx = document.getElementById('analyticsChart');
  if (!ctx) return;

  const nodes = N.slice(1);
  const labels = nodes.map(n => n.id);
  const baseline = nodes.map(() => 60);
  const reported = nodes.map(n => (n.st === 'spoof' ? 0 : n.pr));
  const ghost = nodes.map(() => 59.2);

  analyticsChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Baseline Safe Operation (Unperturbed)',
          data: baseline,
          borderColor: '#38bdf8',
          backgroundColor: 'rgba(56, 189, 248, 0.08)',
          borderWidth: 2.5,
          borderDash: [5, 4],
          pointRadius: 4,
          pointHoverRadius: 7,
          pointBackgroundColor: '#38bdf8',
          pointBorderColor: '#ffffff',
          pointBorderWidth: 1.5,
          fill: false,
          tension: 0.35
        },
        {
          label: 'Received Telemetry (Simulated Attack / Deflection)',
          data: reported,
          borderColor: '#ff2d55',
          backgroundColor: 'rgba(255, 45, 85, 0.15)',
          borderWidth: 3,
          pointRadius: 5,
          pointHoverRadius: 8,
          pointBackgroundColor: '#ff2d55',
          pointBorderColor: '#ffffff',
          pointBorderWidth: 2,
          fill: true,
          tension: 0.35
        },
        {
          label: 'Aquila Ground Truth (Physics Reconstruction)',
          data: ghost,
          borderColor: '#4ade80',
          backgroundColor: 'rgba(74, 222, 128, 0.12)',
          borderWidth: 2.8,
          pointRadius: 5,
          pointHoverRadius: 8,
          pointBackgroundColor: '#4ade80',
          pointBorderColor: '#ffffff',
          pointBorderWidth: 2,
          fill: false,
          tension: 0.35
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 500,
        easing: 'easeOutQuart'
      },
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#07121fee',
          titleColor: '#38bdf8',
          bodyColor: '#e6f1fb',
          borderColor: 'rgba(56, 189, 248, 0.3)',
          borderWidth: 1,
          padding: 10,
          boxPadding: 4,
          usePointStyle: true
        }
      },
      scales: {
        y: {
          grid: { color: 'rgba(255,255,255,0.06)' },
          ticks: { color: '#8aa4bd', font: { family: 'inherit', size: 11 } }
        },
        x: {
          grid: { color: 'rgba(255,255,255,0.03)' },
          ticks: { color: '#8aa4bd', font: { family: 'inherit', size: 11 } }
        }
      }
    }
  });
}

function switchGraph(type, btn) {
  $$('.graph-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentGraphType = type;
  updateAnalyticsChart();
}

function updateAnalyticsChart() {
  if (!analyticsChart) return;
  const nodes = N.slice(1);
  const labels = nodes.map(n => n.id);

  if (currentGraphType === 'pressure') {
    analyticsChart.data.labels = labels;
    analyticsChart.data.datasets[0].label = 'Baseline Safe Pressure (60 psi)';
    analyticsChart.data.datasets[0].data = nodes.map(() => 60);
    analyticsChart.data.datasets[1].label = 'Received Telemetry (Attack Reported)';
    analyticsChart.data.datasets[1].data = nodes.map(n =>
      n.st === 'spoof' ? 0 : Math.round(n.pr)
    );
    analyticsChart.data.datasets[2].label = 'Aquila Reconstructed Truth (Ghost Sensor)';
    analyticsChart.data.datasets[2].data = nodes.map(n =>
      n.st === 'spoof' ? 58.6 : Math.round(n.pr)
    );
    analyticsChart.options.scales.y.title = { display: true, text: 'Pressure Head (psi)', color: '#8aa4bd' };

  } else if (currentGraphType === 'residual') {
    analyticsChart.data.labels = labels;
    analyticsChart.data.datasets[0].label = 'Baseline Invariant Residual (0.0 L/s)';
    analyticsChart.data.datasets[0].data = nodes.map(() => 0.0);
    analyticsChart.data.datasets[1].label = 'Received Telemetry Residual (Under Attack)';
    analyticsChart.data.datasets[1].data = nodes.map(n =>
      n.st === 'spoof' ? -32.5 : n.st === 'leak' ? 25.0 : +(Math.random() * 0.4 - 0.2).toFixed(2)
    );
    analyticsChart.data.datasets[2].label = 'Aquila Rebalanced Mass Balance';
    analyticsChart.data.datasets[2].data = nodes.map(() => 0.1);
    analyticsChart.options.scales.y.title = { display: true, text: 'Flow Residual (L/s)', color: '#8aa4bd' };

  } else if (currentGraphType === 'trust') {
    analyticsChart.data.labels = labels;
    analyticsChart.data.datasets[0].label = 'Baseline Trust Confidence (100%)';
    analyticsChart.data.datasets[0].data = nodes.map(() => 100);
    analyticsChart.data.datasets[1].label = 'Telemetry Credibility Under Attack (%)';
    analyticsChart.data.datasets[1].data = nodes.map(n => Math.round(n.trust));
    analyticsChart.data.datasets[2].label = 'Aquila Byzantine Admission Floor';
    analyticsChart.data.datasets[2].data = nodes.map(() => 80);
    analyticsChart.options.scales.y.title = { display: true, text: 'Trust Score (%)', color: '#8aa4bd' };

  } else if (currentGraphType === 'quality') {
    analyticsChart.data.labels = labels;
    analyticsChart.data.datasets[0].label = 'Baseline Chlorine Disinfection (0.85 mg/L)';
    analyticsChart.data.datasets[0].data = nodes.map(() => 0.85);
    analyticsChart.data.datasets[1].label = 'Received Telemetry (Measured Contaminant)';
    analyticsChart.data.datasets[1].data = nodes.map(n => (n.st === 'contam' ? 0.06 : 0.85));
    analyticsChart.data.datasets[2].label = 'Aquila Health & Safety Threshold';
    analyticsChart.data.datasets[2].data = nodes.map(() => 0.2);
    analyticsChart.options.scales.y.title = { display: true, text: 'Chlorine (mg/L)', color: '#8aa4bd' };
  }

  analyticsChart.update();
}
