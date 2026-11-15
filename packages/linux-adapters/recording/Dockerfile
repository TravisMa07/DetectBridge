FROM debian@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc
RUN printf "#!/bin/sh\nexit 101\n" > /usr/sbin/policy-rc.d && chmod +x /usr/sbin/policy-rc.d && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends openssh-server=1:9.2p1-2+deb12u10 openssh-client=1:9.2p1-2+deb12u10 rsyslog=8.2302.0-1+deb12u2 sshpass=1.09-1 ca-certificates=20250419~deb12u2 && rm -f /etc/ssh/ssh_host_* && rm -rf /var/lib/apt/lists/*
CMD ["sleep", "infinity"]
