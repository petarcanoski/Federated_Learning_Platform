# ✅ Verification Checklist

Complete this checklist to verify all new features are working correctly.

---

## 🔧 Setup Prerequisites

- [ ] Docker & Docker Compose installed (`docker --version`, `docker-compose --version`)
- [ ] Git repository updated (latest code)
- [ ] `.env.example` copied to `.env` (if needed)
- [ ] 2GB free disk space (for datasets)
- [ ] Port 3000, 8000, 5432 available

---

## 1️⃣ Backend Setup & Validation

### Database Connection
- [ ] Run `docker compose up --build`
- [ ] Backend container starts (no connection errors)
- [ ] Postgres container initializes
- [ ] No "port 5432 connection refused" errors
- [ ] Logs show: "Application startup complete"

### Python Imports
```bash
# Inside backend container or venv:
cd backend
python -c "from app.ml.datasets import build_dataset; print('✓ datasets module')"
python -c "from app.privacy.differential_privacy import DifferentialPrivacyAccounting; print('✓ DP accounting')"
python -c "import torchvision; print('✓ torchvision')"
```
- [ ] All imports successful

### API Health
```bash
curl http://localhost:8000/docs
```
- [ ] Returns Swagger UI (FastAPI docs page)
- [ ] No 503 errors

---

## 2️⃣ Multi-Dataset Feature Tests

### Synthetic Dataset (Baseline)
```bash
curl -X POST http://localhost:8000/start_experiment \
  -H "Content-Type: application/json" \
  -d '{
    "num_clients": 2,
    "rounds": 1,
    "dataset_type": "synthetic",
    "epochs": 1
  }'
```
- [ ] Returns 200 OK with job_id
- [ ] Response includes `config.dataset_type: "synthetic"`
- [ ] No download of datasets

### MNIST Dataset
```bash
curl -X POST http://localhost:8000/start_experiment \
  -H "Content-Type: application/json" \
  -d '{
    "num_clients": 2,
    "rounds": 1,
    "dataset_type": "mnist",
    "epochs": 1
  }'
```
- [ ] Returns 200 OK
- [ ] First run: Downloads MNIST (~120MB) to `backend/data/`
- [ ] Shows progress bar or logs
- [ ] Second run: Uses cached data instantly
- [ ] Response includes `config.dataset_type: "mnist"`

### CIFAR-10 Dataset
```bash
curl -X POST http://localhost:8000/start_experiment \
  -H "Content-Type: application/json" \
  -d '{
    "num_clients": 2,
    "rounds": 1,
    "dataset_type": "cifar10",
    "epochs": 1
  }'
```
- [ ] Returns 200 OK
- [ ] First run: Downloads CIFAR-10 (~300MB) to `backend/data/`
- [ ] Second run: Instant (cached)
- [ ] Response includes `config.dataset_type: "cifar10"`

### Dataset Determinism
```bash
# Run same MNIST experiment twice
curl -X POST http://localhost:8000/start_experiment -d '{...}' > exp1.json
curl -X POST http://localhost:8000/start_experiment -d '{...}' > exp2.json

# Get client_1 loss from both
jq '.rounds[0].client_metrics[0].loss' exp1.json
jq '.rounds[0].client_metrics[0].loss' exp2.json
```
- [ ] Both client_1 losses are identical (deterministic seeding)
- [ ] Proves same client gets same data partition

---

## 3️⃣ Privacy Features Tests

### DP Disabled (Baseline)
```bash
curl -X POST http://localhost:8000/start_experiment \
  -H "Content-Type: application/json" \
  -d '{
    "num_clients": 3,
    "rounds": 5,
    "dp_enabled": false
  }'
```
- [ ] Returns 200 OK
- [ ] Response has `dp_epsilon: null` and `dp_delta: null`
- [ ] Experiment completes without privacy overhead

### DP Enabled
```bash
curl -X POST http://localhost:8000/start_experiment \
  -H "Content-Type: application/json" \
  -d '{
    "num_clients": 3,
    "rounds": 5,
    "dp_enabled": true,
    "clipping_norm": 1.0,
    "noise_multiplier": 1.5
  }' > exp_dp.json
```
- [ ] Returns 200 OK
- [ ] Response has `dp_epsilon: null` (computed after first round)

