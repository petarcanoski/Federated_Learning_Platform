# Federated Learning Platform

Enterprise-grade federated learning orchestration platform with PyTorch local training, persistent PostgreSQL experiment tracking, differential privacy accounting, and an interactive React dashboard.

## Features

### Core Capabilities
- **FedAvg Aggregation**: Weighted average of client model updates by sample count
- **Real PyTorch Training**: Local MNIST/CIFAR-10/synthetic dataset support with configurable models
- **PostgreSQL Persistence**: Full experiment, round, and client metric tracking
- **Privacy Research**: Differential privacy with formal epsilon/delta accounting, secure aggregation hooks
- **React Dashboard**: Live metrics visualization, experiment management, CSV/JSON export

### New in This Release
- **Multiple Dataset Support**: Synthetic, MNIST (28x28), and CIFAR-10 (32x32) with automatic partitioning
- **Formal DP Accounting**: RDP-based epsilon/delta computation following Opacus standards
- **Dashboard Enhancements**:
  - Live auto-refresh (3s polling)
  - Experiment filtering by status and dataset type
  - CSV/JSON export functionality
  - Privacy metric visualization (ε/δ)
- **Production Deployment**: Full guide for AWS RDS, Azure Database, Google Cloud SQL
- **Enhanced Privacy**: Compliant with differential privacy composition rules

## Architecture

```
frontend/                      # React + Vite dashboard
├── src/
│   ├── App.jsx               # Main dashboard with filters/export
│   ├── api.js                # HTTP client
│   └── components/
│       ├── ExperimentCharts.jsx
│       └── ClientMetricsTable.jsx
└── package.json

backend/                       # FastAPI + PyTorch orchestrator
├── app/
│   ├── main.py               # API endpoints
│   ├── models.py             # SQLAlchemy ORM (with DP accounting fields)
│   ├── schemas.py            # Pydantic request/response models
│   ├── ml/
│   │   ├── model.py          # SimpleClassifier (configurable input_dim)
│   │   ├── datasets.py       # Synthetic/MNIST/CIFAR-10 dataset loader
│   │   ├── trainer.py        # Local training loop
│   │   └── fedavg.py         # FedAvg aggregation + JSON serialization
│   ├── privacy/
│   │   ├── differential_privacy.py  # DP + RDP epsilon accounting
│   │   └── secure_aggregation.py    # Masking/unmasking protocol
│   ├── services/
│   │   └── experiment_service.py    # Orchestration logic
│   └── repositories/
│       └── experiment_repository.py # Data access layer
├── requirements.txt
└── Dockerfile

k8s/                           # Kubernetes manifests
├── namespace.yaml
├── backend-deployment.yaml
├── backend-service.yaml
├── backend-ingress.yaml
└── postgres-statefulset.yaml

docker-compose.yml             # Local orchestration
DEPLOYMENT.md                  # Production deployment guide
```

## Quick Start

### Prerequisites
- Docker & Docker Compose OR Python 3.10+ with venv
- PostgreSQL 13+ (managed or local)

### Option 1: Docker Compose (Recommended)

1. **Copy environment file**:
   ```bash
   cp backend/.env.example backend/.env
   ```

2. **Start stack** (includes PostgreSQL):
   ```bash
   docker compose up --build
   ```

3. **Access services**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Option 2: Local Development

1. **Backend setup**:
   ```bash
   cd backend
   python -m venv venv
   . venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   
   # Start PostgreSQL (Docker)
   docker run -d --name pg15 -e POSTGRES_PASSWORD=fl_pass -p 5432:5432 postgres:15
   
   # Run server
   uvicorn app.main:app --reload
   ```

2. **Frontend setup**:
   ```bash
   cd frontend
   cp .env.example .env.local   # optional: override VITE_BACKEND_URL
   npm install
   npm run dev
   ```

3. **Access services**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Usage Guide

### Starting an Experiment

1. Click **"Start Experiment"** with parameters:
   - **Clients**: Number of federated clients (1–50)
   - **Rounds**: Total federated rounds (1–100)
   - **Dataset**: Synthetic, MNIST, or CIFAR-10
   - **DP Settings**: Enable differential privacy with clipping/noise params
   - **Secure Aggregation**: Mask client updates during aggregation

2. Click **"Run One Round"** to execute one federated round (parallel client training + FedAvg aggregation)

3. **Monitor** in dashboard:
   - Live accuracy/loss curves
   - Per-round client metrics
   - Privacy epsilon/delta (if DP enabled)

### Filtering & Export

- **Filter experiments**: By status (running/finished) and dataset type
- **Auto-refresh**: Enable live polling every 3 seconds
- **Export**: Download round results as CSV or full experiment as JSON

### Privacy Metrics

