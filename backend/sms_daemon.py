"""Offline intake over a raw TCP socket (default 127.0.0.1:9999).

During a network blackout an SMS gateway (GSM modem or phone) forwards text messages as lines:
    REG name|age|sex|injury|flags|lat|lon       flags: comma list of O2,PREG,WC,UNC or '-'
    REG name|age|sex|injury|flags|D:<district_id>
    STATUS <evacuee_id>
    PING
Each line gets a one-line reply that short enough to send back as an SMS.
"""
import socketserver
import threading

from . import services
from .database import one

FLAG_MAP = {"O2": "needs_oxygen", "PREG": "pregnant", "WC": "uses_wheelchair", "UNC": "unconscious"}


def parse_reg(body):
    parts = [p.strip() for p in body.split("|")]
    if len(parts) not in (6, 7):
        raise ValueError("Use REG name|age|sex|injury|flags|lat|lon")
    name, age, sex, injury, flags = parts[:5]
    p = {"full_name": name, "age": age or None, "sex": sex or "O", "injury_severity": injury or "none"}
    for f in flags.upper().split(","):
        f = f.strip()
        if f and f != "-":
            if f not in FLAG_MAP:
                raise ValueError(f"Unknown flag {f}")
            p[FLAG_MAP[f]] = True
    if len(parts) == 6:
        if not parts[5].upper().startswith("D:"):
            raise ValueError("Give lat|lon or D:<district_id>")
        p["district_id"] = parts[5][2:]
    else:
        p["latitude"], p["longitude"] = parts[5], parts[6]
    return p


def process_line(line, scheduler, user_id):
    cmd, _, body = line.strip().partition(" ")
    cmd = cmd.upper()
    try:
        if cmd == "PING":
            return "PONG"
        if cmd == "STATUS":
            s = services.evacuee_status(int(body))
            where = f" at {s['shelter_name']}" if s["shelter_name"] else ""
            return f"ID {s['evacuee_id']} {s['status']}{where}"
        if cmd == "REG":
            r = services.register(parse_reg(body), user_id, "SMS", scheduler)
            tag = f"ID {r['evacuee_id']} P{r['priority']}"
            if r["status"] == "ALLOCATED":
                sh = r.get("shelter") or {}
                return f"OK {tag} -> {sh.get('shelter_name')} {r.get('distance_km')}km"
            return f"{r['status']} {tag}"
        return "ERR unknown command; use REG, STATUS or PING"
    except services.DuplicateError as exc:
        return f"DUP existing ID {exc.existing_id}"
    except (ValueError, LookupError) as exc:
        return f"ERR {exc}"


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def start(host, port, scheduler):
    sys_user = one("SELECT user_id FROM users WHERE username = 'sms_gateway'")
    user_id = sys_user["user_id"] if sys_user else None

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.wfile.write(b"RELIEF SMS GATEWAY READY\n")
            for raw in self.rfile:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                if line.upper() == "QUIT":
                    break
                self.wfile.write((process_line(line, scheduler, user_id) + "\n").encode())

    server = _Server((host, port), Handler)
    threading.Thread(target=server.serve_forever, name="sms-daemon", daemon=True).start()
    return server
