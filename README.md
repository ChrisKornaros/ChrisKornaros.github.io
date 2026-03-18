### Dockerfiles and Images

Now that Docker is installed, configured, and integrated with your server's security stack, it's time to learn how to actually build something with it. Up to this point, the only image we've pulled is `hello-world` — a tiny test image that confirms Docker is working. In this section, we'll move from verifying installations to creating custom images tailored to your specific needs.

A Dockerfile is where every custom Docker image begins. It's a plain text file that contains a series of instructions Docker uses to assemble an image, layer by layer. Understanding how Dockerfiles work — and how to write them well — is the single most important skill for working with Docker effectively. Everything else in Docker (running containers, composing services, orchestrating deployments) depends on having well-constructed images, and those images start with Dockerfiles.

We'll begin with the general anatomy of a Dockerfile and how the layer system works, then move into writing a real Dockerfile for our Python environment on the Raspberry Pi. Along the way, we'll cover how to build, tag, and publish images, how to take advantage of Docker's build cache for faster iterations, and how multi-stage builds can keep your final images lean. We'll close with best practices and ARM-specific considerations that are particularly relevant for our Raspberry Pi server.

#### Introduction to Dockerfiles

A Dockerfile is a text file — literally named `Dockerfile` with no file extension — that lives in your project directory and tells Docker exactly how to construct an image. Each line in a Dockerfile represents an instruction, and Docker processes these instructions sequentially from top to bottom. The result is a Docker image: a portable, self-contained snapshot of an application and its environment that can be used to spin up containers anywhere Docker runs.

The important thing to internalize early is that a Dockerfile is *declarative infrastructure*. Rather than SSHing into a server and manually installing packages, configuring paths, and copying files (the way we set up our Raspberry Pi in the earlier sections of this guide), a Dockerfile captures all of those steps in a reproducible, version-controllable format. If your container breaks or your server fails, you can rebuild the exact same environment from the Dockerfile alone. This is a fundamental shift in how you think about environment setup — instead of a series of manual steps you need to remember, your environment is defined as code.

**The Anatomy of a Dockerfile**

Every Dockerfile follows the same general structure, with instructions that build upon each other to create a complete application environment. Here are the core instructions you'll encounter most frequently:

`FROM` declares the base image your image will be built upon. Every Dockerfile must begin with a `FROM` instruction (or an `ARG` that precedes it for parameterized base images). The base image provides the foundational filesystem and tools your application will inherit. For example, `FROM python:3.11-slim` starts with a Debian-based Linux environment that already has Python 3.11 installed. You can think of `FROM` as choosing the starting point for your environment — rather than installing an operating system and Python from scratch, you inherit a pre-built foundation maintained by the official Python team.

`WORKDIR` sets the working directory inside the container for all subsequent instructions. If the directory doesn't exist, Docker creates it. This is analogous to `cd`-ing into a directory on your Raspberry Pi before running commands, except `WORKDIR` creates the directory if it's not already there. Setting a `WORKDIR` early keeps your Dockerfile organized and avoids scattering files across the container's filesystem.

`COPY` transfers files from your local machine (the build context) into the image. This is how your application code, configuration files, and dependency manifests get into the container. `COPY requirements.txt .` copies the `requirements.txt` file from your project directory into the current `WORKDIR` inside the image.

`RUN` executes a command inside the image during the build process and commits the result as a new layer. This is where you install packages, compile code, create directories, or perform any setup that should be baked into the image. Each `RUN` instruction creates a new layer, which has implications for image size and build caching that we'll explore shortly.

`EXPOSE` documents which port the container will listen on at runtime. This is purely informational — it doesn't actually publish the port or create any network rules. Think of it as metadata that tells anyone reading the Dockerfile (or tools like Docker Compose) which ports the application expects to use. The actual port publishing happens at runtime with the `-p` flag.