When differential privacy is enabled:
- **ε (Epsilon)**: Privacy loss parameter (lower = stronger privacy)
- **δ (Delta)**: Failure probability (typically 1e-5 or 1e-6)
- Computed using RDP composition formula per Opacus standards

## API Reference

### Startup

```bash
POST /start_experiment
Content-Type: application/json

{
  "num_clients": 3,
  "rounds": 5,
  "epochs": 2,
  "samples_per_client": 128,
  "learning_rate": 0.01,
  "hidden_dim": 16,
  "dataset_type": "synthetic",  # NEW
  "dp_enabled": false,
  "clipping_norm": 1.0,
  "noise_multiplier": 0.0,
  "secure_aggregation_enabled": false
}

Response:
{
  "job_id": "UUID",
  "status": "running",
  "current_round": 0,
  "total_rounds": 5,
  "config": {...},
  "rounds": [],
  "current_weights": {...},
  "dp_epsilon": null,  # NEW: populated if DP enabled
  "dp_delta": null     # NEW
}
```

### Run Round

```bash
POST /experiments/{job_id}/round

Response:
{
  "job_id": "UUID",
  "current_round": 1,
  "rounds": [{
    "round_index": 1,
    "loss": 0.45,
    "accuracy": 0.78,
    "total_samples": 384,
    "client_metrics": [
      {
        "client_id": "client_1",
        "samples": 128,
        "loss": 0.50,
        "accuracy": 0.75
      },
      ...
    ]
  }],
  "dp_epsilon": 0.8234,  # NEW: RDP-composed epsilon
  "dp_delta": 1e-5       # NEW
}
```

See `backend/app/main.py` for full endpoint list.

## Configuration

### Environment Variables

**Backend** (`.env` or `docker-compose.yml`):
```dotenv
DATABASE_URL=postgresql://fl_user:fl_pass@postgres:5432/fl_db
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
```

**Frontend** (Vite — baked at build time):
```env
VITE_BACKEND_URL=http://localhost:8000
```
Copy `frontend/.env.example` to `frontend/.env.local` to override for local development.

### Privacy Tuning

For differential privacy experiments:
- **`clipping_norm`**: Max L2 norm of gradient (default 1.0). Lower = more noise.
- **`noise_multiplier`**: Noise σ relative to clipping norm (default 0.0 = disabled).
  - Example: `noise_multiplier=1.5` → σ = 1.5 × clipping_norm
  - Typical range: 0.5–2.0 for meaningful privacy

Epsilon is computed per round and composed across all rounds. Example:
- 5 rounds, noise_multiplier=1.0 → ε ≈ 0.8 at δ=1e-5
- Use `DEPLOYMENT.md` for production setup

## Testing

```bash
cd backend
pytest tests/ -v

# Or with coverage
pytest tests/ --cov=app --cov-report=html
```

**Test suites**:
- `test_api.py`: Endpoint health and experiment lifecycle
- `test_experiment_service.py`: Service logic, persistence, privacy flags
- `test_privacy_hooks.py`: DP and secure aggregation correctness

## Production Deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for:
- AWS RDS, Azure Database, Google Cloud SQL setup
- Kubernetes manifests and Helm configuration
- Security checklist (secrets, SSL, backups)
- Monitoring and logging best practices
- Performance tuning

Quick example:
```bash
# Set managed DB URL
export DATABASE_URL="postgresql://user:pass@rds-host:5432/fl_db"

# Deploy to K8s
kubectl apply -f k8s/namespace.yaml
kubectl create secret generic database-credentials --from-literal=DATABASE_URL="$DATABASE_URL" -n federated-learning
kubectl apply -f k8s/backend-deployment.yaml
```

## Roadmap

### Completed ✅
- Multi-dataset support (synthetic, MNIST, CIFAR-10)
- Formal DP accounting with RDP composition
- Dashboard filtering and export
- Live polling on frontend
- Production PostgreSQL documentation

### In Progress 🚀
- Fine-tuning model selection (ResNet-like architectures)
- Real-world datasets (FEMNIST, Shakespeare)
- Federated learning metrics (communication cost, convergence analysis)

### Future 📋
- Web3 federation (decentralized aggregation)
- Hardware acceleration (TPU support)
- Advanced privacy techniques (secure multi-party computation)
- Automated hyperparameter optimization
- Interactive privacy budget calculator

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit changes (`git commit -am 'Add feature'`)
4. Push to branch (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

MIT License - See LICENSE file for details

## Citation

If you use this platform in research, please cite:

```bibtex
@software{federated_learning_platform_2026,
  title={Federated Learning Platform},
  author={[Contributors]},
  year={2026},
  url={https://github.com/your-org/federated-learning-platform}
}
```

## Support

- **Issues**: GitHub Issues tracker
- **Discussions**: GitHub Discussions
- **Docs**: See README.md and in-code docstrings
- **Email**: [Contact info if applicable]

---

**Last Updated**: May 2026 | **Version**: 1.2.0

