"""Rich sample data generator for e2e walkthrough tests.

Generates realistic network connections, rules, sockets, and node data
that exercises all views and edge cases in the OpenSnitch UI.
"""

import random
from datetime import datetime, timedelta

PROCESSES = [
    ("/usr/bin/firefox", "firefox https://github.com/opensnitch/opensnitch/issues"),
    ("/usr/bin/chromium", "chromium --no-sandbox https://mail.google.com"),
    ("/usr/bin/curl", "curl -sL https://api.github.com/repos/opensnitch/opensnitch/releases"),
    ("/usr/bin/git", "git fetch origin main"),
    ("/usr/bin/ssh", "ssh -T git@github.com"),
    ("/usr/bin/python3", "python3 -m pip install --upgrade opensnitch-ui"),
    ("/usr/lib/thunderbird/thunderbird", "thunderbird"),
    ("/usr/bin/wget", "wget https://releases.ubuntu.com/22.04/ubuntu-22.04.3-desktop-amd64.iso"),
    ("/usr/bin/docker", "docker pull postgres:16-alpine"),
    ("/usr/bin/slack", "slack --enable-features=UseOzonePlatform"),
    ("/usr/bin/spotify", "spotify --uri=spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"),
    ("/usr/bin/code", "code --enable-proposed-api ms-vscode-remote.remote-ssh"),
    ("/usr/lib/systemd/systemd-resolved", "systemd-resolved"),
    ("/usr/lib/systemd/systemd-timesyncd", "systemd-timesyncd"),
    ("/usr/bin/syncthing", "syncthing serve --no-browser"),
    ("/usr/bin/transmission-gtk", "transmission-gtk"),
    ("/usr/bin/signal-desktop", "signal-desktop --use-tray-icon"),
    ("/nix/store/abc123-nodejs-20.11.0/bin/node", "node /home/user/projects/myapp/server.js"),
    ("/usr/bin/cups-browsed", "cups-browsed"),
    ("/usr/bin/NetworkManager", "NetworkManager --no-daemon"),
]

HOSTS = [
    ("github.com", "140.82.121.3"),
    ("api.github.com", "140.82.121.6"),
    ("mail.google.com", "142.250.80.5"),
    ("smtp.gmail.com", "142.250.80.109"),
    ("releases.ubuntu.com", "91.189.91.49"),
    ("registry.npmjs.org", "104.16.16.35"),
    ("pypi.org", "151.101.0.223"),
    ("hub.docker.com", "44.221.37.199"),
    ("slack-msgs.com", "54.174.73.156"),
    ("audio-sp-ams.spotify.com", "35.186.224.25"),
    ("update.code.visualstudio.com", "20.42.65.90"),
    ("ntp.ubuntu.com", "91.189.89.198"),
    ("tracker.debian.org", "130.89.148.77"),
    ("cdn.signal.org", "76.223.92.165"),
    ("fonts.googleapis.com", "142.250.80.42"),
    ("analytics.google.com", "142.250.190.46"),
    ("telemetry.mozilla.org", "34.120.115.102"),
    ("incoming.telemetry.mozilla.org", "34.120.115.102"),
    ("detectportal.firefox.com", "34.107.221.82"),
    ("connectivity-check.ubuntu.com", "35.224.99.156"),
    ("malware-c2.evil.example.com", "198.51.100.66"),
    ("suspicious-tracker.ads.example.net", "203.0.113.42"),
    ("crypto-miner-pool.example.org", "192.0.2.99"),
    ("unknown-server.cn", "101.42.88.91"),
]

