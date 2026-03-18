**Docker Engine installs cleanly on a Raspberry Pi 4 running Ubuntu Server LTS using the standard apt repository method — but its default networking behavior silently bypasses UFW, exposing published container ports to the internet regardless of your firewall rules.** This is the single most critical fact in this guide. Everything below covers the full installation process, post-install hardening, the UFW bypass problem and its solutions, Fail2Ban coexistence, and verification procedures. The target environment is Ubuntu Server 24.04 LTS (Noble) on a Raspberry Pi 4 (ARM64/aarch64) with UFW active and SSH on port 45000.



#### Docker Installation Prerequisites

Docker Engine for Linux ships through Docker's own apt repository — not through Ubuntu's default `docker.io` package. The installation process on ARM64 is **identical to x86_64**; the repository auto-detects the host architecture via the package metadata, and all core Docker features (Compose, Buildx, Swarm, overlay2 storage) are fully supported on `arm64`. As of 2025–2026, Docker officially supports **Ubuntu 24.04 Noble (LTS)** and **Ubuntu 22.04 Jammy (LTS)** on the `arm64` architecture. Ubuntu 20.04 Focal is no longer listed.

**Removing conflicting packages**

Ubuntu may ship older or unofficial Docker-related packages that conflict with Docker CE. Remove them first:

```bash
sudo apt remove $(dpkg --get-selections docker.io docker-compose docker-compose-v2 \
  docker-doc podman-docker containerd runc 2>/dev/null | cut -f1) 2>/dev/null
```

This is safe to run even if none of these are installed — apt will simply report nothing to remove. Existing images, containers, and volumes in `/var/lib/docker/` are preserved.

**Adding the GPG key and repository**

```bash
# Install prerequisites
sudo apt update
sudo apt install ca-certificates curl

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository (DEB822 format — current official method)
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
```

Let's break this down step by step.

**`sudo install -m 0755 -d /etc/apt/keyrings`**

The `install` command here isn't installing software — it's creating a directory with specific permissions in one step. The flags are:

- `-m 0755` sets the directory permissions: the owner can read, write, and execute; everyone else can only read and execute. This is standard for a directory that should be publicly readable but only root-writable.
- `-d` tells `install` that you're creating a directory, not copying a file.

**What is a GPG Key?**

GPG (GNU Privacy Guard) keys are a form of cryptographic verification. When you download software from the internet, you need a way to confirm it actually came from who it claims to — and hasn't been tampered with. Docker publishes a public GPG key, and every package they release is digitally "signed" with the corresponding private key. Your system uses the public key to verify the signature before installing anything. Without this, you could unknowingly install a malicious package from a compromised or fake repository.

The `curl` command downloads Docker's public GPG key and saves it to `/etc/apt/keyrings/docker.asc`.

**`sudo chmod a+r /etc/apt/keyrings/docker.asc`**

You're familiar with `chmod`, so here's the specific flag: `a+r` means "all users, add read permission." The `a` stands for *all* (owner, group, and others), and `+r` adds the read permission. This ensures that `apt` — which may run as a different user — can read the key file when verifying packages.

**The `tee` command and the file it writes**

`tee` reads from standard input and writes to a file, which is useful here because we need `sudo` privileges to write to a system directory. The `<<EOF` syntax is a *heredoc* — everything between `<<EOF` and `EOF` is treated as the input. This writes a source definition file to `/etc/apt/sources.list.d/docker.sources` in the modern DEB822 format. Here's what each field means:

- `Types: deb` — specifies binary (compiled) packages, as opposed to source code.
- `URIs` — the base URL of Docker's package repository.
- `Suites` — resolves to the Ubuntu codename (e.g., `noble` for 24.04), dynamically pulled from your system's `/etc/os-release` file so the command works across Ubuntu versions.. The repository source uses the **DEB822 `.sources` format**, which replaced the older one-line `.list` format in Docker's current documentation. Both formats work, but `.sources` is now canonical. No `Architectures:` field is needed — apt fetches packages matching the host architecture automatically.
- `Components: stable` — pulls only from the stable release channel.
- `Signed-By` — points to the GPG key we downloaded earlier, so `apt` knows exactly which key to use when verifying Docker packages.

