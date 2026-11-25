import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import RecognitionTab from './components/RecognitionTab.jsx'
import VehiclesTab from './components/VehiclesTab.jsx'

export default function App() {
  const [activeTab, setActiveTab] = useState('recognize')
  const [focusState, setFocusState] = useState({ vehicles: [], active_count: 0 })
  const [health, setHealth] = useState(null)

  const refreshFocus = useCallback(async () => {
    try {
      const [focus, status] = await Promise.all([
        api('/api/focus'),
        api('/api/health')
      ])
      setFocusState(focus)
      setHealth(status)
    } catch {
      setHealth({ ok: false })
    }
  }, [])

  useEffect(() => {
    refreshFocus()
    const interval = window.setInterval(refreshFocus, 10000)
    return () => window.clearInterval(interval)
  }, [refreshFocus])

  return (
    <div className="app-shell">
      <header className="header">
        <div>
          <p className="eyebrow">IP Web Cam + SQLite</p>
          <h1>Control de vehículos por reconocimiento facial</h1>
          <p className="subtitle">
            Toma la foto desde tu celular, identifica al dueño y enciende el foco de su vehículo.
          </p>
        </div>
        <div className={`service-badge ${health?.ok ? 'online' : 'offline'}`}>
          <span className="status-dot" />
          {health?.ok ? 'Backend conectado' : 'Backend sin conexión'}
          {health?.model_trained ? ' · modelo listo' : ' · sin entrenar'}
        </div>
      </header>

      <nav className="tabs">
        <button
          className={`tab-button ${activeTab === 'recognize' ? 'active' : ''}`}
          onClick={() => setActiveTab('recognize')}
        >
          Identificación
        </button>
        <button
          className={`tab-button ${activeTab === 'vehicles' ? 'active' : ''}`}
          onClick={() => setActiveTab('vehicles')}
        >
          Cambiar dueños
        </button>
      </nav>

      <main>
        {activeTab === 'recognize' ? (
          <RecognitionTab focusState={focusState} refreshFocus={refreshFocus} />
        ) : (
          <VehiclesTab focusState={focusState} refreshFocus={refreshFocus} />
        )}
      </main>
    </div>
  )
}