RULES = [
    ("allow-firefox-https", "allow", "always", "simple", "false", "dest.port", "443", "Allow Firefox HTTPS traffic", "true"),
    ("allow-firefox-http", "allow", "always", "simple", "false", "dest.port", "80", "Allow Firefox HTTP traffic", "true"),
    ("allow-system-dns", "allow", "always", "simple", "false", "dest.port", "53", "Allow DNS resolution", "true"),
    ("allow-git-ssh", "allow", "always", "simple", "false", "dest.port", "22", "Allow git SSH connections", "true"),
    ("allow-thunderbird-imap", "allow", "always", "simple", "false", "dest.port", "993", "Allow Thunderbird IMAP", "true"),
    ("allow-thunderbird-smtp", "allow", "always", "simple", "false", "dest.port", "587", "Allow Thunderbird SMTP", "true"),
    ("allow-ntp", "allow", "always", "simple", "false", "dest.port", "123", "Allow NTP time sync", "true"),
    ("allow-docker-registry", "allow", "always", "simple", "false", "dest.host", "hub.docker.com", "Allow Docker Hub", "true"),
    ("allow-syncthing-local", "allow", "always", "simple", "false", "dest.port", "22000", "Allow Syncthing sync", "true"),
    ("deny-telemetry-mozilla", "deny", "always", "simple", "false", "dest.host", "telemetry.mozilla.org", "Block Mozilla telemetry", "true"),
    ("deny-analytics-google", "deny", "always", "simple", "false", "dest.host", "analytics.google.com", "Block Google Analytics", "true"),
    ("deny-suspicious-tracker", "deny", "always", "simple", "false", "dest.host", "suspicious-tracker.ads.example.net", "Block ad tracker", "true"),
    ("deny-crypto-miner", "deny", "always", "simple", "false", "dest.host", "crypto-miner-pool.example.org", "Block crypto miner pool", "true"),
    ("deny-unknown-cn", "deny", "always", "simple", "false", "dest.host", "unknown-server.cn", "Block unknown Chinese server", "true"),
    ("allow-slack-wss", "allow", "always", "simple", "false", "dest.port", "443", "Allow Slack WebSocket", "true"),
    ("allow-spotify-streaming", "allow", "always", "simple", "false", "dest.host", "audio-sp-ams.spotify.com", "Allow Spotify audio", "true"),
    ("deny-cups-browsed", "deny", "always", "simple", "false", "process.path", "/usr/bin/cups-browsed", "Block CUPS broadcast", "true"),
    ("temp-allow-wget-iso", "allow", "30m", "simple", "false", "process.path", "/usr/bin/wget", "Temporary: allow wget ISO download", "true"),
    ("temp-allow-pip-install", "allow", "15m", "simple", "false", "process.path", "/usr/bin/python3", "Temporary: allow pip install", "true"),
    ("allow-signal-cdn", "allow", "always", "simple", "false", "dest.host", "cdn.signal.org", "Allow Signal CDN", "true"),
    ("deny-all-outbound", "deny", "always", "simple", "false", "dest.network", "0.0.0.0/0", "Default deny all outbound", "false"),
]

NODES = [
    ("unix:///tmp/osui.sock", "laptop", "1.6.6", "3d 14h 22m", "21", "4827", "312"),
    ("192.168.1.10:50051", "server-prod", "1.6.5", "14d 2h 05m", "45", "128493", "8921"),
    ("192.168.1.11:50051", "server-dev", "1.6.6", "1d 6h 44m", "12", "3291", "89"),
]

PROTOCOLS = ["tcp", "udp", "tcp6", "udp6"]
ACTIONS = ["allow", "deny", "deny", "allow", "allow", "allow", "allow", "allow"]
UIDS = [1000, 1000, 1000, 0, 65534, 1001]
PORTS_DST = [443, 443, 443, 80, 53, 22, 993, 587, 123, 8080, 3000, 5432, 6379, 22000, 51413]
PORTS_SRC_BASE = 40000


