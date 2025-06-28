# Kubernetes Manifests for Webhook Client

This directory contains all the Kubernetes manifests needed to deploy the webhook client application in the `prognose` namespace.

## Files Overview

- `configmap.yaml` - Configuration for the application
- `secret.yaml` - Webhook secret (needs to be updated with your actual secret)
- `rbac.yaml` - ServiceAccount, ClusterRole, and ClusterRoleBinding for Kubernetes API access
- `deployment.yaml` - Main application deployment
- `service.yaml` - NodePort service to expose the application

## Deployment Instructions

1. **Update the secret**: Replace the base64 encoded webhook secret in `secret.yaml`, this secret is provided from the Web UI when the user create and configure a new webhook
   ```bash
   echo -n "your-actual-webhook-secret" | base64
   ```

2. **Update the image**: In `deployment.yaml`, replace `webhook-client:latest` with your actual Docker image

3. **Deploy in order**:
   ```bash
   kubectl apply -f configmap.yaml
   kubectl apply -f secret.yaml
   kubectl apply -f rbac.yaml
   kubectl apply -f deployment.yaml
   kubectl apply -f service.yaml
   ```

   Or deploy all at once:
   ```bash
   kubectl apply -f k8s/
   ```

## Configuration

### Environment Variables (ConfigMap)
- `K8S_NAMESPACE`: Target namespace for BareMetalHost operations
- `BMH_API_GROUP`: BareMetalHost API group (metal3.io)
- `BMH_API_VERSION`: BareMetalHost API version (v1alpha1)
- `BMH_PLURAL`: BareMetalHost plural name (baremetalhosts)
- `PROVISION_IMAGE`: Default image URL for provisioning
- `PROVISION_CHECKSUM`: Checksum URL for image verification
- `PROVISION_CHECKSUM_TYPE`: Checksum algorithm (sha256)
- `DEPROVISION_IMAGE`: Image for deprovisioning (empty for removal)
- `LOG_LEVEL`: Application log level
- `DISABLE_HEALTHZ_LOGS`: Disable healtz logs if true

### Secrets
- `WEBHOOK_SECRET`: Secret for webhook signature verification

## Health Checks

The application provides a health check endpoint at `/healthz` which is used for:
- Liveness probe (restarts unhealthy pods)
- Readiness probe (removes unhealthy pods from service)

## Accessing the Application

Once deployed, the application will be accessible at:
- Internal: `http://webhook-client-service.prognose.svc.cluster.local`
- Port-forwarding:
   ```bash
   kubectl port-forward -n prognose service/webhook-client-service 31720:80
   ```
   Then access the application at `http://localhost:31720`.

The main webhook endpoint is available at `/webhook` and accepts POST requests.
