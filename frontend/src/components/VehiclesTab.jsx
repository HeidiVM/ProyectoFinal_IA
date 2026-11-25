import { useEffect, useState } from 'react'
import { api, getJson, putJson } from '../api.js'

export default function VehiclesTab({ focusState, refreshFocus }) {
  const [vehicles, setVehicles] = useState([])
  const [people, setPeople] = useState([])
  const [selectedOwners, setSelectedOwners] = useState({})
  const [message, setMessage] = useState(null)
  const [loading, setLoading] = useState(true)

  async function loadData() {
    try {
      const [vehicleData, peopleData] = await Promise.all([
        getJson('/api/vehicles'),
        getJson('/api/people')
      ])
      setVehicles(vehicleData)
      setPeople(peopleData)
      setSelectedOwners(
        Object.fromEntries(vehicleData.map((vehicle) => [vehicle.id, String(vehicle.owner_id)]))
      )
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  async function saveOwner(vehicle) {
    const ownerId = Number(selectedOwners[vehicle.id])
    if (!ownerId || ownerId === vehicle.owner_id) {
      setMessage({ type: 'error', text: 'Selecciona un dueño diferente' })
      return
    }
    try {
      const data = await putJson(`/api/vehicles/${vehicle.id}/owner`, { owner_id: ownerId })
      setMessage({
        type: 'success',
        text: `${data.vehicle.plate} ahora pertenece a ${data.vehicle.owner_name}`
      })
      await loadData()
      await refreshFocus()
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    }
  }

  async function resetFocus() {
    try {
      await api('/api/focus/off', { method: 'POST' })
      await refreshFocus()
      setMessage({ type: 'success', text: 'Focos apagados' })
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    }
  }

  if (loading) return <div className="panel"><p>Cargando vehículos...</p></div>

  return (
    <div className="content-grid single-column">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Asignación de dueños</h2>
            <p className="muted">
              Cambia el dueño de cada vehículo. La identificación usará estos datos para encender el foco.
            </p>
          </div>
          <button className="button ghost" type="button" onClick={resetFocus}>
            Apagar focos
          </button>
        </div>

        {message && <div className={`alert ${message.type}`}>{message.text}</div>}

        <div className="vehicles-list">
          {vehicles.map((vehicle) => {
            const changed = Number(selectedOwners[vehicle.id]) !== vehicle.owner_id
            return (
              <div key={vehicle.id} className="vehicle-row">
                <div className={`bulb ${vehicle.focus_active ? 'on' : ''}`} />
                <div className="vehicle-info">
                  <strong>{vehicle.plate}</strong>
                  <p className="muted small">
                    {vehicle.brand} {vehicle.model} · {vehicle.color}
                  </p>
                </div>
                <label className="field compact">
                  <span>Dueño</span>
                  <select
                    value={selectedOwners[vehicle.id] ?? String(vehicle.owner_id)}
                    onChange={(event) =>
                      setSelectedOwners((current) => ({
                        ...current,
                        [vehicle.id]: event.target.value
                      }))
                    }
                  >
                    {people.map((person) => (
                      <option key={person.id} value={person.id}>
                        {person.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="button primary"
                  type="button"
                  disabled={!changed}
                  onClick={() => saveOwner(vehicle)}
                >
                  Guardar
                </button>
              </div>
            )
          })}
        </div>

        <div className="people-summary">
          <h3>Personas registradas</h3>
          <div className="people-chips">
            {people.map((person) => (
              <span key={person.id} className="person-chip">
                {person.name}
                <small>
                  {vehicles.filter((vehicle) => vehicle.owner_id === person.id).length} vehículo(s)
                </small>
              </span>
            ))}
          </div>
          <p className="muted small">
            Focos activos en este momento: {focusState.active_count}
          </p>
        </div>
      </section>
    </div>
  )
}