def generate_connections(count=150, base_time=None):
    """Generate realistic connection events.

    Returns list of tuples ready for SQL INSERT into connections table.
    Each tuple: (time, node, action, protocol, src_ip, src_port, dst_ip, dst_host, dst_port, uid, pid, process, process_args, process_cwd, rule)
    """
    if base_time is None:
        base_time = datetime(2026, 5, 17, 8, 0, 0)

    connections = []
    for i in range(count):
        t = base_time + timedelta(seconds=i * random.randint(1, 30))
        time_str = t.strftime("%Y-%m-%d %H:%M:%S")

        proc_path, proc_args = random.choice(PROCESSES)
        host, ip = random.choice(HOSTS)
        node = random.choice(NODES)[0]
        protocol = random.choice(PROTOCOLS)
        action = random.choice(ACTIONS)
        uid = random.choice(UIDS)
        pid = random.randint(1000, 65000)
        dst_port = random.choice(PORTS_DST)
        src_port = PORTS_SRC_BASE + random.randint(0, 25000)
        src_ip = f"192.168.1.{random.randint(2, 254)}"

        # Assign a matching rule name based on action/host
        rule = _pick_rule(action, host, proc_path, dst_port)

        connections.append((
            time_str, node, action, protocol,
            src_ip, str(src_port), ip, host, str(dst_port),
            str(uid), str(pid), proc_path, proc_args, "/home/user",
            rule
        ))

    return connections


def generate_rules(node_addr="unix:///tmp/osui.sock"):
    """Generate rule entries for the rules table.

    Returns list of tuples: (time, node, name, enabled, precedence, action, duration,
    operator_type, operator_sensitive, operator_operand, operator_data, description, nolog, created)
    """
    rules = []
    base_time = datetime(2026, 5, 10, 12, 0, 0)
    for i, (name, action, duration, op_type, op_sensitive, op_operand, op_data, desc, enabled) in enumerate(RULES):
        t = base_time + timedelta(hours=i * 6)
        time_str = t.strftime("%Y-%m-%d %H:%M:%S")
        rules.append((
            time_str, node_addr, name, enabled, "0",
            action, duration, op_type, op_sensitive,
            op_operand, op_data, desc, "false", time_str
        ))
    return rules


def generate_sockets(count=30):
    """Generate active socket entries for the sockets/netstat view.

    Returns list of tuples for the sockets table.
    """
    sockets = []
    states = ["ESTABLISHED", "ESTABLISHED", "ESTABLISHED", "LISTEN", "TIME_WAIT", "CLOSE_WAIT"]
    now = datetime(2026, 5, 17, 11, 30, 0)

    for i in range(count):
        proc_path, _ = random.choice(PROCESSES)
        proc_comm = proc_path.split("/")[-1]
        host, ip = random.choice(HOSTS)
        node = random.choice(NODES)[0]
        state = random.choice(states)
        proto = random.choice(["tcp", "tcp6"])
        src_port = str(PORTS_SRC_BASE + random.randint(0, 25000))
        dst_port = str(random.choice(PORTS_DST))
        src_ip = "192.168.1.42" if proto == "tcp" else "::ffff:192.168.1.42"
        uid = str(random.choice(UIDS))
        pid = str(random.randint(1000, 65000))
        family = "2" if proto == "tcp" else "10"
        last_seen = (now - timedelta(seconds=random.randint(0, 300))).strftime("%Y-%m-%d %H:%M:%S")

        sockets.append((
            i + 1, last_seen, node, src_port, src_ip,
            ip, dst_port, 6, uid,
            str(random.randint(10000, 99999)),  # inode
            "eth0", family, {"ESTABLISHED":1,"LISTEN":10,"TIME_WAIT":6,"CLOSE_WAIT":8}[state],
            "", "0", "0", "", "0", "0", "0",
            pid, proc_comm, proc_path
        ))

    return sockets


def generate_nodes():
    """Generate node entries.

    Returns list of tuples for the nodes table:
    (addr, hostname, daemon_version, daemon_uptime, daemon_rules, cons, cons_dropped, version, status, last_connection)
    """
    nodes = []
    now = datetime(2026, 5, 17, 11, 30, 0)
    for addr, hostname, version, uptime, rules_count, cons, dropped in NODES:
        nodes.append((
            addr, hostname, version, uptime, rules_count,
            cons, dropped, "1.6.6",
            "online", now.strftime("%Y-%m-%d %H:%M:%S")
        ))
    return nodes


