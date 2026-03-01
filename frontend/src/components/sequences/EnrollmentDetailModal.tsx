import { useQuery } from '@tanstack/react-query'
import {
  X,
  Loader2,
  Flame,
  Thermometer,
  Snowflake,
  MessageSquare,
  Brain,
  User,
  Building2,
  Briefcase,
  TrendingUp,
  ArrowRight,
  AlertCircle,
  Signal,
} from 'lucide-react'
import { getEnrollmentDetail } from '../../services/api'

interface EnrollmentDetailModalProps {
  sequenceId: string
  enrollmentId: string
  onClose: () => void
}

const sentimentConfig: Record<string, { label: string; icon: typeof Flame; color: string; bg: string }> = {
  hot: { label: 'Hot', icon: Flame, color: 'text-red-600', bg: 'bg-red-100' },
  warm: { label: 'Warm', icon: Thermometer, color: 'text-amber-600', bg: 'bg-amber-100' },
  cold: { label: 'Cold', icon: Snowflake, color: 'text-blue-600', bg: 'bg-blue-100' },
}

const signalConfig: Record<string, { label: string; color: string; bg: string }> = {
  strong: { label: 'Strong', color: 'text-green-700', bg: 'bg-green-100' },
  moderate: { label: 'Moderate', color: 'text-yellow-700', bg: 'bg-yellow-100' },
  weak: { label: 'Weak', color: 'text-gray-600', bg: 'bg-gray-100' },
  none: { label: 'None', color: 'text-gray-400', bg: 'bg-gray-50' },
}

const phaseLabels: Record<string, string> = {
  apertura: 'Apertura',
  calificacion: 'Calificacion',
  valor: 'Valor',
  nurture: 'Nurture',
  reactivacion: 'Reactivacion',
}

const outcomeConfig: Record<string, { label: string; color: string; bg: string }> = {
  advance: { label: 'Advance', color: 'text-green-700', bg: 'bg-green-100' },
  stay: { label: 'Stay', color: 'text-blue-700', bg: 'bg-blue-100' },
  nurture: { label: 'Nurture', color: 'text-amber-700', bg: 'bg-amber-100' },
  park: { label: 'Park', color: 'text-gray-700', bg: 'bg-gray-100' },
  meeting: { label: 'Meeting!', color: 'text-emerald-700', bg: 'bg-emerald-100' },
  exit: { label: 'Exit', color: 'text-red-700', bg: 'bg-red-100' },
}

function formatRelativeTime(dateString: string | null | undefined) {
  if (!dateString) return '-'
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return '-'
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString('es-ES', { month: 'short', day: 'numeric' })
}

