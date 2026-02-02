import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  Users,
  Mail,
  CheckCircle,
  XCircle,
  AlertCircle,
  Flame,
  Thermometer,
  Snowflake,
  MessageSquare,
  Send,
  Loader2,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  X,
  Copy,
  Check,
  StickyNote,
  Edit3,
  Save,
} from 'lucide-react'
import {
  getLeads,
  getCampaigns,
  getBusinessProfiles,
  verifyEmails,
  qualifyLeads,
  generateLinkedInMessage,
  sendLinkedInConnection,
  getLeadStatuses,
  updateLeadStatus,
  type Lead,
  type LeadStatus,
  type LeadStatusValue,
} from '../services/api'

function ScoreBadge({ label, score }: { label: string | null; score: number | null }) {
  if (!label) return <span className="text-gray-400 text-sm">Not scored</span>

  const config = {
    hot: { icon: Flame, color: 'text-orange-500 bg-orange-50', label: 'Hot' },
    warm: { icon: Thermometer, color: 'text-yellow-500 bg-yellow-50', label: 'Warm' },
    cold: { icon: Snowflake, color: 'text-blue-500 bg-blue-50', label: 'Cold' },
  }[label] || { icon: AlertCircle, color: 'text-gray-500 bg-gray-50', label }

  const Icon = config.icon

  return (
    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${config.color}`}>
      <Icon className="w-3 h-3 mr-1" />
      {config.label}
      {score !== null && <span className="ml-1 opacity-75">({score})</span>}
    </span>
  )
}

function EmailStatus({ email, verified, status }: { email: string | null; verified: boolean; status: string | null }) {
  if (!email) {
    return <span className="text-gray-400 text-sm">No email</span>
  }

  return (
    <div>
      <p className="text-gray-900 text-sm font-mono">{email}</p>
      <p className="text-xs mt-0.5">
        {verified || status === 'valid' ? (
          <span className="text-green-600 flex items-center">
            <CheckCircle className="w-3 h-3 mr-1" />
            Verified
          </span>
        ) : status === 'invalid' ? (
          <span className="text-red-600 flex items-center">
            <XCircle className="w-3 h-3 mr-1" />
            Invalid
          </span>
        ) : status === 'risky' ? (
          <span className="text-yellow-600 flex items-center">
            <AlertCircle className="w-3 h-3 mr-1" />
            Risky
          </span>
        ) : (
          <span className="text-gray-400">Not verified</span>
        )}
      </p>
    </div>
  )
}

// CRM Status colors mapping
const STATUS_COLORS: Record<string, string> = {
  new: 'bg-gray-100 text-gray-700',
  pending: 'bg-yellow-100 text-yellow-700',
  invitation_sent: 'bg-blue-100 text-blue-700',
  connected: 'bg-green-100 text-green-700',
  in_conversation: 'bg-purple-100 text-purple-700',
  meeting_scheduled: 'bg-orange-100 text-orange-700',
  qualified: 'bg-emerald-100 text-emerald-700',
  disqualified: 'bg-red-100 text-red-700',
  closed_won: 'bg-green-200 text-green-800',
  closed_lost: 'bg-gray-200 text-gray-600',
}

function StatusBadge({
  status,
  statuses,
  onStatusChange,
  isUpdating
}: {
  status: string
  statuses: LeadStatus[]
  onStatusChange: (newStatus: LeadStatusValue) => void
  isUpdating: boolean
}) {
  const [isOpen, setIsOpen] = useState(false)
  const currentStatus = statuses.find(s => s.value === status)
  const colorClass = STATUS_COLORS[status] || 'bg-gray-100 text-gray-700'

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isUpdating}
        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${colorClass} hover:opacity-80 transition-opacity`}
      >
        {isUpdating ? (
          <Loader2 className="w-3 h-3 mr-1 animate-spin" />
        ) : null}
        {currentStatus?.label || status}
        <ChevronDown className="w-3 h-3 ml-1" />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="absolute z-20 mt-1 w-48 bg-white rounded-lg shadow-lg border py-1 max-h-64 overflow-y-auto">
            {statuses.map((s) => (
              <button
                key={s.value}
                onClick={() => {
                  onStatusChange(s.value as LeadStatusValue)
                  setIsOpen(false)
                }}
                className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center gap-2 ${
                  s.value === status ? 'bg-gray-50 font-medium' : ''
                }`}
              >
                <span className={`w-2 h-2 rounded-full ${STATUS_COLORS[s.value]?.split(' ')[0] || 'bg-gray-200'}`} />
                {s.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// Modal for message preview
function MessageModal({
  lead,
  message,
  onClose,
  onSend,
  isSending
}: {
  lead: Lead
  message: string
  onClose: () => void
  onSend: () => void
  isSending: boolean
}) {
  const [copied, setCopied] = useState(false)

  const copyMessage = () => {
    navigator.clipboard.writeText(message)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full">
        <div className="p-4 border-b flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">LinkedIn Message</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4">
          <div className="mb-4">
            <p className="text-sm text-gray-500">To:</p>
            <p className="font-medium">{lead.first_name} {lead.last_name}</p>
            <p className="text-sm text-gray-600">{lead.job_title} at {lead.company_name}</p>
          </div>
          <div className="mb-4">
            <p className="text-sm text-gray-500 mb-2">Message ({message.length}/300 chars):</p>
            <div className="bg-gray-50 rounded-lg p-3 border">
              <p className="text-gray-800 whitespace-pre-wrap">{message}</p>
            </div>
          </div>
        </div>
        <div className="p-4 border-t flex justify-between">
          <button
            onClick={copyMessage}
            className="btn btn-secondary flex items-center"
          >
            {copied ? <Check className="w-4 h-4 mr-2" /> : <Copy className="w-4 h-4 mr-2" />}
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <div className="flex gap-2">
            <button onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button
              onClick={onSend}
              disabled={isSending || lead.status !== 'new'}
              className="btn btn-primary flex items-center"
            >
              {isSending ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Send className="w-4 h-4 mr-2" />
              )}
              Send via N8N
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function LeadsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedLeads, setSelectedLeads] = useState<Set<string>>(new Set())
  const [expandedLead, setExpandedLead] = useState<string | null>(null)
  const [messageModal, setMessageModal] = useState<{ lead: Lead; message: string } | null>(null)
  const [generatingFor, setGeneratingFor] = useState<string | null>(null)
  const [updatingStatusFor, setUpdatingStatusFor] = useState<string | null>(null)
  const [editingNotes, setEditingNotes] = useState<string | null>(null)
  const [notesText, setNotesText] = useState('')
  const queryClient = useQueryClient()

  const campaignId = searchParams.get('campaign_id')
  const status = searchParams.get('status')
  const scoreLabel = searchParams.get('score_label')
  const page = Number(searchParams.get('page')) || 1

  const { data: leads, isLoading } = useQuery({
    queryKey: ['leads', campaignId, status, scoreLabel, page],
    queryFn: () =>
      getLeads(page, 50, {
        campaign_id: campaignId || undefined,
        status: status || undefined,
        score_label: scoreLabel || undefined,
      }),
  })

  const { data: campaigns } = useQuery({
    queryKey: ['campaigns'],
    queryFn: getCampaigns,
  })

  const { data: profiles } = useQuery({
    queryKey: ['business-profiles'],
    queryFn: getBusinessProfiles,
  })

  const { data: availableStatuses } = useQuery({
    queryKey: ['lead-statuses'],
    queryFn: getLeadStatuses,
  })

  const defaultProfile = profiles?.find(p => p.is_default)

  const verifyMutation = useMutation({
    mutationFn: (ids: string[]) => verifyEmails(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      setSelectedLeads(new Set())
    },
  })

  const qualifyMutation = useMutation({
    mutationFn: (ids: string[]) => qualifyLeads(ids, defaultProfile?.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      setSelectedLeads(new Set())
    },
  })

  const messageMutation = useMutation({
    mutationFn: (leadId: string) => generateLinkedInMessage(leadId, defaultProfile?.id),
    onSuccess: (data, leadId) => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      const lead = leads?.leads.find(l => l.id === leadId)
      if (lead && data.message) {
        setMessageModal({ lead: { ...lead, linkedin_message: data.message }, message: data.message })
      }
      setGeneratingFor(null)
    },
    onError: () => setGeneratingFor(null)
  })

  const sendMutation = useMutation({
    mutationFn: (leadId: string) => sendLinkedInConnection(leadId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      setMessageModal(null)
    },
  })

  const statusMutation = useMutation({
    mutationFn: ({ leadId, status }: { leadId: string; status: LeadStatusValue }) =>
      updateLeadStatus(leadId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      setUpdatingStatusFor(null)
    },
    onError: () => setUpdatingStatusFor(null)
  })

  const handleStatusChange = (leadId: string, newStatus: LeadStatusValue) => {
    setUpdatingStatusFor(leadId)
    statusMutation.mutate({ leadId, status: newStatus })
  }

  // Auto-verify and auto-score leads that haven't been processed
  useEffect(() => {
    if (!leads?.leads || leads.leads.length === 0) return

    // Find leads that need verification (have email but not verified)
    const needsVerification = leads.leads.filter(
      l => l.email && !l.email_verified && l.email_status !== 'valid' && l.email_status !== 'invalid'
    )

    // Find leads that need scoring (not scored yet)
    const needsScoring = leads.leads.filter(l => !l.score_label)

    // Auto-verify if there are leads to verify and not already verifying
    if (needsVerification.length > 0 && !verifyMutation.isPending) {
      const idsToVerify = needsVerification.slice(0, 10).map(l => l.id) // Batch of 10
      verifyMutation.mutate(idsToVerify)
    }

    // Auto-score if there are leads to score, we have a profile, and not already scoring
    if (needsScoring.length > 0 && defaultProfile && !qualifyMutation.isPending && !verifyMutation.isPending) {
      const idsToScore = needsScoring.slice(0, 5).map(l => l.id) // Batch of 5 (scoring is slower)
      qualifyMutation.mutate(idsToScore)
    }
  }, [leads?.leads, defaultProfile])

  const handleGenerateMessage = (lead: Lead) => {
    if (lead.linkedin_message) {
      setMessageModal({ lead, message: lead.linkedin_message })
    } else {
      setGeneratingFor(lead.id)
      messageMutation.mutate(lead.id)
    }
  }

  const toggleLeadSelection = (id: string) => {
    const newSelected = new Set(selectedLeads)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedLeads(newSelected)
  }

  const selectAll = () => {
    if (leads?.leads) {
      if (selectedLeads.size === leads.leads.length) {
        setSelectedLeads(new Set())
      } else {
        setSelectedLeads(new Set(leads.leads.map((l) => l.id)))
      }
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Message Modal */}
      {messageModal && (
        <MessageModal
          lead={messageModal.lead}
          message={messageModal.message}
          onClose={() => setMessageModal(null)}
          onSend={() => sendMutation.mutate(messageModal.lead.id)}
          isSending={sendMutation.isPending}
        />
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Leads</h1>
          <p className="text-gray-500 mt-1">
            {leads?.total ?? 0} leads found
            {defaultProfile && (
              <span className="ml-2 text-blue-600">
                (scoring with: {defaultProfile.name})
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Warning if no business profile */}
      {!defaultProfile && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-yellow-800">
          <AlertCircle className="w-5 h-5 inline mr-2" />
          No business profile configured. <a href="/settings" className="underline font-medium">Create one</a> to enable AI scoring.
        </div>
      )}

      {/* Auto-processing indicator */}
      {(verifyMutation.isPending || qualifyMutation.isPending) && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center gap-3">
          <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
          <div className="text-blue-800 text-sm">
            {verifyMutation.isPending && 'Verifying emails...'}
            {verifyMutation.isPending && qualifyMutation.isPending && ' | '}
            {qualifyMutation.isPending && 'Scoring leads with AI...'}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card flex flex-wrap gap-4 items-center">
        <select
          className="input w-48"
          value={campaignId || ''}
          onChange={(e) => {
            const params = new URLSearchParams(searchParams)
            if (e.target.value) {
              params.set('campaign_id', e.target.value)
            } else {
              params.delete('campaign_id')
            }
            params.delete('page')
            setSearchParams(params)
          }}
        >
          <option value="">All Campaigns</option>
          {campaigns?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        <select
          className="input w-36"
          value={scoreLabel || ''}
          onChange={(e) => {
            const params = new URLSearchParams(searchParams)
            if (e.target.value) {
              params.set('score_label', e.target.value)
            } else {
              params.delete('score_label')
            }
            params.delete('page')
            setSearchParams(params)
          }}
        >
          <option value="">All Scores</option>
          <option value="hot">Hot</option>
          <option value="warm">Warm</option>
          <option value="cold">Cold</option>
        </select>

        <select
          className="input w-44"
          value={status || ''}
          onChange={(e) => {
            const params = new URLSearchParams(searchParams)
            if (e.target.value) {
              params.set('status', e.target.value)
            } else {
              params.delete('status')
            }
            params.delete('page')
            setSearchParams(params)
          }}
        >
          <option value="">All Status</option>
          {availableStatuses?.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>

        <div className="flex gap-2 ml-auto">
          <button
            className="btn btn-secondary flex items-center"
            onClick={() => {
              if (selectedLeads.size === 0) {
                alert('Select leads to verify their emails')
                return
              }
              verifyMutation.mutate(Array.from(selectedLeads))
            }}
            disabled={verifyMutation.isPending}
          >
            {verifyMutation.isPending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Mail className="w-4 h-4 mr-2" />
            )}
            Verify ({selectedLeads.size})
          </button>
          <button
            className="btn btn-secondary flex items-center"
            onClick={() => {
              if (selectedLeads.size === 0) {
                alert('Select leads to score them')
                return
              }
              if (!defaultProfile) {
                alert('Create a business profile first in Settings')
                return
              }
              qualifyMutation.mutate(Array.from(selectedLeads))
            }}
            disabled={qualifyMutation.isPending}
          >
            {qualifyMutation.isPending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Flame className="w-4 h-4 mr-2" />
            )}
            Score ({selectedLeads.size})
          </button>
        </div>
      </div>

      {/* Leads Table */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={leads?.leads && leads.leads.length > 0 && selectedLeads.size === leads.leads.length}
                    onChange={selectAll}
                    className="rounded border-gray-300"
                  />
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Company
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Email
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Score
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {leads?.leads.map((lead) => (
                <>
                  <tr
                    key={lead.id}
                    className={`hover:bg-gray-50 ${expandedLead === lead.id ? 'bg-blue-50' : ''}`}
                  >
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedLeads.has(lead.id)}
                        onChange={() => toggleLeadSelection(lead.id)}
                        className="rounded border-gray-300"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div
                        className="cursor-pointer flex items-center"
                        onClick={() => setExpandedLead(expandedLead === lead.id ? null : lead.id)}
                      >
                        <div className="flex-1">
                          <p className="font-medium text-gray-900">
                            {lead.first_name} {lead.last_name}
                          </p>
                          <p className="text-sm text-gray-500">{lead.job_title}</p>
                        </div>
                        {expandedLead === lead.id ? (
                          <ChevronUp className="w-4 h-4 text-gray-400" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-gray-400" />
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-gray-900">{lead.company_name}</p>
                      <p className="text-sm text-gray-500">
                        {lead.company_size ? `${lead.company_size} emp` : ''}
                        {lead.company_industry && lead.company_size ? ' · ' : ''}
                        {lead.company_industry}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <EmailStatus email={lead.email} verified={lead.email_verified} status={lead.email_status} />
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBadge label={lead.score_label} score={lead.score} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge
                        status={lead.status}
                        statuses={availableStatuses || []}
                        onStatusChange={(newStatus) => handleStatusChange(lead.id, newStatus)}
                        isUpdating={updatingStatusFor === lead.id}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1">
                        {lead.linkedin_url && (
                          <a
                            href={lead.linkedin_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                            title="Open LinkedIn"
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        )}
                        <button
                          className={`p-2 rounded ${
                            lead.linkedin_message
                              ? 'text-green-600 hover:bg-green-50'
                              : 'text-gray-400 hover:text-blue-600 hover:bg-blue-50'
                          }`}
                          onClick={() => handleGenerateMessage(lead)}
                          disabled={generatingFor === lead.id}
                          title={lead.linkedin_message ? 'View/Send Message' : 'Generate Message'}
                        >
                          {generatingFor === lead.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <MessageSquare className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                  {/* Expanded row */}
                  {expandedLead === lead.id && (
                    <tr className="bg-gray-50">
                      <td colSpan={7} className="px-4 py-4">
                        <div className="grid grid-cols-3 gap-4 text-sm">
                          <div>
                            <p className="text-gray-500 font-medium mb-2">Contact Info</p>
                            <p><span className="text-gray-500">Email:</span> {lead.email || 'N/A'}</p>
                            <p><span className="text-gray-500">Country:</span> {lead.country || 'N/A'}</p>
                            <p><span className="text-gray-500">LinkedIn:</span> {lead.linkedin_url ? (
                              <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                                View Profile
                              </a>
                            ) : 'N/A'}</p>
                          </div>
                          <div>
                            <p className="text-gray-500 font-medium mb-2">AI Scoring</p>
                            {lead.score_reason ? (
                              <p className="text-gray-700">{lead.score_reason}</p>
                            ) : (
                              <p className="text-gray-400 italic">Not scored yet. Select and click "Score" to analyze.</p>
                            )}
                          </div>
                          <div>
                            <p className="text-gray-500 font-medium mb-2">Timeline</p>
                            <div className="space-y-1 text-xs">
                              <p><span className="text-gray-500">Created:</span> {new Date(lead.created_at).toLocaleDateString()}</p>
                              {lead.connection_sent_at && (
                                <p><span className="text-gray-500">Invitation Sent:</span> {new Date(lead.connection_sent_at).toLocaleDateString()}</p>
                              )}
                              {lead.connected_at && (
                                <p><span className="text-gray-500">Connected:</span> {new Date(lead.connected_at).toLocaleDateString()}</p>
                              )}
                              {lead.last_message_at && (
                                <p><span className="text-gray-500">Last Message:</span> {new Date(lead.last_message_at).toLocaleDateString()}</p>
                              )}
                            </div>
                          </div>

                          {/* Notes section */}
                          <div className="col-span-3 border-t pt-3 mt-2">
                            <div className="flex items-center justify-between mb-2">
                              <p className="text-gray-500 font-medium flex items-center">
                                <StickyNote className="w-4 h-4 mr-1" />
                                Notes
                              </p>
                              {editingNotes !== lead.id && (
                                <button
                                  onClick={() => {
                                    setEditingNotes(lead.id)
                                    setNotesText(lead.notes || '')
                                  }}
                                  className="text-blue-600 hover:text-blue-800 text-xs flex items-center"
                                >
                                  <Edit3 className="w-3 h-3 mr-1" />
                                  Edit
                                </button>
                              )}
                            </div>
                            {editingNotes === lead.id ? (
                              <div className="space-y-2">
                                <textarea
                                  value={notesText}
                                  onChange={(e) => setNotesText(e.target.value)}
                                  className="w-full border rounded p-2 text-sm min-h-[80px]"
                                  placeholder="Add notes about this lead..."
                                />
                                <div className="flex gap-2">
                                  <button
                                    onClick={async () => {
                                      await updateLeadStatus(lead.id, lead.status as LeadStatusValue, notesText ? `Note: ${notesText}` : undefined)
                                      queryClient.invalidateQueries({ queryKey: ['leads'] })
                                      setEditingNotes(null)
                                    }}
                                    className="btn btn-primary btn-sm flex items-center text-xs"
                                  >
                                    <Save className="w-3 h-3 mr-1" />
                                    Save
                                  </button>
                                  <button
                                    onClick={() => setEditingNotes(null)}
                                    className="btn btn-secondary btn-sm text-xs"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className="bg-white rounded border p-2 min-h-[40px]">
                                {lead.notes ? (
                                  <p className="text-gray-700 whitespace-pre-wrap text-xs">{lead.notes}</p>
                                ) : (
                                  <p className="text-gray-400 italic text-xs">No notes yet. Click Edit to add.</p>
                                )}
                              </div>
                            )}
                          </div>

                          {lead.linkedin_message && (
                            <div className="col-span-3 border-t pt-3">
                              <p className="text-gray-500 font-medium mb-2">Generated LinkedIn Message</p>
                              <div className="bg-white rounded border p-3">
                                <p className="text-gray-700">{lead.linkedin_message}</p>
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>

        {(!leads?.leads || leads.leads.length === 0) && (
          <div className="text-center py-12 text-gray-500">
            <Users className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No leads found</p>
            <p className="text-sm mt-1">Try adjusting your filters or search for new leads</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      {leads && leads.total > 50 && (
        <div className="flex justify-center gap-2">
          <button
            className="btn btn-secondary"
            disabled={page === 1}
            onClick={() => {
              const params = new URLSearchParams(searchParams)
              params.set('page', String(page - 1))
              setSearchParams(params)
            }}
          >
            Previous
          </button>
          <span className="flex items-center px-4 text-gray-600">
            Page {page} of {Math.ceil(leads.total / 50)}
          </span>
          <button
            className="btn btn-secondary"
            disabled={page >= Math.ceil(leads.total / 50)}
            onClick={() => {
              const params = new URLSearchParams(searchParams)
              params.set('page', String(page + 1))
              setSearchParams(params)
            }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
