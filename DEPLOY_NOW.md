# 🚀 Deploy Now - Step by Step

## ⚡ GitHub Token Issues? Deploy Without GitHub!

Your GitHub token is having permission issues. Here's the fastest way to deploy:

---

## 📥 METHOD 1: Download & Deploy Locally

### Step 1: Download the Package
Download this file from the sandbox:
- **File**: `/home/user/solana-moon-scanner-deploy.tar.gz` (154KB)

### Step 2: Extract Locally
```bash
tar -xzf solana-moon-scanner-deploy.tar.gz
cd solana-moon-scanner
```

### Step 3: Install Railway CLI (On Your Machine)
```bash
# Mac/Linux
curl -fsSL https://railway.app/install.sh | sh

# Or via npm
npm install -g @railway/cli
```

### Step 4: Deploy
```bash
railway login
railway init
railway up
```

### Step 5: Add Environment Variables
```bash
railway variables set HELIUS_RPC_URL=your_helius_url_here
railway variables set PRIMARY_RPC_PROVIDER=helius
railway variables set TELEGRAM_ALERTS_ENABLED=false
```

### Step 6: Get Your URL
```bash
railway domain
```

---

## 🌐 METHOD 2: Deploy from Railway Dashboard

### Step 1: Create Railway Account
- Go to https://railway.app/
- Login with GitHub

### Step 2: Create New Project
- Click "New Project"
- Choose "Empty Project"

### Step 3: Upload Code
Since GitHub isn't working, you'll need to:

**Option A: Use Railway CLI** (from your local machine after downloading)
```bash
railway login
railway link  # Select your project
railway up
```

**Option B: Connect GitHub Later**
1. Fix the GitHub token issue (use Classic token with repo scope)
2. Push to GitHub
3. Connect Railway to GitHub repo

---

## 🔧 METHOD 3: Fix GitHub & Deploy (Traditional)

### Create a CLASSIC GitHub Token (Not Fine-Grained)

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name: `railway-deploy`
4. Scopes:
   - ✅ repo (all checkboxes)
   - ✅ workflow
5. Generate token
6. Copy it

### Push with Classic Token

```bash
cd /home/user/solana-moon-scanner

# Update credentials with CLASSIC token
echo "https://dehyzzayd:YOUR_CLASSIC_TOKEN@github.com" > ~/.git-credentials

# Push
git push -u origin main
```

### Deploy on Railway

1. Go to https://railway.app/
2. New Project → Deploy from GitHub
3. Select: dehyzzayd/solana-moon-scanner
4. Add environment variables
5. Deploy!

---

## 🎯 My Recommendation: METHOD 1

Download the package and deploy from your local machine using Railway CLI.

**Why?**
- ✅ Bypasses GitHub token issues
- ✅ Fastest (< 5 minutes)
- ✅ Most reliable
- ✅ You have full control

---

## 📋 Environment Variables Needed

Once deployed, add these in Railway:

```bash
HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
PRIMARY_RPC_PROVIDER=helius
TELEGRAM_ALERTS_ENABLED=false
```

---

## ✅ After Deployment

Your app will be live at:
- `https://solana-moon-scanner-production.up.railway.app` (or similar)

**Features working:**
- ✅ Auto scanner (every 5 minutes)
- ✅ Manual token scan
- ✅ Manual discovery (1-6 hours)
- ✅ Expandable token details
- ✅ Real-time updates
- ✅ Full validation rules

---

## 🆘 Still Having Issues?

**Option 1**: Use Render.com instead
- Go to https://render.com/
- Deploy from GitHub
- Free tier available

**Option 2**: Use Fly.io
- Go to https://fly.io/
- Deploy via CLI
- Free tier available

**Option 3**: Contact me
- Check Railway logs for errors
- Verify environment variables
- Test endpoints

---

## 🎉 Summary

**Fastest path right now:**

1. Download `/home/user/solana-moon-scanner-deploy.tar.gz`
2. Extract on your machine
3. Install Railway CLI: `npm install -g @railway/cli`
4. Deploy: `railway login && railway init && railway up`
5. Add env vars
6. Done!

**Total time: 5 minutes** ⚡
