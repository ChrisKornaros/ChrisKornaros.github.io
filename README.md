### Running Containers

With Docker installed, configured, and secured on your Raspberry Pi, and a Python image built from your Dockerfile, it's time to actually run containers. This section focuses on the commands themselves — what they do, the flags you'll use most often, and how to get your Python container running as a persistent service on your server. We've already covered the conceptual background, security implications, and networking theory in earlier sections, so here we'll move quickly through the practical mechanics.

#### Docker Commands Overview

Docker's CLI follows a consistent pattern: `docker <object> <command> [options]`. While Docker supports dozens of commands, these six form the core workflow you'll use daily when managing containers.

**`docker run`** creates and starts a new container from an image. This is the command you'll use most often, and it accepts the widest range of flags.

```bash
docker run [OPTIONS] IMAGE [COMMAND]
```

The most common flags you'll encounter:

```bash
# Run a container in detached mode (background) with a custom name
docker run -d --name my-python yourusername/python-dev:1.0

# Run interactively with a bash terminal (useful for debugging)
docker run -it --name my-python yourusername/python-dev:1.0 bash

# Run with port mapping, volume mount, and auto-removal on exit
docker run -d --name my-python \
  -p 8080:8000 \
  -v /opt/python-data:/app/data \
  --rm \
  yourusername/python-dev:1.0
```

The `-d` flag runs the container in detached mode, meaning it runs in the background and returns you to your shell prompt immediately — this is what you want for long-running services on a headless server. The `-it` flags are two separate flags combined: `-i` keeps STDIN open and `-t` allocates a pseudo-TTY, together giving you an interactive shell session inside the container. The `--name` flag assigns a human-readable identifier so you can reference the container by name instead of Docker's auto-generated container ID. The `-p` flag publishes a container port to the host (covered in detail below). The `-v` flag mounts a host directory into the container for data persistence. The `--rm` flag automatically removes the container when it exits, which is useful for one-off tasks but not for persistent services.

**`docker ps`** lists running containers. This is your primary tool for checking what's currently active on your server.

```bash
# List running containers
docker ps

# List all containers (including stopped)
docker ps -a

# List only specific containers
docker ps -f [FILTER]

# Show only container IDs (useful for scripting)
docker ps -q
```

The default `docker ps` output shows the container ID, image name, command, creation time, status, exposed ports, and container name. The `-a` flag is important because stopped containers still exist on disk until explicitly removed — running `docker ps -a` reveals containers that exited due to errors or were manually stopped, which is essential for debugging. The `-f` flag allows you to filter for certain conditions, such as the status, helpful when you have multiple containers: `docker ps -f status=exited`, returns all containers that aren't running. The `-q` flag outputs only the container IDs, one per line, which makes it composable with other commands like `docker stop $(docker ps -q)` to stop all running containers at once.

**`docker exec`** runs a command inside an already-running container. This is how you inspect, debug, or interact with a container after it's started.

```bash
# Open an interactive shell in a running container
docker exec -it my-python bash

# Run a single command without an interactive session
docker exec my-python python --version

# Run a command as a specific user
docker exec -u root my-python apt update
```

The `-it` flags work identically to `docker run` — they give you an interactive terminal session. Without `-it`, the command runs and returns its output to your host shell, which is useful for quick checks like verifying a Python version or listing files. The `-u` flag lets you specify which user executes the command inside the container, overriding the `USER` directive set in the Dockerfile. This is occasionally necessary for administrative tasks like installing packages, even when your container normally runs as a non-root user.

**`docker logs`** retrieves the stdout and stderr output from a container. This is your primary debugging tool when a container isn't behaving as expected.

```bash
# View all logs from a container
docker logs my-python

# Follow logs in real time (like tail -f)
docker logs -f my-python

# Show only the last 50 lines
docker logs --tail 50 my-python

# Show logs with timestamps
docker logs -t my-python
```

