"""Send SMS-format lines to the socket daemon, as an SMS gateway would.

Examples:
  python scripts/sms_client.py "REG Ravi Kumar|45|M|serious|O2|D:56"
  python scripts/sms_client.py "REG Meena Negi|29|F|none|PREG|30.32|78.03" "STATUS 1"
  python scripts/sms_client.py            (interactive: type lines, empty line to quit)
"""
import argparse
import socket

ap = argparse.ArgumentParser()
ap.add_argument("lines", nargs="*")
ap.add_argument("--host", default="127.0.0.1")
ap.add_argument("--port", type=int, default=9999)
args = ap.parse_args()

with socket.create_connection((args.host, args.port), timeout=15) as s:
    f = s.makefile("rw", encoding="utf-8", newline="\n")
    print(f.readline().strip())
    lines = args.lines or iter(lambda: input("> "), "")
    for line in lines:
        f.write(line + "\n"); f.flush()
        print(f.readline().strip())
    f.write("QUIT\n"); f.flush()
