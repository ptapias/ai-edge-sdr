import { useState } from 'react'
import { Plus, Send, MessageSquare, Sparkles, ArrowDown, MessageCircle, RefreshCw, Heart, Target } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { addSequenceStep, updateSequenceStep, deleteSequenceStep } from '../../services/api'
import type { Sequence } from '../../services/api'
import StepCard from './StepCard'

interface SequenceBuilderProps {
  sequence: Sequence
}

// Phase configuration for the pipeline view
const pipelinePhases = [
  {
    id: 'connection',
    name: 'Connection Request',
    description: 'AI sends a personalized connection request with a gradual/curiosity approach',
    icon: Send,
    borderColor: 'border-blue-200',
    bgColor: 'bg-blue-50',
    iconColor: 'text-blue-600',
  },
  {
    id: 'apertura',
    name: 'Phase 1: Apertura',
    description: 'Genuine curiosity question about their work. No pitch, no product mention.',
    icon: MessageCircle,
    borderColor: 'border-indigo-200',
    bgColor: 'bg-indigo-50',
    iconColor: 'text-indigo-600',
    trigger: 'Connection accepted',
  },
  {
    id: 'calificacion',
    name: 'Phase 2: Calificación',
    description: 'Qualification questions to discover if they\'re in growth/investment mode.',
    icon: Target,
    borderColor: 'border-violet-200',
    bgColor: 'bg-violet-50',
    iconColor: 'text-violet-600',
    trigger: 'Positive engagement',
  },
  {
    id: 'valor',
    name: 'Phase 3: Valor',
    description: 'Connect their specific need with your newsletter sponsorship. First time product is mentioned.',
    icon: Sparkles,
    borderColor: 'border-purple-200',
    bgColor: 'bg-purple-50',
    iconColor: 'text-purple-600',
    trigger: 'Growth signals detected',
  },
  {
    id: 'nurture',
    name: 'Phase 4: Nurture',
    description: 'Light-touch every 6-8 weeks. Share value, no pressure. Max 4 touches.',
    icon: Heart,
    borderColor: 'border-amber-200',
    bgColor: 'bg-amber-50',
    iconColor: 'text-amber-600',
    trigger: 'Not ready yet / Cold response',
  },
  {
    id: 'reactivacion',
    name: 'Phase 5: Reactivación',
    description: 'Fresh angle after 30+ days of silence. Different approach to re-open conversation.',
    icon: RefreshCw,
    borderColor: 'border-orange-200',
    bgColor: 'bg-orange-50',
    iconColor: 'text-orange-600',
    trigger: '30+ days no response',
  },
]