The `-f` flag streams logs continuously, which is invaluable when monitoring a service during startup or under load — press `Ctrl+C` to stop following. The `--tail` flag limits the output to the most recent N lines, preventing your terminal from being flooded when a container has been running for days and has accumulated extensive logs. The `-t` flag prepends each log line with a timestamp, which helps correlate container events with system-level logs or other container logs. Remember that our `daemon.json` configuration from the installation section caps log files at 10MB × 3 files per container, so logs won't consume your Pi's storage indefinitely.

**`docker stop`** sends a `SIGTERM` signal to the container's main process, giving it a grace period to shut down cleanly before sending `SIGKILL`.

```bash
# Stop a container (10-second grace period by default)
docker stop my-python

# Stop with a custom timeout (30 seconds)
docker stop -t 30 my-python

# Stop all running containers
docker stop $(docker ps -q)
```

The default 10-second grace period gives the application time to finish active requests, close database connections, and flush buffers before the process is forcefully killed. The `-t` flag adjusts this timeout — Python applications that maintain persistent connections or process large datasets may benefit from a longer grace period to avoid data corruption. The `$(docker ps -q)` pattern uses command substitution to pass all running container IDs to `docker stop`, which is useful when shutting down the server for maintenance.

**`docker rm`** removes a stopped container from disk. Containers persist after stopping until explicitly removed.

```bash
# Remove a stopped container
docker rm my-python

# Force remove a running container (stops it first)
docker rm -f my-python

# Remove all stopped containers
docker container prune
```

The `-f` flag combines `docker stop` and `docker rm` into a single operation, which is convenient but bypasses the graceful shutdown period — use it only when you don't care about clean termination. The `docker container prune` command is a cleanup utility that removes all stopped containers at once, prompting for confirmation before proceeding. This is useful for periodic maintenance, especially after debugging sessions where you've created and stopped multiple test containers. Note that removing a container does not remove its associated volumes — volume data persists independently and must be cleaned up separately.

#### Publishing and Exposing Ports

When you run a container, its internal network is isolated from the host by default. The `-p` (publish) flag creates a mapping between a port on the host and a port inside the container, allowing external traffic to reach your containerized application. You'll notice that I'm using **200001** as the port example, the reason being this is a non-standard port that is part of an open range on my host server. For Python specific containers, I plan to use the **20001**-**20999** range, so it's easier for me to keep track of.

```bash
# Map host port 20001 to container port 8000 on any interface
docker run -d -p 20001:8000 --name my-python yourusername/python-dev:1.0

# Map to localhost only (recommended security practice)
docker run -d -p 127.0.0.1:20001:8000 --name my-python yourusername/python-dev:1.0

# Map multiple ports
docker run -d -p 127.0.0.1:20001:8000 -p 127.0.0.1:8443:8443 --name my-python yourusername/python-dev:1.0
```

The syntax is `-p [host_ip:]host_port:container_port`. When no host IP is specified, Docker binds to `0.0.0.0` (all interfaces), which means the port is accessible from any network the host is connected to. As we covered extensively in the security section, this bypasses UFW — so either use the `after.rules` approach to control access through UFW, or bind to `127.0.0.1` to restrict access to the host machine only.

The container port (right side) is determined by your application — Python web frameworks like Flask default to port 5000, FastAPI/Uvicorn to port 8000, and Jupyter to port 8888. The host port (left side) is your choice, though it must be unique across all running containers and must not conflict with existing services on the host. In our setup, SSH is on port 45000, so any other high port is fair game.

**Overriding Container Defaults**

The `docker run` command lets you override several defaults defined in the Dockerfile at runtime, without rebuilding the image. This is useful for adjusting behavior across different environments.

