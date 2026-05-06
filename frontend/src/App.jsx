import React, { useEffect, useMemo, useState } from 'react'
import './App.css'
import ExperimentCharts from './components/ExperimentCharts'
import ClientMetricsTable from './components/ClientMetricsTable'
import {
  broadcastModel,
  clearAuthToken,
  createExperiment,
  createHospitalAccount,
  exportResults,
  getAdminDashboard,
  getAuthToken,
  getExperiment,
  getHospitalDashboard,
  login,
  me,
  runFedAvg,
  setAuthToken,
  trainHospital,
} from './api'

const defaultLogin = { username: 'admin', password: 'admin123' }

const defaultExperimentForm = {
  disease_type: 'sepsis',
  rounds: 5,
  epochs: 2,
  learning_rate: 0.01,
  hidden_dim: 24,
  dp_enabled: true,
  clipping_norm: 1.0,
  noise_multiplier: 0.2,
  secure_aggregation_enabled: true,
  hospital_codes: 'ohrid,bitola,skopje',
}

const defaultHospitalForm = {
  code: 'tetovo',
  name: 'Tetovo Hospital',
  city: 'Tetovo',
  username: 'tetovo',
  password: 'hospital123',
}

function formatPct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return `${Math.round(Number(value) * 100)}%`
}

function formatFixed(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(digits)
}

function shortId(value) {
  return value ? `${value.slice(0, 8)}...` : '-'
}

function getErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(', ')
  return detail || err?.message || fallback
}

function StatusBadge({ status }) {
  const normalized = String(status || 'waiting').toLowerCase()
  return <span className={`status status-${normalized.replace(/\s+/g, '-')}`}>{status || 'waiting'}</span>
}

