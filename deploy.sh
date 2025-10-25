#!/bin/bash
# Deployment script for Solana Moon Scanner

set -e

echo "🚀 Solana Moon Scanner Deployment Script"
echo "=========================================="
echo ""

# Check if GitHub username is provided
if [ -z "$1" ]; then
    echo "❌ Error: GitHub username not provided"
    echo ""
    echo "Usage: ./deploy.sh YOUR_GITHUB_USERNAME"
    echo "Example: ./deploy.sh zayd"
    exit 1
fi

GITHUB_USERNAME=$1
REPO_NAME="solana-moon-scanner"

echo "📋 Configuration:"
echo "   GitHub User: $GITHUB_USERNAME"
echo "   Repository: $REPO_NAME"
echo ""

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "❌ Error: Not a git repository"
    exit 1
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  Warning: You have uncommitted changes"
    echo ""
    read -p "Do you want to commit them now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git add .
        read -p "Enter commit message: " commit_msg
        git commit -m "$commit_msg"
        echo "✅ Changes committed"
    fi
fi

# Check if remote exists
if git remote | grep -q "origin"; then
    echo "📍 Remote 'origin' already exists"
    git remote -v
else
    echo "➕ Adding remote origin..."
    git remote add origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
    echo "✅ Remote added"
fi

echo ""
echo "📤 Pushing to GitHub..."
echo "   (You'll need to enter your GitHub Personal Access Token)"
echo ""

# Push to GitHub
if git push -u origin main; then
    echo ""
    echo "✅ Successfully pushed to GitHub!"
    echo ""
    echo "🌐 Repository URL: https://github.com/$GITHUB_USERNAME/$REPO_NAME"
    echo ""
    echo "📋 Next Steps:"
    echo "   1. Go to https://railway.app/"
    echo "   2. Sign up / Log in"
    echo "   3. Click 'New Project'"
    echo "   4. Choose 'Deploy from GitHub repo'"
    echo "   5. Select: $GITHUB_USERNAME/$REPO_NAME"
    echo "   6. Add environment variables:"
    echo "      - HELIUS_RPC_URL=your_helius_rpc_url"
    echo "      - PRIMARY_RPC_PROVIDER=helius"
    echo "   7. Railway will auto-deploy!"
    echo ""
    echo "🎉 Your app will be live at: https://solana-moon-scanner-production.up.railway.app"
else
    echo ""
    echo "❌ Push failed!"
    echo ""
    echo "💡 Troubleshooting:"
    echo "   1. Make sure the repository exists on GitHub"
    echo "   2. Use Personal Access Token (not password)"
    echo "   3. Token needs 'repo' permissions"
    echo "   4. Get token from: https://github.com/settings/tokens"
    echo ""
    exit 1
fi
