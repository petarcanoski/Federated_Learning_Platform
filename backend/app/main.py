from __future__ import annotations

from contextlib import asynccontextmanager
import time

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import init_db
from .models import User
from .schemas import ExperimentCreateRequest, HospitalCreateRequest, LoginRequest
from .security import decode_access_token
from .services.experiment_service import ExperimentService

@asynccontextmanager
async def lifespan(_app: FastAPI):
    last_error: Exception | None = None
    initialized = False
    for _ in range(10):
        try:
            init_db()
            initialized = True
            break
        except Exception as exc:  # pragma: no cover - startup retry path
            last_error = exc
            time.sleep(1)
    if not initialized and last_error is not None:
        raise last_error
    yield


app = FastAPI(title="FedHealth-MK - Healthcare Federated Learning Platform", root_path="/api", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVICE = ExperimentService()
bearer = HTTPBearer(auto_error=False)


def _service_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    user = User.objects(id=user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


@app.get("/")
def root():
    return {"message": "FedHealth-MK API - login first, then use /docs for authenticated admin and hospital workflows"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login")
def login(request: LoginRequest):
    try:
        return SERVICE.login(request)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@app.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return _service_call(SERVICE.me, current_user)


@app.get("/admin/dashboard")
def admin_dashboard(current_user: User = Depends(get_current_user)):
    return _service_call(SERVICE.get_admin_dashboard, current_user)


@app.get("/admin/hospitals")
def admin_hospitals(current_user: User = Depends(get_current_user)):
    return _service_call(SERVICE.list_hospitals, current_user)


@app.post("/admin/hospitals")
def create_hospital_account(request: HospitalCreateRequest, current_user: User = Depends(get_current_user)):
    return _service_call(SERVICE.create_hospital_account, request, current_user)


@app.post("/admin/experiments")
def admin_create_experiment(request: ExperimentCreateRequest, current_user: User = Depends(get_current_user)):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only ADMIN can create experiments")
    return _service_call(SERVICE.create_experiment, request, current_user)


@app.post("/admin/experiments/{job_id}/fedavg")
def admin_run_fedavg(job_id: str, current_user: User = Depends(get_current_user)):
    return _service_call(SERVICE.admin_run_fedavg, current_user, job_id)


@app.post("/admin/experiments/{job_id}/broadcast")
def admin_broadcast(job_id: str, current_user: User = Depends(get_current_user)):
    return _service_call(SERVICE.admin_broadcast_model, current_user, job_id)


@app.get("/admin/experiments/{job_id}/export")
def admin_export(job_id: str, current_user: User = Depends(get_current_user)):
    return _service_call(SERVICE.export_results, current_user, job_id)


@app.get("/hospital/dashboard")
def hospital_dashboard(current_user: User = Depends(get_current_user)):
    return _service_call(SERVICE.get_hospital_dashboard, current_user)


@app.post("/hospital/train")
def hospital_train(job_id: str | None = None, current_user: User = Depends(get_current_user)):
    return _service_call(SERVICE.train_hospital_local_model, current_user, job_id)


@app.get("/experiments")
def experiments():
    return SERVICE.list_experiments()


@app.post("/start_experiment")
def start_experiment(req: ExperimentCreateRequest):
    return SERVICE.start_experiment(req)


@app.post("/experiments/{job_id}/round")
def aggregate_round(job_id: str):
    try:
        return SERVICE.run_round(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")


@app.post("/aggregate_round/{job_id}")
def aggregate_round_legacy(job_id: str):
    return aggregate_round(job_id)


@app.get("/status/{job_id}")
def status(job_id: str):
    try:
        return SERVICE.get_experiment(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")


@app.get("/global_model/{job_id}")
def global_model(job_id: str):
    try:
        experiment = SERVICE.get_experiment(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")
    return {"global_weights": experiment.current_weights, "round": experiment.current_round}


@app.get("/experiments/{job_id}")
def experiment_detail(job_id: str):
    try:
        return SERVICE.get_experiment(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")

