"""
AQUILA Phone Notification Service (NTFY Dispatcher)
===================================================
Dispatches high-priority push notifications and alerts to municipal engineers
and city water authorities without requiring vendor lock-in or API keys.
"""

import os
import threading
import urllib.request
import uuid


class Notifier:
    """Push alerts to municipal phone as a pop-up via ntfy.sh."""

    STYLE = {
        "CONTAMINATION": (5, "biohazard,rotating_light", "CONTAMINATION detected"),
        "REAL_LEAK":     (5, "droplet,rotating_light", "REAL LEAK confirmed"),
        "CYBERATTACK":   (4, "lock,warning", "CYBERATTACK on sensor"),
        "SENSOR_FAULT":  (3, "wrench", "Sensor fault"),
        "MICRO_CRACK":   (2, "ear", "Hairline crack heard"),
    }

    def __init__(self, topic=None, base_url="https://ntfy.sh", enabled=False):
        self.topic = topic or os.environ.get("AQUILA_NTFY_TOPIC") or f"aquila-{uuid.uuid4().hex[:10]}"
        self.base_url = base_url.rstrip("/")
        self.enabled = enabled
        self.sent = set()
        self.outbox = []
        self.last_error = None
        self.sync = False

    @staticmethod
    def _ascii(s):
        return s.encode("ascii", "ignore").decode()

    def compose(self, inc):
        """Composes priority-tagged title and actionable guidance body."""
        prio, tags, head = self.STYLE.get(inc["kind"], (3, "bell", inc["kind"]))
        info, node = inc["info"], inc["node"]
        where = f"zone {list(node)}" if isinstance(node, tuple) else f"node {node}"
        if inc["kind"] == "REAL_LEAK":
            body = (
                f"~{info.get('lps')} L/s at {where}, confirmed by inflow meter. "
                "Valves isolating; send repair crew."
            )
        elif inc["kind"] == "CONTAMINATION":
            pz = info.get("patient_zero") or {}
            body = (
                f"Plume at {where}. Source: node {pz.get('node')} "
                f"(~{pz.get('age_min', 0):.0f} min ago). Quarantine valves queued; warn hospitals."
            )
        elif inc["kind"] == "CYBERATTACK":
            body = f"{where}: {info.get('vector')}. DO NOT dig - reset the IoT device."
        elif inc["kind"] == "SENSOR_FAULT":
            body = f"{where}: {info.get('vector')}. Ghost sensor in use; schedule inspection."
        else:
            body = f"{where}: {info}"
        return dict(title=f"Aquila: {head} ({where})", body=body, priority=prio, tags=tags)

    def dispatch(self, incidents, tick):
        """Sends notifications for newly confirmed incidents."""
        fresh = []
        for key, inc in incidents.items():
            if key in self.sent:
                continue
            self.sent.add(key)
            msg = dict(self.compose(inc), tick=tick)
            fresh.append(msg)
            self.outbox.append(msg)
            if self.enabled:
                if self.sync:
                    self._post(msg)
                else:
                    threading.Thread(target=self._post, args=(msg,), daemon=True).start()
        return fresh

    def _post(self, msg):
        try:
            req = urllib.request.Request(
                f"{self.base_url}/{self.topic}",
                data=msg["body"].encode("utf-8"),
                method="POST",
                headers={
                    "Title": self._ascii(msg["title"]),
                    "Priority": str(msg["priority"]),
                    "Tags": msg["tags"]
                }
            )
            urllib.request.urlopen(req, timeout=8).read()
            self.last_error = None
        except Exception as e:
            self.last_error = str(e)
