import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FileText,
  X,
  RefreshCw,
  Loader2,
  Send,
  ChevronDown,
  ChevronUp,
  Clock,
  User,
  Building2,
  MessageCircle,
  Brain,
  TrendingUp,
  TrendingDown,
  Minus,
} from 'lucide-react'

// API functions
const api = {
  getDrafts: async (status?: string) => {
    const url = status ? `/api/drafts/?status=${status}` : '/api/drafts/'
    const res = await fetch(url, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
    })
    if (!res.ok) throw new Error('Failed to fetch drafts')
    return res.json()
  },
  getDraftCount: async () => {
    const res = await fetch('/api/drafts/count', {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
    })
    if (!res.ok) throw new Error('Failed')
    return res.json()
  },
  approveDraft: async ({ id, message }: { id: string; message?: string }) => {
    const res = await fetch(`/api/drafts/${id}/approve`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ message: message || undefined })
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Failed to approve')
    }
    return res.json()
  },
  rejectDraft: async ({ id, reason }: { id: string; reason?: string }) => {
    const res = await fetch(`/api/drafts/${id}/reject`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ reason })
    })
    if (!res.ok) throw new Error('Failed to reject')
    return res.json()
  },
  regenerateDraft: async (id: string) => {
    const res = await fetch(`/api/drafts/${id}/regenerate`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
    })
    if (!res.ok) throw new Error('Failed to regenerate')
    return res.json()
  },
}

const PHASE_COLORS: Record<string, string> = {
  apertura: 'bg-blue-100 text-blue-700',
  calificacion: 'bg-yellow-100 text-yellow-700',
  valor: 'bg-green-100 text-green-700',
  nurture: 'bg-purple-100 text-purple-700',
  reactivacion: 'bg-orange-100 text-orange-700',
}

const PHASE_LABELS: Record<string, string> = {
  apertura: 'Apertura',
  calificacion: 'Calificación',
  valor: 'Valor',
  nurture: 'Nurture',
  reactivacion: 'Reactivación',
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700',
  approved: 'bg-blue-100 text-blue-700',
  sent: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
}

interface Draft {
  id: string
  enrollment_id: string
  lead_id: string
  sequence_id: string
  pipeline_phase: string | null
  step_order: number | null
  generated_message: string
  final_message: string | null
  status: string
  created_at: string
  reviewed_at: string | null
  sent_at: string | null
  rejection_reason: string | null
  lead_name: string
  lead_company: string | null
  lead_job_title: string | null
  sequence_name: string
  lead_reply_text: string | null
  analysis_sentiment: string | null
  analysis_signal_strength: string | null
  analysis_buying_signals: string | null
  analysis_reasoning: string | null
  analysis_outcome: string | null
}

const SENTIMENT_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  positive: { label: 'Positivo', color: 'text-green-600 bg-green-50 border-green-200', icon: 'up' },
  neutral: { label: 'Neutral', color: 'text-gray-600 bg-gray-50 border-gray-200', icon: 'flat' },
  cautious: { label: 'Cauteloso', color: 'text-amber-600 bg-amber-50 border-amber-200', icon: 'flat' },
  negative: { label: 'Negativo', color: 'text-red-600 bg-red-50 border-red-200', icon: 'down' },
}

const SIGNAL_CONFIG: Record<string, { label: string; color: string }> = {
  strong: { label: 'Fuerte', color: 'text-green-700 bg-green-100' },
  moderate: { label: 'Moderada', color: 'text-yellow-700 bg-yellow-100' },
  weak: { label: 'Débil', color: 'text-orange-700 bg-orange-100' },
  none: { label: 'Sin señales', color: 'text-gray-500 bg-gray-100' },
}

