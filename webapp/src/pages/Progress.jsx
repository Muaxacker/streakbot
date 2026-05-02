import { useState } from 'react'
import { useApi } from '../hooks/useApi.js'

const PHASE_COLORS = {
  1: '#f97316',
  2: '#eab308',
  3: '#22c55e',
  4: '#3b82f6',
  5: '#a855f7',
}

function PhaseCard({ phaseNum, phase, userName, expanded, onToggle }) {
  const color = PHASE_COLORS[phaseNum] || 'var(--green)'
  const pct = phase.pct

  return (
    <div className="card" style={{ marginBottom: 8, borderLeft: `3px solid ${color}` }}>
      <div
        style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10 }}
        onClick={onToggle}
      >
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{phase.label}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div className="progress-bar" style={{ flex: 1 }}>
              <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
            </div>
            <span style={{ fontSize: 12, color: 'var(--text-dim)', minWidth: 36 }}>
              {phase.completed}/{phase.total}
            </span>
          </div>
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, color, minWidth: 40, textAlign: 'right' }}>
          {pct}%
        </div>
        <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>{expanded ? '▲' : '▼'}</div>
      </div>

      {expanded && (
        <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 10 }}>
          {phase.lessons.map(lesson => (
            <div key={lesson.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--bg3)' }}>
              <div style={{ fontSize: 16 }}>{lesson.done ? '✅' : '📖'}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: lesson.done ? 'var(--text)' : 'var(--text-dim)' }}>
                  {lesson.title}
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
                  <span style={{ fontSize: 10, color: lesson.video ? 'var(--green)' : 'var(--text-dim)' }}>
                    {lesson.video ? '✓' : '○'} Video
                  </span>
                  <span style={{ fontSize: 10, color: lesson.notes ? 'var(--green)' : 'var(--text-dim)' }}>
                    {lesson.notes ? '✓' : '○'} Notes
                  </span>
                  <span style={{ fontSize: 10, color: lesson.exercise ? 'var(--green)' : 'var(--text-dim)' }}>
                    {lesson.exercise ? '✓' : '○'} Exercise
                  </span>
                </div>
              </div>
              {lesson.done_date && (
                <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>{lesson.done_date}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function UserProgress({ user, userId }) {
  const [expanded, setExpanded] = useState({})
  if (!user) return null

  const toggle = (phaseNum) => setExpanded(e => ({ ...e, [phaseNum]: !e[phaseNum] }))

  return (
    <div>
      {/* Overall */}
      <div className="card" style={{ marginBottom: 12, textAlign: 'center' }}>
        <div style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: 4 }}>{user.name}</div>
        <div style={{ fontSize: 36, fontWeight: 800, color: 'var(--green)' }}>{user.overall_pct}%</div>
        <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
          {user.total_completed} / {user.total_lessons} lessons complete
        </div>
        <div className="progress-bar" style={{ marginTop: 10 }}>
          <div className="progress-fill" style={{ width: `${user.overall_pct}%` }} />
        </div>
      </div>

      {/* Phases */}
      {Object.entries(user.phases).map(([phaseNum, phase]) => (
        <PhaseCard
          key={phaseNum}
          phaseNum={parseInt(phaseNum)}
          phase={phase}
          userName={user.name}
          expanded={!!expanded[phaseNum]}
          onToggle={() => toggle(phaseNum)}
        />
      ))}
    </div>
  )
}

export default function Progress() {
  const { data, loading, error } = useApi('/progress')
  const [activeUser, setActiveUser] = useState(1)

  if (loading) return <div className="loading"><div className="spinner" /> Loading course...</div>
  if (error) return <div className="page"><div className="card" style={{ color: 'var(--red)' }}>Failed to load: {error}</div></div>

  const { user1, user2 } = data

  return (
    <div className="page">
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>📚 Course Progress</div>

        {/* User toggle */}
        <div style={{ display: 'flex', background: 'var(--bg2)', borderRadius: 10, padding: 3, border: '1px solid var(--border)' }}>
          {[{ id: 1, name: user1?.name }, { id: 2, name: user2?.name }].map(u => (
            <button
              key={u.id}
              onClick={() => setActiveUser(u.id)}
              style={{
                flex: 1,
                padding: '7px 12px',
                borderRadius: 8,
                border: 'none',
                background: activeUser === u.id ? 'var(--green)' : 'transparent',
                color: activeUser === u.id ? '#000' : 'var(--text-dim)',
                fontWeight: activeUser === u.id ? 700 : 400,
                cursor: 'pointer',
                fontSize: 13,
                transition: 'all 0.2s',
              }}
            >
              {u.name}
            </button>
          ))}
        </div>
      </div>

      {/* Side by side overview */}
      <div className="grid-2" style={{ marginBottom: 16 }}>
        {[user1, user2].map((u, i) => u && (
          <div key={i} className="card" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>{u.name}</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--green)' }}>{u.overall_pct}%</div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{u.total_completed}/{u.total_lessons}</div>
          </div>
        ))}
      </div>

      <UserProgress user={activeUser === 1 ? user1 : user2} userId={activeUser} />
    </div>
  )
}
