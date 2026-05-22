# CodeCure — Google App Engine Deployment Guide

## Prerequisites
1. Google Cloud account (free tier available: $300 credit for 90 days)
2. Google Cloud SDK installed

---

## Step 1: Install Google Cloud SDK

### Windows (PowerShell as Administrator)
```powershell
(New-Object Net.WebClient).DownloadFile("https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe", "$env:TEMP\GoogleCloudSDKInstaller.exe")
& "$env:TEMP\GoogleCloudSDKInstaller.exe"
```

### Or download from:
https://cloud.google.com/sdk/docs/install

After installation, restart your terminal and run:
```bash
gcloud init
```

---

## Step 2: Login & Create Project

```bash
# Login to Google Cloud
gcloud auth login

# Create a new project (replace with your project name)
gcloud projects create codecure-demo-2025 --name="CodeCure Medical Inventory"

# Set the active project
gcloud config set project codecure-demo-2025
```

---

## Step 3: Enable Required APIs

```bash
# Enable App Engine Admin API
gcloud services enable appengine.googleapis.com

# Enable Cloud Build API (needed for deployment)
gcloud services enable cloudbuild.googleapis.com
```

---

## Step 4: Create App Engine App

```bash
# Create App Engine application (choose a region close to you)
gcloud app create --region=us-central
```

Available regions:
- `us-central` (Iowa) — Recommended
- `us-east1` (South Carolina)
- `europe-west` (Belgium)
- `asia-northeast1` (Tokyo)

---

## Step 5: Set Gemini API Key

### Option A: Quick (in app.yaml — for demo only)
Open `app.yaml` and add your Gemini API key:

```yaml
env_variables:
  SECRET_KEY: "codecure-secret-change-in-production"
  GEMINI_API_KEY: "AIzaSy..."  # <-- Add your key here
```

### Option B: Secure (recommended for production)
```bash
# Set environment variable on Google Cloud
gcloud app deploy --set-env-vars GEMINI_API_KEY=your-api-key-here
```

---

## Step 6: Deploy

```bash
# Navigate to your project folder
cd C:\Users\adity\OneDrive\Desktop\Codecure

# Deploy to Google App Engine
gcloud app deploy
```

When prompted:
- "Do you want to continue?" → Type `Y` and press Enter

Deployment takes ~2-4 minutes.

---

## Step 7: View Your Live App

```bash
# Open your app in browser
gcloud app browse
```

Your app will be live at:
```
https://codecure-demo-2025.uc.r.appspot.com
```

---

## Step 8: Update Your App

After making changes:
```bash
git add .
git commit -m "your changes"
gcloud app deploy
```

Each deployment creates a new version. You can rollback anytime:
```bash
# List all versions
gcloud app versions list

# Migrate traffic to a previous version
gcloud app versions migrate <VERSION_ID>
```

---

## Troubleshooting

### Error: "App Engine has not been initialized"
```bash
gcloud app create --region=us-central
```

### Error: "Billing not enabled"
Go to: https://console.cloud.google.com/billing
Link a billing account to your project.

### App not responding after deploy
```bash
# Check logs
gcloud app logs tail -s default

# Check status
gcloud app browse
```

### Reset deployment
```bash
# Delete all versions
gcloud app versions delete $(gcloud app versions list --format="value(version.id)" --filter="traffic_split=0")
```

---

## Cost Estimate

| Service | Free Tier | After Free Tier |
|---------|-----------|-----------------|
| App Engine (F1) | 28 hrs/day free | ~$0.05/hr |
| Storage (SQLite) | 5 GB free | ~$0.026/GB/month |
| Bandwidth | 1 GB/day free | ~$0.12/GB |

**Estimated cost for demo:** ~$0-5/month with light usage

---

## Login Credentials (Demo)
- **Admin:** username: `admin`, password: `1234`
- **Pharmacist:** username: `pharmacist`, password: `1234`
- **Doctor:** username: `doctor`, password: `1234`