export default function DraftsPage() {
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<string>('pending')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [editedMessages, setEditedMessages] = useState<Record<string, string>>({})

  const { data: drafts = [], isLoading } = useQuery({
    queryKey: ['drafts', filter],
    queryFn: () => api.getDrafts(filter || undefined),
    refetchInterval: 15000,
  })

  const approveMutation = useMutation({
    mutationFn: api.approveDraft,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drafts'] })
      queryClient.invalidateQueries({ queryKey: ['draft-count'] })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: api.rejectDraft,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drafts'] })
      queryClient.invalidateQueries({ queryKey: ['draft-count'] })
    },
  })

  const regenerateMutation = useMutation({
    mutationFn: api.regenerateDraft,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drafts'] })
      queryClient.invalidateQueries({ queryKey: ['draft-count'] })
    },
  })

  const handleApprove = (draft: Draft) => {
    const editedMsg = editedMessages[draft.id]
    approveMutation.mutate({
      id: draft.id,
      message: editedMsg !== draft.generated_message ? editedMsg : undefined
    })
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileText className="w-6 h-6" />
            Borradores Smart Pipeline
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            Revisa y aprueba los mensajes generados por IA antes de enviarlos
          </p>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 border-b">
        {[
          { value: 'pending', label: 'Pendientes' },
          { value: 'sent', label: 'Enviados' },
          { value: 'rejected', label: 'Rechazados' },
          { value: '', label: 'Todos' },
        ].map(tab => (
          <button
            key={tab.value}
            onClick={() => setFilter(tab.value)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              filter === tab.value
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
        </div>
      ) : drafts.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="text-lg">No hay borradores {filter === 'pending' ? 'pendientes' : ''}</p>
          <p className="text-sm mt-1">
            Los borradores se crean automáticamente cuando una secuencia Smart Pipeline genera un mensaje
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {(drafts as Draft[]).map((draft) => {
            const isExpanded = expandedId === draft.id
            const editedMsg = editedMessages[draft.id] ?? draft.generated_message

            return (
              <div key={draft.id} className="border rounded-lg bg-white shadow-sm">
                {/* Header row */}
                <div
                  className="flex items-center gap-3 p-4 cursor-pointer hover:bg-gray-50"
                  onClick={() => {
                    setExpandedId(isExpanded ? null : draft.id)
                    if (!editedMessages[draft.id]) {
                      setEditedMessages(prev => ({ ...prev, [draft.id]: draft.generated_message }))
                    }
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{draft.lead_name}</span>
                      {draft.lead_company && (
                        <span className="text-gray-400 text-sm flex items-center gap-1">
                          <Building2 className="w-3 h-3" /> {draft.lead_company}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 truncate mt-0.5">
                      {draft.generated_message.substring(0, 100)}...
                    </p>
                  </div>

                  {/* Phase badge */}
                  {draft.pipeline_phase && (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${PHASE_COLORS[draft.pipeline_phase] || 'bg-gray-100'}`}>
                      {PHASE_LABELS[draft.pipeline_phase] || draft.pipeline_phase}
                    </span>
                  )}

                  {/* Status badge */}
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[draft.status] || 'bg-gray-100'}`}>
                    {draft.status}
                  </span>

                  {/* Time */}
                  <span className="text-xs text-gray-400 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(draft.created_at).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  </span>

                  {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                </div>

                {/* Expanded content */}
                {isExpanded && (
                  <div className="border-t p-4">
                    <div className="flex items-center gap-2 mb-3 text-sm text-gray-500">
                      <User className="w-4 h-4" />
                      <span>{draft.lead_name}</span>
                      {draft.lead_job_title && <span>· {draft.lead_job_title}</span>}
                      <span>· Secuencia: {draft.sequence_name}</span>
                    </div>

                    {/* Lead's reply */}
                    {draft.lead_reply_text && (
                      <div className="mb-4 border border-gray-200 rounded-lg overflow-hidden">
                        <div className="bg-gray-50 px-3 py-2 flex items-center gap-2 text-xs font-medium text-gray-500 border-b">
                          <MessageCircle className="w-3.5 h-3.5" />
                          Mensaje de {draft.lead_name}
                        </div>
                        <div className="p-3 text-sm bg-white whitespace-pre-wrap">
                          {draft.lead_reply_text}
                        </div>
                      </div>
                    )}

                    {/* AI Analysis */}
                    {draft.analysis_sentiment && (
                      <div className="mb-4 border border-indigo-100 rounded-lg overflow-hidden">
                        <div className="bg-indigo-50 px-3 py-2 flex items-center gap-2 text-xs font-medium text-indigo-600 border-b border-indigo-100">
                          <Brain className="w-3.5 h-3.5" />
                          Análisis IA de la conversación
                        </div>
                        <div className="p-3 bg-white">
                          <div className="flex flex-wrap gap-2 mb-2">
                            {/* Sentiment badge */}
                            {(() => {
                              const cfg = SENTIMENT_CONFIG[draft.analysis_sentiment || ''] || SENTIMENT_CONFIG.neutral
                              return (
                                <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${cfg.color}`}>
                                  {cfg.icon === 'up' && <TrendingUp className="w-3 h-3" />}
                                  {cfg.icon === 'down' && <TrendingDown className="w-3 h-3" />}
                                  {cfg.icon === 'flat' && <Minus className="w-3 h-3" />}
                                  Sentimiento: {cfg.label}
                                </span>
                              )
                            })()}
                            {/* Signal strength badge */}
                            {draft.analysis_signal_strength && (() => {
                              const cfg = SIGNAL_CONFIG[draft.analysis_signal_strength] || SIGNAL_CONFIG.none
                              return (
                                <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.color}`}>
                                  Señal de compra: {cfg.label}
                                </span>
                              )
                            })()}
                            {/* Outcome badge */}
                            {draft.analysis_outcome && (
                              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-600">
                                Acción: {draft.analysis_outcome}
                              </span>
                            )}
                          </div>
                          {/* Reasoning */}
                          {draft.analysis_reasoning && (
                            <p className="text-sm text-gray-600 mt-1 italic">
                              {draft.analysis_reasoning}
                            </p>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Generated response label */}
                    <div className="mb-2 flex items-center gap-2 text-xs font-medium text-gray-500">
                      <Send className="w-3.5 h-3.5" />
                      Respuesta generada
                    </div>

                    {draft.status === 'pending' ? (
                      <textarea
                        value={editedMsg}
                        onChange={(e) => setEditedMessages(prev => ({ ...prev, [draft.id]: e.target.value }))}
                        className="w-full h-40 input font-mono text-sm resize-none mb-3"
                      />
                    ) : (
                      <div className="bg-gray-50 rounded-lg p-3 mb-3 text-sm whitespace-pre-wrap">
                        {draft.final_message || draft.generated_message}
                      </div>
                    )}

                    {draft.rejection_reason && (
                      <p className="text-sm text-red-600 mb-3">Motivo de rechazo: {draft.rejection_reason}</p>
                    )}

                    {draft.status === 'pending' && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleApprove(draft)}
                          disabled={approveMutation.isPending}
                          className="btn btn-primary flex items-center gap-1 text-sm"
                        >
                          {approveMutation.isPending ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Send className="w-4 h-4" />
                          )}
                          Aprobar y Enviar
                        </button>
                        <button
                          onClick={() => {
                            const reason = prompt('Motivo del rechazo (opcional):')
                            rejectMutation.mutate({ id: draft.id, reason: reason || undefined })
                          }}
                          disabled={rejectMutation.isPending}
                          className="btn btn-secondary flex items-center gap-1 text-sm text-red-600"
                        >
                          <X className="w-4 h-4" /> Rechazar
                        </button>
                        {editedMsg !== draft.generated_message && (
                          <span className="text-xs text-amber-600 ml-2">Editado</span>
                        )}
                      </div>
                    )}

                    {draft.status === 'rejected' && (
                      <button
                        onClick={() => regenerateMutation.mutate(draft.id)}
                        disabled={regenerateMutation.isPending}
                        className="btn btn-secondary flex items-center gap-1 text-sm"
                      >
                        {regenerateMutation.isPending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <RefreshCw className="w-4 h-4" />
                        )}
                        Regenerar
                      </button>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
