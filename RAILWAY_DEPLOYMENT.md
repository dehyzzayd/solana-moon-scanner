# 🚂 Railway.app Deployment Guide

## Quick Deploy (5 Minutes)

### Prerequisites
- GitHub account
- Railway.app account (free, sign up at https://railway.app)
- Your Helius RPC URL

---

## Step 1: Push to GitHub

### Option A: Using the Deploy Script (Recommended)
```bash
cd /home/user/solana-moon-scanner
./deploy.sh YOUR_GITHUB_USERNAME
```

When prompted, enter your **GitHub Personal Access Token** (not your password).

### Option B: Manual Push
```bash
cd /home/user/solana-moon-scanner

# Add remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/solana-moon-scanner.git

# Push
git push -u origin main
```

**Need a Personal Access Token?**
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name: `solana-moon-scanner`
4. Scopes: Check `repo`
5. Generate & copy the token

---

## Step 2: Deploy on Railway

### 1. Create Railway Account
- Go to https://railway.app/
- Click "Login with GitHub"
- Authorize Railway

### 2. Create New Project
- Click "New Project"
- Select "Deploy from GitHub repo"
- Choose `solana-moon-scanner`

### 3. Configure Environment Variables
Click on your project → Variables → Add Variables:

```bash
# Required
HELIUS_RPC_URL=https://your-helius-rpc-url
PRIMARY_RPC_PROVIDER=helius

# Optional (disable alerts)
TELEGRAM_ALERTS_ENABLED=false
```

### 4. Wait for Deployment
- Railway automatically detects Python
- Installs dependencies from `requirements.txt`
- Runs command from `Procfile`
- Usually takes 2-3 minutes

### 5. Get Your Live URL
- Click "Settings" tab
- Scroll to "Domains"
- Copy your Railway URL (e.g., `https://solana-moon-scanner-production.up.railway.app`)

---

## Step 3: Verify Deployment

Visit your Railway URL and check:
- ✅ Dashboard loads
- ✅ Auto scanner shows status
- ✅ Manual scan works
- ✅ Token discovery functions

Test endpoints:
```bash
# Health check
curl https://YOUR-APP.up.railway.app/health

# Scanner status
curl https://YOUR-APP.up.railway.app/api/auto-scanner/status
```

---

## Troubleshooting

### Build Fails
**Check Railway logs:**
- Go to project → Deployments
- Click on failed deployment
- View build logs

**Common issues:**
- Missing environment variables
- Wrong Python version (should be 3.12)

### App Crashes
**Check runtime logs:**
- Go to project → View Logs
- Look for error messages

**Common issues:**
- RPC URL not set
- Invalid environment variables

### Port Issues
Railway automatically sets `$PORT` environment variable.
The app is configured to use it.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HELIUS_RPC_URL` | ✅ Yes | - | Your Helius RPC endpoint |
| `PRIMARY_RPC_PROVIDER` | ✅ Yes | `helius` | RPC provider to use |
| `TELEGRAM_ALERTS_ENABLED` | ⚪ No | `false` | Enable Telegram alerts |
| `TELEGRAM_BOT_TOKEN` | ⚪ No | - | Telegram bot token |
| `TELEGRAM_CHAT_ID` | ⚪ No | - | Telegram chat ID |

---

## Railway Features

### Auto-Deploy
- Push to GitHub → Railway auto-deploys
- No manual deployment needed

### Monitoring
- View logs in real-time
- Check metrics (CPU, memory, network)
- Monitor deployment history

### Custom Domain (Optional)
1. Go to Settings → Domains
2. Click "Custom Domain"
3. Add your domain
4. Update DNS records

---

## Free Tier Limits

Railway free tier includes:
- ✅ 500 hours/month (enough for 24/7)
- ✅ 512 MB RAM
- ✅ 1 GB disk
- ✅ Shared CPU
- ✅ Unlimited bandwidth

**This is perfect for the Solana Moon Scanner!**

---

## Support

**Railway Issues:**
- Railway Discord: https://discord.gg/railway
- Documentation: https://docs.railway.app/

**App Issues:**
- Check logs in Railway dashboard
- Verify environment variables
- Test endpoints with curl

---

## Next Steps After Deployment

1. ✅ Share your live URL
2. ✅ Test all features
3. ✅ Monitor auto scanner
4. ✅ Set up custom domain (optional)
5. ✅ Configure Telegram alerts (optional)

---

## Quick Commands

```bash
# Check deployment status
railway status

# View logs
railway logs

# Open app in browser
railway open

# Deploy manually
railway up
```

*Note: Requires Railway CLI - install from https://docs.railway.app/develop/cli*

---

🎉 **That's it! Your Solana Moon Scanner is now live!**