export default function EnrollmentDetailModal({
  sequenceId,
  enrollmentId,
  onClose,
}: EnrollmentDetailModalProps) {
  const { data: detail, isLoading } = useQuery({
    queryKey: ['enrollment-detail', sequenceId, enrollmentId],
    queryFn: () => getEnrollmentDetail(sequenceId, enrollmentId),
  })

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between flex-shrink-0">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Enrollment Detail</h3>
            <p className="text-sm text-gray-500">Pipeline supervision & message history</p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {isLoading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            </div>
          ) : !detail ? (
            <div className="flex flex-col items-center justify-center h-40 text-gray-500">
              <AlertCircle className="w-8 h-8 mb-2 text-gray-300" />
              <p className="text-sm">Could not load enrollment details</p>
            </div>
          ) : (
            <>
              {/* Lead Info + Intelligence */}
              <div className="border rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <User className="w-4 h-4 text-gray-400" />
                      <span className="font-semibold text-gray-900">{detail.lead_name || 'Unknown'}</span>
                    </div>
                    {detail.lead_job_title && (
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <Briefcase className="w-3.5 h-3.5" />
                        {detail.lead_job_title}
                      </div>
                    )}
                    {detail.lead_company && (
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <Building2 className="w-3.5 h-3.5" />
                        {detail.lead_company}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Sentiment badge */}
                    {detail.lead_sentiment_level && sentimentConfig[detail.lead_sentiment_level] && (() => {
                      const sc = sentimentConfig[detail.lead_sentiment_level!]
                      const SentIcon = sc.icon
                      return (
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${sc.bg} ${sc.color}`}>
                          <SentIcon className="w-3.5 h-3.5" />
                          {sc.label}
                        </span>
                      )
                    })()}

                    {/* Signal badge */}
                    {detail.lead_signal_strength && signalConfig[detail.lead_signal_strength] && (
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${signalConfig[detail.lead_signal_strength].bg} ${signalConfig[detail.lead_signal_strength].color}`}>
                        <Signal className="w-3 h-3" />
                        {signalConfig[detail.lead_signal_strength].label}
                      </span>
                    )}
                  </div>
                </div>

                {/* Current status bar */}
                <div className="mt-3 pt-3 border-t flex items-center gap-4 text-xs text-gray-500">
                  {detail.current_phase && (
                    <span className="flex items-center gap-1">
                      <TrendingUp className="w-3 h-3" />
                      Phase: <strong className="text-gray-700">{phaseLabels[detail.current_phase] || detail.current_phase}</strong>
                    </span>
                  )}
                  <span>Msgs in phase: <strong className="text-gray-700">{detail.messages_in_phase}/2</strong></span>
                  <span>Total sent: <strong className="text-gray-700">{detail.total_messages_sent}</strong></span>
                  {detail.phase_entered_at && (
                    <span>In phase: <strong className="text-gray-700">{formatRelativeTime(detail.phase_entered_at)}</strong></span>
                  )}
                </div>

                {/* Buying signals */}
                {detail.lead_buying_signals && detail.lead_buying_signals.length > 0 && (
                  <div className="mt-3 pt-3 border-t">
                    <p className="text-xs font-medium text-gray-500 mb-1">Buying Signals</p>
                    <div className="flex flex-wrap gap-1">
                      {detail.lead_buying_signals.map((signal, i) => (
                        <span key={i} className="px-2 py-0.5 bg-green-50 text-green-700 text-xs rounded-full">
                          {signal}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Messages Timeline */}
              <div className="border rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <MessageSquare className="w-4 h-4 text-blue-600" />
                  <h4 className="text-sm font-semibold text-gray-900">Messages Sent</h4>
                </div>

                {detail.messages.length === 0 ? (
                  <p className="text-sm text-gray-400 italic">No messages sent yet</p>
                ) : (
                  <div className="space-y-3">
                    {detail.messages.map((msg, i) => {
                      const isPipelineMsg = msg.key.startsWith('pipeline_')
                      const phaseMatch = msg.key.match(/pipeline_(\w+)_(\d+)/)
                      const phaseLabel = phaseMatch ? (phaseLabels[phaseMatch[1]] || phaseMatch[1]) : `Step ${msg.key}`
                      const msgNum = phaseMatch ? phaseMatch[2] : null

                      return (
                        <div key={i} className="relative pl-4 border-l-2 border-blue-200">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-medium text-blue-600">
                              {isPipelineMsg ? `${phaseLabel} #${msgNum}` : phaseLabel}
                            </span>
                          </div>
                          <p className="text-sm text-gray-700 whitespace-pre-wrap bg-blue-50 rounded-lg p-3">
                            {msg.message_text}
                          </p>
                        </div>
                      )
                    })}
                  </div>
                )}

                {/* Last response from lead */}
                {detail.last_response_text && (
                  <div className="mt-4 pt-3 border-t">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-medium text-gray-500">Last Response from Lead</span>
                      {detail.last_response_at && (
                        <span className="text-xs text-gray-400">{formatRelativeTime(detail.last_response_at)}</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700 whitespace-pre-wrap bg-orange-50 rounded-lg p-3 border-l-2 border-orange-300">
                      {detail.last_response_text}
                    </p>
                  </div>
                )}
              </div>

              {/* AI Analysis */}
              {detail.phase_analysis && Object.keys(detail.phase_analysis).length > 0 && (() => {
                const analysis = detail.phase_analysis as Record<string, string>
                return (
                  <div className="border rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Brain className="w-4 h-4 text-purple-600" />
                      <h4 className="text-sm font-semibold text-gray-900">AI Analysis</h4>
                    </div>

                    <div className="space-y-3">
                      {/* Outcome */}
                      {analysis.outcome && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500 w-20">Decision:</span>
                          {(() => {
                            const oc = outcomeConfig[analysis.outcome] || { label: analysis.outcome, color: 'text-gray-700', bg: 'bg-gray-100' }
                            return (
                              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${oc.bg} ${oc.color}`}>
                                <ArrowRight className="w-3 h-3" />
                                {oc.label}
                              </span>
                            )
                          })()}
                          {analysis.next_phase && (
                            <span className="text-xs text-gray-500">
                              &rarr; {phaseLabels[analysis.next_phase] || analysis.next_phase}
                            </span>
                          )}
                        </div>
                      )}

                      {/* Reason */}
                      {analysis.reason && (
                        <div>
                          <span className="text-xs text-gray-500">Reasoning:</span>
                          <p className="text-sm text-gray-700 mt-0.5 bg-purple-50 rounded p-2">
                            {analysis.reason}
                          </p>
                        </div>
                      )}

                      {/* Suggested angle */}
                      {analysis.suggested_angle && (
                        <div>
                          <span className="text-xs text-gray-500">Suggested angle for next message:</span>
                          <p className="text-sm text-gray-600 mt-0.5 italic">
                            {analysis.suggested_angle}
                          </p>
                        </div>
                      )}

                      {/* Sentiment & signals from analysis */}
                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        {analysis.sentiment && (
                          <span>Sentiment: <strong className="text-gray-700">{analysis.sentiment}</strong></span>
                        )}
                        {analysis.signal_strength && (
                          <span>Signal: <strong className="text-gray-700">{analysis.signal_strength}</strong></span>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })()}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t flex justify-end flex-shrink-0">
          <button onClick={onClose} className="btn btn-secondary text-sm">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