### Epsilon Composition
```bash
# After running first round:
curl http://localhost:8000/experiments/<job_id> | jq '.dp_epsilon'
# Should show non-null epsilon value (e.g., 0.82)

# After running second round:
curl http://localhost:8000/experiments/<job_id> | jq '.dp_epsilon'
# Should show slightly higher epsilon (composition)
```
- [ ] First round: ε ≈ 0.5–1.0 (depends on noise_multiplier)
- [ ] Second round: ε increases (RDP composition)
- [ ] Epsilon values monotonically increasing
- [ ] Delta constant (e.g., 1e-05)

### Privacy Correctness
```bash
# Check DP formulas in differential_privacy.py
more backend/app/privacy/differential_privacy.py
```
- [ ] `RDP_alpha = (alpha * num_rounds) / (2 * sigma^2)` formula visible
- [ ] Epsilon conversion using log(1/delta) visible
- [ ] Noise applied per-parameter with correct scale

---

## 4️⃣ Dashboard Features Tests

### Frontend Loads
```bash
curl http://localhost:3000
```
- [ ] Returns HTML (React app loads)
- [ ] Browser: Navigate to http://localhost:3000
- [ ] Page renders without console errors (F12)

### Form Dataset Field
- [ ] Dataset dropdown has options: Synthetic, MNIST, CIFAR-10
- [ ] Default selected: Synthetic
- [ ] Changing option works (no errors)

### Create Experiment (MNIST)
```
Form:
  - Clients: 3
  - Rounds: 5
  - Dataset: MNIST
  - DP Enabled: False
Click "Start Experiment"
```
- [ ] Button shows "Working..." briefly
- [ ] Experiment appears in Experiments list
- [ ] Shows: "Dataset: mnist" label

### Filters - Status
```
Original list has mixed running/finished experiments
Select filter: "Running"
```
- [ ] List updates instantly
- [ ] Only "running" experiments shown
- [ ] Switching back to "All" shows all

### Filters - Dataset
```
Select filter: "MNIST"
```
- [ ] Shows only MNIST experiments
- [ ] Combined with status filter: works together
- [ ] "No experiments match filters" message if none

### Auto-Refresh
```
Create new experiment
Select it
Check "Auto-refresh every 3s"
Run Round manually
```
- [ ] Accuracy/loss update without manual refresh
- [ ] Updates every ~3 seconds
- [ ] Uncheck: updates stop

### Export CSV
```
Select completed experiment
Click "Export CSV"
```
- [ ] Downloads `experiment_<ID>_results.csv`
- [ ] File contains: Round,Accuracy,Loss,Total Samples
- [ ] Headers present
- [ ] Data matches dashboard

### Export JSON
```
Click "Export JSON"
```
- [ ] Downloads `experiment_<ID>.json`
- [ ] Contains full experiment object
- [ ] Valid JSON (opens in editor)
- [ ] Includes config, all rounds, metrics

### Privacy Metrics Display
```
Create DP experiment (dp_enabled=true, noise_mult=1.0)
Select it
Run 1 round
```
- [ ] **DP Epsilon (ε)** card appears: shows number like "0.8234"
- [ ] **DP Delta (δ)** card appears: shows like "1e-05"
- [ ] Cards styled with purple/pink accents
- [ ] Values update after each round

---

## 5️⃣ Workflow Tests

### Full Synthetic Workflow
- [ ] Create experiment (synthetic, 3 clients, 5 rounds)
- [ ] Run all 5 rounds (click button 5 times)
- [ ] Verify accuracy increases
- [ ] Export CSV
- [ ] Assert row count = 5 (one per round)

### Full MNIST Workflow (with DP)
- [ ] Create experiment (MNIST, 3 clients, 3 rounds, DP enabled)
- [ ] Enable auto-refresh
- [ ] Run rounds (wait for auto-update)
- [ ] Verify epsilon increases per round
- [ ] Export CSV + JSON
- [ ] Close and reopen app
- [ ] Filter by MNIST: verify experiment still visible

### Sensitive Data Scenario
- [ ] Create experiment: CIFAR-10, DP enabled, noise_mult=2.0
- [ ] Calculate expected epsilon:
  - RDP_10 = (10 × 5) / (2 × 2.0²) = 6.25
  - ε ≈ 0.25 (strong privacy)
- [ ] Verify dashboard shows low epsilon
- [ ] Accuracy should be degraded vs non-DP version

---

## 6️⃣ Database & Persistence Tests

### Check Database Schema
```bash
# Inside postgres container or psql:
docker exec -it <postgres_container> psql -U fl_user -d fl_db -c "\dt"
```
- [ ] Tables visible: `experiments`, `experiment_rounds`, `client_metrics`