`CMD` specifies the default command that runs when a container starts from this image. Unlike `RUN`, which executes during the build, `CMD` executes at container startup. A Dockerfile should have exactly one `CMD` instruction. If you provide multiple, only the last one takes effect. This is the instruction that actually starts your application — for a Python container, this might launch a script, start a Jupyter server, or open an interactive Python shell.

There are additional instructions like `ENV` (for setting environment variables), `ARG` (for build-time variables), `ENTRYPOINT` (for configuring the container to run as an executable), and `VOLUME` (for declaring mount points), but the six above form the core vocabulary you'll use in nearly every Dockerfile.

**Understanding the Layers**

One of Docker's most powerful and most misunderstood features is its layer-based architecture. Every instruction in a Dockerfile that modifies the filesystem — primarily `FROM`, `COPY`, `RUN`, and `ADD` — creates a new *layer* in the image. These layers are stacked on top of each other using a union filesystem, producing the final image you see when you run `docker images`.

To understand why this matters, think about how we set up the Raspberry Pi server earlier in this guide. If you installed a package with `apt install`, your entire filesystem changed. If you later uninstalled that package, the files were removed, but the disk space was essentially reclaimed by the filesystem. Docker layers work differently. Each layer is an immutable snapshot of filesystem changes made by that instruction. If you install a 200MB package in one `RUN` layer and then remove it in the next `RUN` layer, your image still contains both layers — the 200MB is baked into the first layer permanently. The removal in the second layer only *masks* those files; it doesn't reclaim the space.

This has two practical consequences. First, you should combine related operations into a single `RUN` instruction wherever possible. Installing build dependencies, compiling your application, and cleaning up temporary files should all happen in one `RUN` statement connected with `&&` operators. Second, the order of your instructions matters significantly for build performance. Docker caches each layer, and when rebuilding an image, it reuses cached layers until it encounters an instruction whose inputs have changed. Everything after that changed instruction must be rebuilt from scratch. We'll revisit this caching behavior in detail when we discuss the build cache.

Each layer is identified by a SHA256 hash of its contents. When Docker pulls an image, it only downloads layers it doesn't already have locally. This means that if you have two images that share the same base (say, both use `python:3.11-slim`), the base layers are stored only once on disk and shared between both images. This deduplication makes Docker extremely storage-efficient when running multiple containers based on related images — a real advantage on the Raspberry Pi where storage is limited.

**Writing a Dockerfile**

Let's put these concepts together by examining what a simple Dockerfile looks like. Before we write our actual Python Dockerfile (which we'll do in the next subsection), here's a minimal example that illustrates the structure:

```dockerfile
# Every Dockerfile starts with a base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy dependency manifest first (for cache optimization)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Document which port the application uses
EXPOSE 8000

# Define the default command to run when the container starts
CMD ["python", "app.py"]
```

There are several deliberate choices in this structure worth noting. The `FROM` instruction selects `python:3.11-slim` rather than the full `python:3.11` image, which reduces our starting image size from roughly 900MB down to around 120–150MB — a significant difference on a Raspberry Pi with limited storage. The `WORKDIR /app` creates a clean, dedicated directory for our application rather than dumping files into the container's root filesystem. The `COPY requirements.txt .` appears before `COPY . .` intentionally — this is a cache optimization pattern where the dependency manifest (which changes infrequently) is copied and installed before the application code (which changes frequently). If you only modify your Python code between builds, Docker can reuse the cached layer for `pip install` and skip re-downloading all your dependencies. The `--no-cache-dir` flag on `pip install` prevents pip from storing downloaded package archives inside the image, keeping the layer smaller. The `CMD` uses the *exec form* (JSON array syntax) rather than the *shell form* (`CMD python app.py`) — the exec form runs the process directly without wrapping it in a shell, which ensures proper signal handling when Docker needs to stop or restart the container.

This structure — base image, working directory, dependencies, application code, runtime configuration — is the pattern you'll follow for virtually every Dockerfile you write, regardless of the application language or framework.

