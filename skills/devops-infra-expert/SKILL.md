---
name: "devops-infra-expert"
description: "Comprehensive guide for DevOps, Infrastructure as Code, and Observability. Covers Docker, Kubernetes, CI/CD, Network Security, Monitoring, and Workspace Management."
---

# DevOps & Infrastructure Expert Guide

This skill provides the operational standards for deploying, scaling, and monitoring modern cloud-native applications.

## 🏗 Infrastructure as Code (IaC)
- **Terraform/Pulumi**: Use IaC for all cloud resources. Maintain state securely.
- **Docker**: Create optimized, multi-stage Dockerfiles. Use small base images (e.g., Alpine or Distroless).
- **Kubernetes (K8s)**: Use `kind` for local development. Define clear resource limits and readiness/liveness probes.

## 🚀 CI/CD & Deployment
- **GitHub Actions**: Automate linting, testing, and deployment. Use OIDC for secure cloud provider authentication.
- **Strategies**: Implement Blue/Green or Canary deployments for zero-downtime releases.
- **Environment Management**: Use separate environments (Dev, Staging, Prod). Keep configurations in environment variables or secret managers.

## 📡 Networking & Security
- **Network Design**: Implement VPCs, subnets, and security groups. Follow the principle of least privilege.
- **SSL/TLS**: Ensure all traffic is encrypted. Automate certificate renewal (e.g., Let's Encrypt).
- **Secrets**: Never commit secrets to Git. Use tools like `TruffleHog` to detect leaks.

## 📈 Observability & Monitoring
- **Logging**: Use structured logging (JSON). Centralize logs for easy searching and alerting.
- **Metrics**: Monitor key performance indicators (Latency, Error Rate, Throughput).
- **Tracing**: Implement distributed tracing (e.g., OpenTelemetry) to debug complex microservices.
- **Alerting**: Define actionable alerts with clear runbooks.

## 📦 Workspace Management
- **Nx**: Use for monorepo orchestration. Optimize build times using caching and affected commands.
- **Higiene**: Maintain a clean worktree. Automate the removal of temporary artifacts.

## 🔗 References
- [Terraform Documentation](https://developer.hashicorp.com/terraform/docs)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Nx Documentation](https://nx.dev/)
