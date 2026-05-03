import React from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  Cell,
} from 'recharts'

const palette = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6']

export default function ExperimentCharts({ rounds }) {
  const latestRound = rounds?.[rounds.length - 1]
  const latestClients = latestRound?.client_metrics || []

  return (
    <div style={{ display: 'grid', gap: 24 }}>
      <div style={{ background: '#fff', borderRadius: 12, padding: 16, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
        <h3 style={{ marginTop: 0 }}>Global model progress</h3>
        <div style={{ width: '100%', height: 320 }}>
          <ResponsiveContainer>
            <LineChart data={rounds || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="round_index" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="accuracy" stroke="#2563eb" strokeWidth={3} dot />
              <Line type="monotone" dataKey="global_accuracy" stroke="#10b981" strokeWidth={3} dot={false} />
              <Line type="monotone" dataKey="loss" stroke="#ef4444" strokeWidth={3} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ background: '#fff', borderRadius: 12, padding: 16, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
        <h3 style={{ marginTop: 0 }}>Latest round client accuracy</h3>
        <div style={{ width: '100%', height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={latestClients}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="client_id" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="accuracy" fill="#10b981">
                {latestClients.map((_, index) => (
                  <Cell key={index} fill={palette[index % palette.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

