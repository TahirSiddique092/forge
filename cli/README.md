# Forge CI/CD CLI

Forge is a spec-driven CI/CD platform designed for modern, full-stack applications. It bridges the gap between your local terminal and production deployments by orchestrating builds, running CI steps in local/remote workers, and managing deployments to platforms like Railway and Vercel.

## Features

- **Spec-driven**: Define your build and deploy pipeline in a simple YAML or JSON spec.
- **Local Workers**: Run your CI jobs locally using Docker while still reporting status to the cloud.
- **Integrated Deployments**: Native support for Railway (backend) and Vercel (frontend).
- **GitHub Integration**: Securely authenticate with GitHub and link your repositories effortlessly.
- **Real-time Logs**: Stream build and deployment logs directly to your terminal.

## Installation

Forge requires Python 3.9 or higher.

```bash
pip install forge-cicd
```

## Quick Start

1. **Initialize your project**:
   ```bash
   forge init
   ```

2. **Login with GitHub**:
   ```bash
   forge login
   ```

3. **Link your repository**:
   ```bash
   forge link <your-project-id>
   ```

4. **Set your cloud credentials**:
   ```bash
   forge set-cred railway
   forge set-cred vercel
   ```

5. **Start a local worker** (optional, for CI execution):
   ```bash
   forge worker start
   ```

6. **Deploy**:
   ```bash
   forge deploy
   ```

## Documentation

For full documentation and advanced usage, visit [github.com/TahirSiddique092/forge](https://github.com/TahirSiddique092/forge).

## License

Forge is released under the MIT License.
