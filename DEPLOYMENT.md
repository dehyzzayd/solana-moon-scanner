# 🚀 Deployment Guide - Solana Moon Scanner

Complete guide for deploying the Solana Moon Scanner to production environments.

## 📋 Table of Contents
- [VPS Deployment](#vps-deployment)
- [AWS EC2 Deployment](#aws-ec2-deployment)
- [Docker Swarm](#docker-swarm)
- [Kubernetes](#kubernetes)
- [Monitoring Setup](#monitoring-setup)
- [Production Checklist](#production-checklist)

---

## 🖥️ VPS Deployment

### Prerequisites
- Ubuntu 20.04+ or Debian 11+
- 2GB+ RAM
- 20GB+ storage
- Python 3.10+
- Docker (optional)

### Step 1: Prepare Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.10+
sudo apt install python3.10 python3.10-venv python3-pip -y

# Install Docker (optional)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### Step 2: Clone and Setup

```bash
# Create application directory
sudo mkdir -p /opt/moon-scanner
sudo chown $USER:$USER /opt/moon-scanner

# Clone repository
cd /opt/moon-scanner
git clone https://github.com/yourusername/solana-moon-scanner.git .

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Environment

```bash
# Copy and edit configuration
cp config.example.env .env
nano .env

# Set required variables
# - QUICKNODE_RPC_URL or HELIUS_RPC_URL
# - Alert channel credentials
# - Adjust thresholds as needed
```

### Step 4: Setup Systemd Service

```bash
# Create systemd service file
sudo nano /etc/systemd/system/moon-scanner.service
```

**Service file content:**
```ini
[Unit]
Description=Solana Moon Scanner
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/opt/moon-scanner
Environment="PATH=/opt/moon-scanner/venv/bin"
ExecStart=/opt/moon-scanner/venv/bin/python -m src.cli monitor
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# Reload systemd, enable and start service
sudo systemctl daemon-reload
sudo systemctl enable moon-scanner
sudo systemctl start moon-scanner

# Check status
sudo systemctl status moon-scanner

# View logs
sudo journalctl -u moon-scanner -f
```

### Step 5: Setup Log Rotation

```bash
# Create logrotate config
sudo nano /etc/logrotate.d/moon-scanner
```

**Logrotate config:**
```
/opt/moon-scanner/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
    create 0640 your-username your-username
}
```

---

## ☁️ AWS EC2 Deployment

### Step 1: Launch EC2 Instance

**Recommended Specs:**
- Instance Type: `t3.medium` (2 vCPU, 4GB RAM)
- AMI: Ubuntu Server 22.04 LTS
- Storage: 30GB gp3 SSD
- Security Group:
  - Inbound: SSH (22) from your IP
  - Inbound: Prometheus (9090) from monitoring subnet (optional)
  - Outbound: All traffic

### Step 2: Connect and Setup

```bash
# Connect to instance
ssh -i your-key.pem ubuntu@your-instance-ip

# Follow VPS deployment steps above
```

### Step 3: Setup CloudWatch Logs (Optional)

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Configure CloudWatch
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard

# Start agent
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json
```

### Step 4: Setup Auto-Scaling (Optional)

Create an AMI from your configured instance and set up an Auto Scaling group with CloudWatch alarms for CPU/memory usage.

---

## 🐳 Docker Swarm Deployment

### Step 1: Initialize Swarm

```bash
# On manager node
docker swarm init

# Add worker nodes (run on worker)
docker swarm join --token <token> <manager-ip>:2377
```

### Step 2: Create Docker Secrets

```bash
# Create secrets for sensitive data
echo "your-helius-key" | docker secret create helius_api_key -
echo "your-telegram-token" | docker secret create telegram_token -
echo "your-discord-webhook" | docker secret create discord_webhook -
```

### Step 3: Deploy Stack

```bash
# Create docker-compose.swarm.yml
cat > docker-compose.swarm.yml << 'EOF'
version: '3.8'

services:
  moon-scanner:
    image: your-registry/solana-moon-scanner:latest
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '1'
          memory: 2G
    secrets:
      - helius_api_key
      - telegram_token
      - discord_webhook
    environment:
      - HELIUS_API_KEY_FILE=/run/secrets/helius_api_key
      - TELEGRAM_BOT_TOKEN_FILE=/run/secrets/telegram_token
      - DISCORD_WEBHOOK_URL_FILE=/run/secrets/discord_webhook
    volumes:
      - scanner-logs:/app/logs
    networks:
      - scanner-net

volumes:
  scanner-logs:

networks:
  scanner-net:
    driver: overlay

secrets:
  helius_api_key:
    external: true
  telegram_token:
    external: true
  discord_webhook:
    external: true
EOF

# Deploy stack
docker stack deploy -c docker-compose.swarm.yml moon-scanner

# Check status
docker stack services moon-scanner
docker service logs moon-scanner_moon-scanner -f
```

---

## ☸️ Kubernetes Deployment

### Step 1: Create Namespace

```bash
kubectl create namespace moon-scanner
```

### Step 2: Create Secrets

```bash
kubectl create secret generic moon-scanner-secrets \
  --from-literal=helius-api-key='your-key' \
  --from-literal=telegram-token='your-token' \
  --from-literal=discord-webhook='your-webhook' \
  -n moon-scanner
```

### Step 3: Create Deployment

```yaml
# moon-scanner-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: moon-scanner
  namespace: moon-scanner
spec:
  replicas: 2
  selector:
    matchLabels:
      app: moon-scanner
  template:
    metadata:
      labels:
        app: moon-scanner
    spec:
      containers:
      - name: moon-scanner
        image: your-registry/solana-moon-scanner:latest
        env:
        - name: HELIUS_API_KEY
          valueFrom:
            secretKeyRef:
              name: moon-scanner-secrets
              key: helius-api-key
        - name: TELEGRAM_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: moon-scanner-secrets
              key: telegram-token
        - name: DISCORD_WEBHOOK_URL
          valueFrom:
            secretKeyRef:
              name: moon-scanner-secrets
              key: discord-webhook
        resources:
          limits:
            cpu: "1"
            memory: "2Gi"
          requests:
            cpu: "500m"
            memory: "512Mi"
        volumeMounts:
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: logs
        persistentVolumeClaim:
          claimName: moon-scanner-logs
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: moon-scanner-logs
  namespace: moon-scanner
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: moon-scanner-metrics
  namespace: moon-scanner
spec:
  selector:
    app: moon-scanner
  ports:
  - port: 9090
    targetPort: 9090
  type: ClusterIP
```

```bash
# Apply deployment
kubectl apply -f moon-scanner-deployment.yaml

# Check status
kubectl get pods -n moon-scanner
kubectl logs -f deployment/moon-scanner -n moon-scanner
```

---

## 📊 Monitoring Setup

### Prometheus + Grafana

```bash
# Using docker-compose
docker-compose --profile monitoring up -d

# Access services
# Prometheus: http://localhost:9091
# Grafana: http://localhost:3000 (admin/admin)
```

### Grafana Dashboard Setup

1. Login to Grafana
2. Add Prometheus data source:
   - URL: `http://prometheus:9090`
3. Import dashboard:
   - Create new dashboard
   - Add panels for key metrics

**Key Metrics to Monitor:**
- Tokens scanned per minute
- MoonScore distribution
- Alert delivery success rate
- RPC request latency
- Error rates

### AlertManager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'ops-team'

receivers:
- name: 'ops-team'
  email_configs:
  - to: 'ops@example.com'
    from: 'alertmanager@example.com'
    smarthost: smtp.gmail.com:587
    auth_username: 'alertmanager@example.com'
    auth_password: 'your-app-password'
```

---

## ✅ Production Checklist

### Security
- [ ] All API keys stored in secrets/environment variables
- [ ] No keys committed to version control
- [ ] Firewall configured (only necessary ports open)
- [ ] SSL/TLS enabled for webhooks
- [ ] Regular security updates applied
- [ ] Non-root user running the application

### Reliability
- [ ] Systemd service or container orchestration configured
- [ ] Automatic restart on failure
- [ ] Log rotation configured
- [ ] Backups configured for important data
- [ ] Health checks configured
- [ ] Multiple RPC providers configured for failover

### Monitoring
- [ ] Prometheus metrics exposed
- [ ] Grafana dashboards created
- [ ] Alerts configured for critical errors
- [ ] Log aggregation setup (ELK, CloudWatch, etc.)
- [ ] Performance baseline established

### Operations
- [ ] Documentation updated
- [ ] Runbook created for common issues
- [ ] On-call rotation established
- [ ] Incident response plan documented
- [ ] Regular maintenance windows scheduled

### Testing
- [ ] All tests passing
- [ ] Load testing completed
- [ ] Alert channels tested
- [ ] Failover procedures tested
- [ ] Rollback plan documented

---

## 🔄 Updating

### Rolling Update

```bash
# Pull latest changes
cd /opt/moon-scanner
git pull origin main

# Activate venv and update dependencies
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Restart service
sudo systemctl restart moon-scanner

# Check logs
sudo journalctl -u moon-scanner -f
```

### Docker Update

```bash
# Pull latest image
docker pull your-registry/solana-moon-scanner:latest

# Restart container
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs -f moon-scanner
```

---

## 🆘 Troubleshooting

### Service Won't Start
```bash
# Check service status
sudo systemctl status moon-scanner

# Check logs
sudo journalctl -u moon-scanner -n 100

# Check configuration
python -m src.cli config
```

### High Memory Usage
```bash
# Monitor memory
htop

# Adjust configuration
# Reduce SCAN_INTERVAL_SECONDS
# Reduce MAX_TOKEN_AGE_MINUTES
```

### RPC Rate Limiting
```bash
# Adjust rate limits in .env
RATE_LIMIT_PER_MINUTE=30
MAX_CONCURRENT_REQUESTS=5
```

---

**For additional support, consult the main README.md or create an issue on GitHub.**
