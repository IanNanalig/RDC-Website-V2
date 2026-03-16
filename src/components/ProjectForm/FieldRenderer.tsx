import React from 'react'
import { UseFormRegister, FieldValues } from 'react-hook-form'

type Field = any

export default function FieldRenderer({ field, register, watch }: { field: Field, register: UseFormRegister<FieldValues>, watch: any }) {
  const visible = (() => {
    if (!field.visible_when) return true
    const conditions = field.visible_when
    for (const k of Object.keys(conditions)) {
      if (watch(k) !== conditions[k]) return false
    }
    return true
  })()

  if (!visible) return null

  switch (field.type) {
    case 'text':
    case 'year':
      return (
        <div style={{ marginBottom: 12 }}>
          <label>{field.label}{field.required ? ' *' : ''}</label>
          <input {...register(field.name)} type="text" style={{ display: 'block', width: '100%', padding: 8 }} />
        </div>
      )

    case 'textarea':
      return (
        <div style={{ marginBottom: 12 }}>
          <label>{field.label}{field.required ? ' *' : ''}</label>
          <textarea {...register(field.name)} rows={4} style={{ display: 'block', width: '100%', padding: 8 }} />
        </div>
      )

    case 'select':
      return (
        <div style={{ marginBottom: 12 }}>
          <label>{field.label}{field.required ? ' *' : ''}</label>
          <select {...register(field.name)} style={{ display: 'block', width: '100%', padding: 8 }}>
            <option value="">-- choose --</option>
            {(field.options || []).map((opt: any) => (
              typeof opt === 'object'
                ? <option key={opt.value} value={opt.value}>{opt.label}</option>
                : <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </div>
      )

    case 'boolean':
      return (
        <div style={{ marginBottom: 12 }}>
          <label>
            <input type="checkbox" {...register(field.name)} /> {field.label}
          </label>
        </div>
      )

    case 'array':
      return (
        <div style={{ marginBottom: 12 }}>
          <label>{field.label}</label>
          <input {...register(field.name)} placeholder="Comma-separated values" />
          <small>Enter items separated by commas.</small>
        </div>
      )

    case 'files':
      return (
        <div style={{ marginBottom: 12 }}>
          <label>{field.label}</label>
          <input type="file" {...register(field.name)} multiple={!!field.multiple} />
        </div>
      )

    case 'array_of_objects':
      return (
        <div style={{ marginBottom: 12 }}>
          <label>{field.label}</label>
          <small>Use the review step to add complex table rows. (MVP)</small>
        </div>
      )

    case 'json':
      return (
        <div style={{ marginBottom: 12 }}>
          <label>{field.label}</label>
          <textarea {...register(field.name)} placeholder='JSON' rows={3} />
          <small>Enter JSON object (MVP).</small>
        </div>
      )

    default:
      return null
  }
}