export default function SequenceBuilder({ sequence }: SequenceBuilderProps) {
  const queryClient = useQueryClient()
  const [showAddStep, setShowAddStep] = useState(false)
  const isActive = sequence.status === 'active'
  const isPipeline = sequence.sequence_mode === 'smart_pipeline'

  const addStepMutation = useMutation({
    mutationFn: (step: { step_type: string; delay_days: number; prompt_context?: string }) =>
      addSequenceStep(sequence.id, step),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sequence', sequence.id] })
      setShowAddStep(false)
    },
  })

  const updateStepMutation = useMutation({
    mutationFn: ({ stepId, data }: { stepId: string; data: Partial<{ delay_days: number; prompt_context: string }> }) =>
      updateSequenceStep(sequence.id, stepId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sequence', sequence.id] })
    },
  })

  const deleteStepMutation = useMutation({
    mutationFn: (stepId: string) => deleteSequenceStep(sequence.id, stepId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sequence', sequence.id] })
    },
  })

  const handleAddStep = (stepType: 'connection_request' | 'follow_up_message') => {
    const isFirstStep = sequence.steps.length === 0
    addStepMutation.mutate({
      step_type: stepType,
      delay_days: isFirstStep ? 0 : 3,
    })
  }

  const handleUpdateStep = (stepId: string, data: Partial<{ delay_days: number; prompt_context: string }>) => {
    updateStepMutation.mutate({ stepId, data })
  }

  const handleDeleteStep = (stepId: string) => {
    if (confirm('Remove this step from the sequence?')) {
      deleteStepMutation.mutate(stepId)
    }
  }

  // Smart Pipeline view
  if (isPipeline) {
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="w-5 h-5 text-purple-600" />
          <h4 className="text-sm font-semibold text-gray-900">Smart Pipeline Phases</h4>
          <span className="text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full">AI-driven</span>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          Phase advancement is based on the lead's response, not time elapsed. AI analyzes each reply and decides the next action.
        </p>

        <div className="relative">
          {pipelinePhases.map((phase, index) => {
            const Icon = phase.icon
            return (
              <div key={phase.id}>
                <div className={`flex items-start gap-3 p-3 rounded-lg border ${phase.borderColor} ${phase.bgColor} mb-2`}>
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 bg-white border ${phase.borderColor}`}>
                    <Icon className={`w-5 h-5 ${phase.iconColor}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-900">{phase.name}</p>
                      {phase.trigger && (
                        <span className="text-xs text-gray-400 italic">← {phase.trigger}</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-600 mt-0.5">{phase.description}</p>
                  </div>
                </div>

                {index < pipelinePhases.length - 1 && (
                  <div className="flex justify-center -my-1 mb-1">
                    <ArrowDown className="w-4 h-4 text-gray-300" />
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div className="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
          <p className="text-xs font-medium text-gray-700 mb-1">Key rules:</p>
          <ul className="text-xs text-gray-500 space-y-0.5">
            <li>• Max 2 outbound messages per phase before forcing transition</li>
            <li>• Max 4 nurture touches over ~24-32 weeks</li>
            <li>• Max 1 reactivation attempt per lead</li>
            <li>• Meeting intent → human takes over immediately</li>
          </ul>
        </div>
      </div>
    )
  }

  // Classic step builder (existing)
  const hasConnectionStep = sequence.steps.some(s => s.step_type === 'connection_request')

  return (
    <div className="space-y-2">
      {/* Steps timeline */}
      {sequence.steps.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <MessageSquare className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="text-sm font-medium">No steps yet</p>
          <p className="text-xs mt-1">Add steps to build your outreach sequence</p>
        </div>
      ) : (
        <div className="space-y-0">
          {sequence.steps.map((step, index) => (
            <StepCard
              key={step.id}
              step={step}
              isFirst={index === 0}
              isLast={index === sequence.steps.length - 1}
              onUpdate={handleUpdateStep}
              onDelete={handleDeleteStep}
              disabled={isActive}
            />
          ))}
        </div>
      )}

      {/* Add step buttons */}
      {!isActive && (
        <div className="pt-2">
          {showAddStep ? (
            <div className="flex items-center gap-2">
              {!hasConnectionStep && (
                <button
                  onClick={() => handleAddStep('connection_request')}
                  disabled={addStepMutation.isPending}
                  className="btn btn-primary text-sm flex items-center gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" />
                  Connection Request
                </button>
              )}
              <button
                onClick={() => handleAddStep('follow_up_message')}
                disabled={addStepMutation.isPending || (!hasConnectionStep && sequence.steps.length === 0)}
                className="btn btn-secondary text-sm flex items-center gap-1.5"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                Follow-up Message
              </button>
              <button
                onClick={() => setShowAddStep(false)}
                className="text-sm text-gray-500 hover:text-gray-700 ml-2"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowAddStep(true)}
              className="w-full py-2 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors flex items-center justify-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              Add Step
            </button>
          )}

          {!hasConnectionStep && sequence.steps.length === 0 && (
            <p className="text-xs text-amber-600 mt-2 text-center">
              Start with a Connection Request step
            </p>
          )}
        </div>
      )}
    </div>
  )
}
