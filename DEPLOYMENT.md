# GCP Compute Engine Deployment Guide

## Prerequisites

- GCP account with billing enabled
- `gcloud` CLI installed and authenticated
- Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

## Quick Deploy

### 1. Create a Compute Engine VM

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Create VM (e2-small is sufficient for low-medium traffic)
gcloud compute instances create spend-rail-api \
    --zone=us-central1-a \
    --machine-type=e2-small \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=20GB \
    --tags=http-server,https-server

# Allow HTTP traffic on port 8000
gcloud compute firewall-rules create allow-spend-rail \
    --allow=tcp:8000 \
    --target-tags=http-server \
    --description="Allow traffic to Spend-Rail API"
```

### 2. Connect to VM and Deploy

```bash
# SSH into the VM
gcloud compute ssh spend-rail-api --zone=us-central1-a

# Clone or copy your code (option 1: via git)
git clone YOUR_REPO_URL /opt/spend-rail
cd /opt/spend-rail

# Or copy files (option 2: via scp from local machine)
# gcloud compute scp --recurse ./spend-rail spend-rail-api:/opt/ --zone=us-central1-a

# Run deployment script
cd /opt/spend-rail
export GEMINI_API_KEY=your-api-key-here
./deploy.sh
```

### 3. Verify Deployment

```bash
# Check if container is running
docker ps

# Check API health
curl http://localhost:8000/health

# View logs
docker-compose logs -f
```

## Manual Deployment (Without Script)

```bash
# 1. Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Log out and back in, then:

# 2. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 3. Create .env file
cd /opt/spend-rail
cat > .env << EOF
GEMINI_API_KEY=your-api-key-here
APP_ENV=production
LOG_FORMAT=json
EOF

# 4. Build and run
docker-compose up -d --build
```

## Enable Auto-Start on Boot

```bash
# Copy systemd service
sudo cp spend-rail.service /etc/systemd/system/

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable spend-rail
sudo systemctl start spend-rail

# Check status
sudo systemctl status spend-rail
```

## Access Your API

- **API Docs**: `http://YOUR_VM_EXTERNAL_IP:8000/docs`
- **Health Check**: `http://YOUR_VM_EXTERNAL_IP:8000/health`
- **Categorize Image**: `POST http://YOUR_VM_EXTERNAL_IP:8000/api/v1/images/categorize`

Get your VM's external IP:
```bash
gcloud compute instances describe spend-rail-api --zone=us-central1-a --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

## Useful Commands

```bash
# View logs
docker-compose logs -f

# Restart service
docker-compose restart

# Stop service
docker-compose down

# Update application
git pull
docker-compose up -d --build

# Check resource usage
docker stats
```

## Security Recommendations

1. **Use HTTPS**: Set up a reverse proxy (nginx/caddy) with SSL
2. **Restrict CORS**: Update `CORS_ORIGINS` in `.env`
3. **Use Secret Manager**: Store `GEMINI_API_KEY` in GCP Secret Manager
4. **Enable IAP**: Use Identity-Aware Proxy for authentication
5. **Firewall**: Restrict port 8000 to specific IPs if needed
