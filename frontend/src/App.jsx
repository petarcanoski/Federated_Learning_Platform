import React, { useEffect, useMemo, useState } from 'react'
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
  getHospitalDashboard,
  login,
  me,
  runFedAvg,
  setAuthToken,
  trainHospital,
} from './api'

const defaultLogin = {
  username: 'admin',
  password: 'admin123',
}

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
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return `${Math.round(Number(value) * 100)}%`
}

function formatFixed(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Number(value).toFixed(digits)
}

function Card({ title, value, subtitle, accent = '#2563eb' }) {
  return (
    <div style={{ background: '#fff', borderRadius: 14, padding: 16, boxShadow: '0 1px 4px rgba(0,0,0,0.08)', borderTop: `4px solid ${accent}` }}>
      <div style={{ fontSize: 12, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.8 }}>{title}</div>
      <div style={{ fontSize: 24, fontWeight: 800, marginTop: 8 }}>{value}</div>
      {subtitle ? <div style={{ marginTop: 6, fontSize: 13, color: '#6b7280' }}>{subtitle}</div> : null}
    </div>
  )
}

function Section({ title, action, children }) {
  return (
    <div style={{ background: '#fff', borderRadius: 14, padding: 18, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        {action}
      </div>
      {children}
    </div>
  )
}

function TextInput({ label, value, onChange, type = 'text', placeholder }) {
  return (
    <label style={{ display: 'grid', gap: 6, fontSize: 13 }}>
      <span style={{ color: '#374151', fontWeight: 600 }}>{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #d1d5db', fontSize: 14 }}
      />
    </label>
  )
}

function NumberInput({ label, value, onChange, step = '1' }) {
  return (
    <label style={{ display: 'grid', gap: 6, fontSize: 13 }}>
      <span style={{ color: '#374151', fontWeight: 600 }}>{label}</span>
      <input
        type="number"
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #d1d5db', fontSize: 14 }}
      />
    </label>
  )
}

function ProgressBar({ value }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <div style={{ width: '100%', height: 12, background: '#e5e7eb', borderRadius: 999, overflow: 'hidden' }}>
      <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, #2563eb, #10b981)', transition: 'width 300ms ease' }} />
    </div>
  )
}

function StatusBadge({ status }) {
  const colorMap = {
    waiting: '#f59e0b',
    training: '#2563eb',
    'weights sent': '#8b5cf6',
    done: '#10b981',
    'aggregation pending': '#f97316',
    aggregated: '#14b8a6',
    finished: '#10b981',
  }
  const color = colorMap[status] || '#6b7280'
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 999, background: `${color}15`, color, fontSize: 12, fontWeight: 700 }}>
      {status}
    </span>
  )
}

function compareAccuracy(state) {
  const previous = Number(state?.previous_accuracy || 0)
  const next = Number(state?.new_accuracy || 0)
  const improvement = next - previous
  return { previous, next, improvement }
}

