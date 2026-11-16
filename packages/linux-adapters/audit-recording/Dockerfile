FROM debian@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    qemu-system-arm=1:7.2+dfsg-7+deb12u18+b3 \
    busybox-static=1:1.35.0-4+deb12u1+b1 auditd=1:3.0.9-1 \
    gcc=4:12.2.0-3 libc6-dev=2.36-9+deb12u14 linux-image-arm64=6.1.192-1 \
    cpio=2.13+dfsg-7.1 python3=3.11.2-1+b1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /capture
COPY probe.c guest-init build-initramfs.py ./
RUN python3 build-initramfs.py
CMD ["qemu-system-aarch64", "-machine", "virt", "-cpu", "cortex-a72", "-m", "512", "-smp", "1", "-accel", "tcg", "-nodefaults", "-nographic", "-serial", "stdio", "-monitor", "none", "-nic", "none", "-no-reboot", "-kernel", "/capture/kernel", "-initrd", "/capture/guest.cpio.gz", "-append", "console=ttyAMA0 audit=1 panic=1 rdinit=/init"]
RUN tar -czhf /capture/copyrights.tar.gz /usr/share/doc/*/copyright /usr/share/common-licenses/* \
    && sha256sum /sbin/auditd /sbin/auditctl /usr/bin/qemu-system-aarch64 /bin/busybox \
       /capture/kernel /capture/guest.cpio.gz /guest/usr/local/bin/bridge-audit-probe > /capture/binaries.sha256
