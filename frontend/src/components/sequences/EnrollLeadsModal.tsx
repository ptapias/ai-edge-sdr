import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Search, Users, Loader2, CheckCircle } from 'lucide-react'
import { getLeads, getCampaigns, enrollLeads } from '../../services/api'
import type { Lead } from '../../services/api'

interface EnrollLeadsModalProps {
  sequenceId: string
  sequenceName: string
  onClose: () => void
}

export default function EnrollLeadsModal({ sequenceId, sequenceName, onClose }: EnrollLeadsModalProps) {
  const queryClient = useQueryClient()
  const [selectedLeads, setSelectedLeads] = useState<Set<string>>(new Set())
  const [campaignFilter, setCampaignFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)

  const { data: leads, isLoading } = useQuery({
    queryKey: ['leads-for-enroll', campaignFilter, statusFilter, page],
    queryFn: () => getLeads(page, 50, {
      campaign_id: campaignFilter || undefined,
      status: statusFilter || undefined,
    }),
  })

  const { data: campaigns } = useQuery({
    queryKey: ['campaigns'],
    queryFn: getCampaigns,
  })

  const enrollMutation = useMutation({
    mutationFn: () => enrollLeads(sequenceId, Array.from(selectedLeads)),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['sequence', sequenceId] })
      queryClient.invalidateQueries({ queryKey: ['enrollments', sequenceId] })
      alert(`Enrolled ${result.enrolled} leads${result.skipped > 0 ? ` (${result.skipped} skipped)` : ''}`)
      onClose()
    },
  })

  const toggleLead = (id: string) => {
    const next = new Set(selectedLeads)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelectedLeads(next)
  }

  const toggleAll = () => {
    if (!leads?.leads) return
    const available = leads.leads.filter((l: Lead) => !l.active_sequence_id)
    if (selectedLeads.size === available.length) {
      setSelectedLeads(new Set())
    } else {
      setSelectedLeads(new Set(available.map((l: Lead) => l.id)))
    }
  }

  const availableLeads = leads?.leads?.filter((l: Lead) => !l.active_sequence_id) || []

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-3xl w-full max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between flex-shrink-0">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Enroll Leads</h3>
            <p className="text-sm text-gray-500">Select leads to enroll in "{sequenceName}"</p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filters */}
        <div className="p-4 border-b flex items-center gap-3 flex-shrink-0">
          <select
            value={campaignFilter}
            onChange={(e) => { setCampaignFilter(e.target.value); setPage(1) }}
            className="input w-48 text-sm"
          >
            <option value="">All Campaigns</option>
            {campaigns?.map((c: { id: string; name: string }) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
            className="input w-40 text-sm"
          >
            <option value="">All Statuses</option>
            <option value="new">New</option>
            <option value="pending">Pending</option>
            <option value="connected">Connected</option>
          </select>
          <div className="flex-1" />
          <span className="text-sm text-gray-500">
            {selectedLeads.size} selected
          </span>
        </div>

        {/* Lead list */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            </div>
          ) : availableLeads.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-gray-500">
              <Users className="w-8 h-8 mb-2 text-gray-300" />
              <p className="text-sm">No available leads found</p>
              <p className="text-xs">Leads already in a sequence are excluded</p>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-4 py-2 text-left">
                    <input
                      type="checkbox"
                      checked={selectedLeads.size > 0 && selectedLeads.size === availableLeads.length}
                      onChange={toggleAll}
                      className="rounded"
                    />
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Company</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {availableLeads.map((lead: Lead) => (
                  <tr
                    key={lead.id}
                    className={`hover:bg-gray-50 cursor-pointer ${selectedLeads.has(lead.id) ? 'bg-blue-50' : ''}`}
                    onClick={() => toggleLead(lead.id)}
                  >
                    <td className="px-4 py-2">
                      <input
                        type="checkbox"
                        checked={selectedLeads.has(lead.id)}
                        onChange={() => toggleLead(lead.id)}
                        className="rounded"
                      />
                    </td>
                    <td className="px-4 py-2 text-sm font-medium text-gray-900">
                      {lead.first_name} {lead.last_name}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">{lead.company_name || '-'}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{lead.job_title || '-'}</td>
                    <td className="px-4 py-2">
                      {lead.score_label && (
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          lead.score_label === 'hot' ? 'bg-orange-100 text-orange-700' :
                          lead.score_label === 'warm' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-blue-100 text-blue-700'
                        }`}>
                          {lead.score_label}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-500">{lead.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {leads && leads.total > 50 && (
          <div className="px-4 py-2 border-t flex items-center justify-between text-sm text-gray-500 flex-shrink-0">
            <span>Page {page} of {Math.ceil(leads.total / 50)}</span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn btn-secondary text-xs"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={page * 50 >= leads.total}
                className="btn btn-secondary text-xs"
              >
                Next
              </button>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="p-4 border-t flex items-center justify-between flex-shrink-0">
          <span className="text-sm text-gray-500">
            {selectedLeads.size} lead{selectedLeads.size !== 1 ? 's' : ''} selected
          </span>
          <div className="flex gap-2">
            <button onClick={onClose} className="btn btn-secondary">Cancel</button>
            <button
              onClick={() => enrollMutation.mutate()}
              disabled={selectedLeads.size === 0 || enrollMutation.isPending}
              className="btn btn-primary flex items-center gap-2"
            >
              {enrollMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle className="w-4 h-4" />
              )}
              Enroll {selectedLeads.size} Lead{selectedLeads.size !== 1 ? 's' : ''}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
