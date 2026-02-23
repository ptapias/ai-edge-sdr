import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Loader2, MessageSquare, Flame, Thermometer, Snowflake, Clock, X, ExternalLink,
  ArrowRight, User
} from 'lucide-react'
import {
  getPipelineLeads,
  updateLeadStatus,
  type PipelineLead,
  type LeadStatusValue,
} from '../services/api'

const COLUMNS: { key: string; label: string; color: string; bgColor: string }[] = [
  { key: 'new', label: 'New', color: 'border-gray-300', bgColor: 'bg-gray-50' },
  { key: 'invitation_sent', label: 'Invitation Sent', color: 'border-blue-300', bgColor: 'bg-blue-50' },
  { key: 'connected', label: 'Connected', color: 'border-green-300', bgColor: 'bg-green-50' },
  { key: 'in_conversation', label: 'In Conversation', color: 'border-purple-300', bgColor: 'bg-purple-50' },
  { key: 'meeting_scheduled', label: 'Meeting', color: 'border-orange-300', bgColor: 'bg-orange-50' },
  { key: 'qualified', label: 'Qualified', color: 'border-emerald-300', bgColor: 'bg-emerald-50' },
  { key: 'closed_won', label: 'Won', color: 'border-green-400', bgColor: 'bg-green-50' },
]

function ScoreIcon({ label }: { label: string | null }) {
  if (label === 'hot') return <Flame className="w-3 h-3 text-orange-500" />
  if (label === 'warm') return <Thermometer className="w-3 h-3 text-yellow-500" />
  if (label === 'cold') return <Snowflake className="w-3 h-3 text-blue-500" />
  return null
}

function ConversationIndicator({ status }: { status: 'responded' | 'awaiting' | 'no_contact' }) {
  const config = {
    responded: { color: 'bg-green-500', title: 'Has conversation' },
    awaiting: { color: 'bg-orange-400', title: 'Awaiting response' },
    no_contact: { color: 'bg-gray-300', title: 'No contact' },
  }[status]

  return (
    <span className={`w-2 h-2 rounded-full ${config.color} flex-shrink-0`} title={config.title} />
  )
}

function formatLastActivity(dateStr: string | null): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / 86400000)
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString('en', { month: 'short', day: 'numeric' })
}

function LeadCard({
  lead,
  onDragStart,
  onClick,
}: {
  lead: PipelineLead
  onDragStart: (e: React.DragEvent, lead: PipelineLead) => void
  onClick: (lead: PipelineLead) => void
}) {
  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, lead)}
      onClick={() => onClick(lead)}
      className="bg-white rounded-lg border p-3 cursor-pointer hover:shadow-md transition-shadow group"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <ConversationIndicator status={lead.response_status} />
            <p className="text-sm font-medium text-gray-900 truncate">
              {lead.full_name || `${lead.first_name || ''} ${lead.last_name || ''}`}
            </p>
          </div>
          <p className="text-xs text-gray-500 truncate mt-0.5">{lead.company_name}</p>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <ScoreIcon label={lead.score_label} />
          {lead.has_conversation && <MessageSquare className="w-3 h-3 text-green-500" />}
        </div>
      </div>
      {lead.last_activity && (
        <p className="text-xs text-gray-400 mt-2 flex items-center">
          <Clock className="w-3 h-3 mr-1" />
          {formatLastActivity(lead.last_activity)}
        </p>
      )}
    </div>
  )
}

