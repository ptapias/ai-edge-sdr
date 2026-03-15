import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getExperimentDashboard,
  getExperimentDetail,
  createBaseline,
  evaluateExperiment,
  proposeAndCreateExperiment,
  startExperiment,
  deleteExperiment,
  type Experiment,
  type ExperimentDetail,
  type ExperimentDashboard,
} from '../services/api'

function StatusBadge({ status, decision }: { status: string; decision: string }) {
  const colorMap: Record<string, string> = {
    baseline: 'bg-blue-100 text-blue-800',
    running: 'bg-yellow-100 text-yellow-800',
    evaluating: 'bg-purple-100 text-purple-800',
    kept: 'bg-green-100 text-green-800',
    discarded: 'bg-red-100 text-red-800',
    pending: 'bg-gray-100 text-gray-800',
  }
  const label = decision === 'baseline' ? 'BASELINE' :
    decision === 'keep' ? 'KEPT' :
    decision === 'discard' ? 'DISCARDED' :
    status.toUpperCase()
  const color = colorMap[decision === 'keep' ? 'kept' : decision === 'discard' ? 'discarded' : status] || colorMap.pending
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {label}
    </span>
  )
}

function StatsCards({ dashboard }: { dashboard: ExperimentDashboard }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-white rounded-lg shadow p-4">
        <div className="text-sm font-medium text-gray-500">Experiments</div>
        <div className="mt-1 text-2xl font-bold text-gray-900">{dashboard.total_experiments}</div>
        <div className="text-xs text-gray-500 mt-1">
          {dashboard.kept_count} kept / {dashboard.discarded_count} discarded
        </div>
      </div>
      <div className="bg-white rounded-lg shadow p-4">
        <div className="text-sm font-medium text-gray-500">Current Acceptance Rate</div>
        <div className="mt-1 text-2xl font-bold text-blue-600">
          {dashboard.current_baseline_rate != null ? `${dashboard.current_baseline_rate}%` : '--'}
        </div>
        <div className="text-xs text-gray-500 mt-1">Active baseline</div>
      </div>
      <div className="bg-white rounded-lg shadow p-4">
        <div className="text-sm font-medium text-gray-500">Best Ever</div>
        <div className="mt-1 text-2xl font-bold text-green-600">
          {dashboard.best_ever_rate != null ? `${dashboard.best_ever_rate}%` : '--'}
        </div>
        <div className="text-xs text-gray-500 mt-1">Highest acceptance rate</div>
      </div>
      <div className="bg-white rounded-lg shadow p-4">
        <div className="text-sm font-medium text-gray-500">Total Improvement</div>
        <div className={`mt-1 text-2xl font-bold ${(dashboard.total_improvement ?? 0) > 0 ? 'text-green-600' : 'text-gray-400'}`}>
          {dashboard.total_improvement != null ? `${dashboard.total_improvement > 0 ? '+' : ''}${dashboard.total_improvement}pp` : '--'}
        </div>
        <div className="text-xs text-gray-500 mt-1">From first baseline</div>
      </div>
    </div>
  )
}

