# Quick Start Guide: New Features

This guide walks you through the new capabilities added to the Federated Learning Platform.

## 🚀 Quick Setup

### Prerequisites
- Docker & Docker Compose installed
- 2GB free disk space (for datasets)
- 5 minutes

### Steps

1. **Clone and navigate**:
   ```bash
   cd Federated_Learning_Platform
   cp backend/.env.example backend/.env
   ```

2. **Start services**:
   ```bash
   docker compose up --build
   ```

3. **Open dashboard**:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000/docs

---

## 1️⃣ Multi-Dataset Support

### Try MNIST

1. **Fill form**:
   - Clients: 3
   - Rounds: 5
   - **Dataset: MNIST** ← New!
   - Leave other defaults

2. **Click "Start Experiment"**
   - ⏳ First run: Downloads MNIST (~120MB)
   - ✅ Subsequent runs: Instant (cached)

3. **Monitor**:
   - Accuracy should converge faster than synthetic data
   - Real 28×28 images → 784-dim features
   - Same model architecture (MLP)

### Try CIFAR-10

Same steps, but select **Dataset: CIFAR-10**:
- 32×32 RGB images → 3,072-dim features
- More complex classification task
- First download ~300MB
- Convergence slower (more samples/features)

### How It Works Behind the Scenes

```
User selects "mnist" in dashboard
    ↓
sent to API in config
    ↓
Each client downloads MNIST to ./data/
    ↓
Deterministic partitioning (client_1 always gets same samples)
    ↓
Model input auto-adjusts: 2D → 784D
    ↓
Training proceeds normally
```

---

## 2️⃣ Dashboard Filters & Export

### Filter Experiments

1. **By Status**:
   - Select dropdown: Running / Finished / All
   - Experiments list updates instantly

2. **By Dataset Type**:
   - Select dropdown: Synthetic / MNIST / CIFAR-10 / All
   - Stacks with status filter

3. **Auto-Refresh**:
   - Check "Auto-refresh every 3s"
   - Dashboard polls selected experiment live
   - Great for watching experiments run

### Export Results

1. **Create an experiment** (any dataset type)

2. **Run 2-3 rounds**

3. **Click "Export CSV"**:
   - Downloads `experiment_<ID>_results.csv`
   - Format: Round, Accuracy, Loss, Total Samples
   - Open in Excel/Python for analysis

4. **Click "Export JSON"**:
   - Downloads full experiment blob
   - All config, rounds, metrics
   - Share with collaborators or archive

### Example Workflow

```
Create experiment (MNIST, 5 rounds)
    ↓
Run Round 1 → Accuracy 0.65
    ↓
Enable auto-refresh ✓
    ↓
Run remaining rounds (auto-updates)
    ↓
Export CSV → Paste into Jupyter
    ↓
Plot convergence curve
```

---

## 3️⃣ Differential Privacy with Epsilon/Delta

### Enable Differential Privacy

1. **Fill form**:
   - Clients: 3
   - Rounds: 5
   - Dataset: synthetic
   - **DP Enabled**: ✓ Check
   - **Clipping Norm**: 1.0 (default)
   - **Noise Multiplier**: 1.5 ← Increase for more privacy

2. **Click "Start Experiment"**

3. **Monitor Privacy Metrics**:
   - After Round 1, new cards appear:
     - **DP Epsilon (ε)**: 0.8234 (privacy loss, lower = stronger)
     - **DP Delta (δ)**: 1e-05 (failure prob)
   - Epsilon increases with each round (RDP composition)

### Understanding Privacy Metrics

| Epsilon | Privacy Level | Use Case |
|---------|---------------|----------|
| ε < 0.5 | Very Strong | Sensitive data (health records) |
| 0.5–1.0 | Strong | Personal data |
| 1.0–2.0 | Moderate | General scenarios |
| > 2.0 | Weak | Low-sensitivity data |

### Tuning Privacy

**More Privacy** (increase ε):
- Lower `noise_multiplier` (less noise)
- Example: 0.5 instead of 1.5
- But: Slower convergence, degraded accuracy

**Less Privacy** (lower ε):
- Higher `noise_multiplier` (more noise)
- Example: 2.0 instead of 1.5
- Better: Faster convergence, higher accuracy

### Export Privacy Analysis

1. **Run DP experiment** (5 rounds, noise_mult=1.0)
2. **Click Export CSV**
3. Get CSV with all rounds + final ε/δ in experiment details
4. Include in research paper: "ε=0.82 at δ=1e-5"

---

## 4️⃣ Production PostgreSQL

### Local Development (Current Setup)

Default: Uses Docker PostgreSQL
```bash
docker compose up --build
# Postgres container: docker:postgres:15
# Connection: localhost:5432 (from host)
# No setup needed!
```

