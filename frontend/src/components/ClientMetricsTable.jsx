import React from 'react'

export default function ClientMetricsTable({ round }) {
  const rows = round?.client_metrics || []

  if (!rows.length) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Round output</p>
            <h2>Client metrics</h2>
          </div>
        </div>
        <div className="empty-state">
          <strong>No client metrics yet</strong>
          <span>Run a round to see per-client results.</span>
        </div>
      </section>
    )
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Round output</p>
          <h2>Client metrics</h2>
        </div>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Client / Hospital</th>
              <th>Samples</th>
              <th>Loss</th>
              <th>Accuracy</th>
              <th>Masked</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.client_id}>
                <td>
                  <strong>{row.hospital_name || row.client_id}</strong>
                  {row.hospital_name ? <small>{row.client_id}</small> : null}
                </td>
                <td>{row.samples}</td>
                <td>{Number(row.loss).toFixed(4)}</td>
                <td>{Number(row.accuracy).toFixed(4)}</td>
                <td>{row.masked ? 'Yes' : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
