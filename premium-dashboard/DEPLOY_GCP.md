# Deploy to Google Cloud Run

This guide explains how to deploy the MP Intelligence Dashboard to Google Cloud Run.

## Prerequisites
1.  **Google Cloud Project**: Have a project ID ready.
2.  **GCP CLI Installed**: Run `gcloud auth login` and `gcloud config set project [YOUR_PROJECT_ID]`.
3.  **Artifact Registry**: Create a repository for Docker images if you haven't.

## Automated Deployment (Cloud Build)
We have provided a `cloud-build.yaml` to handle the build and deploy process automatically.

```bash
gcloud builds submit --config cloud-build.yaml
```

## Manual Deployment steps
If you prefer manual steps:

1. **Build and Tag**:
   ```bash
   docker build -t gcr.io/[PROJECT_ID]/mp-intelligence .
   ```

2. **Push to GCR**:
   ```bash
   docker push gcr.io/[PROJECT_ID]/mp-intelligence
   ```

3. **Deploy to Cloud Run**:
   ```bash
   gcloud run deploy mp-intelligence \
     --image gcr.io/[PROJECT_ID]/mp-intelligence \
     --platform managed \
     --region europe-west4 \
     --allow-unauthenticated
   ```

## Cloud Run Configuration
- **Port**: 8080 (handled dynamically by the app)
- **Memory**: 512Mi / 1Gi recommended
- **Environment Variables**: None required for basic setup.
