import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Target, Flame, Thermometer, Snowflake, MessageSquare, ArrowRight, Loader2 } from 'lucide-react'
import { getFocusLeads, type FocusLead } from '../services/api'

function PriorityBadge({ score }: { score: number }) {
  const config = score >= 70
    ? { color: 'bg-red-100 text-red-700', label: 'High' }
    : score >= 40
    ? { color: 'bg-orange-100 text-orange-700', label: 'Medium' }
    : { color: 'bg-gray-100 text-gray-600', label: 'Low' }

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${config.color}`}>
      {config.label} ({score})
    </span>
  )
}

function ScoreIcon({ label }: { label: string | null }) {
  if (label === 'hot') return <Flame className="w-3.5 h-3.5 text-orange-500" />
  if (label === 'warm') return <Thermometer className="w-3.5 h-3.5 text-yellow-500" />
  if (label === 'cold') return <Snowflake className="w-3.5 h-3.5 text-blue-500" />
  return null
}

function formatLastActivity(dateStr: string | null): string {
  if (!dateStr) return 'No activity'
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString('en', { month: 'short', day: 'numeric' })
}

export default function FocusLeads() {
  const navigate = useNavigate()

  const { data, isLoading } = useQuery({
    queryKey: ['focus-leads'],
    queryFn: () => getFocusLeads(10),
    staleTime: 60000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
      </div>
    )
  }

  const leads = data?.focus_leads || []

  if (leads.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <Target className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No actionable leads yet</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {leads.map((lead) => (
        <button
          key={lead.id}
          onClick={() => {
            if (lead.has_conversation) {
              navigate('/inbox')
            } else {
              navigate(`/leads?status=${lead.status}`)
            }
          }}
          className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors text-left group"
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium text-gray-900 truncate">
                {lead.full_name || `${lead.first_name || ''} ${lead.last_name || ''}`}
              </p>
              <ScoreIcon label={lead.score_label} />
              {lead.has_conversation && (
                <MessageSquare className="w-3.5 h-3.5 text-green-500" />
              )}
            </div>
            <p className="text-xs text-gray-500 truncate">
              {lead.job_title}{lead.company_name ? ` at ${lead.company_name}` : ''}
            </p>
            <div className="flex items-center gap-2 mt-1">
              <PriorityBadge score={lead.priority_score} />
              <span className="text-xs text-gray-400">{formatLastActivity(lead.last_activity)}</span>
            </div>
          </div>
          <div className="flex-shrink-0 text-right">
            <p className="text-xs text-blue-600 group-hover:text-blue-800 font-medium">
              {lead.recommended_action}
            </p>
            <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-blue-500 ml-auto mt-1" />
          </div>
        </button>
      ))}
    </div>
  )
}
