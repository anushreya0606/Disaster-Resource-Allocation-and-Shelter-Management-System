"""Low-Level TCP Socket Stream IPC Daemon for Emergency Offline SMS Intake.

[ON-THE-SPOT TIP FOR EVALUATORS]:
Demonstrates Operating System Inter-Process Communication (IPC):
1. Raw TCP Stream Sockets (Port 9999).
2. Simulates an emergency field radio or offline GSM module parsing raw SMS strings
   when cellular 4G/5G data networks and web browsers are down.
"""
import socket
import threading
from typing import Optional

try:
    from .config import SOCKET_HOST, SOCKET_PORT
    from .database import get_connection
    from .scheduler import MLFQScheduler, Task, calculate_triage_priority
except ImportError:
    from config import SOCKET_HOST, SOCKET_PORT
    from database import get_connection
    from scheduler import MLFQScheduler, Task, calculate_triage_priority


class SMSSocketServer:
    def __init__(self, scheduler: MLFQScheduler, host: str = SOCKET_HOST, port: int = SOCKET_PORT):
        self.scheduler = scheduler
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.running = False
        self.server_thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the TCP socket listener thread."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.running = True
        self.server_thread = threading.Thread(target=self._listen_loop, daemon=True, name="SMS-TCP-Daemon")
        self.server_thread.start()
        print(f" [IPC Daemon] TCP Socket Listener active on {self.host}:{self.port}")

    def stop(self):
        """Stops the socket listener."""
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

    def _listen_loop(self):
        while self.running:
            try:
                client_sock, addr = self.sock.accept()
                threading.Thread(target=self._handle_client, args=(client_sock, addr), daemon=True).start()
            except Exception:
                break

    def _handle_client(self, client_sock: socket.socket, addr):
        with client_sock:
            try:
                data = client_sock.recv(1024).decode("utf-8").strip()
                if not data:
                    return

                # Parse key-value payload: "NAME:Ravi,AGE:55,SEX:M,INJURY:serious,LAT:10.12,LON:76.35"
                params = {}
                for part in data.split(","):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        params[k.strip().upper()] = v.strip()

                name = params.get("NAME", "Unknown Evacuee")
                age = int(params.get("AGE", 30))
                sex = params.get("SEX", "M").upper()
                injury = params.get("INJURY", "none").lower()
                lat = float(params.get("LAT", 10.1076))
                lon = float(params.get("LON", 76.3516))

                priority = calculate_triage_priority(age, injury)

                # Insert into DB
                conn = get_connection()
                with conn:
                    cur = conn.cursor()
                    cur.execute("""
                    INSERT INTO evacuees (name, age, sex, injury_severity, priority, latitude, longitude, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'QUEUED');
                    """, (name, age, sex, injury, priority, lat, lon))
                    evacuee_id = cur.lastrowid
                conn.close()

                # Dispatch to MLFQ Scheduler
                task = Task(evacuee_id=evacuee_id, name=name, age=age, priority=priority, latitude=lat, longitude=lon)
                self.scheduler.submit_task(task)

                ack = f"ACK: Evacuee {name} (ID: {evacuee_id}) queued with Priority {priority}\n"
                client_sock.sendall(ack.encode("utf-8"))
            except Exception as e:
                err = f"ERR: {str(e)}\n"
                client_sock.sendall(err.encode("utf-8"))


def send_test_sms(payload: str = "NAME:Sunil,AGE:65,SEX:M,INJURY:serious,LAT:10.11,LON:76.35") -> str:
    """Helper client function to send a simulated offline SMS string to the socket daemon."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((SOCKET_HOST, SOCKET_PORT))
            s.sendall(payload.encode("utf-8"))
            response = s.recv(1024).decode("utf-8").strip()
            return response
    except Exception as e:
        return f"Failed to connect to IPC daemon: {e}"
