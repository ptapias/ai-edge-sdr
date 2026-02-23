import { useState } from 'react'
import { Plus, Send, MessageSquare } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { addSequenceStep, updateSequenceStep, deleteSequenceStep } from '../../services/api'
import type { Sequence } from '../../services/api'
import StepCard from './StepCard'

interface SequenceBuilderProps {
  sequence: Sequence
}

export default function SequenceBuilder({ sequence }: SequenceBuilderProps) {
  const queryClient = useQueryClient()
  const [showAddStep, setShowAddStep] = useState(false)
  const isActive = sequence.status === 'active'

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