#### Creating a Dockerfile for Python

Now let's build the actual Dockerfile we'll use for our persistent Python container on the Raspberry Pi. This container needs to serve as a general-purpose Python development environment that runs 24/7 on your server, accessible from your MacBook for development while leveraging the Pi's compute resources and persistent storage.

**Image Layers for Python**

Before writing the Dockerfile, let's think through what our image needs to contain, layer by layer. Understanding what each layer contributes helps you make informed decisions about image construction.

The foundation is the base image layer, provided by `FROM python:3.11-slim`. This layer contains a minimal Debian Linux filesystem plus a complete Python 3.11 installation — the interpreter, the standard library, `pip`, and essential C libraries that Python depends on. The slim variant excludes build tools like `gcc` and `make`, development headers, and extra system utilities that aren't needed at runtime. On ARM64 (our Raspberry Pi's architecture), this base layer is approximately 120–150MB.

On top of that, we add a system dependency layer. Some Python packages — particularly scientific computing libraries like `numpy`, `pandas`, and `scipy` — include C extensions that require compilation. Since we're using the slim base image (which lacks build tools), we need to install those tools temporarily. This layer uses `apt-get` to install compilers and development headers.

Next comes the Python dependency layer. This is where `pip install` runs against your `requirements.txt` file, downloading and installing all the Python packages your projects need. For data engineering work, this might include pandas, numpy, requests, sqlalchemy, and similar libraries. This layer can be substantial in size depending on your dependency list.

Finally, we add the application layer, which contains your actual project code, configuration files, and any scripts you want available inside the container. This layer changes most frequently during development, which is why it appears last — maximizing cache reuse for the heavier dependency layers above it.

**Build, Tag, and Publish the Image**

Here's the Dockerfile we'll use for our Python development environment. Create a project directory on your Raspberry Pi server and save this as `Dockerfile`:

```dockerfile
# Use the official Python slim image as our base
# The slim variant balances size (~150MB) with compatibility
FROM python:3.11-slim

# Set environment variables for Python behavior inside the container
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc bytecode files to disk,
#   keeping the container filesystem cleaner
# PYTHONUNBUFFERED: Forces stdout and stderr to be unbuffered, ensuring log output
#   appears immediately in `docker logs` rather than being held in a buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory for all subsequent instructions
WORKDIR /app

# Install system-level build dependencies needed for compiling Python packages
# with C extensions (numpy, pandas, etc.), then clean up apt caches to reduce
# the layer size. Combining install and cleanup in one RUN avoids persisting
# the apt cache in a separate layer.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the dependency manifest first, separately from application code.
# This ensures Docker can cache the expensive pip install layer and only
# re-run it when requirements.txt actually changes.
COPY requirements.txt .

# Install Python dependencies without caching downloaded archives.
# The --no-cache-dir flag prevents pip from storing .whl and .tar.gz files
# inside the image, which would bloat the layer with no runtime benefit.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container.
# This layer changes most frequently, so placing it last maximizes
# cache reuse for all preceding layers.
COPY . .

# Document the port our Python application will listen on.
# This is informational only — actual publishing happens with -p at runtime.
EXPOSE 8000

# Default command: start an interactive Python shell.
# This can be overridden at runtime with docker run ... python my_script.py
CMD ["python"]
```

Let's walk through the build, tag, and publish workflow. From the directory containing your Dockerfile on the Raspberry Pi:

```bash
# Build the image and tag it with a name and version
docker build -t python-dev:1.0 .
```

