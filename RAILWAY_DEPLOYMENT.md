# 🚂 Railway Deployment Guide

Complete guide to deploy RAG Profile Agent on Railway.

## Prerequisites

1. Railway account: https://railway.app
2. GitHub repository connected (or deploy from CLI)

---

## 🚀 Quick Deploy

### Option 1: Deploy from GitHub (Recommended)

1. **Go to Railway Dashboard**: https://railway.app/new
2. **Select "Deploy from GitHub repo"**
3. **Select your repository**: `Azim1588/rag-profile-agent`
4. **Railway will automatically detect**:
   - Python project
   - Procfile with start command
   - Build from `requirements.txt`

5. **Add Environment Variables** (see below)
6. **Add PostgreSQL Service** (see below)
7. **Add Redis Service** (see below)

---

## 📦 Services Setup

### 1. Main Application Service

Railway will automatically create this when you deploy from GitHub.

**Configure**:
- Port: Auto-detected (Railway sets `PORT` env var)
- Health Check: `/v1/health/live`

### 2. PostgreSQL Service (Required)

1. In Railway dashboard, click **"+ New"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway automatically:
   - Creates PostgreSQL instance
   - Sets environment variables:
     - `DATABASE_URL`
     - `PGHOST`
     - `PGPORT`
     - `PGDATABASE`
     - `PGUSER`
     - `PGPASSWORD`

4. **Enable pgvector extension**:
   - Railway PostgreSQL supports pgvector
   - Run this SQL in Railway's PostgreSQL admin panel:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

5. **Link to your app**:
   - The PostgreSQL service will automatically share env vars with your app
   - Update your app's env vars if needed (see below)

### 3. Redis Service (Required)

1. In Railway dashboard, click **"+ New"**
2. Select **"Database"** → **"Add Redis"**
3. Railway automatically sets:
   - `REDIS_URL`
   - `REDISHOST`
   - `REDISPORT`
   - `REDISUSER`
   - `REDISPASSWORD`

4. **Link to your app** (auto-linked)

---

## 🔧 Environment Variables

Set these in Railway dashboard → Your Service → Variables:

### Required Variables

| Variable | Value | Source |
|----------|-------|--------|
| `OPENAI_API_KEY` | `sk-...` | Your OpenAI API key |
| `ENVIRONMENT` | `production` | Set to production |
| `DEBUG` | `False` | Disable debug mode |

### Database Variables (Auto-set by PostgreSQL service)

Railway automatically provides these when PostgreSQL service is linked:

| Variable | Auto-set | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | Full PostgreSQL connection string |
| `PGHOST` | ✅ | PostgreSQL host |
| `PGPORT` | ✅ | PostgreSQL port |
| `PGDATABASE` | ✅ | Database name |
| `PGUSER` | ✅ | PostgreSQL user |
| `PGPASSWORD` | ✅ | PostgreSQL password |

**Update your app config to use Railway's variables**:

If Railway provides `DATABASE_URL`, update your service to use:
- `POSTGRES_HOST` = `${{Postgres.PGHOST}}` (or use DATABASE_URL directly)
- `POSTGRES_PORT` = `${{Postgres.PGPORT}}`
- `POSTGRES_DB` = `${{Postgres.PGDATABASE}}`
- `POSTGRES_USER` = `${{Postgres.PGUSER}}`
- `POSTGRES_PASSWORD` = `${{Postgres.PGPASSWORD}}`

Or set in Railway:
- `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`

### Redis Variables (Auto-set by Redis service)

| Variable | Auto-set | Description |
|----------|----------|-------------|
| `REDIS_URL` | ✅ | Full Redis connection string |
| `REDISHOST` | ✅ | Redis host |
| `REDISPORT` | ✅ | Redis port |

Set in Railway:
- `REDIS_URL` = `${{Redis.REDISURL}}`
- `CELERY_BROKER_URL` = `${{Redis.REDISURL}}`
- `CELERY_RESULT_BACKEND` = `${{Redis.REDISURL}}`

### Optional Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `AWS_ACCESS_KEY_ID` | Your AWS key | For S3 document sync |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret | For S3 document sync |
| `S3_BUCKET` | `your-bucket` | S3 bucket name |
| `S3_REGION` | `us-east-1` | AWS region |
| `LANGCHAIN_API_KEY` | `lsv2_...` | For LangSmith tracing |
| `LANGCHAIN_PROJECT` | `rag-profile-agent` | LangSmith project |

---

## 🗄️ Database Initialization

After PostgreSQL is set up:

1. **Get database credentials** from Railway PostgreSQL service
2. **Connect using Railway's database admin panel** or psql:
   ```bash
   # Railway provides connection command in dashboard
   psql $DATABASE_URL
   ```

3. **Run initialization SQL**:
   ```sql
   -- Enable pgvector
   CREATE EXTENSION IF NOT EXISTS vector;
   
   -- Run scripts/init_db.sql
   -- (Copy contents from scripts/init_db.sql)
   ```

Or use Railway's **PostgreSQL Admin Panel**:
- Click on PostgreSQL service → "Data" tab
- Run SQL queries there

---

## 🔄 After Deployment

1. **Verify deployment**:
   ```bash
   curl https://your-app-name.railway.app/v1/health/
   ```

2. **Check logs**:
   - Railway Dashboard → Your Service → "Deployments" → View logs

3. **Initialize database** (if not done):
   - Connect to PostgreSQL
   - Run `scripts/init_db.sql`

---

## 🐛 Troubleshooting

### Issue: "No start command found"

**Solution**: The `Procfile` should fix this. Make sure it's committed:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Issue: Port binding error

**Solution**: Railway sets `PORT` env var automatically. The Procfile uses `$PORT`.

### Issue: Database connection failed

**Solution**:
1. Ensure PostgreSQL service is linked to your app
2. Check `DATABASE_URL` is set correctly
3. Verify pgvector extension is enabled: `CREATE EXTENSION vector;`

### Issue: Redis connection failed

**Solution**:
1. Ensure Redis service is linked
2. Check `REDIS_URL` is set: `${{Redis.REDISURL}}`

### Issue: Module not found errors

**Solution**:
- Ensure `requirements.txt` is up to date
- Railway installs from requirements.txt automatically

---

## 📊 Monitoring

- **Logs**: Railway Dashboard → Your Service → "Deployments" → Logs
- **Metrics**: Railway Dashboard → Your Service → Metrics
- **Health Checks**: Use `/v1/health/live` endpoint

---

## 🔗 Useful Links

- **Railway Dashboard**: https://railway.app
- **Railway Docs**: https://docs.railway.app
- **PostgreSQL on Railway**: https://docs.railway.app/databases/postgresql
- **Redis on Railway**: https://docs.railway.app/databases/redis

---

## ✅ Deployment Checklist

- [ ] Repository deployed from GitHub
- [ ] PostgreSQL service added and linked
- [ ] Redis service added and linked
- [ ] pgvector extension enabled in PostgreSQL
- [ ] Environment variables configured
- [ ] Database initialized (run init_db.sql)
- [ ] Health check endpoint working
- [ ] Application accessible via Railway URL

---

**🎉 Your app should now be live on Railway!**

