import { useState } from 'react'
import Home from './pages/Home.jsx'
import Leaderboard from './pages/Leaderboard.jsx'
import Progress from './pages/Progress.jsx'
import Stats from './pages/Stats.jsx'

const TABS = [
  { id: 'home',        icon: '🏠', label: 'Home' },
  { id: 'leaderboard', icon: '⚡', label: 'XP' },
  { id: 'progress',    icon: '📚', label: 'Course' },
  { id: 'stats',       icon: '📊', label: 'Stats' },
]

export default function App() {
  const [tab, setTab] = useState('home')

  return (
    <div>
      {tab === 'home'        && <Home />}
      {tab === 'leaderboard' && <Leaderboard />}
      {tab === 'progress'    && <Progress />}
      {tab === 'stats'       && <Stats />}

      <nav className="nav">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`nav-btn ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            <span>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>
    </div>
  )
}