function ExperimentTable({
  experiments,
  onSelect,
  selectedId,
}: {
  experiments: Experiment[]
  onSelect: (id: string) => void
  selectedId: string | null
}) {
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">#</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Accept %</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Resp %</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sent</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Change</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {experiments.map((exp) => (
            <tr
              key={exp.id}
              onClick={() => onSelect(exp.id)}
              className={`cursor-pointer hover:bg-gray-50 ${selectedId === exp.id ? 'bg-blue-50' : ''}`}
            >
              <td className="px-4 py-3 text-sm text-gray-900 font-mono">#{exp.experiment_number}</td>
              <td className="px-4 py-3 text-sm text-gray-900">{exp.experiment_name}</td>
              <td className="px-4 py-3 text-sm font-medium">
                {exp.acceptance_rate != null ? (
                  <span className={exp.improvement_acceptance && exp.improvement_acceptance > 0 ? 'text-green-600' : exp.improvement_acceptance && exp.improvement_acceptance < 0 ? 'text-red-600' : 'text-gray-900'}>
                    {exp.acceptance_rate}%
                    {exp.improvement_acceptance != null && exp.decision !== 'baseline' && (
                      <span className="text-xs ml-1">
                        ({exp.improvement_acceptance > 0 ? '+' : ''}{exp.improvement_acceptance}pp)
                      </span>
                    )}
                  </span>
                ) : <span className="text-gray-400">--</span>}
              </td>
              <td className="px-4 py-3 text-sm">
                {exp.response_rate != null ? `${exp.response_rate}%` : <span className="text-gray-400">--</span>}
              </td>
              <td className="px-4 py-3 text-sm text-gray-600">{exp.connections_sent}/{exp.batch_size}</td>
              <td className="px-4 py-3"><StatusBadge status={exp.status} decision={exp.decision} /></td>
              <td className="px-4 py-3 text-sm text-gray-500 max-w-xs truncate">{exp.change_description || '-'}</td>
            </tr>
          ))}
          {experiments.length === 0 && (
            <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">No experiments yet. Create a baseline to start.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function ExperimentDetailPanel({
  experimentId,
  onClose,
  onEvaluate,
  onStart,
  onDelete,
}: {
  experimentId: string
  onClose: () => void
  onEvaluate: (id: string) => void
  onStart: (id: string) => void
  onDelete: (id: string) => void
}) {
  const { data: detail, isLoading } = useQuery<ExperimentDetail>({
    queryKey: ['experiment-detail', experimentId],
    queryFn: () => getExperimentDetail(experimentId),
  })

  if (isLoading || !detail) {
    return (
      <div className="bg-white rounded-lg shadow p-6 mt-4">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded w-1/3"></div>
          <div className="h-20 bg-gray-200 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 mt-4">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            #{detail.experiment_number} — {detail.experiment_name}
          </h3>
          <p className="text-sm text-gray-600 mt-1">{detail.hypothesis}</p>
        </div>
        <div className="flex gap-2">
          {detail.status === 'pending' && (
            <button
              onClick={() => onStart(detail.id)}
              className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
            >
              Start
            </button>
          )}
          {(detail.status === 'running' || detail.status === 'evaluating' || detail.status === 'baseline') && (
            <button
              onClick={() => onEvaluate(detail.id)}
              className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded-md hover:bg-purple-700"
            >
              Evaluate
            </button>
          )}
          {(detail.status === 'pending' || detail.decision === 'discard') && (
            <button
              onClick={() => onDelete(detail.id)}
              className="px-3 py-1.5 bg-red-100 text-red-700 text-sm rounded-md hover:bg-red-200"
            >
              Delete
            </button>
          )}
          <button onClick={onClose} className="px-3 py-1.5 text-gray-500 text-sm hover:text-gray-700">
            Close
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4 mb-4">
        <div className="text-center p-3 bg-gray-50 rounded">
          <div className="text-lg font-bold">{detail.connections_sent}</div>
          <div className="text-xs text-gray-500">Sent</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded">
          <div className="text-lg font-bold text-green-600">{detail.connections_accepted}</div>
          <div className="text-xs text-gray-500">Accepted</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded">
          <div className="text-lg font-bold text-blue-600">{detail.responses_received}</div>
          <div className="text-xs text-gray-500">Responded</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded">
          <div className="text-lg font-bold">
            {detail.acceptance_rate != null ? `${detail.acceptance_rate}%` : '--'}
          </div>
          <div className="text-xs text-gray-500">Accept Rate</div>
        </div>
      </div>

      {/* Change description */}
      {detail.change_description && detail.decision !== 'baseline' && (
        <div className="mb-4 p-3 bg-yellow-50 rounded border border-yellow-100">
          <div className="text-xs font-medium text-yellow-800 mb-1">Change vs Baseline:</div>
          <div className="text-sm text-yellow-900">{detail.change_description}</div>
        </div>
      )}

      {/* Prompt template (collapsible) */}
      <details className="mb-4">
        <summary className="text-sm font-medium text-gray-700 cursor-pointer hover:text-gray-900">
          View Prompt Template
        </summary>
        <pre className="mt-2 p-3 bg-gray-50 rounded text-xs text-gray-700 whitespace-pre-wrap max-h-60 overflow-y-auto">
          {detail.prompt_template}
        </pre>
      </details>

      {/* Lead outcomes table */}
      {detail.leads.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Lead Outcomes ({detail.leads.length})</h4>
          <div className="max-h-64 overflow-y-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs text-gray-500">Lead</th>
                  <th className="px-3 py-2 text-left text-xs text-gray-500">Company</th>
                  <th className="px-3 py-2 text-left text-xs text-gray-500">Message</th>
                  <th className="px-3 py-2 text-left text-xs text-gray-500">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {detail.leads.map((lead) => (
                  <tr key={lead.id}>
                    <td className="px-3 py-2 text-gray-900">{lead.lead_name || 'Unknown'}</td>
                    <td className="px-3 py-2 text-gray-600">{lead.lead_company || '-'}</td>
                    <td className="px-3 py-2 text-gray-600 max-w-xs truncate" title={lead.message_sent || ''}>
                      {lead.message_sent ? lead.message_sent.substring(0, 80) + (lead.message_sent.length > 80 ? '...' : '') : '-'}
                    </td>
                    <td className="px-3 py-2">
                      {lead.accepted === true ? (
                        <span className="text-green-600 font-medium">Accepted</span>
                      ) : lead.accepted === false ? (
                        <span className="text-red-600">Rejected</span>
                      ) : (
                        <span className="text-gray-400">Pending</span>
                      )}
                      {lead.responded && <span className="ml-2 text-blue-600 text-xs">+ Replied</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ExperimentsPage() {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: dashboard, isLoading } = useQuery<ExperimentDashboard>({
    queryKey: ['experiment-dashboard'],
    queryFn: getExperimentDashboard,
    refetchInterval: 30000,
  })

  const baselineMutation = useMutation({
    mutationFn: createBaseline,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiment-dashboard'] })
    },
  })

  const proposeMutation = useMutation({
    mutationFn: proposeAndCreateExperiment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiment-dashboard'] })
    },
  })

  const evaluateMutation = useMutation({
    mutationFn: evaluateExperiment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiment-dashboard'] })
      if (selectedId) {
        queryClient.invalidateQueries({ queryKey: ['experiment-detail', selectedId] })
      }
    },
  })

  const startMutation = useMutation({
    mutationFn: startExperiment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiment-dashboard'] })
      if (selectedId) {
        queryClient.invalidateQueries({ queryKey: ['experiment-detail', selectedId] })
      }
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteExperiment,
    onSuccess: () => {
      setSelectedId(null)
      queryClient.invalidateQueries({ queryKey: ['experiment-dashboard'] })
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const experiments = dashboard?.experiments || []
  const hasBaseline = experiments.some(e => e.decision === 'baseline')
  const hasRunning = experiments.some(e => e.status === 'running' || e.status === 'evaluating')

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AutoOutreach</h1>
          <p className="text-sm text-gray-500 mt-1">
            Self-improving connection messages — inspired by Karpathy's autoresearch
          </p>
        </div>
        <div className="flex gap-3">
          {!hasBaseline && (
            <button
              onClick={() => baselineMutation.mutate()}
              disabled={baselineMutation.isPending}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {baselineMutation.isPending ? 'Creating...' : 'Create Baseline'}
            </button>
          )}
          {hasBaseline && !hasRunning && (
            <button
              onClick={() => proposeMutation.mutate()}
              disabled={proposeMutation.isPending}
              className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {proposeMutation.isPending ? 'Claude is thinking...' : 'Propose Next Experiment'}
            </button>
          )}
        </div>
      </div>

      {/* Error display */}
      {(baselineMutation.isError || proposeMutation.isError) && (
        <div className="mb-4 p-3 bg-red-50 rounded-lg border border-red-200">
          <p className="text-sm text-red-700">
            {(baselineMutation.error as Error)?.message || (proposeMutation.error as Error)?.message || 'An error occurred'}
          </p>
        </div>
      )}

      {/* Stats Cards */}
      {dashboard && <StatsCards dashboard={dashboard} />}

      {/* Experiment Table */}
      <ExperimentTable
        experiments={experiments}
        onSelect={setSelectedId}
        selectedId={selectedId}
      />

      {/* Detail Panel */}
      {selectedId && (
        <ExperimentDetailPanel
          experimentId={selectedId}
          onClose={() => setSelectedId(null)}
          onEvaluate={(id) => evaluateMutation.mutate(id)}
          onStart={(id) => startMutation.mutate(id)}
          onDelete={(id) => {
            if (window.confirm('Delete this experiment?')) {
              deleteMutation.mutate(id)
            }
          }}
        />
      )}

      {/* How it works */}
      {experiments.length === 0 && (
        <div className="mt-8 bg-blue-50 rounded-lg p-6 border border-blue-100">
          <h3 className="text-lg font-semibold text-blue-900 mb-3">How AutoOutreach Works</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm text-blue-800">
            <div className="flex flex-col items-center text-center p-3">
              <div className="text-2xl mb-2">1</div>
              <div className="font-medium">Baseline</div>
              <div className="text-xs mt-1">Measure current acceptance rate with the default prompt</div>
            </div>
            <div className="flex flex-col items-center text-center p-3">
              <div className="text-2xl mb-2">2</div>
              <div className="font-medium">Propose</div>
              <div className="text-xs mt-1">Claude analyzes results and proposes ONE small change</div>
            </div>
            <div className="flex flex-col items-center text-center p-3">
              <div className="text-2xl mb-2">3</div>
              <div className="font-medium">Run</div>
              <div className="text-xs mt-1">Send 20-30 connections with the new prompt variant</div>
            </div>
            <div className="flex flex-col items-center text-center p-3">
              <div className="text-2xl mb-2">4</div>
              <div className="font-medium">Decide</div>
              <div className="text-xs mt-1">Better rate? KEEP. Worse? DISCARD. Repeat forever.</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
