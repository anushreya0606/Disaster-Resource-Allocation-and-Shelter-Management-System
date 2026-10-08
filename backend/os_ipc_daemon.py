import socket
import threading
import time
from typing import Dict, Any, List
from backend.database import get_db_connection, execute_concurrency_safe_allocation

class OfflineSMSIPCSocketDaemon:
    """
    OS IPC Concept: Low-Level Socket Stream & IPC Listener Daemon
    Simulates receiving offline SMS/USSD payloads or serial mesh communications
    from field agents in disaster blackout zones (e.g. flood areas).
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 9999):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None
        self.processed_sms_count = 0
        self.latest_sms_logs: List[Dict[str, Any]] = []

    def start_daemon(self):
        """Starts the low-level TCP socket listener in a background thread."""
        self.running = True
        self.thread = threading.Thread(target=self._socket_listener_loop, daemon=True)
        self.thread.start()
        print(f"[OS IPC DAEMON] Offline SMS Socket Daemon listening on {self.host}:{self.port}")

    def _socket_listener_loop(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(2.0)
            
            while self.running:
                try:
                    client_sock, addr = self.server_socket.accept()
                    data = client_sock.recv(1024).decode('utf-8')
                    if data:
                        self._parse_and_process_sms_payload(data)
                        client_sock.sendall(b"IPC_ACK_PROCESSED\n")
                    client_sock.close()
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[OS IPC DAEMON] Socket Error: {e}")
        except Exception as err:
            print(f"[OS IPC DAEMON] Could not start listener on port {self.port}: {err}")

    def _parse_and_process_sms_payload(self, raw_payload: str):
        """
        Parses raw SMS format:
        SOS#NAME=EvacueeName#PRIORITY=0#LAT=10.10#LON=76.35#BEDS=1#SHELTER_ID=1
        """
        try:
            parts = raw_payload.strip().split('#')
            params = {}
            for part in parts[1:]:
                if '=' in part:
                    k, v = part.split('=', 1)
                    params[k] = v
                    
            name = params.get("NAME", "Anonymous Evacuee")
            priority = int(params.get("PRIORITY", 2))
            lat = float(params.get("LAT", 9.98))
            lon = float(params.get("LON", 76.29))
            beds = int(params.get("BEDS", 1))
            shelter_id = int(params.get("SHELTER_ID", 1))
            
            # Insert into database evacuees table
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO evacuees (full_name, age, gender, triage_priority, medical_conditions, latitude, longitude)
                VALUES (?, 35, 'UNSPECIFIED', ?, 'Offline SMS Ingestion', ?, ?)
            """, (name, priority, lat, lon))
            evacuee_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Concurrency-Safe Allocation
            alloc_res = execute_concurrency_safe_allocation(evacuee_id, shelter_id, beds=beds)
            
            self.processed_sms_count += 1
            log_entry = {
                "timestamp": time.strftime("%H:%M:%S"),
                "raw_sms": raw_payload,
                "parsed_name": name,
                "allocation_status": alloc_res
            }
            self.latest_sms_logs.insert(0, log_entry)
            if len(self.latest_sms_logs) > 20:
                self.latest_sms_logs.pop()
                
            print(f"[OS IPC DAEMON] Processed Offline SMS for {name} -> Allocation: {alloc_res.get('success')}")
        except Exception as ex:
            print(f"[OS IPC DAEMON] SMS Parse Error: {ex}")

# Global Daemon Instance
sms_ipc_daemon = OfflineSMSIPCSocketDaemon()
