# Server Provisioning Webhook

A Python FastAPI webhook service for handling server provisioning events. This service manages Kubernetes BareMetalHost resources without network configuration.

This webhook has been developed to serve events produced by the [Cloud Resource Reservation System](https://github.com/giovannimirarchi420/cloud-resource-reservation), a comprehensive platform for managing cloud resource reservations with authentication, monitoring, and multi-service orchestration.

## Overview

This webhook receives server reservation events and provisions/deprovisions BareMetalHost resources in a Kubernetes cluster using the Metal³ operator.

## Features

- **Server Provisioning**: Automatically provisions BareMetalHost resources
- **Server Deprovisioning**: Handles resource cleanup and deprovisioning
- **Security**: HMAC signature verification for webhook security
- **Monitoring**: Health checks and comprehensive logging
- **Kubernetes Integration**: Native Kubernetes API integration

## Key Differences from Original

This service is focused only on server provisioning and does **NOT** include:
- Network switch configuration
- VLAN management
- Port assignment

## Configuration

### Environment Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `PORT` | integer | No | `5001` | HTTP server listening port |
| `LOG_LEVEL` | string | No | `INFO` | Logging level |
| `K8S_NAMESPACE` | string | No | `default` | Target namespace for BareMetalHost resources |
| `PROVISION_IMAGE` | string | Yes | None | Image URL for provisioning operations |
| `DEPROVISION_IMAGE` | string | No | None | Image URL for deprovisioning |
| `WEBHOOK_SECRET` | string | No | None | Shared secret for HMAC verification |

## API Endpoints

### POST /webhook
Processes reservation lifecycle events and manages corresponding Kubernetes resources.

### GET /healthz
Health check endpoint for monitoring.

## Deployment

See the `k8s/` directory for Kubernetes deployment manifests.

## Usage

```bash
# Start the service
python -m app.main

# Send a webhook event
curl -X POST http://localhost:5001/webhook \
  -H "Content-Type: application/json" \
  -d '{"eventType": "EVENT_START", "resourceName": "bmh-node-001", ...}'
```
