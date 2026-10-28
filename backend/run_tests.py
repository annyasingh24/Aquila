"""
AQUILA 23-Scenario Verification & Test Suite
============================================
Executes headless tests across physical leaks, cyberattacks, sensor drift,
chlorine spoofing, acoustic crack listening, SHA-256 tamper verification,
and phone notifications.
"""

import http.server
import sys
import threading
from backend.engine import Simulation
from backend.notifier import Notifier


def run_tests():
    results = []

    def check(name, cond, extra=""):
        results.append(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {extra}")

    def fresh():
        s = Simulation()
        s.advance(8)
        return s

    print("0) Baseline")
    s = fresh()
    check("no false alarms", s.aquila.summary["classes"] == ["NORMAL"], str(s.aquila.summary["classes"]))
    check("legacy quiet", len(s.legacy.alarms) == 0)

    print("1) REAL leak, node 12, 25 L/s")
    s = fresh()
    s.world.burst_pipe(12, 25)
    s.advance(5)
    inc = [k for k in s.aquila.incidents if k[0] == "REAL_LEAK"]
    check("leak localised to node 12", inc == [("REAL_LEAK", 12)], str(inc))
    check("valves isolate it & hospitals safe", s.aquila.last_plan["safe"], str(s.aquila.last_plan["steps"]))
    check("leak stopped", 12 not in s.world.truth["sol"]["leakq"] or s.world.truth["sol"]["leakq"][12] == 0)
    check("litres saved > 0", s.aquila.roi["litres"] > 0, f"{s.aquila.roi['litres']:,.0f} L")

    print("2) CYBERATTACK: fake burst at node 8 (legacy panics)")
    s = fresh()
    s.world.hack_sensor(8, "fake_burst", True)
    s.advance(4)
    check("legacy sent ghost crew", s.legacy.ghost_dispatches >= 1, f"ghost crews={s.legacy.ghost_dispatches}")
    check(
        "aquila flagged node 8 only",
        s.aquila.incidents.keys() >= {("CYBERATTACK", 8)}
        and not any(k[0] == "REAL_LEAK" for k in s.aquila.incidents),
        str(list(s.aquila.incidents))
    )
    inc = s.aquila.incidents[("CYBERATTACK", 8)]
    print("     vector:", inc["info"]["vector"])
    check("rogue IP blocked", "185.220.101.47" in s.aquila.blocked_ips)
    check("sensor recovered after block", s.aquila.incidents[("CYBERATTACK", 8)]["status"].startswith("MITIGATED"))

    print("3) Honest hardware fault (valid signature) at node 17")
    s = fresh()
    s.world.hack_sensor(17, "drift", False)
    s.advance(4)
    check("classified SENSOR_FAULT", ("SENSOR_FAULT", 17) in s.aquila.incidents, str(list(s.aquila.incidents)))

    print("4) STEALTH: real leak at 17 hidden by replay attack")
    s = fresh()
    s.world.burst_pipe(17, 30)
    s.world.hack_sensor(17, "hide_leak", True)
    s.advance(5)
    keys = set(s.aquila.incidents)
    check("leak still found via ghost sensor", ("REAL_LEAK", 17) in keys, str(keys))
    check("attack also flagged", ("CYBERATTACK", 17) in keys)

    print("5) Contamination at node 6 -> patient zero")
    s = fresh()
    s.world.contaminate(6, 0.02)
    s.advance(3)
    pz = s.aquila.summary["patient_zero"] or next(
        (v["info"]["patient_zero"] for k, v in s.aquila.incidents.items() if k[0] == "CONTAMINATION"), None
    )
    check("plume detected", any(k[0] == "CONTAMINATION" for k in s.aquila.incidents), str(list(s.aquila.incidents)))
    check("patient zero = node 6", pz is not None and pz["node"] == 6, str(pz))

    print("6) Spoofed chlorine at node 14 (isolated, no plume)")
    s = fresh()
    s.world.hack_sensor(14, "fake_chlorine", True)
    s.advance(3)
    check("NOT called contamination", not any(k[0] == "CONTAMINATION" for k in s.aquila.incidents))
    check("flagged as cyber/sensor", any(k[1] == 14 and k[0] in ("CYBERATTACK", "SENSOR_FAULT") for k in s.aquila.incidents))

    print("7) Hairline crack at node 18 (acoustic)")
    s = fresh()
    s.world.crack_pipe(18)
    s.advance(1)
    check("crack located", ("MICRO_CRACK", 18) in s.aquila.incidents, str(s.aquila.summary["acoustic"]))

    print("8) Flight recorder")
    ok, _ = s.aquila.log.verify()
    check("chain valid", ok)
    s.aquila.log.chain[2]["payload"] = {"x": 1}
    ok, bad = s.aquila.log.verify()
    check("tampering detected", (not ok) and bad == 2, f"broken at {bad}")

    print("9) Phone notifications (local mock server)")
    got = []

    class MockHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            content_len = int(self.headers["Content-Length"])
            got.append((self.path, dict(self.headers), self.rfile.read(content_len).decode()))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), MockHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    s = fresh()
    s.notifier = Notifier("demo-topic", f"http://127.0.0.1:{srv.server_port}", enabled=True)
    s.notifier.sync = True
    s.world.burst_pipe(12, 25)
    s.world.hack_sensor(8, "fake_burst", True)
    s.advance(5)
    srv.shutdown()

    kinds = sorted(p[1]["Title"] for p in got)
    check("pop-ups sent to topic", len(got) >= 2 and all(p[0] == "/demo-topic" for p in got), str(kinds))
    check("leak is urgent (priority 5)", any(p[1]["Priority"] == "5" for p in got))
    check("each incident sent once", len(got) == len(s.notifier.sent))
    print("     sample:", got[0][1]["Title"], "|", got[0][2][:90])

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return all(results)


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
