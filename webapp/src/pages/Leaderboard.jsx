import { useApi } from '../hooks/useApi.js'

const LEVELS = [
  { level: 1,  title: 'Beginner',       xp: 0 },
  { level: 2,  title: 'Explorer',       xp: 100 },
  { level: 3,  title: 'Builder',        xp: 250 },
  { level: 4,  title: 'Developer',      xp: 500 },
  { level: 5,  title: 'Engineer',       xp: 900 },
  { level: 6,  title: 'Senior Dev',     xp: 1400 },
  { level: 7,  title: 'Architect',      xp: 2000 },
  { level: 8,  title: 'Full Stack Pro', xp: 3000 },
  { level: 9,  title: 'Tech Lead',      xp: 4500 },
  { level: 10, title: 'Elite Coder',    xp: 7000 },
]

function XpCard({ user, isLeader }) {
  if (!user) return null

  const currentLevel = LEVELS.find(l => l.level === user.level) || LEVELS[0]
  const nextLevel = LEVELS.find(l => l.level === user.level + 1)
  const progressInLevel = user.xp - currentLevel.xp
  const totalForLevel = nextLevel ? nextLevel.xp - currentLevel.xp : 1
  const pct = nextLevel ? Math.min(100, Math.round(progressInLevel / totalForLevel * 100)) : 100

  return (
    <div className="card" style={{ borderColor: isLeader ? 'var(--green)' : 'var(--border)', position: 'relative' }}>
      {isLeader && (
        <div style={{ position: 'absolute', top: -10, right: 12, fontSize: 20 }}>👑</div>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700 }}>{user.name}</div>
          <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>Level {user.level} — {user.level_title}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--green)' }}>{user.xp}</div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>XP</div>
        </div>
      </div>

      {/* Level progress */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>Lv.{user.level}</span>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
            {nextLevel ? `${user.xp_to_next} XP to Lv.${user.level + 1}` : '🏆 MAX LEVEL'}
          </span>
        </div>
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Recent XP history */}
      {user.recent_history?.length > 0 && (
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 6 }}>Recent activity</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {user.recent_history.slice(-5).reverse().map((h, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: 'var(--text-dim)' }}>{h.action?.replace(/_/g, ' ')}</span>
                <span style={{ color: 'var(--green)', fontWeight: 600 }}>+{h.xp}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function Leaderboard() {
  const { data, loading, error } = useApi('/leaderboard')

  if (loading) return <div className="loading"><div className="spinner" /> Loading XP...</div>
  if (error) return <div className="page"><div className="card" style={{ color: 'var(--red)' }}>Failed to load: {error}</div></div>

  const { user1, user2, leader, gap } = data

  return (
    <div className="page">
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>⚡ XP Leaderboard</div>
        <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>
          {gap === 0
            ? 'Perfectly tied — someone needs to pull ahead'
            : `${leader} is leading by ${gap} XP`}
        </div>
      </div>

      {/* VS comparison */}
      <div className="card" style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{user1?.name}</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: user1?.xp >= user2?.xp ? 'var(--green)' : 'var(--text-dim)' }}>
              {user1?.xp}
            </div>
          </div>
          <div style={{ fontSize: 16, color: 'var(--text-dim)', fontWeight: 700 }}>VS</div>
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{user2?.name}</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: user2?.xp > user1?.xp ? 'var(--green)' : 'var(--text-dim)' }}>
              {user2?.xp}
            </div>
          </div>
        </div>

        {/* Relative bar */}
        <div style={{ marginTop: 12 }}>
          <div style={{ height: 8, background: 'var(--bg3)', borderRadius: 4, overflow: 'hidden', display: 'flex' }}>
            <div style={{
              width: `${Math.round((user1?.xp || 0) / ((user1?.xp || 0) + (user2?.xp || 1)) * 100)}%`,
              background: 'var(--green)',
              transition: 'width 0.6s ease',
            }} />
            <div style={{ flex: 1, background: 'var(--blue)' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 11, color: 'var(--text-dim)' }}>
            <span style={{ color: 'var(--green)' }}>■ {user1?.name}</span>
            <span style={{ color: 'var(--blue)' }}>■ {user2?.name}</span>
          </div>
        </div>
      </div>

      {/* Individual cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <XpCard user={user1} isLeader={(user1?.xp || 0) >= (user2?.xp || 0)} />
        <XpCard user={user2} isLeader={(user2?.xp || 0) > (user1?.xp || 0)} />
      </div>

      {/* Level roadmap */}
      <div className="card" style={{ marginTop: 12 }}>
        <div className="card-title">Level Roadmap</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {LEVELS.map(l => {
            const u1done = (user1?.xp || 0) >= l.xp
            const u2done = (user2?.xp || 0) >= l.xp
            return (
              <div key={l.level} style={{ display: 'flex', alignItems: 'center', gap: 8, opacity: u1done || u2done ? 1 : 0.4 }}>
                <div style={{ width: 24, height: 24, borderRadius: '50%', background: u1done && u2done ? 'var(--green)' : u1done || u2done ? 'var(--yellow)' : 'var(--bg3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, flexShrink: 0 }}>
                  {l.level}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{l.title}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{l.xp} XP</div>
                </div>
                <div style={{ fontSize: 12 }}>
                  {u1done ? '✅' : '⬜'} {u2done ? '✅' : '⬜'}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
