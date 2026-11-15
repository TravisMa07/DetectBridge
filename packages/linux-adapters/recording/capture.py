"""Opt-in real loopback daemon capture; logs and credentials never enter Git."""

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import time
import uuid
from pathlib import Path

parser = argparse.ArgumentParser(
    description="Capture real OpenSSH9 password actions in a local immutable lab image; never synthesize log messages."
)
parser.add_argument("image", help="Already built immutable local sha256 image ID")
parser.add_argument("output", type=Path)
args = parser.parse_args()
if not args.image.startswith("sha256:") or len(args.image) != 71:
    raise ValueError("immutable_image_required")
os.umask(0o077)
p = args.output.resolve()
p.mkdir(parents=True, exist_ok=False)
name = "detectbridge-p12-auth-" + uuid.uuid4().hex[:12]


def run(args, data=None, check=True):
    r = subprocess.run(args, input=data, capture_output=True, check=check)
    return r


def ex(*args, data=None, check=True):
    return run(["docker", "exec", "-i", name, *args], data, check)


container = (
    run(
        [
            "docker",
            "run",
            "-d",
            "--network",
            "none",
            "--hostname",
            "p12-auth-lab",
            "--name",
            name,
            args.image,
        ]
    )
    .stdout.decode()
    .strip()
)
try:
    (p / "image.json").write_bytes(run(["docker", "image", "inspect", args.image]).stdout)
    (p / "container.json").write_bytes(run(["docker", "inspect", name]).stdout)
    ex(
        "sh",
        "-c",
        "mkdir -p /run/sshd /capture; useradd -m -s /bin/sh bridgeauth; ssh-keygen -A >/dev/null 2>&1",
    )
    password = secrets.token_urlsafe(32)
    ex("chpasswd", data=("bridgeauth:" + password + "\n").encode())
    server = """Port 2222
ListenAddress 127.0.0.1
HostKey /etc/ssh/ssh_host_ed25519_key
PasswordAuthentication yes
PubkeyAuthentication no
KbdInteractiveAuthentication no
UsePAM no
PermitRootLogin no
PermitEmptyPasswords no
AllowUsers bridgeauth
MaxAuthTries 1
LogLevel VERBOSE
SyslogFacility AUTH
PidFile /run/p12-sshd.pid
"""
    collector = """module(load="imuxsock")
template(name="Native" type="string" string="%rawmsg%\\n")
template(name="Rfc5424" type="string" string="<%PRI%>1 %TIMESTAMP:::date-rfc3339% %HOSTNAME% %APP-NAME% %PROCID% %MSGID% %STRUCTURED-DATA% %msg:2:$%\\n")
if ($programname == "sshd") then {
 action(type="omfile" file="/capture/auth.native" template="Native")
 action(type="omfile" file="/capture/auth.rfc5424" template="Rfc5424")
 stop
}
"""
    (p / "sshd_config").write_text(server)
    (p / "rsyslog.conf").write_text(collector)
    ex("sh", "-c", "cat > /capture/sshd_config", data=server.encode())
    ex("sh", "-c", "cat > /capture/rsyslog.conf", data=collector.encode())
    metadata = ex(
        "sh",
        "-c",
        "/usr/sbin/sshd -V 2>&1; rsyslogd -v; dpkg-query -W; uname -a; sha256sum /usr/sbin/sshd /usr/sbin/rsyslogd /usr/bin/ssh; /usr/sbin/sshd -T -f /capture/sshd_config",
    ).stdout
    (p / "environment.txt").write_bytes(metadata)
    (p / "capture-source.sha256").write_text(
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest() + "\n"
    )
    if not metadata.startswith(b"OpenSSH_9."):
        raise RuntimeError("version_mismatch")
    for pkg in ("openssh-server", "rsyslog", "sshpass"):
        (p / (pkg + "-copyright")).write_bytes(
            ex("cat", "/usr/share/doc/" + pkg + "/copyright").stdout
        )
    ex(
        "sh",
        "-c",
        "LC_ALL=C rsyslogd -n -f /capture/rsyslog.conf > /capture/collector.stderr 2>&1 &",
    )
    time.sleep(1)
    ex(
        "sh",
        "-c",
        "LC_ALL=C /usr/sbin/sshd -D -f /capture/sshd_config > /capture/daemon.stderr 2>&1 &",
    )
    time.sleep(1)
    expected = {
        "version": "1.0.0",
        "definition": "independently specified before authentication; never derived from evaluator output",
        "actions": [
            {
                "action": "accepted-password",
                "user": "bridgeauth",
                "source_ip": "127.0.0.1",
                "expected_exit": 0,
                "expected_outcome": "success",
            },
            {
                "action": "failed-password",
                "user": "bridgeauth",
                "source_ip": "127.0.0.1",
                "expected_exit": 255,
                "expected_outcome": "failure",
            },
        ],
    }
    (p / "action-expectations.json").write_text(json.dumps(expected, indent=2) + "\n")
    results = []
    for action, pw in zip(expected["actions"], [password, secrets.token_urlsafe(32)]):
        started = time.time_ns()
        r = ex(
            "sshpass",
            "-d0",
            "ssh",
            "-T",
            "-p",
            "2222",
            "-o",
            "PreferredAuthentications=password",
            "-o",
            "PubkeyAuthentication=no",
            "-o",
            "NumberOfPasswordPrompts=1",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "UserKnownHostsFile=/tmp/p12-known-hosts",
            "bridgeauth@127.0.0.1",
            "true",
            data=(pw + "\n").encode(),
            check=False,
        )
        # sshpass maps authentication failure to 5; preserve actual process exit.
        results.append(
            {
                "action": action["action"],
                "client_exit": r.returncode,
                "started_ns": started,
                "ended_ns": time.time_ns(),
                "stdout_sha256": hashlib.sha256(r.stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(r.stderr).hexdigest(),
            }
        )
    time.sleep(1)
    for fname in ("auth.native", "auth.rfc5424", "collector.stderr", "daemon.stderr"):
        (p / fname).write_bytes(ex("cat", "/capture/" + fname).stdout)
    (p / "actions.json").write_text(json.dumps(results, indent=2) + "\n")
    print(
        json.dumps(
            {
                "container": container,
                "actions": [r["client_exit"] for r in results],
                "bytes": (p / "auth.rfc5424").stat().st_size,
            }
        )
    )
finally:
    run(["docker", "rm", "-f", name], check=False)