### Production: AWS RDS

1. **Create RDS instance** (AWS Console or CLI):
   ```bash
   aws rds create-db-instance \
     --db-instance-identifier federated-learning-db \
     --engine postgres \
     --master-username fl_user \
     ...
   ```

2. **Get connection details**:
   - Host: `federated-learning-db.xxxxx.rds.amazonaws.com`
   - Port: 5432
   - Database: `fl_db`

3. **Update `.env`**:
   ```bash
   DATABASE_URL=postgresql://fl_user:PASSWORD@federated-learning-db.xxxxx.rds.amazonaws.com:5432/fl_db
   ```

4. **Deploy**:
   ```bash
   docker compose up
   ```
   - Backend auto-connects to managed RDS
   - No local database setup needed

### Production: Azure

1. **Create Azure Database for PostgreSQL**:
   ```bash
   az postgres server create --name federated-learning-db ...
   ```

2. **Update `.env`**:
   ```bash
   # Note: Requires SSL
   DATABASE_URL=postgresql://fl_user:PASSWORD@federated-learning-db.postgres.database.azure.com:5432/fl_db?sslmode=require
   ```

3. **Deploy**:
   ```bash
   docker compose up
   ```

### Production: Google Cloud SQL

1. **Create Cloud SQL instance**:
   ```bash
   gcloud sql instances create federated-learning-db --database-version=POSTGRES_15 ...
   ```

2. **Get public IP or use Cloud SQL Proxy** (recommended)

3. **Update `.env` with proxy or public IP**

4. **Deploy**:
   ```bash
   docker compose up
   ```

### See Full Guide

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for:
- Detailed RDS/Azure/GCP setup
- Kubernetes deployment
- Monitoring with cloud tools
- Security checklist
- Backup automation

---

## 5️⃣ Combining All Features

### Full Advanced Experiment

```
Configuration:
  - Clients: 5
  - Rounds: 10
  - Dataset: CIFAR-10 (realistic)
  - DP Enabled: ✓
  - Noise Multiplier: 1.2
  - Secure Aggregation: ✓

Steps:
  1. Create experiment → Starts federation with CIFAR-10
  2. Enable auto-refresh → Watch real-time updates
  3. Run rounds 1-10 → See epsilon accumulate
  4. Filter by CIFAR-10 → Only shows this type
  5. Export JSON → Full reproducible blob
  6. Export CSV → Feed into analysis

Results:
  - Epsilon: 1.4 at δ=1e-5 (formal privacy guarantee)
  - Accuracy: 0.72 (convergence on real images)
  - Demonstrable federated learning on realistic data
```

---

## 🔍 Troubleshooting

### Dataset Download Fails

**Issue**: "Connection timeout downloading MNIST"

**Fix**:
```bash
# Manual download
cd backend
mkdir -p data
python -c "from torchvision import datasets; datasets.MNIST(root='./data', train=True, download=True)"
```

### Auto-Refresh Not Working

**Issue**: Dashboard doesn't update every 3s

**Fix**:
1. Check backend is running: `curl http://localhost:8000/docs`
2. Check browser console for errors (F12)
3. Try unchecking and rechecking auto-refresh

### DP Epsilon Not Showing

**Issue**: Epsilon/delta cards don't appear

**Fix**:
1. Verify `dp_enabled: true` was sent
2. Run at least 1 round (epsilon computes at round completion)
3. Check browser console for API errors

### Export Button Downloads Nothing

**Issue**: Click export but no file appears

**Fix**:
1. Check browser downloads folder (Ctrl+J)
2. Check browser console (F12) for 403/CORS errors
3. Ensure an experiment is selected

---

## 📚 Next Learning Steps

1. **Read IMPLEMENTATION_SUMMARY.md** for technical details
2. **Read DEPLOYMENT.md** for production setup
3. **Explore backend/app/** code comments
4. **Try modifying** dataset types, privacy settings, client counts
5. **Export** experiments and analyze with pandas/matplotlib

---

## 🎯 Key Takeaways

✅ **Multi-Dataset**: Swap between synthetic/MNIST/CIFAR-10 with one dropdown

✅ **Filters & Export**: Manage experiments easily, download results for analysis

✅ **Privacy Metrics**: See formal ε/δ values, understand privacy-utility tradeoff

✅ **Production Ready**: Use managed PostgreSQL (AWS/Azure/GCP) in minutes

✅ **Backward Compatible**: Old experiments still work with new features

---

## 💬 Questions?

- **Code**: Check docstrings in `backend/app/ml/datasets.py`, `privacy/differential_privacy.py`
- **Deployment**: See DEPLOYMENT.md
- **Examples**: Run experiments with different dataset_type values
- **Bugs**: Check logs: `docker compose logs -f backend`

**Happy Federated Learning! 🚀**


