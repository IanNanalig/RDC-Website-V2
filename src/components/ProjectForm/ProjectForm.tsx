import React, { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import schema from '../../forms/project_form_schema.json'
import FieldRenderer from './FieldRenderer'

type Props = {
  initial?: any
  onSave?: (payload: any) => void
  onCancel?: () => void
}

export default function ProjectForm({ initial, onSave, onCancel }: Props) {
  const { register, handleSubmit, watch, setValue, getValues, reset } = useForm({ defaultValues: initial || {} })
  useEffect(() => {
    if (initial) reset(initial)
  }, [initial, reset])
  const [stepIndex, setStepIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const steps = schema.steps

  const onSubmit = async (data: any) => {
    setLoading(true)
    try {
      // extract files if any
      const files = data.attachments || null

      // Prepare payload: transform comma-separated arrays into arrays
      const payload: any = { ...data }
      // remove attachments from JSON payload
      delete payload.attachments

      // simple normalization for fields of type array (comma-separated)
      steps.forEach((s: any) => s.fields.forEach((f: any) => {
        if (f.type === 'array' && payload[f.name] && typeof payload[f.name] === 'string') {
          payload[f.name] = payload[f.name].split(',').map((x: string) => x.trim()).filter(Boolean)
        }
      }))

      // handle save_as_draft / submit_now flags
      const saveAsDraft = !!payload.save_as_draft
      const submitNow = !!payload.submit_now
      // remove those flags from payload to avoid unknown fields
      delete payload.save_as_draft
      delete payload.submit_now

      const res = await fetch('/api/projects/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error('Failed to save: ' + errText)
      }
      const project = await res.json()

      // if consumer provided onSave handler, call it and skip server-side uploads/submits
      if (onSave) {
        onSave({ ...payload, id: project.id })
      }

      // if files were attached, upload them to attachments endpoint
      if (files && files.length > 0) {
        const formData = new FormData()
        formData.append('project', project.id)
        // files may be FileList or an array
        const fileList = files instanceof FileList ? Array.from(files) : files
        fileList.forEach((f: File) => formData.append('file', f))

        const up = await fetch('/api/attachments/', {
          method: 'POST',
          credentials: 'include',
          body: formData
        })
        if (!up.ok) {
          const errText = await up.text()
          // non-fatal: alert user but keep project
          alert('Project saved but file upload failed: ' + errText)
        }
      }

      // if user wants to submit immediately, call submit action
      if (submitNow && !saveAsDraft) {
        const sub = await fetch(`/api/projects/${project.id}/submit/`, {
          method: 'POST',
          credentials: 'include'
        })
        if (!sub.ok) {
          const errText = await sub.text()
          alert('Project saved but submit failed: ' + errText)
        }
      }

      alert('Saved project')
    } catch (err: any) {
      alert(err.message || 'Error')
    } finally {
      setLoading(false)
    }
  }

  const next = () => setStepIndex(i => Math.min(steps.length - 1, i + 1))
  const prev = () => setStepIndex(i => Math.max(0, i - 1))

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 16 }}>
      <h2>{schema.title}</h2>
      <div style={{ border: '1px solid #eee', padding: 12 }}>
        <h3>{steps[stepIndex].title}</h3>
        <form onSubmit={handleSubmit(onSubmit)}>
          {steps[stepIndex].fields.map((field: any) => (
            <FieldRenderer key={field.name} field={field} register={register} watch={watch} />
          ))}

          <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            {onCancel && <button type="button" onClick={onCancel}>Cancel</button>}
            {stepIndex > 0 && <button type="button" onClick={prev}>Back</button>}
            {stepIndex < steps.length - 1 && <button type="button" onClick={next}>Next</button>}
            {stepIndex === steps.length - 1 && <button type="submit" disabled={loading}>{loading ? 'Saving...' : 'Save / Submit'}</button>}
          </div>
        </form>
      </div>
      <div style={{ marginTop: 12 }}>
        <small>Step {stepIndex + 1} of {steps.length}</small>
      </div>
    </div>
  )
}