export default function App() {
  const [authReady, setAuthReady] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [user, setUser] = useState(null)
  const [adminDashboard, setAdminDashboard] = useState(null)
  const [hospitalDashboard, setHospitalDashboard] = useState(null)
  const [selectedJobId, setSelectedJobId] = useState('')
  const [loginForm, setLoginForm] = useState(defaultLogin)
  const [experimentForm, setExperimentForm] = useState(defaultExperimentForm)
  const [hospitalForm, setHospitalForm] = useState(defaultHospitalForm)

  const activeExperiment = useMemo(() => {
    if (!adminDashboard?.experiments?.length) return null
    return adminDashboard.experiments.find((item) => item.job_id === selectedJobId) || adminDashboard.experiments[0]
  }, [adminDashboard, selectedJobId])

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
        setAdminDashboard(dashboard)
        setHospitalDashboard(null)
        setSelectedJobId((prev) => prev || dashboard.experiments?.[0]?.job_id || '')
      } else {
        const dashboard = await getHospitalDashboard()
        setHospitalDashboard(dashboard)
        setAdminDashboard(null)
      }
    } catch (err) {
      clearAuthToken()
      setUser(null)
      setAdminDashboard(null)
      setHospitalDashboard(null)
      setError(err?.response?.data?.detail || err?.message || 'Authentication expired')
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

  async function handleLogin(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const result = await login(loginForm)
      setAuthToken(result.access_token)
      await refreshSession()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Login failed')
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
  }

  async function handleCreateHospital() {
    setLoading(true)
    setError('')
    try {
      await createHospitalAccount(hospitalForm)
      await refreshSession()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create hospital account')
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
        hospital_codes: experimentForm.hospital_codes
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      }
      const created = await createExperiment(payload)
      setSelectedJobId(created.job_id)
      await refreshSession()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create experiment')
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
      setError(err?.response?.data?.detail || err?.message || 'Training failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleRunFedAvg() {
    if (!activeExperiment?.job_id) return
    setLoading(true)
    setError('')
    try {
      await runFedAvg(activeExperiment.job_id)
      await refreshSession()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'FedAvg failed')
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
      await refreshSession()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Broadcast failed')
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
      setError(err?.response?.data?.detail || err?.message || 'Export failed')
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
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'linear-gradient(180deg, #eff6ff, #f8fafc)', color: '#111827', padding: 24 }}>
        <div style={{ background: '#fff', borderRadius: 18, padding: 28, boxShadow: '0 20px 40px rgba(0,0,0,0.08)', width: 'min(520px, 100%)' }}>
          <h1 style={{ marginTop: 0, marginBottom: 8 }}>FedHealth-MK</h1>
          <p style={{ marginTop: 0, color: '#6b7280' }}>
            Research simulation platform for healthcare federated learning. Login first to continue.
          </p>
          <form onSubmit={handleLogin} style={{ display: 'grid', gap: 14 }}>
            <TextInput label="Username" value={loginForm.username} onChange={(value) => setLoginForm((prev) => ({ ...prev, username: value }))} />
            <TextInput label="Password" type="password" value={loginForm.password} onChange={(value) => setLoginForm((prev) => ({ ...prev, password: value }))} />
            <button type="submit" disabled={loading} style={primaryButtonStyle}>
              {loading ? 'Signing in…' : 'Login'}
            </button>
          </form>
          <div style={{ marginTop: 14, fontSize: 13, color: '#6b7280', lineHeight: 1.5 }}>
            Demo credentials: <strong>admin / admin123</strong> or hospital users like <strong>ohrid / hospital123</strong>.
          </div>
          {error ? <div style={{ marginTop: 14, padding: 12, borderRadius: 10, background: '#fef2f2', color: '#b91c1c' }}>{error}</div> : null}
        </div>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f3f4f6', color: '#111827' }}>
      <div style={{ maxWidth: 1500, margin: '0 auto', padding: 24 }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, marginBottom: 24 }}>
          <div>
            <h1 style={{ margin: 0 }}>FedHealth-MK</h1>
            <p style={{ margin: '8px 0 0', color: '#6b7280', maxWidth: 900 }}>
              Healthcare federated learning simulation for Ministry of Health and hospitals in Ohrid, Bitola, and Skopje.
              Local training is simulated on one machine but architecturally represents separate hospital sites in production.
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ marginBottom: 8 }}><StatusBadge status={user.role} /></div>
            <button onClick={handleLogout} style={secondaryButtonStyle}>Logout</button>
          </div>
        </header>

        {error ? (
          <div style={{ marginBottom: 16, padding: 12, background: '#fef2f2', color: '#b91c1c', borderRadius: 10 }}>
            {error}
          </div>
        ) : null}

        {user.role === 'ADMIN' ? (
          <AdminView
            user={user}
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
          <HospitalView
            user={user}
            dashboard={hospitalDashboard}
            loading={loading}
            onTrain={handleTrainHospital}
          />
        )}
      </div>
    </div>
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
  const hospitals = dashboard?.hospitals || []
  const experiments = dashboard?.experiments || []
  const selectedExperiment = activeExperiment
  const globalAccuracy = selectedExperiment?.global_accuracy
  const epsilon = selectedExperiment?.dp_epsilon
  const roundProgress = selectedExperiment?.round_progress || '0/0'
  const readyToAggregate = hospitals.length > 0 && hospitals.every((item) => item.status === 'weights sent' || item.status === 'done')

  return (
    <div style={{ display: 'grid', gap: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 16 }}>
        <Card title="Hospitals" value={hospitals.length} subtitle="Real-time status from all sites" accent="#2563eb" />
        <Card title="Selected round" value={roundProgress} subtitle="Round progress for current experiment" accent="#10b981" />
        <Card title="Global accuracy" value={formatPct(globalAccuracy)} subtitle="After aggregation / distribution" accent="#f59e0b" />
        <Card title="Privacy ε" value={formatFixed(epsilon)} subtitle="Differential privacy accounting" accent="#8b5cf6" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '380px minmax(0, 1fr)', gap: 24, alignItems: 'start' }}>
        <div style={{ display: 'grid', gap: 16 }}>
          <Section title="Create hospital account">
            <div style={{ display: 'grid', gap: 12 }}>
              <TextInput label="Hospital code" value={hospitalForm.code} onChange={(value) => setHospitalForm((prev) => ({ ...prev, code: value }))} />
              <TextInput label="Hospital name" value={hospitalForm.name} onChange={(value) => setHospitalForm((prev) => ({ ...prev, name: value }))} />
              <TextInput label="City" value={hospitalForm.city} onChange={(value) => setHospitalForm((prev) => ({ ...prev, city: value }))} />
              <TextInput label="Login username" value={hospitalForm.username} onChange={(value) => setHospitalForm((prev) => ({ ...prev, username: value }))} />
              <TextInput label="Temporary password" type="password" value={hospitalForm.password} onChange={(value) => setHospitalForm((prev) => ({ ...prev, password: value }))} />
              <button onClick={onCreateHospital} disabled={loading} style={primaryButtonStyle}>Create hospital</button>
            </div>
          </Section>

          <Section title="Create experiment / round setup">
            <div style={{ display: 'grid', gap: 12 }}>
              <TextInput label="Disease type" value={experimentForm.disease_type} onChange={(value) => setExperimentForm((prev) => ({ ...prev, disease_type: value }))} />
              <TextInput label="Hospitals (comma-separated codes)" value={experimentForm.hospital_codes} onChange={(value) => setExperimentForm((prev) => ({ ...prev, hospital_codes: value }))} />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                <NumberInput label="Rounds" value={experimentForm.rounds} onChange={(value) => setExperimentForm((prev) => ({ ...prev, rounds: value }))} />
                <NumberInput label="Epochs" value={experimentForm.epochs} onChange={(value) => setExperimentForm((prev) => ({ ...prev, epochs: value }))} />
                <NumberInput label="Learning rate" value={experimentForm.learning_rate} step="0.001" onChange={(value) => setExperimentForm((prev) => ({ ...prev, learning_rate: value }))} />
                <NumberInput label="Hidden dim" value={experimentForm.hidden_dim} onChange={(value) => setExperimentForm((prev) => ({ ...prev, hidden_dim: value }))} />
                <NumberInput label="Clipping norm" value={experimentForm.clipping_norm} step="0.1" onChange={(value) => setExperimentForm((prev) => ({ ...prev, clipping_norm: value }))} />
                <NumberInput label="Noise multiplier" value={experimentForm.noise_multiplier} step="0.05" onChange={(value) => setExperimentForm((prev) => ({ ...prev, noise_multiplier: value }))} />
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
                <input type="checkbox" checked={experimentForm.dp_enabled} onChange={(e) => setExperimentForm((prev) => ({ ...prev, dp_enabled: e.target.checked }))} />
                Enable differential privacy
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
                <input type="checkbox" checked={experimentForm.secure_aggregation_enabled} onChange={(e) => setExperimentForm((prev) => ({ ...prev, secure_aggregation_enabled: e.target.checked }))} />
                Enable secure aggregation
              </label>
              <button onClick={onCreateExperiment} disabled={loading} style={primaryButtonStyle}>Create experiment</button>
            </div>
          </Section>
        </div>

        <div style={{ display: 'grid', gap: 16 }}>
          <Section
            title="Hospital status board"
            action={<span style={{ color: '#6b7280', fontSize: 13 }}>waiting / training / weights sent / done</span>}
          >
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>
                    <th style={tableTh}>Hospital</th>
                    <th style={tableTh}>Status</th>
                    <th style={tableTh}>Progress</th>
                    <th style={tableTh}>Local accuracy</th>
                    <th style={tableTh}>Weights</th>
                    <th style={tableTh}>Notification</th>
                  </tr>
                </thead>
                <tbody>
                  {hospitals.map((item) => {
                    const weightsReceived = item.weights_json ? '✅' : '⏳'
                    return (
                      <tr key={`${item.hospital_code}-${item.hospital_id}`} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td style={tableTd}>
                          <div style={{ fontWeight: 700 }}>{item.hospital_name}</div>
                          <div style={{ color: '#6b7280', fontSize: 12 }}>{item.hospital_code}</div>
                        </td>
                        <td style={tableTd}><StatusBadge status={item.status} /></td>
                        <td style={tableTd}><ProgressBar value={item.training_progress} /></td>
                        <td style={tableTd}>{formatPct(item.local_accuracy)}</td>
                        <td style={tableTd}>{weightsReceived}</td>
                        <td style={tableTd}>
                          <div style={{ fontSize: 13 }}>{item.notification || '—'}</div>
                          {item.previous_accuracy !== null && item.new_accuracy !== null ? (
                            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                              Previous {formatPct(item.previous_accuracy)} → New {formatPct(item.new_accuracy)}
                            </div>
                          ) : null}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Section>

          <Section
            title="Federated control center"
            action={<span style={{ color: '#6b7280', fontSize: 13 }}>Research simulation; no raw data leaves hospitals</span>}
          >
            <div style={{ display: 'grid', gap: 12 }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                <button disabled={!selectedExperiment?.job_id || loading || !readyToAggregate} onClick={onRunFedAvg} style={primaryButtonStyle}>
                  Run FedAvg &amp; Improve Global Model
                </button>
                <button disabled={!selectedExperiment?.job_id || loading} onClick={onBroadcastModel} style={secondaryButtonStyle}>
                  Send Improved Model to All Hospitals
                </button>
                <button disabled={!selectedExperiment?.job_id} onClick={onExportCsv} style={secondaryButtonStyle}>Export CSV</button>
                <button disabled={!selectedExperiment?.job_id} onClick={onExportJson} style={secondaryButtonStyle}>Export JSON</button>
              </div>
              <div style={{ color: '#6b7280', fontSize: 13 }}>
                Round progress: <strong>{roundProgress}</strong> • Global accuracy: <strong>{formatPct(globalAccuracy)}</strong> • Privacy epsilon: <strong>{formatFixed(epsilon)}</strong>
              </div>
            </div>
          </Section>

          <Section title="Experiments">
            <div style={{ display: 'grid', gap: 8, maxHeight: 240, overflowY: 'auto' }}>
              {experiments.map((item) => (
                <button
                  key={item.job_id}
                  onClick={() => setSelectedJobId(item.job_id)}
                  style={{
                    textAlign: 'left',
                    padding: 12,
                    borderRadius: 10,
                    border: selectedJobId === item.job_id ? '2px solid #2563eb' : '1px solid #e5e7eb',
                    background: '#fff',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                    <strong>{item.job_id.slice(0, 8)}…</strong>
                    <StatusBadge status={item.status} />
                  </div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                    {item.disease_type} • {item.round_progress} • accuracy {formatPct(item.global_accuracy)}
                  </div>
                </button>
              ))}
            </div>
          </Section>

          {selectedExperiment ? (
            <>
              <Section title="Current experiment summary">
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 13, lineHeight: 1.5 }}>
{JSON.stringify(
  {
    job_id: selectedExperiment.job_id,
    status: selectedExperiment.status,
    disease_type: selectedExperiment.disease_type,
    current_round: selectedExperiment.current_round,
    total_rounds: selectedExperiment.total_rounds,
    round_progress: selectedExperiment.round_progress,
    global_accuracy: selectedExperiment.global_accuracy,
    dp_epsilon: selectedExperiment.dp_epsilon,
    dp_delta: selectedExperiment.dp_delta,
    hospitals: selectedExperiment.hospital_states?.map((item) => ({
      hospital: item.hospital_name,
      status: item.status,
      local_accuracy: item.local_accuracy,
      weights_sent: Boolean(item.weights_json),
    })),
  },
  null,
  2,
)}
                </pre>
              </Section>
              <ExperimentCharts rounds={selectedExperiment.rounds} />
              <ClientMetricsTable round={selectedExperiment.rounds?.[selectedExperiment.rounds.length - 1]} />
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function HospitalView({ dashboard, loading, onTrain }) {
  const hospital = dashboard?.hospital
  const user = dashboard?.user
  const active = dashboard?.active_experiment
  const stats = dashboard?.dataset_stats
  const comparison = compareAccuracy(active)
  const improvement = Number(comparison.improvement || 0)

  return (
    <div style={{ display: 'grid', gap: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 16 }}>
        <Card title="Hospital" value={hospital?.name || '—'} subtitle={`${hospital?.city || '—'} • ${user?.username || ''}`} accent="#2563eb" />
        <Card title="Patients" value={stats?.num_patients ?? '—'} subtitle="Local dataset partition only" accent="#10b981" />
        <Card title="Columns" value={stats?.num_columns ?? '—'} subtitle="age, temperature, heart_rate, ..." accent="#f59e0b" />
        <Card title="Local accuracy" value={formatPct(active?.local_accuracy)} subtitle="Before Ministry aggregation" accent="#8b5cf6" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '360px minmax(0, 1fr)', gap: 24, alignItems: 'start' }}>
        <Section title="Hospital workspace">
          <div style={{ display: 'grid', gap: 12 }}>
            <div><strong>Status:</strong> <StatusBadge status={active?.status || hospital?.status || 'waiting'} /></div>
            <div><strong>Round:</strong> {active?.round_progress || '0/0'}</div>
            <div><strong>Training progress:</strong></div>
            <ProgressBar value={active?.status === 'training' ? 55 : active?.status === 'weights sent' ? 100 : 0} />
            <div><strong>Local accuracy:</strong> {formatPct(active?.local_accuracy)}</div>
            <div><strong>Previous accuracy:</strong> {formatPct(comparison.previous)}</div>
            <div><strong>New accuracy:</strong> {formatPct(comparison.next)}</div>
            <div><strong>Improvement:</strong> <span style={{ color: improvement >= 0 ? '#10b981' : '#ef4444', fontWeight: 700 }}>{improvement >= 0 ? '+' : ''}{formatPct(Math.abs(improvement))}</span></div>
            <button onClick={onTrain} disabled={loading} style={primaryButtonStyle}>
              Train Local Model
            </button>
            <div style={{ fontSize: 13, color: '#6b7280' }}>
              This is a simulation of local hospital training. In production each hospital would run on its own machine and send only model updates, not raw patient data.
            </div>
            {active?.notification ? (
              <div style={{ padding: 12, borderRadius: 10, background: '#eff6ff', color: '#1d4ed8' }}>{active.notification}</div>
            ) : null}
          </div>
        </Section>

        <div style={{ display: 'grid', gap: 16 }}>
          <Section title="Dataset snapshot">
            <div style={{ display: 'grid', gap: 8, fontSize: 14 }}>
              <div><strong>Disease:</strong> {stats?.disease_type || hospital?.disease_type || 'sepsis'}</div>
              <div><strong>Columns:</strong> {stats?.columns?.join(', ') || 'age, temperature, heart_rate, respiratory_rate, wbc, blood_pressure, sepsis_label'}</div>
              <div><strong>Dataset source:</strong> Deterministic hospital split of a PhysioNet-style sepsis simulation dataset</div>
            </div>
          </Section>

          <Section title="Ministry feedback">
            <div style={{ display: 'grid', gap: 8 }}>
              <div><strong>Notification:</strong> {active?.notification || 'Waiting for Ministry to aggregate...'}</div>
              <div><strong>Received model:</strong> {active?.status === 'done' ? '✅' : '⏳'}</div>
              <div><strong>Previous accuracy:</strong> {formatPct(comparison.previous)}</div>
              <div><strong>New accuracy:</strong> {formatPct(comparison.next)}</div>
              <div><strong>Improvement:</strong> {improvement >= 0 ? `+${formatPct(improvement)}` : `-${formatPct(Math.abs(improvement))}`}</div>
            </div>
          </Section>
        </div>
      </div>
    </div>
  )
}

const primaryButtonStyle = {
  background: '#2563eb',
  color: '#fff',
  border: 'none',
  borderRadius: 10,
  padding: '12px 16px',
  fontWeight: 700,
  cursor: 'pointer',
}

const secondaryButtonStyle = {
  background: '#f3f4f6',
  color: '#111827',
  border: '1px solid #d1d5db',
  borderRadius: 10,
  padding: '12px 16px',
  fontWeight: 700,
  cursor: 'pointer',
}

const tableTh = { padding: '8px 6px', fontSize: 13 }
const tableTd = { padding: '10px 6px', verticalAlign: 'top', fontSize: 13 }
