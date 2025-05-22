### Introduction (COMPLETED)

- What is Docker and why it matters for development
- Docker's role in solving environment consistency problems
- Why Jupyter is an ideal example application
- Benefits of running Jupyter on Raspberry Pi with Docker
- Overview of what we'll accomplish in this guide

### Docker Concepts and Background Information

- Docker components (Engine, CLI, daemon)
  - What do you actually download on a headless server?
- Images vs containers
  - How is an image different from a container?
  - What is a base image?
  - What is a parent image?
  - What is a child image?
  - What is a layered image?
- Registries
  - What is a registry?
  - Why is this important?
  - How do you benefit?
- Docker compose
  - What is Docker Compose?
  - Why is this important?
  - We'll cover this in the advanced section of the guide
- Other considerations
  - Docker architecture
  - Docker on ARM architecture considerations
  - Docker's isolation mechanisms

### Configuring VS Code and Docker (COMPLETED)

- Essential VS Code extensions
- Configuring Docker integration

### Installing and Setting Up Docker on the Server

- Prerequisites
- Install using the `apt` repository
  - Upgrade Docker
  - Uninstalling Docker
- Configuring Docker to start on boot
- User permissions and security
- Configuring Docker to work with UFW and Fail2Ban
  - Things to consider
  - Configuring UFW
  - Configuring Fail2Ban
- Verifying the installation

### Dockerfiles and Images

- Introduction to Dockerfiles
  - The anatomy of a Dockerfile
  - Understanding the layers
  - Writing a Dockerfile
- Creating a Dockerfile for Jupyter
  - Image layers for Jupyter
  - Build, tag, and publish the image
  - Using the build cache
  - Using multi-stage builds
- Dockerfile best practices
- ARM compatibility considerations

### Running Containers

- Docker commands overview
  - `docker run`
  - `docker ps`
  - `docker exec`
  - `docker logs`
  - `docker stop`
  - `docker rm`
- Publishing and Exposing ports
  - Overriding container defaults
- Running your first Jupyter container
  - Data persistence with volumes
  - Configuring UFW and Fail2Ban to allow Jupyter access
  - Accessing your Jupyter server
- Container management basics
  - Setting container to auto-restart
  - Shutting down the container

### Container Management

- Monitoring Containers
  - Container resources
  - Security
  - Performance
- Managing Containers
  - Limiting container resources
  - Updating container configuration
  - Container security hardening
- Creating a backup strategy
  - Updating the Jupyter image
  - Container cleanup

### Advanced Docker

- Introduction to Docker Compose
  - What is orchestration?
  - Single-host orchestration
  - Multi-host orchestration
  - Docker Compose .yaml anatomy
  - Docker Compose commands
- Managing services with Docker Compose
  - Managing multi-container applications
  - Scaling and resource allocation
  - Backup strategy with Docker Compose
  - Upgrading services with Docker Compose
- Integrating with system monitoring

### Conclusion

- Summary of what we've accomplished
- Benefits of the Docker-based approach
- Practical applications of this setup
  - Future guides building on this