### Verify DP Fields
```bash
docker exec -it <postgres_container> psql -U fl_user -d fl_db -c "SELECT job_id, dp_epsilon, dp_delta FROM experiments LIMIT 1;"
```
- [ ] DP experiment shows non-null epsilon
- [ ] Non-DP experiment shows NULL epsilon
- [ ] Delta = 1e-05 for DP experiments

### Persistence Check
```
1. Create experiment
2. Run 2 rounds
3. docker compose down
4. docker compose up
5. Access via API: GET /experiments/<job_id>
```
- [ ] All rounds saved
- [ ] Metrics intact
- [ ] Epsilon persisted

---

## 7️⃣ Configuration Tests

### .env File
```bash
cat backend/.env
```
- [ ] DATABASE_URL present
- [ ] No syntax errors
- [ ] Supports both local and managed PostgreSQL URLs

### Environment Variables
```bash
# Start with custom DATABASE_URL
export DATABASE_URL="postgresql://..." 
docker compose up
```
- [ ] Overrides .env file correctly
- [ ] Backend connects to custom database

---

## 8️⃣ Documentation Validation

### README.md
- [ ] Contains new features documentation
- [ ] Includes multi-dataset examples
- [ ] Shows DP config example
- [ ] Lists all new API parameters
- [ ] Links to DEPLOYMENT.md and QUICKSTART_NEW_FEATURES.md

### DEPLOYMENT.md
- [ ] AWS RDS setup documented
- [ ] Azure Database documented
- [ ] Google Cloud SQL documented
- [ ] Security checklist present
- [ ] Monitoring guidance included
- [ ] Example connection strings (✗ with credentials)

### QUICKSTART_NEW_FEATURES.md
- [ ] Step-by-step for each feature
- [ ] Screenshots/examples clear
- [ ] Troubleshooting section
- [ ] Before/after comparisons

### IMPLEMENTATION_SUMMARY.md
- [ ] Files changed documented
- [ ] Technical details explained
- [ ] Backward compatibility noted

---

## 9️⃣ Error Handling Tests

### Invalid Dataset Type
```bash
curl -X POST http://localhost:8000/start_experiment \
  -d '{..., "dataset_type": "imagenet"}'
```
- [ ] Returns 422 (Pydantic validation error)
- [ ] Error message clear

### Invalid DP Parameters
```bash
curl -X POST http://localhost:8000/start_experiment \
  -d '{..., "noise_multiplier": -1.0}'
```
- [ ] Returns 422
- [ ] Validation catches negative noise

### Missing Required Fields
```bash
curl -X POST http://localhost:8000/start_experiment \
  -d '{}'
```
- [ ] Returns 422
- [ ] Lists missing fields

---

## 🔟 Performance Tests

### Startup Time
```bash
time docker compose up --build
```
- [ ] Completes in < 2 minutes
- [ ] Database connects within 10s
- [ ] No timeout errors

### Round Execution Time
```
Synthetic (2 clients): ~5s per round
MNIST (2 clients): ~10s per round
CIFAR-10 (2 clients): ~15s per round
(Varies by CPU)
```
- [ ] Synthetic fastest
- [ ] Complex datasets slower
- [ ] No crashes under load

### Dashboard Responsiveness
- [ ] Forms submit instantly
- [ ] Exports download < 1s
- [ ] Filters update < 100ms

---

## Summary

**Total Checks**: 100+

**Recommended Test Order**:
1. Setup Prerequisites (10 min)
2. Backend Setup & Validation (5 min)
3. Multi-Dataset Tests (10 min)
4. Privacy Features Tests (10 min)
5. Dashboard Features Tests (10 min)
6. Workflow Tests (15 min)
7. Database & Persistence (5 min)
8. Configuration Tests (5 min)
9. Documentation (5 min)
10. Error Handling (5 min)
11. Performance (5 min)

**Total Time**: ~90 minutes comprehensive validation

---

## ✅ Sign-Off

Once ALL checks pass:

```bash
# Commit verification
git add -A
git commit -m "✅ All feature tests passed - v1.2.0 ready"

# Tag release
git tag v1.2.0-release
```

**Status**: Ready for production deployment ✅

---

## Notes

- Tests assume fresh Docker Compose setup
- Adjust timeouts for slower hardware
- Dataset downloads require internet connection
- Some tests may vary by data transfer speed

**Questions?** Refer to QUICKSTART_NEW_FEATURES.md or check logs: `docker compose logs -f`


