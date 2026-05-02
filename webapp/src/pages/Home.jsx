import { useApi } from '../hooks/useApi.js'

function StreakFire({ streak }) {
  const fires =
    streak >= 100 ? '🔥🔥🔥🔥🔥' :
    streak >= 60  ? '🔥🔥🔥🔥' :
    streak >= 30  ? '🔥🔥🔥' :
    streak >= 14  ? '🔥🔥' :
    streak >= 7   ? '🔥' :
    streak >= 3   ? '✨' : '🌱'
  return <span className="streak-fire">{fires}</span>
}

function UserCard({ user, label }) {
  if (!user) return null
  const diff = user.today_report?.difficulty
  const diffColor = diff === 'easy' ? '#22c55e' : diff === 'hard' ? '#f85149' : '#d29922'

  return (
    <div className="card" style={{ flex: 1 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700 }}>{user.name}</div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>Lv.{user.level} {user.level_title}</div>
        </div>
        <span className={`badge ${user.reported_today ? 'badge-green' : 'badge-red'}`}>
          {user.reported_today ? '✅ Done' : '⏳ Pending'}
        </span>
      </div>

      {/* XP bar */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>⚡ {user.xp} XP</span>
          {user.xp_to_next && (
            <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{user.xp_to_next} to next</span>
          )}
        </div>
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{
              width: user.xp_to_next
                ? `${Math.min(100, Math.round((user.xp / (user.xp + user.xp_to_next)) * 100))}%`
                : '100%'
            }}
          />
        </div>
      </div>

      {/* Today's report */}
      {user.today_report && (
        <div style={{ background: 'var(--bg3)', borderRadius: 8, padding: '8px 10px', fontSize: 12 }}>
          <div style={{ color: 'var(--text-dim)', marginBottom: 4 }}>Today's report</div>
          <div style={{ marginBottom: 3 }}>
            📖 {user.today_report.learned?.slice(0, 60) || '—'}
            {user.today_report.learned?.length > 60 ? '...' : ''}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span>⏱ {user.today_report.time_spent || '—'}</span>
            <span style={{ color: diffColor }}>
              {diff === 'easy' ? '🟢' : diff === 'hard' ? '🔴' : '🟡'} {diff || '—'}
            </span>
          </div>
        </div>
      )}

      {/* Next topic */}
      {user.next_topic && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-dim)' }}>
          📌 Next: <span style={{ color: 'var(--text)' }}>{user.next_topic}</span>
        </div>
      )}
    </div>
  )
}

function CalendarHeatmap({ days }) {
  if (!days) return null
  const reversed = [...days].reverse()

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        {reversed.map(d => (
          <div
            key={d.date}
            title={d.date}
            style={{
              width: 14,
              height: 14,
              borderRadius: 3,
              background: d.both
                ? 'var(--green)'
                : d.user1_reported || d.user2_reported
                ? 'var(--green-dim)'
                : 'var(--bg3)',
              opacity: d.both ? 1 : d.user1_reported || d.user2_reported ? 0.6 : 0.3,
            }}
          />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 8, fontSize: 11, color: 'var(--text-dim)' }}>
        <span><span style={{ color: 'var(--green)' }}>■</span> Both reported</span>
        <span><span style={{ color: 'var(--green-dim)' }}>■</span> One reported</span>
        <span><span style={{ color: 'var(--bg3)', opacity: 0.5 }}>■</span> Missed</span>
      </div>
    </div>
  )
}

export default function Home() {
  const { data, loading, error, refetch } = useApi('/dashboard')
  const { data: calData } = useApi('/calendar')

  if (loading) return (
    <div className="loading">
      <div className="spinner" /> Loading dashboard...
    </div>
  )

  if (error) return (
    <div className="page">
      <div className="card" style={{ textAlign: 'center', color: 'var(--red)' }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>⚠️</div>
        <div>Could not connect to bot API</div>
        <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>Make sure the bot is running</div>
        <button
          onClick={refetch}
          style={{ marginTop: 12, padding: '6px 16px', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', cursor: 'pointer' }}
        >
          Retry
        </button>
      </div>
    </div>
  )

  const { streak, longest_streak, both_reported_today, user1, user2 } = data

  return (
    <div className="page">

      {/* Streak hero */}
      <div className="card" style={{ textAlign: 'center', marginBottom: 12, background: both_reported_today ? 'rgba(34,197,94,0.08)' : 'var(--bg2)', borderColor: both_reported_today ? 'var(--green)' : 'var(--border)' }}>
        <div style={{ fontSize: 48, marginBottom: 4 }}>
          <StreakFire streak={streak} />
        </div>
        <div style={{ fontSize: 36, fontWeight: 800, lineHeight: 1 }}>{streak}</div>
        <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 4 }}>
          day streak · best: {longest_streak}
        </div>
        <div style={{ marginTop: 10 }}>
          <span className={`badge ${both_reported_today ? 'badge-green' : 'badge-yellow'}`}>
            {both_reported_today ? '🎯 Streak secured today!' : '👀 Waiting for both reports'}
          </span>
        </div>
      </div>

      {/* User cards */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <UserCard user={user1} label="User 1" />
        <UserCard user={user2} label="User 2" />
      </div>

      {/* Calendar */}
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="card-title">Last 30 Days</div>
        <CalendarHeatmap days={calData?.days} />
      </div>

      {/* Footer */}
      <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-dim)', paddingBottom: 8 }}>
        Updated {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        <button
          onClick={refetch}
          style={{ marginLeft: 8, background: 'none', border: 'none', color: 'var(--green)', cursor: 'pointer', fontSize: 11 }}
        >
          ↻ Refresh
        </button>
      </div>

    </div>
  )
}
