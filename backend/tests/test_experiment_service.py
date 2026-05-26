from backend.app.schemas import ExperimentCreateRequest
from backend.app.services.experiment_service import ExperimentService



def test_start_experiment_and_run_round_persists_history():
    service = ExperimentService()
    created = service.start_experiment(
        ExperimentCreateRequest(
            num_clients=3,
            rounds=2,
            epochs=1,
            samples_per_client=64,
            learning_rate=0.01,
            hidden_dim=8,
        )
    )

    assert created.status == 'running'
    assert created.current_round == 0
    assert created.rounds == []

    after_round = service.run_round(created.job_id)
    assert after_round.current_round == 1
    assert len(after_round.rounds) == 1
    assert after_round.rounds[0].total_samples > 0
    assert 0.0 <= after_round.rounds[0].accuracy <= 1.0

    loaded = service.get_experiment(created.job_id)
    assert loaded.job_id == created.job_id
    assert loaded.current_round == 1
    assert len(loaded.rounds) == 1


def test_secure_and_dp_flags_work_together():
    service = ExperimentService()
    created = service.start_experiment(
        ExperimentCreateRequest(
            num_clients=2,
            rounds=1,
            epochs=1,
            samples_per_client=32,
            learning_rate=0.01,
            hidden_dim=8,
            dp_enabled=True,
            clipping_norm=0.5,
            noise_multiplier=0.1,
            secure_aggregation_enabled=True,
        )
    )

    result = service.run_round(created.job_id)
    assert result.status == 'finished'
    assert result.rounds[0].client_metrics
    assert all(metric.client_id.startswith('client_') for metric in result.rounds[0].client_metrics)


def test_healthcare_experiment_serializes_hospital_states_on_create():
    service = ExperimentService()
    created = service.create_experiment(
        ExperimentCreateRequest(
            disease_type='sepsis',
            rounds=1,
            epochs=1,
            hidden_dim=8,
            hospital_codes=['ohrid', 'bitola', 'skopje'],
        )
    )

    assert len(created.hospital_states) == 3
    assert all(state.hospital_id is not None for state in created.hospital_states)
    assert all(state.last_trained_round == 0 for state in created.hospital_states)