def generate_stats():
    """Generate hits data for hosts, procs, addrs, ports, users tables.

    Returns dict with keys: hosts, procs, addrs, ports, users
    Each value is a list of (what, hits) tuples.
    """
    stats = {
        "hosts": [(h[0], random.randint(5, 500)) for h in HOSTS],
        "procs": [(p[0], random.randint(10, 1000)) for p in PROCESSES],
        "addrs": [(h[1], random.randint(5, 500)) for h in HOSTS],
        "ports": [(str(p), random.randint(20, 2000)) for p in set(PORTS_DST)],
        "users": [
            ("1000", 3500),
            ("0", 890),
            ("65534", 120),
            ("1001", 45),
        ],
    }
    return stats


def _pick_rule(action, host, proc_path, dst_port):
    """Pick a plausible rule name for a connection."""
    if "evil" in host or "suspicious" in host or "miner" in host or "unknown" in host:
        return "deny-" + host.split(".")[0]
    if action == "deny":
        if "telemetry" in host:
            return "deny-telemetry-mozilla"
        if "analytics" in host:
            return "deny-analytics-google"
        return "deny-all-outbound"
    if dst_port == 443:
        if "firefox" in proc_path:
            return "allow-firefox-https"
        return "allow-firefox-https"
    if dst_port == 53:
        return "allow-system-dns"
    if dst_port == 22:
        return "allow-git-ssh"
    if dst_port == 993:
        return "allow-thunderbird-imap"
    if dst_port == 587:
        return "allow-thunderbird-smtp"
    if dst_port == 123:
        return "allow-ntp"
    return "allow-firefox-https"


def populate_database(db, connection_count=150, socket_count=30):
    """Insert all sample data into the database.

    Args:
        db: Database instance (must be initialized)
        connection_count: number of connections to generate
        socket_count: number of active sockets to generate
    """
    from PyQt6.QtSql import QSqlQuery
    from opensnitch.database import Database

    if db.get_db_file() != Database.DB_IN_MEMORY:
        raise RuntimeError(
            "sample data only goes into an in-memory database, not into {0}".format(db.get_db_file()))

    q = QSqlQuery(db.get_db())

    # Insert connections
    connections = generate_connections(count=connection_count)
    for conn in connections:
        q.prepare(
            "INSERT OR IGNORE INTO connections "
            "(time, node, action, protocol, src_ip, src_port, dst_ip, dst_host, dst_port, uid, pid, process, process_args, process_cwd, rule) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for i, val in enumerate(conn):
            q.bindValue(i, val)
        q.exec()

    # Insert rules
    rules = generate_rules()
    for rule in rules:
        q.prepare(
            "INSERT OR REPLACE INTO rules "
            "(time, node, name, enabled, precedence, action, duration, "
            "operator_type, operator_sensitive, operator_operand, operator_data, description, nolog, created) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for i, val in enumerate(rule):
            q.bindValue(i, val)
        q.exec()

    # Insert nodes
    nodes = generate_nodes()
    for node in nodes:
        q.prepare(
            "INSERT OR REPLACE INTO nodes "
            "(addr, hostname, daemon_version, daemon_uptime, daemon_rules, "
            "cons, cons_dropped, version, status, last_connection) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for i, val in enumerate(node):
            q.bindValue(i, val)
        q.exec()

    # Insert sockets
    sockets = generate_sockets(count=socket_count)
    for sock in sockets:
        q.prepare(
            "INSERT OR REPLACE INTO sockets "
            "(id, last_seen, node, src_port, src_ip, dst_ip, dst_port, proto, uid, "
            "inode, iface, family, state, cookies, rqueue, wqueue, expires, retrans, timer, mark, "
            "proc_pid, proc_comm, proc_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for i, val in enumerate(sock):
            q.bindValue(i, val)
        q.exec()

    # Insert stats (hosts, procs, addrs, ports, users)
    stats = generate_stats()
    for table, rows in stats.items():
        for what, hits in rows:
            q.prepare(f"INSERT OR REPLACE INTO {table} (what, hits) VALUES (?, ?)")
            q.bindValue(0, what)
            q.bindValue(1, hits)
            q.exec()

    q.finish()
