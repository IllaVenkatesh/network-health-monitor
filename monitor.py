"""
Network & Server Health Monitor with Incident Logging
-----------------------------------------------------
Pings a list of hosts, records whether each is UP or DOWN with its response
time, and automatically opens an incident (like a ticket) when a host goes
down. The incident is closed when the host comes back up.

Uses only the Python standard library. Works on Windows, Linux and macOS.

Run:
    python monitor.py                       # 5 rounds, 10 seconds apart
    python monitor.py --rounds 10 --interval 30
"""

import argparse
import csv
import json
import platform
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------------
# 1. Hosts to monitor. "critical" hosts get High priority incidents.
#    The last host is unreachable on purpose, so you can see an incident open.
# ----------------------------------------------------------------------------
HOSTS = [
    {"name": "Localhost", "address": "127.0.0.1", "critical": False},
    {"name": "Google DNS", "address": "8.8.8.8", "critical": True},
    {"name": "Cloudflare DNS", "address": "1.1.1.1", "critical": True},
    {"name": "Google Website", "address": "google.com", "critical": False},
    {"name": "Test Server (offline)", "address": "10.255.255.1", "critical": False},
]

LOG_FILE = Path("health_log.csv")
INCIDENT_FILE = Path("incidents.json")


# ----------------------------------------------------------------------------
# 2. Check a host using the operating system's ping command
# ----------------------------------------------------------------------------
def ping(address, timeout_s=2):
    """Return (is_up, response_time_ms). response_time_ms is None if down."""
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_s * 1000), address]
    elif system == "darwin":  # macOS takes the timeout in milliseconds
        cmd = ["ping", "-c", "1", "-W", str(timeout_s * 1000), address]
    else:  # Linux
        cmd = ["ping", "-c", "1", "-W", str(timeout_s), address]

    start = time.perf_counter()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s + 3
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, None
    elapsed_ms = (time.perf_counter() - start) * 1000

    output = result.stdout.lower()
    # A real reply always contains "ttl=". This also catches Windows replies
    # such as "Destination host unreachable" that still exit with code 0.
    if result.returncode != 0 or "ttl=" not in output:
        return False, None

    match = re.search(r"time[=<]\s*([\d.]+)\s*ms", output)
    response_ms = float(match.group(1)) if match else round(elapsed_ms, 1)
    return True, response_ms


# ----------------------------------------------------------------------------
# 3. Log every check to a CSV file
# ----------------------------------------------------------------------------
def log_result(timestamp, host, status, response_ms):
    new_file = not LOG_FILE.exists()
    with LOG_FILE.open("a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["timestamp", "name", "address", "status", "response_ms"])
        writer.writerow(
            [timestamp, host["name"], host["address"], status,
             "" if response_ms is None else response_ms]
        )


# ----------------------------------------------------------------------------
# 4. Incident management: open when DOWN, resolve when UP again
# ----------------------------------------------------------------------------
def load_incidents():
    if INCIDENT_FILE.exists():
        return json.loads(INCIDENT_FILE.read_text())
    return []


def save_incidents(incidents):
    INCIDENT_FILE.write_text(json.dumps(incidents, indent=2))


def find_open_incident(incidents, address):
    for incident in incidents:
        if incident["address"] == address and incident["status"] == "Open":
            return incident
    return None


def open_incident(incidents, host, timestamp):
    incident = {
        "id": f"INC{len(incidents) + 1:04d}",
        "host": host["name"],
        "address": host["address"],
        "priority": "High" if host["critical"] else "Medium",
        "status": "Open",
        "opened_at": timestamp,
        "resolved_at": None,
    }
    incidents.append(incident)
    print(f"    >> INCIDENT OPENED: {incident['id']} "
          f"({incident['priority']} priority) for {host['name']}")


def resolve_incident(incident, timestamp):
    incident["status"] = "Resolved"
    incident["resolved_at"] = timestamp
    print(f"    >> INCIDENT RESOLVED: {incident['id']}")


# ----------------------------------------------------------------------------
# 5. Main loop
# ----------------------------------------------------------------------------
def run(rounds, interval):
    incidents = load_incidents()
    stats = {h["address"]: {"checks": 0, "up": 0, "times": []} for h in HOSTS}

    for round_number in range(1, rounds + 1):
        print(f"\n=== Round {round_number} of {rounds} ===")
        for host in HOSTS:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            is_up, response_ms = ping(host["address"])
            status = "UP" if is_up else "DOWN"

            record = stats[host["address"]]
            record["checks"] += 1
            if is_up:
                record["up"] += 1
                record["times"].append(response_ms)
                print(f"[{timestamp}] {host['name']:<24} UP    {response_ms} ms")
            else:
                print(f"[{timestamp}] {host['name']:<24} DOWN")

            log_result(timestamp, host, status, response_ms)

            open_inc = find_open_incident(incidents, host["address"])
            if not is_up and open_inc is None:
                open_incident(incidents, host, timestamp)
            elif is_up and open_inc is not None:
                resolve_incident(open_inc, timestamp)

        save_incidents(incidents)
        if round_number < rounds:
            time.sleep(interval)

    print_summary(stats, incidents)


def print_summary(stats, incidents):
    print("\n=== Summary ===")
    print(f"{'Host':<24}{'Uptime %':>10}{'Avg ms':>10}")
    for host in HOSTS:
        record = stats[host["address"]]
        uptime = 100 * record["up"] / record["checks"] if record["checks"] else 0
        times = record["times"]
        avg = f"{sum(times) / len(times):.1f}" if times else "-"
        print(f"{host['name']:<24}{uptime:>9.0f}%{avg:>10}")

    open_count = sum(1 for i in incidents if i["status"] == "Open")
    print(f"\nTotal incidents: {len(incidents)} | Still open: {open_count}")
    print(f"Details saved in {LOG_FILE} and {INCIDENT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network & server health monitor")
    parser.add_argument("--rounds", type=int, default=5, help="number of check rounds")
    parser.add_argument("--interval", type=int, default=10, help="seconds between rounds")
    args = parser.parse_args()
    run(args.rounds, args.interval)
