from fastapi.testclient import TestClient

from backend.app.main import app



def test_health_and_start_experiment_endpoints():
    client = TestClient(app)

    health = client.get('/health')
    assert health.status_code == 200
    assert health.json()['status'] == 'ok'

    response = client.post('/start_experiment', json={'num_clients': 2, 'rounds': 1, 'epochs': 1, 'samples_per_client': 32, 'learning_rate': 0.01, 'hidden_dim': 8})
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'running'
    assert payload['current_round'] == 0
    assert payload['job_id']