Finally, `sudo apt update` refreshes the package list so your system is aware of the newly added Docker repository.

#### Installing Docker Engine

```bash
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

This installs five packages:

| Package | Purpose |
|---|---|
| `docker-ce` | Docker Engine daemon (`dockerd`) |
| `docker-ce-cli` | Docker CLI client |
| `containerd.io` | Container runtime (bundles containerd + runc) |
| `docker-buildx-plugin` | Extended build capabilities |
| `docker-compose-plugin` | Docker Compose v2 (invoked as `docker compose`) |

Verify immediately with `sudo docker run hello-world`. On ARM64, Docker Hub pulls the `linux/arm64` variant of multi-arch images automatically. If an image lacks ARM64 support, you'll see a platform mismatch warning — most official images (Nginx, Alpine, Python, Node, PostgreSQL) provide ARM64 builds.

#### Upgrading Docker

Upgrading is simply re-running the install command after refreshing the package index:

```bash
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

To pin a specific version instead:

```bash
apt list --all-versions docker-ce
VERSION_STRING=5:28.0.1-1~ubuntu.24.04~noble
sudo apt install docker-ce=$VERSION_STRING docker-ce-cli=$VERSION_STRING containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

#### Complete uninstallation and cleanup

```bash
# Remove all Docker packages
sudo apt purge docker-ce docker-ce-cli containerd.io docker-buildx-plugin \
  docker-compose-plugin docker-ce-rootless-extras

# Delete all Docker data (images, containers, volumes, build cache)
sudo rm -rf /var/lib/docker
sudo rm -rf /var/lib/containerd

# Remove the repository and GPG key
sudo rm /etc/apt/sources.list.d/docker.sources
sudo rm /etc/apt/keyrings/docker.asc

# Remove daemon configuration
sudo rm -rf /etc/docker

# Remove user-level Docker config
rm -rf ~/.docker
```

#### Post-installation: systemd, user permissions, and daemon hardening

**Enabling Docker on boot**

On Ubuntu, Docker enables itself at boot by default after installation. To verify or explicitly set this:

```bash
sudo systemctl enable docker.service
sudo systemctl enable containerd.service
```

To check: `systemctl is-enabled docker` should return `enabled`. To disable auto-start: replace `enable` with `disable`.

**The docker group grants root-equivalent access**

The Docker daemon runs as root and communicates through a Unix socket at `/var/run/docker.sock`. By default, only root can access this socket. Adding a user to the `docker` group lets them run Docker commands without `sudo`:

```bash
sudo groupadd docker          # May already exist
sudo usermod -aG docker $USER
newgrp docker                  # Activate in current session (or log out/in)
docker run hello-world         # Test without sudo
```

That being said, if the `docker` group already exists, you can skip `groupadd` and run only the following three commands:
```bash
sudo usermod -aG docker $USER
newgrp docker
docker run hello-world
```

**What's actually happening here?**

`sudo usermod -aG docker $USER`

`usermod` modifies an existing user account. The `-aG` flag is actually two flags working together: `-a` means *append* (rather than replace existing group memberships), and `-G` specifies the group you're adding the user to. Without the `-a` flag, `-G` would *overwrite* all of your existing supplementary groups with just `docker`, which would be a significant problem. Together, `-aG docker` safely adds `docker` to your user's list of groups without touching anything else. `$USER` is a shell variable that resolves to your current username — in this case, `chris`.


`newgrp docker`

Group membership changes in Linux don't take effect in your current shell session automatically — the system only re-evaluates your groups at login time. `newgrp docker` forces your current session to recognize the new `docker` group immediately, without requiring a full logout and login. Think of it as refreshing your session's credentials. Alternatively, you can log out and back in, which accomplishes the same thing.


`docker run hello-world`

This is the verification step. Running this *without* `sudo` is the important part — it confirms that your user can communicate directly with the Docker daemon via the socket (`/var/run/docker.sock`) using group-level permissions, rather than relying on root access. If this succeeds, your permissions are configured correctly.

**This carries a critical security implication.** Any user in the `docker` group has **unrestricted root-equivalent access** to the host. A single command demonstrates why:

```bash
docker run -v /:/hostfs -it ubuntu bash
```

This mounts the entire host filesystem into a container where the user is root. From there, they can read `/etc/shadow`, write to `/etc/sudoers`, modify system binaries, or extract SSH private keys. The `--privileged` flag grants even broader access, including all kernel capabilities and device access. Docker's official documentation explicitly states: *"only trusted users should be allowed to control your Docker daemon."*

On a **single-user headless server** where the operator already has `sudo`, this tradeoff is widely accepted — the user already possesses root-equivalent privileges, and the docker group simply removes the friction of typing `sudo` before every command. On multi-user or shared systems, **rootless mode** is the safer alternative. Rootless mode runs both the daemon and containers under a non-root user namespace, preventing container-escape vulnerabilities from granting host root access. Its limitations include no binding to privileged ports below 1024, reduced network performance (user-space networking via slirp4netns), and limited cgroup resource controls.

**Recommended daemon.json for a headless server**

Create `/etc/docker/daemon.json` with these settings:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true,
  "userland-proxy": false,
  "no-new-privileges": true
}
```