The `-t` flag assigns a tag to the image in the format `name:version`. The `.` at the end specifies the *build context* — the directory Docker will use as the root for `COPY` instructions. Docker sends this entire directory to the daemon, so keep it clean (we'll discuss `.dockerignore` in the best practices section). The build process executes each Dockerfile instruction sequentially, creating a layer for each filesystem-modifying step. You'll see output for each step, and the final line will confirm the image was successfully built and tagged.

```bash
# Verify the image was created
docker images python-dev
```

This command lists all images matching the `python-dev` name, showing the tag, image ID, creation time, and size. You should see your `python-dev:1.0` image listed.

```bash
# Tag the image for Docker Hub (or your private registry)
docker tag python-dev:1.0 yourusername/python-dev:1.0

# Push to Docker Hub
docker login
docker push yourusername/python-dev:1.0
```

The `docker tag` command creates an additional reference to the same image with a registry-qualified name. Docker Hub expects the format `username/repository:tag`. The `docker push` command uploads your image layers to the registry. Docker is smart about this — it only uploads layers that aren't already present in the registry, which makes subsequent pushes much faster than the initial one.

Publishing to a registry is optional for our setup (since we're building and running on the same Raspberry Pi), but it's a good practice to understand. If your Pi's storage fails, having your image on Docker Hub means you can pull and redeploy on a replacement device without rebuilding from scratch.

**Using the Build Cache**

Docker's build cache is one of its most powerful features for development productivity, and understanding how it works will save you significant time during iterative development. When Docker builds an image, it checks each instruction against its cache of previously built layers. If the instruction and all of its inputs (files being copied, commands being run) are identical to a previous build, Docker reuses the cached layer instead of executing the instruction again.

The cache follows a strict sequential invalidation rule: once Docker encounters an instruction that can't be served from cache, *every subsequent instruction must also be rebuilt*. This is why the order of instructions in your Dockerfile matters so much. Consider the cache behavior of our Python Dockerfile:

```bash
# First build — everything is built fresh
docker build -t python-dev:1.0 .

# Second build after modifying only app.py — fast!
# Layers 1-5 (FROM through pip install) are cached
# Only the final COPY . . layer is rebuilt
docker build -t python-dev:1.0 .
```

If we had structured our Dockerfile differently — copying all files first and then running `pip install` — every code change would trigger a full dependency reinstall. With our current structure, modifying Python source code only triggers a rebuild of the final `COPY . .` layer, because `requirements.txt` hasn't changed and the `pip install` layer remains cached. On a Raspberry Pi, where `pip install` for packages like `numpy` or `pandas` can take several minutes due to ARM compilation, this optimization is not just a convenience — it's a practical necessity.

You can inspect the cache behavior during a build by watching the output. Cached layers will display `CACHED` next to the step number, while rebuilt layers will show the full execution output. If you need to force a clean build and bypass the cache entirely (useful when debugging dependency issues), use the `--no-cache` flag:

```bash
# Force rebuild all layers, ignoring the cache
docker build --no-cache -t python-dev:1.0 .
```

**Using Multi-Stage Builds**

Multi-stage builds are an advanced Dockerfile technique that dramatically reduces final image size by separating the build environment from the runtime environment. The core idea is straightforward: some things you need during the build process (compilers, development headers, build tools) are not needed when actually running the application. Multi-stage builds let you use one stage to build and compile, then copy only the results into a clean, minimal final stage.

Here's how our Python Dockerfile would look as a multi-stage build:

```dockerfile
# ---- Stage 1: Builder ----
# This stage installs build tools and compiles Python packages.
# It will NOT be part of the final image.
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies needed for compiling C extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install packages into a specific target directory so we can
# copy just the installed packages (not the build tools) later.
# The --prefix flag tells pip where to install everything.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: Runtime ----
# This stage starts fresh from the slim base — no build tools.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy ONLY the installed Python packages from the builder stage.
# The build tools (gcc, build-essential, etc.) are left behind entirely.
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

EXPOSE 8000

CMD ["python"]
```

The key mechanism here is the `AS builder` alias on the first `FROM` instruction and the `COPY --from=builder` in the second stage. The first stage does all the heavy lifting — installing `gcc`, `build-essential`, and compiling any C extensions your Python packages require. The `--prefix=/install` flag on `pip install` directs all installed packages into a dedicated directory rather than the system-wide Python path. The second stage starts from a completely fresh `python:3.11-slim` base (no build tools whatsoever) and uses `COPY --from=builder /install /usr/local` to pull in only the compiled Python packages from the first stage. The build tools, development headers, apt caches, and everything else from the first stage are discarded entirely.

The size savings can be substantial. The build tools and development headers installed in the first stage can add 200-400MB to an image. With a multi-stage build, the final image contains only the Python runtime and your compiled packages — no compilers, no header files, no apt cache. On a Raspberry Pi with limited storage, this reduction from roughly 500-600MB down to 200-300MB (depending on your Python dependencies) is meaningful, especially when you start running multiple containers.

The tradeoff is that multi-stage builds add complexity to your Dockerfile and can make debugging build issues slightly harder, since you can't easily inspect the builder stage's filesystem after the build completes. For our Python development environment, I recommend starting with the single-stage Dockerfile we wrote above and transitioning to a multi-stage build once your `requirements.txt` stabilizes and you're optimizing for production use. Both approaches are valid, and understanding when to use each is more valuable than defaulting to one style.

#### Dockerfile Best Practices

Writing a functional Dockerfile is one thing; writing a *well-constructed* Dockerfile is another. These best practices will help you write Dockerfiles that build faster, produce smaller images, and are easier to maintain — all of which matter on a resource-constrained platform like the Raspberry Pi.

**Use a `.dockerignore` file.** When you run `docker build`, Docker sends the entire build context directory to the daemon. Without a `.dockerignore` file, this includes everything: Git history, editor configuration, local virtual environments, data files, and anything else in the directory. A `.dockerignore` works exactly like `.gitignore` — it specifies patterns of files and directories to exclude from the build context. For our Python project, a sensible `.dockerignore` looks like this:

```
.git
.gitignore
__pycache__
*.pyc
.env
venv/
.vscode/
*.md
data/
logs/
```

This keeps the build context small and prevents sensitive files (like `.env` containing credentials) from being accidentally baked into the image. It also ensures that local development artifacts like `__pycache__` directories and virtual environments don't end up inside your container.

**Minimize the number of layers.** Each `RUN` instruction creates a new layer, and layers have overhead. Combine related commands into single `RUN` instructions using `&&` to chain them. The most common example is combining `apt-get update` with `apt-get install` and the subsequent cleanup, as we did in our Dockerfile above. Running `apt-get update` in a separate `RUN` from `apt-get install` can also cause caching issues — if the `apt-get update` layer is cached but package repositories have changed, the subsequent `install` might fail or install outdated packages.

**Use specific image tags, not `latest`.** Always pin your base image to a specific version tag like `python:3.11-slim` rather than `python:latest`. The `latest` tag is a moving target — it points to whatever the most recent version happens to be, which means your builds could break unexpectedly when a new Python version is released. Pinning to a specific version ensures your builds are reproducible. When you want to upgrade, change the tag deliberately and test the new version.

**Run containers as non-root when possible.** By default, processes inside a Docker container run as root. While container namespaces provide isolation from the host, running as root inside the container is still a security concern — if an attacker escapes the container isolation, they'd have root privileges on the host. Adding a non-root user to your Dockerfile is straightforward:

```dockerfile
# Create a non-root user for running the application
RUN useradd --create-home appuser
USER appuser
```

Place these instructions after your `RUN` commands that require root (like `apt-get install`) but before `CMD`, so the application runs with reduced privileges. For our development container, running as root is acceptable during the learning phase, but adopting this practice early builds good security habits.

**Keep your images lean.** Beyond the multi-stage build approach discussed above, several smaller practices contribute to leaner images. Always include `--no-install-recommends` with `apt-get install` to avoid pulling in suggested packages you don't need. Clean up apt caches with `rm -rf /var/lib/apt/lists/*` in the same `RUN` instruction as your install. Use `--no-cache-dir` with `pip install` to prevent pip from caching downloaded package files. These practices compound — individually they might save 20-50MB each, but together they can reduce your image size by several hundred megabytes.

**Order instructions from least to most frequently changing.** This maximizes build cache effectiveness. Base image selection and system package installation rarely change, so they belong at the top. Python dependency installation changes occasionally (when you add or update a package), so it belongs in the middle. Application code changes frequently during development, so it belongs at the bottom. This ordering ensures that a typical code change only rebuilds the final layer rather than triggering a full dependency reinstall.

#### ARM Compatibility Considerations

Running Docker on a Raspberry Pi means running on ARM64 (aarch64) architecture, which introduces compatibility considerations that don't exist on standard x86_64 development machines. Understanding these considerations will save you from confusing build failures and runtime errors.

The most fundamental consideration is that Docker images are architecture-specific. An image built on your MacBook (which uses Apple Silicon, also ARM64, or Intel x86_64 depending on your model) may or may not run on your Raspberry Pi, and vice versa. The official Python images we're using are *multi-architecture* images — Docker Hub hosts variants for both x86_64 and ARM64 under the same tag, and Docker automatically pulls the correct variant for your platform. When you run `docker pull python:3.11-slim` on your Raspberry Pi, Docker detects the ARM64 architecture and downloads the ARM64 variant. This happens transparently, which is why we haven't had to specify architecture explicitly in our Dockerfile.

However, not all images on Docker Hub offer ARM64 support. When evaluating third-party or community-maintained images, always check the "OS/ARCH" column on the image's Docker Hub page to confirm ARM64 compatibility. If an image only provides x86_64 builds, you have two options: find an alternative image that supports ARM64, or build a custom image from an ARM-compatible base. Attempting to run an x86_64 image on ARM64 will result in an `exec format error` — the container will fail to start because the binaries inside are compiled for the wrong architecture.

Compilation times on ARM processors are generally longer than on x86_64 for CPU-intensive tasks like compiling C extensions. Python packages such as `numpy`, `pandas`, `scipy`, and `cryptography` include C code that must be compiled during installation. On a Raspberry Pi 4 with 8GB RAM, installing `numpy` from source can take 5-10 minutes compared to under a minute on a modern x86_64 machine. This makes the build cache optimization we discussed earlier even more critical — you really don't want to recompile `numpy` every time you change a line of application code. Additionally, using pre-compiled wheels (binary packages) where available can dramatically reduce build times. The `pip install` command will automatically prefer wheels over source distributions when a compatible wheel exists for your platform.

If you're developing on an Apple Silicon MacBook (M1, M2, M3, or M4), your local machine also runs ARM64, which means images built locally will generally work on your Raspberry Pi without architecture issues. However, if your MacBook is an older Intel model (x86_64), any images you build locally will not run on the Pi. In that case, you can use Docker's `buildx` tool to cross-compile images for ARM64 from your x86_64 machine:

```bash
# Create a multi-architecture builder instance
docker buildx create --name pibuilder --use

# Build for ARM64 specifically, even from an x86_64 host
docker buildx build --platform linux/arm64 -t python-dev:1.0 --load .
```

The `docker buildx create` command sets up a builder instance that supports multi-platform builds through QEMU emulation. The `--platform linux/arm64` flag tells Docker to build the image targeting the ARM64 architecture regardless of the host machine's architecture. The `--load` flag imports the resulting image into your local Docker image store. Note that cross-compilation through QEMU is significantly slower than native builds — a build that takes 5 minutes natively on the Pi might take 15-20 minutes through emulation. For this reason, building directly on the Raspberry Pi is usually the more practical approach for our setup, and it guarantees the resulting image is natively compatible.

When writing Dockerfiles intended for ARM deployment, stick to well-maintained official images as your base (like `python:3.11-slim`, `ubuntu`, or `alpine`) — these consistently provide ARM64 variants. Be cautious with smaller community images and always verify architecture support before committing to a base image in your Dockerfile.