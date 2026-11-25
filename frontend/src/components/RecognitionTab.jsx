import { useEffect, useRef, useState } from 'react'
import { api, cameraPreviewUrl, postForm, postJson } from '../api.js'

export default function RecognitionTab({ focusState, refreshFocus }) {
  const [previewKey, setPreviewKey] = useState(0)
  const [previewFailed, setPreviewFailed] = useState(false)
  const [cameraStatus, setCameraStatus] = useState({ configured: false })
  const [result, setResult] = useState(null)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const [faceStatus, setFaceStatus] = useState({
    trained: false,
    provider: 'lbph',
    people: [],
    total_samples: 0
  })
  const [trainingPerson, setTrainingPerson] = useState('')
  const [sampleFile, setSampleFile] = useState(null)
  const [trainingBusy, setTrainingBusy] = useState(false)
  const uploadRef = useRef(null)

  const externalModel = faceStatus.provider && faceStatus.provider !== 'lbph'

  async function loadFaceStatus() {
    try {
      const status = await api('/api/faces/status')
      setFaceStatus(status)
      setTrainingPerson((current) => {
        if (current || !status.people.length) return current
        return String(status.people[0].id)
      })
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    }
  }

  async function loadCameraStatus() {
    try {
      const status = await api('/api/camera/status')
      setCameraStatus(status)
      if (!status.configured) setPreviewFailed(true)
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    }
  }

  useEffect(() => {
    loadFaceStatus()
    loadCameraStatus()
  }, [])

  async function recognize(payload, isForm = false) {
    setBusy(true)
    setMessage(null)
    setResult(null)
    try {
      const data = isForm
        ? await postForm('/api/recognize', payload)
        : await postJson('/api/recognize/json', payload)
      setResult(data)
      await refreshFocus()
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    } finally {
      setBusy(false)
    }
  }

  function handleCapture() {
    if (!cameraStatus.configured) {
      setMessage({ type: 'error', text: 'Configure IPWEBCAM_URL en el backend' })
      return
    }
    setPreviewKey(Date.now())
    recognize({})
  }

  function handleUpload(event) {
    const file = event.target.files?.[0]
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    recognize(form, true)
    event.target.value = ''
  }

  async function handleSample(source) {
    if (!trainingPerson) {
      setMessage({ type: 'error', text: 'Selecciona una persona' })
      return
    }
    if (source === 'file' && !sampleFile) {
      setMessage({ type: 'error', text: 'Selecciona una imagen' })
      return
    }
    if (source === 'camera' && !cameraStatus.configured) {
      setMessage({ type: 'error', text: 'Configure IPWEBCAM_URL en el backend' })
      return
    }
    setTrainingBusy(true)
    try {
      const form = new FormData()
      form.append('person_id', trainingPerson)
      if (source === 'file') form.append('file', sampleFile)
      const data = await postForm('/api/faces/enroll', form)
      setMessage({
        type: 'success',
        text: `Muestra agregada a ${data.sample.person_name}.`
      })
      setSampleFile(null)
      await loadFaceStatus()
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    } finally {
      setTrainingBusy(false)
    }
  }

  async function handleTrain() {
    setTrainingBusy(true)
    try {
      const data = await api('/api/faces/train', { method: 'POST' })
      setMessage({
        type: 'success',
        text: `Modelo entrenado con ${data.sample_count} muestras de ${data.person_count} personas.`
      })
      await loadFaceStatus()
      await refreshFocus()
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    } finally {
      setTrainingBusy(false)
    }
  }

  async function turnOff() {
    await api('/api/focus/off', { method: 'POST' })
    setResult(null)
    await refreshFocus()
  }

  const vehicle = result?.focus?.vehicle
  const activeVehicle = focusState.vehicles.find((item) => item.focus_active)
  const modelLabel = externalModel ? `Modelo ${faceStatus.provider}` : faceStatus.trained ? 'Modelo entrenado' : 'Modelo sin entrenar'

  return (
    <div className="content-grid">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Captura desde IP Web Cam</h2>
            <p className="muted">La cámara se configura en el backend y no se muestra en la interfaz.</p>
          </div>
          <div className="chip-row">
            <span className={faceStatus.trained ? 'chip success' : 'chip warning'}>{modelLabel}</span>
            <span className={cameraStatus.configured ? 'chip success' : 'chip warning'}>
              {cameraStatus.configured ? 'Cámara configurada' : 'Cámara sin configurar'}
            </span>
          </div>
        </div>

        <div className="camera-layout">
          <div className="preview-frame">
            {!cameraStatus.configured ? (
              <div className="preview-empty">Configure IPWEBCAM_URL en el backend</div>
            ) : previewFailed ? (
              <div className="preview-empty">No se pudo cargar la vista previa</div>
            ) : (
              <img
                src={cameraPreviewUrl(previewKey)}
                alt="Vista previa de IP Web Cam"
                onError={() => setPreviewFailed(true)}
              />
            )}
          </div>
          <div className="action-column">
            <button
              className="button ghost"
              type="button"
              disabled={!cameraStatus.configured}
              onClick={() => {
                setPreviewFailed(false)
                setPreviewKey(Date.now())
              }}
            >
              Actualizar vista
            </button>
            <button
              className="button primary"
              type="button"
              onClick={handleCapture}
              disabled={busy || !cameraStatus.configured}
            >
              {busy ? 'Procesando...' : 'Tomar foto y reconocer'}
            </button>
            <button
              className="button secondary"
              type="button"
              onClick={() => uploadRef.current?.click()}
              disabled={busy}
            >
              Subir foto desde la PC
            </button>
            <input
              ref={uploadRef}
              className="hidden-input"
              type="file"
              accept="image/*"
              onChange={handleUpload}
            />
            <p className="muted small">
              La foto se envía al backend, se compara con el modelo activo y se activa el foco del vehículo.
            </p>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Resultado</h2>
            <p className="muted">Dueño, vehículo y foco activado</p>
          </div>
          {activeVehicle && <span className="chip live">Foco encendido</span>}
        </div>

        {message && <div className={`alert ${message.type}`}>{message.text}</div>}

        {result ? (
          <div className="result-layout">
            <img className="result-image" src={result.annotated_image} alt="Foto analizada" />
            <div className="result-details">
              <h3 className={result.recognized ? 'name-success' : 'name-unknown'}>
                {result.recognized ? result.person.name : 'Persona no identificada'}
              </h3>
              <p className="muted">{result.message}</p>
              <div className="metrics">
                <div>
                  <span>Confianza</span>
                  <strong>{result.confidence != null ? `${result.confidence}%` : 'N/A'}</strong>
                </div>
                <div>
                  <span>Distancia</span>
                  <strong>{result.distance != null ? result.distance : 'N/A'}</strong>
                </div>
              </div>
              <div className="result-vehicle">
                <span className="muted">Vehículo asignado</span>
                {vehicle ? (
                  <>
                    <strong>{vehicle.plate}</strong>
                    <p>{vehicle.brand} {vehicle.model} · {vehicle.color}</p>
                    <p className="muted">Dueño actual: {vehicle.owner_name}</p>
                  </>
                ) : (
                  <p className="muted">Esta persona no tiene vehículo asignado</p>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <p>Toma una foto para ver el resultado del reconocimiento.</p>
          </div>
        )}

        <div className="focus-section">
          <div className="focus-heading">
            <h3>Focos de vehículos</h3>
            <button className="button ghost small-button" type="button" onClick={turnOff}>
              Apagar todos
            </button>
          </div>
          <div className="focus-grid">
            {focusState.vehicles.map((item) => (
              <div
                key={item.id}
                className={`focus-card ${item.focus_active ? 'active' : ''}`}
              >
                <span className={`bulb ${item.focus_active ? 'on' : ''}`} />
                <div>
                  <strong>{item.plate}</strong>
                  <p className="muted small">{item.owner_name}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="panel full-width">
        <div className="panel-header">
          <div>
            <h2>Registro de rostros</h2>
            <p className="muted">
              Captura muestras desde la cámara configurada en el backend o sube imágenes.
            </p>
          </div>
          <span className="chip">{faceStatus.total_samples} muestras</span>
        </div>

        <div className="training-layout">
          <label className="field">
            <span>Persona</span>
            <select
              value={trainingPerson}
              onChange={(event) => setTrainingPerson(event.target.value)}
            >
              {faceStatus.people.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name} ({person.sample_count})
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Muestra desde archivo</span>
            <input
              type="file"
              accept="image/*"
              onChange={(event) => setSampleFile(event.target.files?.[0] || null)}
            />
          </label>
          <div className="training-actions">
            <button
              className="button secondary"
              type="button"
              disabled={trainingBusy || !cameraStatus.configured}
              onClick={() => handleSample('camera')}
            >
              Capturar muestra
            </button>
            <button
              className="button secondary"
              type="button"
              disabled={trainingBusy}
              onClick={() => handleSample('file')}
            >
              Subir muestra
            </button>
            {!externalModel && (
              <button
                className="button primary"
                type="button"
                disabled={trainingBusy}
                onClick={handleTrain}
              >
                Entrenar modelo
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