Apply with `sudo systemctl restart docker`. Here's what each setting does:

- **`log-driver` and `log-opts`**: The default `json-file` driver grows unbounded, which will eventually exhaust the SD card or disk on a Pi 4. Capping at **10 MB × 3 files = 30 MB per container** prevents this.
- **`live-restore`**: Keeps containers running during daemon restarts or upgrades — essential for a headless server where daemon updates shouldn't cause downtime.
- **`userland-proxy: false`**: Replaces the `docker-proxy` userland process with kernel-level iptables/hairpin NAT for port forwarding. Reduces attack surface and improves performance.
- **`no-new-privileges`**: Prevents container processes from gaining additional privileges via SUID binaries or capabilities.

Never expose the Docker daemon socket over TCP. If remote management is needed, use SSH tunneling (`DOCKER_HOST=ssh://user@host`). The Docker documentation is explicit: exposing the daemon API without TLS mutual authentication allows any network-reachable user to gain root on the host.


#### Docker bypasses UFW — and how to fix it

This is the most important security topic in this guide. **Docker directly manipulates iptables to implement container networking, and this bypasses UFW entirely.** The official Docker documentation acknowledges this directly: *"When you publish a container's ports using Docker, traffic to and from that container gets diverted before it goes through the ufw firewall settings."*

***Why this happens***

UFW manages the **INPUT** and **OUTPUT** chains. Docker operates in the **FORWARD** chain and the **nat** table. When you run `docker run -p 8080:80 nginx`, Docker adds a DNAT rule in the nat table's PREROUTING chain that rewrites incoming packets destined for port 8080 to the container's internal IP. These packets then traverse the FORWARD chain — through Docker's own chains (`DOCKER-USER` → `DOCKER-FORWARD` → `DOCKER`) — and **never touch the INPUT chain that UFW controls**.