```bash
# Override the default command (CMD)
docker run -d --name my-python yourusername/python-dev:1.0 python /app/scripts/analysis.py

# Override environment variables
docker run -d --name my-python \
  -e PYTHONUNBUFFERED=1 \
  -e APP_ENV=production \
  yourusername/python-dev:1.0

# Override the working directory
docker run -d --name my-python -w /app/scripts yourusername/python-dev:1.0

# Override the entrypoint entirely
docker run -it --entrypoint bash yourusername/python-dev:1.0
```

The command at the end of `docker run` replaces the `CMD` instruction from the Dockerfile, letting you run different scripts or tools from the same image without rebuilding. The `-e` flag sets environment variables inside the container, which is the standard way to pass configuration like database URLs, API keys, or runtime modes — these override any `ENV` directives in the Dockerfile. The `-w` flag changes the working directory, overriding the `WORKDIR` instruction. The `--entrypoint` flag replaces the `ENTRYPOINT` instruction entirely, which is a powerful debugging tool — setting it to `bash` lets you drop into a shell to inspect the container's filesystem and troubleshoot startup issues.

#### Running Your First Python Container

With the commands understood, let's put them together to launch your Python container as a persistent service on the Raspberry Pi. This combines port publishing, volume mounts for data persistence, and the security configurations we set up earlier.

**Data Persistence with Volumes**

Containers are ephemeral by default — any data written inside the container is lost when the container is removed. For a persistent Python environment, you need volume mounts to store code, data, and logs on the host filesystem.

```bash
docker run -d --name my-python \
  -p 20001:8000 \
  -v /opt/python-dev/code:/app/code:rw \
  -v /opt/python-dev/data:/app/data:rw \
  -v /opt/python-dev/logs:/app/logs:rw \
  -e PYTHONUNBUFFERED=1 \
  yourusername/python-dev:1.0
```

Each `-v` flag follows the pattern `host_path:container_path:mode`. The host paths (`/opt/python-app/code`, `/opt/python-app/data`, `/opt/python-app/logs`) are directories on your Raspberry Pi's filesystem that persist across container restarts, rebuilds, and removals. The container paths (`/app/code`, `/app/data`, `/app/logs`) are where those directories appear inside the container. The `:rw` suffix grants read-write access (this is the default, but being explicit improves readability). You could use `:ro` for read-only mounts if your container only needs to read certain files.

The `code` volume holds your Python source files — you edit these on your client system through the VS Code Remote-SSH connection, and the container executes them. The `data` volume stores datasets, model outputs, or any files your scripts generate that you want to persist. The `logs` volume is where the application writes log files, and it's also the path Fail2Ban monitors (as configured in the security section). The `PYTHONUNBUFFERED=1` environment variable forces Python to write output directly to stdout/stderr without buffering, which ensures `docker logs` displays output in real time rather than in delayed chunks.

Before running the container, create the host directories:

```bash
sudo mkdir -p /opt/python-dev/{code,data,logs}
sudo chown -R $USER:$USER /opt/python-dev
```

The `mkdir -p` command creates the directory tree in one step, and the brace expansion `{code,data,logs}` creates all three subdirectories. Setting ownership to your user account ensures you can read and write files through VS Code without needing root permissions on the host side.

**Configuring UFW and Fail2Ban to Allow Python Access**

If you followed the `after.rules` approach from the installation section, your container port is blocked by default. To allow access to your Python container, add a UFW route rule:

```bash
# Allow access from your local network only
sudo ufw route allow proto tcp from 192.168.1.0/24 to any port 20001

# Verify the rule was added
sudo ufw status
```

This rule permits TCP traffic from your local network (`192.168.1.0/24` — adjust to match your subnet) to reach port 20001 on the host, which Docker forwards to port 8000 inside the container. Using a network range instead of `from any` ensures that only devices on your LAN can reach the Python service, while the internet at large remains blocked. If you bound the port to `127.0.0.1` instead, no UFW route rule is needed — the service is already restricted to localhost.

