# CodeCure — Vercel Deployment Guide

## Prerequisites
1. [GitHub account](https://github.com) (to store your code)
2. [Vercel account](https://vercel.com) (free tier available)
3. [Vercel CLI](https://vercel.com/docs/cli) (optional, for local deployment)
4. MongoDB Atlas account for your database

---

## Step 1: Prepare MongoDB Atlas

Your app uses MongoDB. You need a remote database:

### Option A: MongoDB Atlas (Recommended - Free tier available)
1. Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Sign up for a free account
3. Create a new project
4. Create a cluster (free tier)
5. Create a database user with a strong password
6. Get your connection string: `mongodb+srv://username:password@cluster-name.mongodb.net/codecure_db?retryWrites=true&w=majority`

### Option B: Use your existing MongoDB
If you have MongoDB running elsewhere, get the connection URI.

---

## Step 2: Push Code to GitHub

```powershell
# Navigate to your project
cd C:\Users\adity\OneDrive\Desktop\Codecure

# Initialize git (if not done)
git init
git add .
git commit -m "Initial commit for Vercel deployment"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/codecure.git
git branch -M main
git push -u origin main
```

---

## Step 3: Deploy to Vercel

### Option A: Via Vercel Dashboard (Recommended for beginners)

1. Go to [vercel.com/new](https://vercel.com/new)
2. Click "Import Git Repository"
3. Select your GitHub repository (`codecure`)
4. Under "Environment Variables", add:
   - `SECRET_KEY` → Generate a random key (e.g., `codecure_secret_$(date +%s)`)
   - `MONGO_URI` → Your MongoDB Atlas connection string
   - `MONGO_DB_NAME` → `codecure_db`
   - `GEMINI_API_KEY` → Your Gemini API key (keep it secure!)

5. Click "Deploy"

### Option B: Via Vercel CLI

```powershell
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Navigate to your project
cd C:\Users\adity\OneDrive\Desktop\Codecure

# Deploy
vercel

# For production deployment
vercel --prod
```

When prompted, add the same environment variables as Option A.

---

## Step 4: Configure Environment Variables in Vercel

If you didn't add them during deployment:

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your `codecure` project
3. Go to **Settings → Environment Variables**
4. Add the following:

| Variable | Value |
|----------|-------|
| `SECRET_KEY` | Random secret string |
| `MONGO_URI` | `mongodb+srv://user:pass@cluster.mongodb.net/codecure_db` |
| `MONGO_DB_NAME` | `codecure_db` |
| `GEMINI_API_KEY` | Your Gemini API key |

5. Redeploy: **Deployments → Select latest → Redeploy**

---

## Step 5: Test Your Deployment

1. Go to your Vercel project URL (shown on dashboard)
2. Test login with demo credentials:
   - Username: `admin` | Password: `1234`
   - Username: `pharmacist` | Password: `1234`
   - Username: `cashier` | Password: `1234`
   - Username: `doctor` | Password: `1234`

---

## Troubleshooting

### Issue: "ModuleNotFoundError"
**Solution:** Ensure `requirements.txt` is in the root directory and all dependencies are listed.

```bash
pip freeze > requirements.txt
```

### Issue: "Deployment timed out"
**Solution:** This usually means the database initialization is slow. Add a timeout to MongoDB connection in `config.py`:
```python
MONGO_URI = os.environ.get("MONGO_URI", "...") + "?serverSelectionTimeoutMS=10000"
```

### Issue: "Static files not loading"
**Solution:** Vercel serves static files automatically. Ensure they're in the `static/` folder (which you have).

### Issue: "Database connection refused"
**Solution:** 
1. Check your MongoDB Atlas IP whitelist: Add `0.0.0.0/0` or Vercel's IP ranges
2. Verify `MONGO_URI` environment variable is set correctly
3. Test connection: `python -c "from config import Config; print(Config.MONGO_URI)"`

---

## Useful Links

- [Vercel Python Documentation](https://vercel.com/docs/frameworks/python)
- [MongoDB Atlas Documentation](https://docs.atlas.mongodb.com/)
- [Flask Deployment Guide](https://flask.palletsprojects.com/en/latest/deploying/)

---

## Redeploy After Changes

```bash
# After making changes:
git add .
git commit -m "Your changes"
git push origin main

# Vercel automatically redeploys on push to main
```

---

## Production Checklist

- [ ] Use strong `SECRET_KEY` (not default)
- [ ] Database is on MongoDB Atlas (not localhost)
- [ ] All environment variables set in Vercel
- [ ] HTTPS is enabled (automatic with Vercel)
- [ ] Custom domain configured (optional)
- [ ] Logging/monitoring enabled (optional)