The result: port 8080 is exposed to the entire internet, even if UFW has `default deny incoming` and you explicitly run `ufw deny 8080`. UFW will even report port 8080 as blocked, while it remains wide open. This has been documented in GitHub issues (moby/moby#4737, docker/for-linux#690) since 2013 and remains architecturally unchanged.

**Solution: the `/etc/ufw/after.rules` approach (recommended for UFW-managed servers)**

This is the most elegant solution for servers already using UFW. While there are other solutions, depending on your use case, they are not recommended for every use case. So, I've gone with what seemed to be the most straightforward solution. Popularized by the [chaifeng/ufw-docker](https://github.com/chaifeng/ufw-docker) project (6.4k GitHub stars, updated November 2025), it redirects Docker traffic into UFW's forwarding chain so that UFW becomes the control point for container access.

Append this block to the **end** of `/etc/ufw/after.rules`:

```
# BEGIN UFW AND DOCKER
*filter
:ufw-user-forward - [0:0]
:ufw-docker-logging-deny - [0:0]
:DOCKER-USER - [0:0]
-A DOCKER-USER -j ufw-user-forward

-A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
-A DOCKER-USER -m conntrack --ctstate INVALID -j DROP
-A DOCKER-USER -i docker0 -o docker0 -j ACCEPT

-A DOCKER-USER -j RETURN -s 10.0.0.0/8
-A DOCKER-USER -j RETURN -s 172.16.0.0/12
-A DOCKER-USER -j RETURN -s 192.168.0.0/16

-A DOCKER-USER -j ufw-docker-logging-deny -m conntrack --ctstate NEW -d 10.0.0.0/8
-A DOCKER-USER -j ufw-docker-logging-deny -m conntrack --ctstate NEW -d 172.16.0.0/12
-A DOCKER-USER -j ufw-docker-logging-deny -m conntrack --ctstate NEW -d 192.168.0.0/16

-A DOCKER-USER -j RETURN

-A ufw-docker-logging-deny -m limit --limit 3/min --limit-burst 10 -j LOG --log-prefix "[UFW DOCKER BLOCK] "
-A ufw-docker-logging-deny -j DROP

COMMIT
# END UFW AND DOCKER
```

Restart UFW with `sudo systemctl restart ufw` or `sudo ufw reload`. If rules don't take immediate effect, reboot. After applying these rules, **all published Docker ports are blocked by default** from external access. 

Container-to-container communication and traffic from private subnets (LAN) are allowed. To selectively open a container port to external traffic, use `ufw route allow` (not `ufw allow`, which only controls the INPUT chain):

```bash
# Allow everyone to reach container port 443
ufw route allow proto tcp from any to any port 443

# Allow only a specific IP to reach container port 8080
ufw route allow proto tcp from 203.0.113.50 to any port 8080

# Remove a rule
ufw route delete allow proto tcp from any to any port 443
```

This approach preserves Docker's networking functionality, integrates with UFW's rule management, logs blocked traffic with a `[UFW DOCKER BLOCK]` prefix, and requires no changes to Docker's configuration.

#### Binding to localhost: the simplest complementary defense

For services accessed only through a host-level reverse proxy, bind published ports exclusively to the loopback interface:

```bash
docker run -d -p 127.0.0.1:8080:80 nginx
```

Or in Docker Compose:

```yaml
services:
  web:
    image: nginx
    ports:
      - "127.0.0.1:8080:80"
```

This makes the service physically unreachable from external networks regardless of iptables state. Combined with a host-installed reverse proxy (Nginx or Caddy) that UFW controls normally on ports 80/443, this is the **cleanest architecture for production**: containers are invisible to the network, the reverse proxy handles TLS termination and access logging, and UFW manages the proxy ports through the standard INPUT chain with no special Docker configuration required.


#### Fail2Ban coexists with Docker but needs per-jail chain configuration

Fail2Ban adds ban rules to the **INPUT** chain by default. Since Docker container traffic flows through the **FORWARD** chain, a standard Fail2Ban ban has **zero effect on traffic destined for containers**. However, the existing SSH jail (protecting port 45000) is unaffected by Docker installation — SSH traffic hits the INPUT chain regardless, so no changes are needed for host-level services.

When you run services in Docker containers that need Fail2Ban protection, two adjustments are required: pointing Fail2Ban at the container's logs, and directing bans to the correct iptables chain.

**Jail configuration with chain = DOCKER-USER**

The Fail2Ban project's official wiki recommends setting `chain = DOCKER-USER` on a per-jail basis for containerized services, while keeping `chain = INPUT` as the global default for host services:

**UPDATE THIS EXAMPLE TO A PYTHON ONE**

```ini
# /etc/fail2ban/jail.local

[DEFAULT]
chain = INPUT              # Default for host-level services (SSH, etc.)

[sshd]
enabled = true
port = 45000
# chain = INPUT (inherited from DEFAULT — correct for host SSH)

[nginx-docker]
enabled = true
port = http,https
logpath = /opt/nginx-logs/error.log
chain = DOCKER-USER        # Bans go to DOCKER-USER chain for container traffic
maxretry = 3
bantime = 600
```

When `chain = DOCKER-USER` is set, Fail2Ban creates a sub-chain (e.g., `f2b-nginx-docker`) and inserts a jump rule at the top of DOCKER-USER. Banned IPs are caught before Docker's own forwarding rules, so the ban actually takes effect on container-bound traffic.

**Accessing container logs for monitoring**

The recommended approach is **volume-mounting** the application's log directory to a host path, then pointing Fail2Ban at that path:

```bash
docker run -d --name nginx \
  -v /opt/nginx-logs:/var/log/nginx:rw \
  -p 80:80 \
  nginx
```

Avoid pointing Fail2Ban at Docker's internal JSON log files (`/var/lib/docker/containers/<id>/<id>-json.log`) — these use a JSON wrapper format, container IDs change on recreation, and Docker's documentation warns against external tool access to these files.

**Ensuring correct startup order**

If Fail2Ban starts before Docker, it cannot find the DOCKER-USER chain and will fail to initialize jails targeting it. Fix with a systemd override:

```bash
sudo systemctl edit fail2ban.service
```

Add:

```ini
[Unit]
After=docker.service
```

This ensures Docker creates its chains before Fail2Ban attempts to hook into them.


#### Verifying the installation end to end

**Docker Engine and CLI**

Run these four commands and confirm the expected output:

```bash
docker version         # Must show Client AND Server sections, OS/Arch: linux/arm64
docker info            # Check: Storage Driver: overlay2, Architecture: aarch64, 
                       # Cgroup Driver: systemd, Compose plugin listed
docker compose version # Confirms Compose v2 plugin (e.g., v2.24.x or later)
docker run hello-world # Pulls arm64 image from Docker Hub, prints success message
```

The `docker run hello-world` command without `sudo` confirms three things simultaneously: the daemon is running, the user has docker group permissions, and Docker Hub connectivity works. If you see `Got permission denied while trying to connect to the Docker daemon socket`, run `groups` to verify `docker` is listed, and if not, re-run `sudo usermod -aG docker $USER` and log out/in.

**Systemd services**

```bash
systemctl is-enabled docker       # Expected: enabled
systemctl is-enabled containerd   # Expected: enabled
sudo systemctl status docker      # Expected: active (running), loaded (enabled)
```

**Firewall verification from an external machine**

This is the most important verification step. After applying the `after.rules` configuration, test from a separate machine:

```bash
# From an external machine — should timeout or be refused
curl -v --connect-timeout 5 http://<server-ip>:8080

# Should show "filtered" (not "open") for blocked Docker ports
nmap -p 8080 <server-ip>

# SSH on port 45000 should still be reachable
nmap -p 45000 <server-ip>
```

On the server itself, inspect the DOCKER-USER chain to confirm your rules are in place:

```bash
sudo iptables -L DOCKER-USER -n -v --line-numbers
```

Watch for blocked packets in real time:

```bash
sudo tail -f /var/log/syslog | grep "UFW DOCKER BLOCK"
```

If the `after.rules` approach is configured correctly, externally-initiated connections to published container ports will be dropped and logged, while LAN traffic, container-to-container traffic, and explicitly allowed `ufw route allow` rules will pass through normally.

**Conclusion**

Docker on a Raspberry Pi 4 with Ubuntu Server ARM64 is a first-class experience — the installation process is identical to x86_64, and all core features work without modification. The critical pitfall is Docker's iptables manipulation bypassing UFW, which is not a bug but an architectural consequence of Docker's bridge networking operating in the FORWARD chain while UFW manages INPUT. The `/etc/ufw/after.rules` approach with the ufw-docker ruleset is the most maintainable solution for UFW-based servers, giving you default-deny behavior for container ports with selective `ufw route allow` overrides. For maximum simplicity, binding container ports to `127.0.0.1` and fronting them with a host-level reverse proxy eliminates the firewall problem entirely. Fail2Ban requires per-jail `chain = DOCKER-USER` configuration only for Docker-hosted services; your existing SSH jail continues working unchanged.