For Fail2Ban, the `[python-app]` jail we configured in the installation section is already watching `/opt/python-app/logs/access.log` with `chain = DOCKER-USER`. No additional configuration is needed here — just make sure your Python application writes its access logs to `/app/logs/access.log` inside the container, which maps to the host path Fail2Ban is monitoring.

**Accessing Your Python Server**

Once the container is running and the firewall rule is in place, you can access your Python application from your MacBook.

```bash
# Verify the container is running
docker ps

# Check the logs for any startup errors
docker logs my-python

# Test from the Raspberry Pi itself
curl http://localhost:8080

# Test from your MacBook (replace with your Pi's IP)
curl http://192.168.1.100:8080
```

If you're running a web framework like FastAPI, your browser can access the application at `http://<pi-ip>:8080`. If you're using Jupyter, you'd typically publish port 8888 instead and access the notebook interface through your browser. For non-web Python scripts, you can attach to the container's output with `docker logs -f my-python` to monitor execution, or use `docker exec -it my-python bash` to open a shell and run scripts interactively.

#### Container Management Basics

With the container running, you need to know how to keep it running reliably and how to shut it down cleanly when needed.

**Setting the Container to Auto-Restart**

For a persistent service that should survive reboots and recover from crashes, Docker provides restart policies.

```bash
# Start a new container with an auto-restart policy
docker run -d --name python-app \
  --restart unless-stopped \
  -p 8080:8000 \
  -v /opt/python-app/code:/app/code:rw \
  -v /opt/python-app/data:/app/data:rw \
  -v /opt/python-app/logs:/app/logs:rw \
  -e PYTHONUNBUFFERED=1 \
  python-app

# Update the restart policy on an existing container
docker update --restart unless-stopped python-app
```

Docker supports four restart policies: `no` (the default — never restart), `on-failure` (restart only if the container exits with a non-zero exit code), `always` (restart unconditionally, including after daemon restarts and reboots), and `unless-stopped` (like `always`, but doesn't restart containers that were explicitly stopped before the daemon restarted). The `unless-stopped` policy is the best choice for most services — it ensures your Python container comes back after a power outage or system reboot, but respects your decision if you manually stop it with `docker stop`. The `docker update` command modifies a container's configuration without recreating it, which means you can add a restart policy to an already-running container without any downtime.

Combined with the `systemctl enable docker` we configured during installation, this creates a complete auto-recovery chain: systemd starts the Docker daemon on boot, and the Docker daemon restarts containers with the `unless-stopped` policy.

**Shutting Down the Container**

When you need to stop the container — for image updates, configuration changes, or server maintenance — use the standard stop and remove workflow.

```bash
# Graceful stop (sends SIGTERM, waits 10s, then SIGKILL)
docker stop python-app

# Check that it stopped
docker ps -a | grep python-app

# Remove the container (volumes are preserved)
docker rm python-app
```

Stopping the container does not delete it — the container remains in a "stopped" state and retains its configuration, logs, and writable layer. This means you can inspect a stopped container's logs with `docker logs python-app` to diagnose why it stopped or crashed. When you're ready to fully clean up, `docker rm` removes the stopped container. Your volume-mounted data in `/opt/python-app/` is completely unaffected by both `stop` and `rm` — that data lives on the host filesystem and persists independently of the container's lifecycle. To bring the service back up, simply run a new container from the same image with the same volume mounts, and your data will be exactly where you left it.

For server maintenance scenarios where you need to stop everything:

```bash
# Stop all running containers gracefully
docker stop $(docker ps -q)

# Verify everything is stopped
docker ps

# After maintenance, restart containers with restart policies
# (Docker handles this automatically if the daemon restarts)
sudo systemctl restart docker
```

When the Docker daemon restarts, it automatically starts any containers with `always` or `unless-stopped` restart policies that were running before the daemon stopped. This means a simple `systemctl restart docker` after maintenance brings your entire container stack back online without manually restarting each container.