function StatTile({ label, value, detail, tone = 'blue' }) {
  return (
    <div className={`stat-tile stat-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  )
}

function Panel({ title, eyebrow, action, children, className = '' }) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-header">
        <div>
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
        </div>
        {action ? <div className="panel-action">{action}</div> : null}
      </div>
      {children}
    </section>
  )
}

function TextInput({ label, value, onChange, type = 'text', placeholder }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  )
}

function NumberInput({ label, value, onChange, step = '1' }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type="number" step={step} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  )
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="toggle-row">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  )
}

function ProgressBar({ value }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <div className="progress-track" aria-label={`${pct}% complete`}>
      <div className="progress-fill" style={{ width: `${pct}%` }} />
    </div>
  )
}

export default function App() {
  const [authReady, setAuthReady] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [user, setUser] = useState(null)
  const [adminDashboard, setAdminDashboard] = useState(null)
  const [hospitalDashboard, setHospitalDashboard] = useState(null)
  const [selectedJobId, setSelectedJobId] = useState('')
  const [selectedExperiment, setSelectedExperiment] = useState(null)
  const [loginForm, setLoginForm] = useState(defaultLogin)
  const [experimentForm, setExperimentForm] = useState(defaultExperimentForm)
  const [hospitalForm, setHospitalForm] = useState(defaultHospitalForm)

  const activeSummary = useMemo(() => {
    if (!adminDashboard?.experiments?.length) return null
    return adminDashboard.experiments.find((item) => item.job_id === selectedJobId) || adminDashboard.experiments[0]
  }, [adminDashboard, selectedJobId])

  const activeExperiment = selectedExperiment || activeSummary

  async function refreshSession() {
    const token = getAuthToken()
    if (!token) {
      setAuthReady(true)
      return
    }
    setLoading(true)
    setError('')
    try {
      const meResponse = await me()
      setUser(meResponse.user)
      if (meResponse.user.role === 'ADMIN') {
        const dashboard = await getAdminDashboard()
        const fallbackJobId = dashboard.experiments?.[0]?.job_id || ''
        setAdminDashboard(dashboard)
        setHospitalDashboard(null)
        setSelectedJobId((prev) => prev || fallbackJobId)
      } else {
        const dashboard = await getHospitalDashboard()
        setHospitalDashboard(dashboard)
        setAdminDashboard(null)
        setSelectedExperiment(null)
      }
    } catch (err) {
      clearAuthToken()
      setUser(null)
      setAdminDashboard(null)
      setHospitalDashboard(null)
      setSelectedExperiment(null)
      setError(getErrorMessage(err, 'Authentication expired'))
    } finally {
      setLoading(false)
      setAuthReady(true)
    }
  }

  useEffect(() => {
    refreshSession().catch(() => setAuthReady(true))
  }, [])

  useEffect(() => {
    if (!authReady || !user) return
    const interval = setInterval(() => {
      refreshSession().catch(() => null)
    }, 3000)
    return () => clearInterval(interval)
  }, [authReady, user?.id, user?.role])

  useEffect(() => {
    if (user?.role !== 'ADMIN' || !selectedJobId) {
      setSelectedExperiment(null)
      return
    }
    let cancelled = false
    getExperiment(selectedJobId)
      .then((experiment) => {
        if (!cancelled) setSelectedExperiment(experiment)
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err, 'Could not load experiment details'))
      })
    return () => {
      cancelled = true
    }
  }, [user?.role, selectedJobId, adminDashboard?.experiments?.length])

  async function handleLogin(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const result = await login(loginForm)
      setAuthToken(result.access_token)
      await refreshSession()
    } catch (err) {
      setError(getErrorMessage(err, 'Login failed'))
    } finally {
      setLoading(false)
    }
  }

  async function handleLogout() {
    clearAuthToken()
    setUser(null)
    setAdminDashboard(null)
    setHospitalDashboard(null)
    setSelectedJobId('')
    setSelectedExperiment(null)
  }

  async function handleCreateHospital() {
    setLoading(true)
    setError('')
    try {
      await createHospitalAccount(hospitalForm)
      await refreshSession()
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to create hospital account'))
    } finally {
      setLoading(false)
    }
  }

  async function handleCreateExperiment() {
    setLoading(true)
    setError('')
    try {
      const payload = {
        ...experimentForm,
        rounds: Number(experimentForm.rounds),
        epochs: Number(experimentForm.epochs),
        learning_rate: Number(experimentForm.learning_rate),
        hidden_dim: Number(experimentForm.hidden_dim),
        clipping_norm: Number(experimentForm.clipping_norm),
        noise_multiplier: Number(experimentForm.noise_multiplier),
        hospital_codes: experimentForm.hospital_codes.split(',').map((item) => item.trim()).filter(Boolean),
      }
      const created = await createExperiment(payload)
      setSelectedJobId(created.job_id)
      setSelectedExperiment(created)
      await refreshSession()
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to create experiment'))
    } finally {
      setLoading(false)
    }
  }

  async function handleTrainHospital() {
    setLoading(true)
    setError('')
    try {
      await trainHospital()
      await refreshSession()
    } catch (err) {
      setError(getErrorMessage(err, 'Training failed'))
    } finally {
      setLoading(false)
    }
  }

  async function handleRunFedAvg() {
    if (!activeExperiment?.job_id) return
    setLoading(true)
    setError('')
    try {
      const updated = await runFedAvg(activeExperiment.job_id)
      setSelectedExperiment(updated)
      await refreshSession()
    } catch (err) {
      setError(getErrorMessage(err, 'FedAvg failed'))
    } finally {
      setLoading(false)
    }
  }

  async function handleBroadcastModel() {
    if (!activeExperiment?.job_id) return
    setLoading(true)
    setError('')
    try {
      await broadcastModel(activeExperiment.job_id)
      const updated = await getExperiment(activeExperiment.job_id)
      setSelectedExperiment(updated)
      await refreshSession()
    } catch (err) {
      setError(getErrorMessage(err, 'Broadcast failed'))
    } finally {
      setLoading(false)
    }
  }

  async function handleExport(format) {
    if (!activeExperiment?.job_id) return
    try {
      const payload = await exportResults(activeExperiment.job_id)
      const blob = new Blob([format === 'csv' ? toCSV(payload) : JSON.stringify(payload, null, 2)], {
        type: format === 'csv' ? 'text/csv' : 'application/json',
      })
      const url = window.URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `fedhealth_mk_${activeExperiment.job_id.slice(0, 8)}.${format}`
      anchor.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError(getErrorMessage(err, 'Export failed'))
    }
  }

  function toCSV(payload) {
    const rows = [['job_id', 'round', 'status', 'disease_type', 'global_accuracy', 'dp_epsilon', 'round_progress']]
    rows.push([
      payload.job_id,
      payload.current_round,
      payload.status,
      payload.disease_type,
      payload.global_accuracy ?? '',
      payload.dp_epsilon ?? '',
      payload.round_progress ?? '',
    ])
    rows.push([])
    rows.push(['round_index', 'accuracy', 'loss', 'global_accuracy', 'total_samples'])
    ;(payload.rounds || []).forEach((round) => {
      rows.push([round.round_index, round.accuracy, round.loss, round.global_accuracy ?? '', round.total_samples])
    })
    return rows.map((row) => row.join(',')).join('\n')
  }

  if (!authReady || !user) {
    return (
      <LoginView
        loginForm={loginForm}
        setLoginForm={setLoginForm}
        loading={loading}
        error={error}
        onLogin={handleLogin}
      />
    )
  }

  return (
    <div className="app-shell">
      <TopBar user={user} loading={loading} onLogout={handleLogout} />
      <main className="workspace">
        {error ? <div className="alert alert-error">{error}</div> : null}
        {user.role === 'ADMIN' ? (
          <AdminView
            dashboard={adminDashboard}
            selectedJobId={selectedJobId}
            setSelectedJobId={setSelectedJobId}
            activeExperiment={activeExperiment}
            loading={loading}
            experimentForm={experimentForm}
            setExperimentForm={setExperimentForm}
            hospitalForm={hospitalForm}
            setHospitalForm={setHospitalForm}
            onCreateHospital={handleCreateHospital}
            onCreateExperiment={handleCreateExperiment}
            onRunFedAvg={handleRunFedAvg}
            onBroadcastModel={handleBroadcastModel}
            onExportCsv={() => handleExport('csv')}
            onExportJson={() => handleExport('json')}
          />
        ) : (
          <HospitalView dashboard={hospitalDashboard} loading={loading} onTrain={handleTrainHospital} />
        )}
      </main>
    </div>
  )
}

function LoginView({ loginForm, setLoginForm, loading, error, onLogin }) {
  return (
    <main className="login-screen">
      <section className="login-card">
        <div className="brand-mark">FH</div>
        <p className="eyebrow">Federated Learning Platform</p>
        <h1>FedHealth-MK</h1>
        <p className="login-copy">Operational workspace for ministry-led healthcare model training across hospital sites.</p>
        <form className="form-stack" onSubmit={onLogin}>
          <TextInput label="Username" value={loginForm.username} onChange={(value) => setLoginForm((prev) => ({ ...prev, username: value }))} />
          <TextInput label="Password" type="password" value={loginForm.password} onChange={(value) => setLoginForm((prev) => ({ ...prev, password: value }))} />
          <button className="btn btn-primary" type="submit" disabled={loading}>{loading ? 'Signing in...' : 'Login'}</button>
        </form>
        <p className="hint">Demo: admin / admin123 or ohrid / hospital123</p>
        {error ? <div className="alert alert-error">{error}</div> : null}
      </section>
    </main>
  )
}

function TopBar({ user, loading, onLogout }) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <div className="brand-mark">FH</div>
        <div>
          <h1>FedHealth-MK</h1>
          <p>{user.role === 'ADMIN' ? 'Ministry control center' : 'Hospital training workspace'}</p>
        </div>
      </div>
      <div className="topbar-actions">
        <StatusBadge status={user.role} />
        <span className="user-chip">{user.username}</span>
        <button className="btn btn-secondary" onClick={onLogout} disabled={loading}>Logout</button>
      </div>
    </header>
  )
}

function AdminView({
  dashboard,
  selectedJobId,
  setSelectedJobId,
  activeExperiment,
  loading,
  experimentForm,
  setExperimentForm,
  hospitalForm,
  setHospitalForm,
  onCreateHospital,
  onCreateExperiment,
  onRunFedAvg,
  onBroadcastModel,
  onExportCsv,
  onExportJson,
}) {
  const experiments = dashboard?.experiments || []
  const hospitalStates = activeExperiment?.hospital_states || []
  const readyToAggregate = hospitalStates.length > 0 && hospitalStates.every((item) => item.status === 'weights sent' || item.status === 'done')
  const trainedCount = hospitalStates.filter((item) => item.weights_json).length

  return (
    <div className="screen-grid">
      <section className="hero-panel admin-hero">
        <div>
          <p className="eyebrow">Admin Section</p>
          <h2>Coordinate experiments, hospitals, aggregation, and model delivery.</h2>
        </div>
        <div className="hero-status">
          <StatusBadge status={activeExperiment?.status || 'no experiment'} />
          <span>{activeExperiment?.job_id ? shortId(activeExperiment.job_id) : 'Create an experiment to begin'}</span>
        </div>
      </section>

      <div className="stats-grid">
        <StatTile label="Hospitals enrolled" value={hospitalStates.length || dashboard?.hospitals?.length || 0} detail={`${trainedCount} sent weights`} tone="blue" />
        <StatTile label="Round progress" value={activeExperiment?.round_progress || '0/0'} detail="Selected experiment" tone="green" />
        <StatTile label="Global accuracy" value={formatPct(activeExperiment?.global_accuracy)} detail="Latest model score" tone="amber" />
        <StatTile label="Privacy epsilon" value={formatFixed(activeExperiment?.dp_epsilon)} detail="DP accountant" tone="violet" />
      </div>

      <div className="admin-layout">
        <aside className="side-column">
          <ExperimentForm
            form={experimentForm}
            setForm={setExperimentForm}
            loading={loading}
            onCreate={onCreateExperiment}
          />
          <HospitalAccountForm
            form={hospitalForm}
            setForm={setHospitalForm}
            loading={loading}
            onCreate={onCreateHospital}
          />
        </aside>

        <section className="main-column">
          <Panel
            title="Federated Control"
            eyebrow="Selected experiment"
            action={<StatusBadge status={activeExperiment?.status || 'waiting'} />}
          >
            <div className="control-grid">
              <div>
                <dl className="detail-list">
                  <div><dt>Experiment</dt><dd>{shortId(activeExperiment?.job_id)}</dd></div>
                  <div><dt>Disease</dt><dd>{activeExperiment?.disease_type || '-'}</dd></div>
                  <div><dt>Rounds</dt><dd>{activeExperiment?.round_progress || '0/0'}</dd></div>
                  <div><dt>Hospitals ready</dt><dd>{trainedCount}/{hospitalStates.length || 0}</dd></div>
                </dl>
              </div>
              <div className="button-cluster">
                <button className="btn btn-primary" disabled={!activeExperiment?.job_id || loading || !readyToAggregate} onClick={onRunFedAvg}>Run FedAvg</button>
                <button className="btn btn-secondary" disabled={!activeExperiment?.job_id || loading} onClick={onBroadcastModel}>Broadcast Model</button>
                <button className="btn btn-secondary" disabled={!activeExperiment?.job_id} onClick={onExportCsv}>Export CSV</button>
                <button className="btn btn-secondary" disabled={!activeExperiment?.job_id} onClick={onExportJson}>Export JSON</button>
              </div>
            </div>
          </Panel>

          <Panel title="Hospital Status Board" eyebrow="Live training state">
            <HospitalStateTable states={hospitalStates} />
          </Panel>

          <div className="two-column">
            <Panel title="Experiments" eyebrow={`${experiments.length} total`}>
              <ExperimentList experiments={experiments} selectedJobId={selectedJobId} onSelect={setSelectedJobId} />
            </Panel>
            <Panel title="Configuration" eyebrow="Current run">
              <ConfigSummary experiment={activeExperiment} />
            </Panel>
          </div>

          <ExperimentCharts rounds={activeExperiment?.rounds || []} />
          <ClientMetricsTable round={activeExperiment?.rounds?.[activeExperiment.rounds.length - 1]} />
        </section>
      </div>
    </div>
  )
}

function ExperimentForm({ form, setForm, loading, onCreate }) {
  return (
    <Panel title="Create Experiment" eyebrow="Round setup">
      <div className="form-stack">
        <TextInput label="Disease type" value={form.disease_type} onChange={(value) => setForm((prev) => ({ ...prev, disease_type: value }))} />
        <TextInput label="Hospital codes" value={form.hospital_codes} onChange={(value) => setForm((prev) => ({ ...prev, hospital_codes: value }))} />
        <div className="form-grid">
          <NumberInput label="Rounds" value={form.rounds} onChange={(value) => setForm((prev) => ({ ...prev, rounds: value }))} />
          <NumberInput label="Epochs" value={form.epochs} onChange={(value) => setForm((prev) => ({ ...prev, epochs: value }))} />
          <NumberInput label="Learning rate" value={form.learning_rate} step="0.001" onChange={(value) => setForm((prev) => ({ ...prev, learning_rate: value }))} />
          <NumberInput label="Hidden dim" value={form.hidden_dim} onChange={(value) => setForm((prev) => ({ ...prev, hidden_dim: value }))} />
          <NumberInput label="Clip norm" value={form.clipping_norm} step="0.1" onChange={(value) => setForm((prev) => ({ ...prev, clipping_norm: value }))} />
          <NumberInput label="Noise" value={form.noise_multiplier} step="0.05" onChange={(value) => setForm((prev) => ({ ...prev, noise_multiplier: value }))} />
        </div>
        <Toggle label="Differential privacy" checked={form.dp_enabled} onChange={(checked) => setForm((prev) => ({ ...prev, dp_enabled: checked }))} />
        <Toggle label="Secure aggregation" checked={form.secure_aggregation_enabled} onChange={(checked) => setForm((prev) => ({ ...prev, secure_aggregation_enabled: checked }))} />
        <button className="btn btn-primary" onClick={onCreate} disabled={loading}>Create Experiment</button>
      </div>
    </Panel>
  )
}

function HospitalAccountForm({ form, setForm, loading, onCreate }) {
  return (
    <Panel title="Hospital Account" eyebrow="Provision access">
      <div className="form-stack">
        <TextInput label="Code" value={form.code} onChange={(value) => setForm((prev) => ({ ...prev, code: value }))} />
        <TextInput label="Name" value={form.name} onChange={(value) => setForm((prev) => ({ ...prev, name: value }))} />
        <TextInput label="City" value={form.city} onChange={(value) => setForm((prev) => ({ ...prev, city: value }))} />
        <TextInput label="Username" value={form.username} onChange={(value) => setForm((prev) => ({ ...prev, username: value }))} />
        <TextInput label="Temporary password" type="password" value={form.password} onChange={(value) => setForm((prev) => ({ ...prev, password: value }))} />
        <button className="btn btn-secondary" onClick={onCreate} disabled={loading}>Create Hospital</button>
      </div>
    </Panel>
  )
}

function HospitalStateTable({ states }) {
  if (!states.length) return <EmptyState title="No hospitals enrolled" detail="Create or select an experiment to see hospital states." />
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>Hospital</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Samples</th>
            <th>Accuracy</th>
            <th>Weights</th>
            <th>Notification</th>
          </tr>
        </thead>
        <tbody>
          {states.map((item) => (
            <tr key={`${item.hospital_id}-${item.hospital_code}`}>
              <td>
                <strong>{item.hospital_name}</strong>
                <small>{item.hospital_code}</small>
              </td>
              <td><StatusBadge status={item.status} /></td>
              <td><ProgressBar value={item.training_progress} /></td>
              <td>{item.sample_count}</td>
              <td>{formatPct(item.local_accuracy)}</td>
              <td>{item.weights_json ? 'Received' : 'Pending'}</td>
              <td className="muted-cell">{item.notification || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ExperimentList({ experiments, selectedJobId, onSelect }) {
  if (!experiments.length) return <EmptyState title="No experiments" detail="Create the first experiment from the setup panel." />
  return (
    <div className="experiment-list">
      {experiments.map((item) => (
        <button className={`experiment-row ${selectedJobId === item.job_id ? 'is-active' : ''}`} key={item.job_id} onClick={() => onSelect(item.job_id)}>
          <span>
            <strong>{shortId(item.job_id)}</strong>
            <small>{item.disease_type} - {item.round_progress}</small>
          </span>
          <StatusBadge status={item.status} />
        </button>
      ))}
    </div>
  )
}

function ConfigSummary({ experiment }) {
  const config = experiment?.config || {}
  return (
    <dl className="detail-list compact">
      <div><dt>Model</dt><dd>{experiment?.model_name || 'simple_classifier'}</dd></div>
      <div><dt>Input dim</dt><dd>{config.input_dim ?? '-'}</dd></div>
      <div><dt>Hidden dim</dt><dd>{config.hidden_dim ?? '-'}</dd></div>
      <div><dt>Learning rate</dt><dd>{config.learning_rate ?? '-'}</dd></div>
      <div><dt>DP enabled</dt><dd>{config.dp_enabled ? 'Yes' : 'No'}</dd></div>
      <div><dt>Secure agg</dt><dd>{config.secure_aggregation_enabled ? 'Yes' : 'No'}</dd></div>
    </dl>
  )
}

function HospitalView({ dashboard, loading, onTrain }) {
  const hospital = dashboard?.hospital
  const user = dashboard?.user
  const active = dashboard?.active_experiment
  const stats = dashboard?.dataset_stats
  const previous = Number(active?.previous_accuracy || 0)
  const next = Number(active?.new_accuracy || 0)
  const improvement = next - previous
  const status = active?.status || hospital?.status || 'waiting'
  const progress = status === 'weights sent' || status === 'done' ? 100 : status === 'training' ? 55 : 0

  return (
    <div className="screen-grid">
      <section className="hero-panel hospital-hero">
        <div>
          <p className="eyebrow">Hospital Section</p>
          <h2>{hospital?.name || 'Hospital'} local training workspace.</h2>
        </div>
        <div className="hero-status">
          <StatusBadge status={status} />
          <span>{user?.username}</span>
        </div>
      </section>

      <div className="stats-grid">
        <StatTile label="Patients" value={stats?.num_patients ?? '-'} detail="Local records" tone="blue" />
        <StatTile label="Columns" value={stats?.num_columns ?? '-'} detail="Dataset features" tone="green" />
        <StatTile label="Local accuracy" value={formatPct(active?.local_accuracy)} detail="After local training" tone="amber" />
        <StatTile label="Global accuracy" value={formatPct(active?.global_accuracy)} detail="Ministry model" tone="violet" />
      </div>

      <div className="hospital-layout">
        <Panel title="Training Console" eyebrow="Local operation">
          <div className="training-console">
            <div className="training-ring">
              <strong>{progress}%</strong>
              <span>progress</span>
            </div>
            <div className="training-details">
              <dl className="detail-list">
                <div><dt>Hospital</dt><dd>{hospital?.name || '-'}</dd></div>
                <div><dt>City</dt><dd>{hospital?.city || '-'}</dd></div>
                <div><dt>Round</dt><dd>{active?.round_progress || '0/0'}</dd></div>
                <div><dt>Disease</dt><dd>{active?.disease_type || stats?.disease_type || '-'}</dd></div>
              </dl>
              <ProgressBar value={progress} />
              <button className="btn btn-primary" onClick={onTrain} disabled={loading}>Train Local Model</button>
            </div>
          </div>
        </Panel>

        <Panel title="Ministry Feedback" eyebrow="Model update">
          <div className="feedback-grid">
            <div className="feedback-number">
              <span>Improvement</span>
              <strong className={improvement >= 0 ? 'positive' : 'negative'}>{improvement >= 0 ? '+' : ''}{formatPct(improvement)}</strong>
            </div>
            <dl className="detail-list compact">
              <div><dt>Previous</dt><dd>{formatPct(active?.previous_accuracy)}</dd></div>
              <div><dt>New</dt><dd>{formatPct(active?.new_accuracy)}</dd></div>
              <div><dt>Notification</dt><dd>{active?.notification || 'Waiting for aggregation'}</dd></div>
            </dl>
          </div>
        </Panel>

        <Panel title="Dataset Snapshot" eyebrow="Local data">
          <div className="dataset-chips">
            {(stats?.columns || []).map((column) => <span key={column}>{column}</span>)}
          </div>
          <dl className="detail-list compact">
            <div><dt>Hospital code</dt><dd>{stats?.hospital_code || hospital?.code || '-'}</dd></div>
            <div><dt>Disease</dt><dd>{stats?.disease_type || hospital?.disease_type || '-'}</dd></div>
            <div><dt>Rows</dt><dd>{stats?.num_patients ?? '-'}</dd></div>
            <div><dt>Features</dt><dd>{stats?.num_columns ?? '-'}</dd></div>
          </dl>
        </Panel>

        <Panel title="Workflow State" eyebrow="What happens next">
          <ol className="step-list">
            <li className={progress >= 0 ? 'done' : ''}>Receive selected global model</li>
            <li className={progress >= 55 ? 'done' : ''}>Train on local hospital data</li>
            <li className={progress >= 100 ? 'done' : ''}>Send model weights to Ministry</li>
            <li className={status === 'done' ? 'done' : ''}>Receive improved global model</li>
          </ol>
        </Panel>
      </div>
    </div>
  )
}

function EmptyState({ title, detail }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  )
}
