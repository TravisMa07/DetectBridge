"""Build a minimal disposable audit guest from installed pinned Debian binaries."""

import gzip
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

root = Path("/guest")
for directory in (
    "bin",
    "sbin",
    "etc/audit/plugins.d",
    "dev",
    "proc",
    "sys",
    "run",
    "tmp",
    "var/log/audit",
    "usr/local/bin",
):
    (root / directory).mkdir(parents=True, exist_ok=True)


def copy_binary(path):
    target = root / path.relative_to("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
    target.chmod(0o755)
    result = subprocess.run(["ldd", str(path)], text=True, capture_output=True)
    for library in re.findall(r"(/[^\s]+)", result.stdout):
        original = Path(library)
        destination = root / original.relative_to("/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
        destination.chmod(0o755)


subprocess.run(["gcc", "-static", "-O2", "-o", "/tmp/bridge-audit-probe", "probe.c"], check=True)
for path in (Path("/bin/busybox"), Path("/sbin/auditctl"), Path("/sbin/auditd")):
    copy_binary(path)
copy_binary(Path("/lib/aarch64-linux-gnu/libgcc_s.so.1"))
shutil.copyfile("/tmp/bridge-audit-probe", root / "usr/local/bin/bridge-audit-probe")
(root / "usr/local/bin/bridge-audit-probe").chmod(0o755)
# Debian BusyBox installs links to its canonical /usr/bin/busybox path.
(root / "usr/bin").mkdir(parents=True, exist_ok=True)
(root / "usr/bin/busybox").symlink_to("/bin/busybox")
# BusyBox links are absolute within the guest, not host paths.
subprocess.run(["/bin/busybox", "--install", "-s", str(root / "bin")], check=True)
shutil.copyfile("guest-init", root / "init")
(root / "init").chmod(0o755)
(root / "etc/passwd").write_text("root:x:0:0:root:/:/bin/sh\n")
(root / "etc/group").write_text("root:x:0:\n")
(root / "etc/nsswitch.conf").write_text("passwd: files\ngroup: files\n")
(root / "etc/audit/auditd.conf").write_text("""local_events = yes
write_logs = yes
log_file = /var/log/audit/audit.log
log_group = root
log_format = RAW
flush = SYNC
priority_boost = 0
name_format = NONE
max_log_file = 8
max_log_file_action = IGNORE
space_left = 4
space_left_action = IGNORE
admin_space_left = 1
admin_space_left_action = IGNORE
disk_full_action = HALT
disk_error_action = HALT
""")
os.mknod(root / "dev/console", stat.S_IFCHR | 0o600, os.makedev(5, 1))
paths = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
archive = subprocess.run(
    ["cpio", "-o", "-H", "newc", "--quiet"],
    input=("\n".join(paths) + "\n").encode(),
    cwd=root,
    capture_output=True,
    check=True,
)
Path("/capture/guest.cpio.gz").write_bytes(gzip.compress(archive.stdout, mtime=0))
kernels = list(Path("/boot").glob("vmlinuz-*"))
assert len(kernels) == 1
shutil.copyfile(kernels[0], "/capture/kernel")
shutil.copyfile(str(kernels[0]).replace("vmlinuz-", "config-"), "/capture/kernel.config")
subprocess.run(["dpkg-query", "-W"], stdout=Path("/capture/packages.txt").open("wb"), check=True)
