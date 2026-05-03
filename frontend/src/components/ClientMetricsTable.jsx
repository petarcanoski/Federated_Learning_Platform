import React from 'react'

export default function ClientMetricsTable({ round }) {
  const rows = round?.client_metrics || []

  if (!rows.length) {
    return (
      <div style={{ padding: 16, background: '#fff', borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
        <h3 style={{ marginTop: 0 }}>Client metrics</h3>
        <p style={{ margin: 0, color: '#6b7280' }}>Run a round to see per-client results.</p>
      </div>
    )
  }

  return (
    <div style={{ padding: 16, background: '#fff', borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
      <h3 style={{ marginTop: 0 }}>Client metrics</h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>
              <th style={{ padding: '8px 4px' }}>Client / Hospital</th>
              <th style={{ padding: '8px 4px' }}>Samples</th>
              <th style={{ padding: '8px 4px' }}>Loss</th>
              <th style={{ padding: '8px 4px' }}>Accuracy</th>
              <th style={{ padding: '8px 4px' }}>Masked</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.client_id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: '8px 4px' }}>
                  <div style={{ fontWeight: 600 }}>{row.hospital_name || row.client_id}</div>
                  {row.hospital_name ? <div style={{ fontSize: 12, color: '#6b7280' }}>{row.client_id}</div> : null}
                </td>
                <td style={{ padding: '8px 4px' }}>{row.samples}</td>
                <td style={{ padding: '8px 4px' }}>{Number(row.loss).toFixed(4)}</td>
                <td style={{ padding: '8px 4px' }}>{Number(row.accuracy).toFixed(4)}</td>
                <td style={{ padding: '8px 4px' }}>{row.masked ? '✅' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

