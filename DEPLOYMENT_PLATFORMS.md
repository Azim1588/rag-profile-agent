# Deployment Platforms Guide

This guide covers deployment platforms suitable for the RAG Profile Agent application.

## 🔍 Project Requirements

Your application needs:
- ✅ **FastAPI** web application (Python)
- ✅ **PostgreSQL** with **pgvector** extension
- ✅ **Redis** for caching and Celery broker
- ✅ **Celery** workers for background tasks
- ✅ **WebSocket** support
- ✅ **Docker** containerization
- ✅ **Multiple services** (app, workers, beat scheduler, flower)

---

## 🏆 Recommended Platforms

### **1. AWS (Amazon Web Services) - BEST FOR SCALE**

**Best For:** Production deployments, enterprise applications, high scale

**Services Needed:**
- **ECS (Elastic Container Service)** or **EKS (Kubernetes)** for containers
- **RDS PostgreSQL** with pgvector extension (custom instance)
- **ElastiCache Redis**
- **Application Load Balancer** (supports WebSockets)
- **ECS/EKS** for Celery workers

**Pros:**
- ✅ Full control and flexibility
- ✅ Enterprise-grade reliability
- ✅ Auto-scaling capabilities
- ✅ Comprehensive monitoring (CloudWatch)
- ✅ High availability
- ✅ pgvector support via RDS PostgreSQL

**Cons:**
- ❌ Complex setup
- ❌ Higher cost
- ❌ Steeper learning curve

**Cost:** ~$100-500/month (depending on resources)

**Setup Difficulty:** ⭐⭐⭐⭐ (4/5)

**Documentation:**
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [RDS PostgreSQL with Extensions](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)

---

### **2. Railway - BEST FOR EASE OF USE**

**Best For:** Quick deployments, startups, MVP launches

**Services:**
- Railway supports PostgreSQL, Redis, and Docker deployments
- Automatic HTTPS
- Built-in monitoring

**Pros:**
- ✅ Extremely easy setup (GitHub integration)
- ✅ Automatic deployments
- ✅ PostgreSQL with extensions support
- ✅ Built-in Redis
- ✅ Reasonable pricing
- ✅ Good developer experience

**Cons:**
- ❌ Less control than AWS
- ❌ May have resource limits

**Cost:** ~$20-100/month (pay-as-you-go)

**Setup Difficulty:** ⭐⭐ (2/5) - **EASIEST**

