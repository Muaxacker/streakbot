import { useApi } from '../hooks/useApi.js'

function StatCard({ label, value, sub, color }) {
  return (
    <div className="card">
      <div className="stat-num" style={{ color: color || 'var(--text)' }}>{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function DifficultyBar({ difficulties }) {
  const total = Object.values(difficulties).reduce((a, b) => a + b, 0)
  if (total === 0) return <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>No data yet</div>

  return (
    <div>
      <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden', marginBottom: 8 }}>
        {difficulties.easy > 0 && (
          <div style={{ flex: difficulties.easy, background: '#22c55e' }} title={`Easy: ${difficulties.easy}`} />
        )}
        {difficulties.medium > 0 && (
          <div style={{ flex: difficulties.medium, background: '#d29922' }} title={`Medium: ${difficulties.medium}`} />
        )}
        {difficulties.hard > 0 && (
          <div style={{ flex: difficulties.hard, background: '#f85149' }} title={`Hard: ${difficulties.hard}`} />
        )}
      </div>
      <div style={{ display: 'flex', gap: 12, fontSize: 11 }}>
        <span style={{ color: '#22c55e' }}>🟢 Easy: {difficulties.easy}</span>
        <span style={{ color: '#d29922' }}>🟡 Medium: {difficulties.medium}</span>
        <span style={{ color: '#f85149' }}>🔴 Hard: {difficulties.hard}</span>
      </div>
    </div>
  )
}

function UserStats({ user }) {
  if (!user) return null
  return (
    <div>
      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 10, color: 'var(--green)' }}>
        {user.name}
      </div>

      <div className="grid-2" style={{ marginBottom: 10 }}>
        <StatCard
          label="Days Reported"
          value={user.days_reported}
          sub={`of ${user.total_days} total`}
        />
        <StatCard
          label="Consistency"
          value={`${user.completion_pct}%`}
          color={user.completion_pct >= 80 ? 'var(--green)' : user.completion_pct >= 50 ? 'var(--yellow)' : 'var(--red)'}
        />
        <StatCard
          label="Total Study Time"
          value={`${user.total_hours}h`}
        />
        <StatCard
          label="Avg Per Day"
          value={`${user.avg_hours_per_day}h`}
        />
      </div>

      <div className="card" style={{ marginBottom: 10 }}>
        <div className="card-title">Difficulty Breakdown</div>
        <DifficultyBar difficulties={user.difficulties} />
      </div>
    </div>
  )
}

export default function Stats() {
  const { data, loading, error } = useApi('/stats')
  const { data: scoresData } = useApi('/scores')
  const { data: strugglesData } = useApi('/struggles')

  if (loading) return <div className="loading"><div className="spinner" /> Loading stats...</div>
  if (error) return <div className="page"><div className="card" style={{ color: 'var(--red)' }}>Failed to load: {error}</div></div>

  const { streak, longest_streak, user1, user2 } = data

  return (
    <div className="page">
      <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>📊 Learning Stats</div>

      {/* Streak overview */}
      <div className="grid-2" style={{ marginBottom: 12 }}>
        <StatCard label="Current Streak" value={`${streak}🔥`} color="var(--green)" />
        <StatCard label="Best Streak" value={`${longest_streak}🏆`} />
      </div>

      {/* Accountability scores */}
      {scoresData && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div className="card-title">Accountability Scores</div>
          <div style={{ display: 'flex', gap: 12 }}>
            {[scoresData.user1, scoresData.user2].map((u, i) => u && (
              <div key={i} style={{ flex: 1, textAlign: 'center' }}>
                <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>{u.name}</div>
                <div style={{ fontSize: 28, fontWeight: 800, color: u.total >= 70 ? 'var(--green)' : u.total >= 40 ? 'var(--yellow)' : 'var(--red)' }}>
                  {u.total}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{u.grade}</div>
                <div className="progress-bar" style={{ marginTop: 6 }}>
                  <div className="progress-fill" style={{
                    width: `${u.total}%`,
                    background: u.total >= 70 ? 'var(--green)' : u.total >= 40 ? 'var(--yellow)' : 'var(--red)'
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-user stats */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <UserStats user={user1} />
        <UserStats user={user2} />
      </div>

      {/* Struggles */}
      {strugglesData && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-title">⚠️ Active Struggles</div>
          {[strugglesData.user1, strugglesData.user2].map((u, i) => (
            <div key={i} style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>{u.name}</div>
              {u.struggles.length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--green)' }}>✅ No active struggles</div>
              ) : (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {u.struggles.map((s, j) => (
                    <span key={j} className="badge badge-yellow">{s.topic}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
