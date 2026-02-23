import { useState } from 'react'
import { Send, MessageSquare, Trash2, GripVertical, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import type { SequenceStep } from '../../services/api'

interface StepCardProps {
  step: SequenceStep
  isFirst: boolean
  isLast: boolean
  onUpdate: (stepId: string, data: Partial<{ delay_days: number; prompt_context: string }>) => void
  onDelete: (stepId: string) => void
  disabled?: boolean
}

export default function StepCard({ step, isFirst, isLast, onUpdate, onDelete, disabled }: StepCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [delayDays, setDelayDays] = useState(step.delay_days)
  const [promptContext, setPromptContext] = useState(step.prompt_context || '')

  const isConnection = step.step_type === 'connection_request'
  const Icon = isConnection ? Send : MessageSquare
  const typeLabel = isConnection ? 'Connection Request' : 'Follow-up Message'
  const typeColor = isConnection ? 'blue' : 'purple'

  const handleSaveDelay = () => {
    if (delayDays !== step.delay_days) {
      onUpdate(step.id, { delay_days: delayDays })
    }
  }

  const handleSavePrompt = () => {
    if (promptContext !== (step.prompt_context || '')) {
      onUpdate(step.id, { prompt_context: promptContext || undefined })
    }
  }

  return (
    <div className="relative">
      {/* Connector line */}
      {!isFirst && (
        <div className="absolute left-6 -top-6 w-0.5 h-6 bg-gray-300" />
      )}

      {/* Delay badge between steps */}
      {!isFirst && step.delay_days > 0 && (
        <div className="flex items-center justify-center mb-2 -mt-1">
          <div className="flex items-center gap-1 px-2 py-0.5 bg-amber-50 border border-amber-200 rounded-full text-xs text-amber-700">
            <Clock className="w-3 h-3" />
            Wait {step.delay_days} day{step.delay_days !== 1 ? 's' : ''}
          </div>
        </div>
      )}

      <div className={`border rounded-lg bg-white shadow-sm hover:shadow-md transition-shadow ${
        expanded ? 'ring-2 ring-blue-200' : ''
      }`}>
        {/* Header */}
        <div className="flex items-center gap-3 p-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
          <GripVertical className="w-4 h-4 text-gray-400 flex-shrink-0" />

          <div className={`w-8 h-8 rounded-full flex items-center justify-center bg-${typeColor}-100`}>
            <Icon className={`w-4 h-4 text-${typeColor}-600`} />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-900">
                Step {step.step_order}: {typeLabel}
              </span>
              <span className={`px-1.5 py-0.5 rounded text-xs font-medium bg-${typeColor}-50 text-${typeColor}-700`}>
                {isConnection ? 'Invite' : 'Message'}
              </span>
            </div>
            {step.prompt_context && (
              <p className="text-xs text-gray-500 truncate mt-0.5">{step.prompt_context}</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            {!disabled && (
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(step.id) }}
                className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                title="Remove step"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
            {expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
          </div>
        </div>

        {/* Expanded config */}
        {expanded && (
          <div className="border-t px-4 py-3 space-y-3">
            {/* Delay configuration */}
            {!isFirst && (
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Delay (days after previous step)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={0}
                    max={90}
                    value={delayDays}
                    onChange={(e) => setDelayDays(parseInt(e.target.value) || 0)}
                    onBlur={handleSaveDelay}
                    className="input w-24 text-sm"
                    disabled={disabled}
                  />
                  <span className="text-xs text-gray-500">days</span>
                </div>
              </div>
            )}

            {/* Prompt context */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                AI Guidance (optional)
              </label>
              <textarea
                value={promptContext}
                onChange={(e) => setPromptContext(e.target.value)}
                onBlur={handleSavePrompt}
                placeholder={isConnection
                  ? "e.g., Mention shared interest in AI and marketing"
                  : "e.g., Ask about their marketing goals, mention newsletter sponsorship"
                }
                className="input text-sm h-20 resize-none"
                disabled={disabled}
              />
              <p className="text-xs text-gray-400 mt-1">
                Guide the AI on what to focus on in this message
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Bottom connector */}
      {!isLast && (
        <div className="flex justify-center">
          <div className="w-0.5 h-6 bg-gray-300" />
        </div>
      )}
    </div>
  )
}
