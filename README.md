# Network & Server Health Monitor with Incident Logging

A Python tool that checks whether servers and network devices are reachable, logs the results, and automatically raises an incident when a host goes down. The incident is closed when the host recovers.

I built this to practise the basics of IT infrastructure support: network monitoring, incident management and troubleshooting.

## Features

- Pings a list of hosts and records UP or DOWN with response time
- Logs every check to `health_log.csv` with a timestamp
- Opens an incident (INC0001, INC0002, ...) when a host goes down, with High priority for critical hosts and Medium for others
- Resolves the incident automatically when the host comes back up, and never opens duplicates
- Prints an uptime percentage and average response time per host at the end
- Uses only the Python standard library and works on Windows, Linux and macOS

## How to run

```
python monitor.py                        # 5 rounds, 10 seconds apart
python monitor.py --rounds 10 --interval 30
```

Edit the `HOSTS` list at the top of `monitor.py` to monitor your own devices.

## Output files

| File | Contents |
|---|---|
| `health_log.csv` | Timestamp, host, status and response time for every check |
| `incidents.json` | Incident ID, host, priority, status, opened and resolved times |

## How it works

1. `ping()` runs the operating system's ping command and reads the reply (TTL and time).
2. `log_result()` appends each check to the CSV file.
3. `open_incident()` and `resolve_incident()` manage the incident lifecycle.
4. `run()` loops through all hosts for the chosen number of rounds, then prints a summary.

## Possible improvements

- Email or Telegram alerts when an incident opens
- Port checks for services such as HTTP, SSH and DNS
- A simple web dashboard for the logs

## Tech

Python 3 (subprocess, csv, json, argparse, datetime)