**Documentation:**
- [Railway Documentation](https://docs.railway.app/)
- [Deploy PostgreSQL on Railway](https://docs.railway.app/databases/postgresql)

---

### **3. Render - GREAT BALANCE**

**Best For:** Modern applications, balanced features

**Services:**
- Render PostgreSQL (supports extensions)
- Render Redis
- Docker container support
- Background workers

**Pros:**
- ✅ Easy setup
- ✅ PostgreSQL with extensions
- ✅ WebSocket support
- ✅ Background workers (for Celery)
- ✅ Free tier available
- ✅ Automatic SSL

**Cons:**
- ❌ Free tier has limitations
- ❌ Less scalable than AWS

**Cost:** ~$25-150/month (free tier available)

**Setup Difficulty:** ⭐⭐⭐ (3/5)

**Documentation:**
- [Render Documentation](https://render.com/docs)
- [Deploy Docker on Render](https://render.com/docs/docker)

---

### **4. DigitalOcean App Platform**

**Best For:** Simplicity with good performance

**Services:**
- Managed PostgreSQL (with extensions)
- Managed Redis
- App Platform (Docker support)
- Background workers

**Pros:**
- ✅ Simple pricing
- ✅ Good performance
- ✅ Managed databases
- ✅ WebSocket support
- ✅ Clear documentation

**Cons:**
- ❌ Less enterprise features than AWS
- ❌ Regional limitations

**Cost:** ~$25-200/month

**Setup Difficulty:** ⭐⭐⭐ (3/5)

**Documentation:**
- [DigitalOcean App Platform](https://docs.digitalocean.com/products/app-platform/)
- [Managed Databases](https://docs.digitalocean.com/products/databases/)

---

### **5. Google Cloud Platform (GCP)**

**Best For:** Enterprise applications, Google ecosystem

**Services:**
- **Cloud Run** or **GKE** (Kubernetes) for containers
- **Cloud SQL PostgreSQL** (with pgvector)
- **Memorystore Redis**
- **Cloud Scheduler** for periodic tasks

**Pros:**
- ✅ Scalable and reliable
- ✅ Good integration with Google services
- ✅ Cloud SQL supports extensions
- ✅ Auto-scaling

**Cons:**
- ❌ Complex setup
- ❌ Higher cost
- ❌ Steeper learning curve

**Cost:** ~$100-500/month

**Setup Difficulty:** ⭐⭐⭐⭐ (4/5)

**Documentation:**
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud SQL PostgreSQL](https://cloud.google.com/sql/docs/postgres)

---

### **6. Fly.io - GREAT FOR EDGE DEPLOYMENT**

**Best For:** Global distribution, low latency

**Services:**
- Fly.io PostgreSQL (volumes)
- Fly.io Redis
- Global edge deployment

**Pros:**
- ✅ Global edge deployment
- ✅ Low latency
- ✅ Docker support
- ✅ Good for WebSockets

**Cons:**
- ❌ Newer platform
- ❌ Less mature than AWS/GCP

**Cost:** ~$20-150/month

**Setup Difficulty:** ⭐⭐⭐ (3/5)

**Documentation:**
- [Fly.io Documentation](https://fly.io/docs/)
- [PostgreSQL on Fly.io](https://fly.io/docs/postgres/)

---

### **7. Heroku - SIMPLE BUT EXPENSIVE**

**Best For:** Quick prototyping (note: Heroku has shifted focus)

**Services:**
- Heroku Postgres (add-on)
- Heroku Redis (add-on)
- Dynos for workers

**Pros:**
- ✅ Very easy setup
- ✅ Simple git-based deployment
- ✅ Add-ons ecosystem

**Cons:**
- ❌ Expensive at scale
- ❌ Limited PostgreSQL extension support (may need custom buildpack)
- ❌ Heroku has shifted focus (less recommended)

**Cost:** ~$50-300/month

**Setup Difficulty:** ⭐⭐ (2/5)

**Documentation:**
- [Heroku Platform](https://devcenter.heroku.com/)

---

## 🎯 Platform Comparison Matrix

| Platform | Ease of Setup | Cost | Scalability | WebSocket | pgvector | Best For |
|----------|---------------|------|-------------|-----------|----------|----------|
| **Railway** | ⭐⭐⭐⭐⭐ | $$ | ⭐⭐⭐ | ✅ | ✅ | Quick deployment |
| **Render** | ⭐⭐⭐⭐ | $$ | ⭐⭐⭐ | ✅ | ✅ | Modern apps |
| **DigitalOcean** | ⭐⭐⭐ | $$ | ⭐⭐⭐⭐ | ✅ | ✅ | Balanced |
| **AWS** | ⭐⭐ | $$$ | ⭐⭐⭐⭐⭐ | ✅ | ✅ | Enterprise |
| **GCP** | ⭐⭐ | $$$ | ⭐⭐⭐⭐⭐ | ✅ | ✅ | Enterprise |
| **Fly.io** | ⭐⭐⭐ | $$ | ⭐⭐⭐⭐ | ✅ | ✅ | Global edge |
| **Heroku** | ⭐⭐⭐⭐ | $$$ | ⭐⭐⭐ | ✅ | ⚠️ | Legacy/simple |

---

## 🚀 Recommended Deployment Strategy

### **For MVP / Small Projects:**
1. **Railway** (easiest) or **Render** (balanced)

### **For Production / Growing Applications:**
1. **DigitalOcean App Platform** or **Render**

### **For Enterprise / High Scale:**
1. **AWS ECS/EKS** or **GCP Cloud Run/GKE**

---

## 📋 Deployment Checklist

### Before Deploying:

- [ ] Fix all critical security issues (see PRODUCTION_READINESS_REPORT.md)
- [ ] Set up environment variables
- [ ] Configure production database
- [ ] Set up Redis instance
- [ ] Configure CORS for production domain
- [ ] Set up SSL/HTTPS
- [ ] Configure monitoring and logging
- [ ] Set up backup strategy
- [ ] Test deployment in staging

### Required Environment Variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
POSTGRES_HOST=your-postgres-host
POSTGRES_USER=your-user
POSTGRES_PASSWORD=your-password

# Redis
REDIS_URL=redis://your-redis-host:6379/0
CELERY_BROKER_URL=redis://your-redis-host:6379/0
CELERY_RESULT_BACKEND=redis://your-redis-host:6379/1

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Security
SECRET_KEY=your-secret-key-min-32-chars
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# AWS S3 (if using)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET=your-bucket-name

# Environment
ENVIRONMENT=production
DEBUG=False
```

---

## 🔧 Platform-Specific Setup Guides

### **Railway Deployment (RECOMMENDED FOR EASE)**

1. **Create Railway Account:**
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub

2. **Create PostgreSQL Database:**
   - Click "New Project" → "Add Database" → "PostgreSQL"
   - Railway will create a PostgreSQL instance with extensions support

3. **Create Redis Instance:**
   - Click "New" → "Add Database" → "Redis"

4. **Deploy Application:**
   - Click "New" → "GitHub Repo"
   - Select your repository
   - Railway will auto-detect Docker

5. **Configure Environment Variables:**
   - Go to your service → Variables
   - Add all required environment variables
   - Link database/Redis URLs automatically

6. **Deploy Celery Workers:**
   - Create new service from same repo
   - Set start command: `celery -A app.tasks.celery_app worker --loglevel=info`
   - Configure environment variables

7. **Deploy Celery Beat:**
   - Create new service
   - Set start command: `celery -A app.tasks.celery_app beat --loglevel=info`

8. **Deploy Flower (optional):**
   - Create new service
   - Set start command: `celery -A app.tasks.celery_app flower --port=5555`

**Cost:** ~$20-50/month for small deployments

---

### **Render Deployment**

1. **Create Render Account:**
   - Go to [render.com](https://render.com)
   - Sign up with GitHub

2. **Create PostgreSQL Database:**
   - New → PostgreSQL
   - Select plan
   - Note connection string

3. **Create Redis Instance:**
   - New → Redis
   - Select plan

4. **Deploy Web Service:**
   - New → Web Service
   - Connect GitHub repo
   - Build Command: `docker build -t app -f docker/Dockerfile.app .`
   - Start Command: `docker run app`
   - Set environment variables

5. **Deploy Background Workers:**
   - New → Background Worker
   - Same repo
   - Start Command: `celery -A app.tasks.celery_app worker --loglevel=info`

6. **Deploy Cron Jobs (for Celery Beat):**
   - New → Cron Job
   - Command: `celery -A app.tasks.celery_app beat --loglevel=info`

**Cost:** Free tier available, then ~$25-100/month

---

### **AWS ECS Deployment (Advanced)**

1. **Set up Infrastructure:**
   - Create ECS cluster
   - Create RDS PostgreSQL instance (enable pgvector)
   - Create ElastiCache Redis cluster
   - Create Application Load Balancer

2. **Build and Push Docker Images:**
   ```bash
   # Build images
   docker build -f docker/Dockerfile.app -t your-ecr-repo/app:latest .
   docker build -f docker/Dockerfile.worker -t your-ecr-repo/worker:latest .
   
   # Push to ECR
   aws ecr get-login-password | docker login --username AWS --password-stdin your-account.dkr.ecr.region.amazonaws.com
   docker tag your-ecr-repo/app:latest your-account.dkr.ecr.region.amazonaws.com/app:latest
   docker push your-account.dkr.ecr.region.amazonaws.com/app:latest
   ```

3. **Create ECS Task Definitions:**
   - Web service task (FastAPI app)
   - Worker task (Celery worker)
   - Beat task (Celery beat)

4. **Create ECS Services:**
   - Web service → Application Load Balancer
   - Worker service → background task
   - Beat service → scheduled task

5. **Configure Environment Variables:**
   - Use AWS Systems Manager Parameter Store
   - Or AWS Secrets Manager for sensitive data

**Cost:** ~$100-500/month depending on resources

---

### **DigitalOcean App Platform**

1. **Create DigitalOcean Account:**
   - Go to [digitalocean.com](https://digitalocean.com)

2. **Create Managed Databases:**
   - Databases → Create → PostgreSQL
   - Databases → Create → Redis

3. **Deploy App:**
   - Apps → Create App
   - Connect GitHub repo
   - Auto-detect Docker
   - Add environment variables
   - Link databases

4. **Add Workers:**
   - Add Component → Worker
   - Set command: `celery -A app.tasks.celery_app worker`
   - Link to same databases

**Cost:** ~$25-200/month

---

## 🔐 Security Configuration for Production

### Required Changes:

1. **CORS:**
   ```python
   # app/main.py
   allow_origins=settings.ALLOWED_ORIGINS.split(",") if settings.ALLOWED_ORIGINS else []
   ```

2. **SECRET_KEY:**
   ```python
   # Must be 32+ characters, random
   SECRET_KEY=secrets.token_urlsafe(32)
   ```

3. **DEBUG:**
   ```python
   DEBUG=False  # In production
   ```

4. **Database Passwords:**
   - Never hardcode in docker-compose.yml
   - Use environment variables or secrets management

---

## 📊 Monitoring Recommendations

### Essential Monitoring:

1. **Application Logs:**
   - Set up centralized logging (Datadog, LogRocket, or platform-native)

2. **Metrics:**
   - Response times
   - Error rates
   - Rate limit violations
   - Celery task success/failure rates

3. **Alerts:**
   - Service downtime
   - High error rates
   - Database connection issues
   - Redis connectivity issues
   - OpenAI API quota warnings

---

## 💰 Cost Estimation

### Small Deployment (MVP):
- **Railway/Render:** $20-50/month
- **DigitalOcean:** $25-75/month

### Medium Deployment (Growing):
- **Render/DigitalOcean:** $75-200/month
- **AWS/GCP:** $150-400/month

### Large Deployment (Enterprise):
- **AWS/GCP:** $400-2000+/month

---

## 🎯 My Recommendation

**For Quick Start:** Use **Railway** - It's the easiest and handles PostgreSQL with extensions well.

**For Production:** Use **Render** or **DigitalOcean** - Good balance of features, price, and ease of use.

**For Enterprise:** Use **AWS** or **GCP** - Full control and scalability.

---

## 📚 Additional Resources

- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Docker Production Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [PostgreSQL with pgvector Setup](https://github.com/pgvector/pgvector)

---

## 🆘 Need Help?

If you need help with deployment, check:
1. Platform-specific documentation
2. Docker logs: `docker compose logs app`
3. Application logs in platform dashboard
4. Database connection strings
5. Environment variables configuration