function LeadDetailSidebar({
  lead,
  onClose,
}: {
  lead: PipelineLead
  onClose: () => void
}) {
  const navigate = useNavigate()

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="fixed inset-0 bg-black bg-opacity-30" onClick={onClose} />
      <div className="ml-auto relative w-96 bg-white shadow-xl flex flex-col">
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Lead Details</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Profile */}
          <div className="flex items-start gap-3">
            <div className="w-12 h-12 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
              <User className="w-6 h-6 text-gray-500" />
            </div>
            <div>
              <p className="font-semibold text-gray-900">{lead.full_name}</p>
              <p className="text-sm text-gray-600">{lead.job_title}</p>
              <p className="text-sm text-gray-500">{lead.company_name}</p>
            </div>
          </div>

          {/* Score & Status */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">AI Score</p>
              <div className="flex items-center gap-2">
                <ScoreIcon label={lead.score_label} />
                <span className="font-semibold">
                  {lead.score !== null ? `${lead.score}/100` : 'Unscored'}
                </span>
              </div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Conversation</p>
              <div className="flex items-center gap-2">
                <ConversationIndicator status={lead.response_status} />
                <span className="text-sm font-medium capitalize">
                  {lead.response_status.replace('_', ' ')}
                </span>
              </div>
            </div>
          </div>

          {/* Last Activity */}
          {lead.last_activity && (
            <div>
              <p className="text-xs text-gray-500 mb-1">Last Activity</p>
              <p className="text-sm text-gray-700">
                {new Date(lead.last_activity).toLocaleString()}
              </p>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="p-4 border-t space-y-2">
          {lead.has_conversation && (
            <button
              onClick={() => { onClose(); navigate('/inbox') }}
              className="w-full btn btn-primary flex items-center justify-center"
            >
              <MessageSquare className="w-4 h-4 mr-2" />
              Open in Inbox
            </button>
          )}
          <button
            onClick={() => { onClose(); navigate(`/leads?status=${lead.id}`) }}
            className="w-full btn btn-secondary flex items-center justify-center"
          >
            <ExternalLink className="w-4 h-4 mr-2" />
            View in Leads
          </button>
        </div>
      </div>
    </div>
  )
}

export default function PipelinePage() {
  const queryClient = useQueryClient()
  const [selectedLead, setSelectedLead] = useState<PipelineLead | null>(null)
  const [dragOverColumn, setDragOverColumn] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['pipeline-leads'],
    queryFn: getPipelineLeads,
  })

  const statusMutation = useMutation({
    mutationFn: ({ leadId, status }: { leadId: string; status: LeadStatusValue }) =>
      updateLeadStatus(leadId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-leads'] })
    },
  })

  const handleDragStart = (e: React.DragEvent, lead: PipelineLead) => {
    e.dataTransfer.setData('text/plain', JSON.stringify({ id: lead.id }))
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDrop = (e: React.DragEvent, targetStatus: string) => {
    e.preventDefault()
    setDragOverColumn(null)

    try {
      const data = JSON.parse(e.dataTransfer.getData('text/plain'))
      if (data.id) {
        statusMutation.mutate({ leadId: data.id, status: targetStatus as LeadStatusValue })
      }
    } catch { /* ignore parse errors */ }
  }

  const handleDragOver = (e: React.DragEvent, column: string) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOverColumn(column)
  }

  const pipeline = data?.pipeline || {}

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Pipeline</h1>
        <p className="text-gray-500 mt-1">Drag leads between stages to update their status</p>
      </div>

      {/* Kanban Board */}
      <div className="flex gap-4 overflow-x-auto pb-4" style={{ minHeight: '70vh' }}>
        {COLUMNS.map((col) => {
          const leads = pipeline[col.key] || []
          const isDragOver = dragOverColumn === col.key

          return (
            <div
              key={col.key}
              className={`flex-shrink-0 w-64 flex flex-col rounded-xl border-2 transition-colors ${
                isDragOver ? `${col.color} ${col.bgColor}` : 'border-gray-200 bg-gray-50'
              }`}
              onDragOver={(e) => handleDragOver(e, col.key)}
              onDragLeave={() => setDragOverColumn(null)}
              onDrop={(e) => handleDrop(e, col.key)}
            >
              {/* Column Header */}
              <div className={`px-4 py-3 border-b-2 ${col.color}`}>
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-700">{col.label}</h3>
                  <span className="text-xs font-medium text-gray-500 bg-white px-2 py-0.5 rounded-full">
                    {leads.length}
                  </span>
                </div>
              </div>

              {/* Cards */}
              <div className="flex-1 p-2 space-y-2 overflow-y-auto">
                {leads.map((lead) => (
                  <LeadCard
                    key={lead.id}
                    lead={lead}
                    onDragStart={handleDragStart}
                    onClick={setSelectedLead}
                  />
                ))}
                {leads.length === 0 && (
                  <div className="text-center py-8 text-gray-400 text-xs">
                    No leads
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Detail Sidebar */}
      {selectedLead && (
        <LeadDetailSidebar
          lead={selectedLead}
          onClose={() => setSelectedLead(null)}
        />
      )}
    </div>
  )
}
