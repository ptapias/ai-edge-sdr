import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Users,
  Loader2,
  UserMinus,
  CheckCircle2,
  MessageCircle,
  AlertCircle,
  Pause,
  Clock,
  XCircle,
  Filter,
  ParkingCircle
} from 'lucide-react'
import { getEnrollments, unenrollLeads } from '../../services/api'
import type { SequenceEnrollment } from '../../services/api'

interface EnrollmentTableProps {
  sequenceId: string
  isActive: boolean
  isPipeline?: boolean
}

const statusConfig: Record<string, { label: string; icon: typeof CheckCircle2; color: string; bg: string }> = {
  active: { label: 'Active', icon: Clock, color: 'text-blue-700', bg: 'bg-blue-100' },
  completed: { label: 'Completed', icon: CheckCircle2, color: 'text-green-700', bg: 'bg-green-100' },
  replied: { label: 'Replied', icon: MessageCircle, color: 'text-orange-700', bg: 'bg-orange-100' },
  paused: { label: 'Paused', icon: Pause, color: 'text-gray-700', bg: 'bg-gray-100' },
  failed: { label: 'Failed', icon: AlertCircle, color: 'text-red-700', bg: 'bg-red-100' },
  withdrawn: { label: 'Withdrawn', icon: XCircle, color: 'text-gray-500', bg: 'bg-gray-50' },
  parked: { label: 'Parked', icon: ParkingCircle, color: 'text-gray-600', bg: 'bg-gray-100' },
}

const phaseConfig: Record<string, { label: string; color: string; bg: string }> = {
  apertura: { label: 'Apertura', color: 'text-indigo-700', bg: 'bg-indigo-100' },
  calificacion: { label: 'Calificación', color: 'text-violet-700', bg: 'bg-violet-100' },
  valor: { label: 'Valor', color: 'text-purple-700', bg: 'bg-purple-100' },
  nurture: { label: 'Nurture', color: 'text-amber-700', bg: 'bg-amber-100' },
  reactivacion: { label: 'Reactivación', color: 'text-orange-700', bg: 'bg-orange-100' },
}

function formatDate(dateString: string | null | undefined) {
  if (!dateString) return '-'
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return '-'
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatRelative(dateString: string | null | undefined) {
  if (!dateString) return '-'
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return '-'

  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMs < 0) {
    // Future date (next step due)
    const absMins = Math.abs(diffMins)
    const absHours = Math.abs(diffHours)
    const absDays = Math.abs(diffDays)
    if (absMins < 60) return `in ${absMins}m`
    if (absHours < 24) return `in ${absHours}h`
    return `in ${absDays}d`
  }

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDate(dateString)
}

export default function EnrollmentTable({ sequenceId, isPipeline = false }: EnrollmentTableProps) {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedEnrollments, setSelectedEnrollments] = useState<Set<string>>(new Set())

  const { data: enrollments, isLoading } = useQuery({
    queryKey: ['enrollments', sequenceId, statusFilter],
    queryFn: () => getEnrollments(sequenceId, statusFilter || undefined),
  })

  const unenrollMutation = useMutation({
    mutationFn: (leadIds: string[]) => unenrollLeads(sequenceId, leadIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['enrollments', sequenceId] })
      queryClient.invalidateQueries({ queryKey: ['sequence', sequenceId] })
      setSelectedEnrollments(new Set())
    },
  })

  const toggleEnrollment = (id: string) => {
    const next = new Set(selectedEnrollments)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelectedEnrollments(next)
  }

  const toggleAll = () => {
    if (!enrollments) return
    const activeIds = enrollments
      .filter((e: SequenceEnrollment) => e.status === 'active' || e.status === 'paused')
      .map((e: SequenceEnrollment) => e.lead_id)
    if (selectedEnrollments.size === activeIds.length) {
      setSelectedEnrollments(new Set())
    } else {
      setSelectedEnrollments(new Set(activeIds))
    }
  }

  const handleUnenroll = () => {
    if (selectedEnrollments.size === 0) return
    if (confirm(`Remove ${selectedEnrollments.size} lead(s) from this sequence?`)) {
      unenrollMutation.mutate(Array.from(selectedEnrollments))
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-40">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-sm text-gray-600">
            <Filter className="w-4 h-4" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input text-sm w-40"
            >
              <option value="">All Statuses</option>
              <option value="active">Active</option>
              <option value="completed">Completed</option>
              <option value="replied">Replied</option>
              <option value="paused">Paused</option>
              <option value="failed">Failed</option>
              <option value="withdrawn">Withdrawn</option>
              {isPipeline && <option value="parked">Parked</option>}
            </select>
          </div>
          <span className="text-sm text-gray-500">
            {enrollments?.length || 0} enrollment{(enrollments?.length || 0) !== 1 ? 's' : ''}
          </span>
        </div>

        {selectedEnrollments.size > 0 && (
          <button
            onClick={handleUnenroll}
            disabled={unenrollMutation.isPending}
            className="btn btn-secondary text-sm text-red-600 border-red-200 hover:bg-red-50 flex items-center gap-1.5"
          >
            {unenrollMutation.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <UserMinus className="w-3.5 h-3.5" />
            )}
            Unenroll {selectedEnrollments.size}
          </button>
        )}
      </div>

      {/* Table */}
      {!enrollments || enrollments.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 text-gray-500">
          <Users className="w-8 h-8 mb-2 text-gray-300" />
          <p className="text-sm">No enrollments found</p>
          <p className="text-xs">Enroll leads to start the sequence</p>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2.5 text-left">
                  <input
                    type="checkbox"
                    onChange={toggleAll}
                    checked={selectedEnrollments.size > 0}
                    className="rounded"
                  />
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">Lead</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">
                  {isPipeline ? 'Phase' : 'Step'}
                </th>
                {isPipeline && (
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">Last Response</th>
                )}
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">
                  {isPipeline ? 'Messages' : 'Next Due'}
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase">Enrolled</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {enrollments.map((enrollment: SequenceEnrollment) => {
                const config = statusConfig[enrollment.status] || statusConfig.active
                const StatusIcon = config.icon
                const canSelect = enrollment.status === 'active' || enrollment.status === 'paused'
                const phase = enrollment.current_phase ? phaseConfig[enrollment.current_phase] : null

                return (
                  <tr
                    key={enrollment.id}
                    className={`hover:bg-gray-50 ${
                      selectedEnrollments.has(enrollment.lead_id) ? 'bg-blue-50' : ''
                    } ${enrollment.status === 'replied' ? 'bg-orange-50/50' : ''}`}
                  >
                    <td className="px-4 py-2.5">
                      {canSelect && (
                        <input
                          type="checkbox"
                          checked={selectedEnrollments.has(enrollment.lead_id)}
                          onChange={() => toggleEnrollment(enrollment.lead_id)}
                          className="rounded"
                        />
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {enrollment.lead_name || 'Unknown Lead'}
                        </p>
                        {enrollment.lead_job_title && (
                          <p className="text-xs text-gray-500">{enrollment.lead_job_title}</p>
                        )}
                        {enrollment.lead_company && (
                          <p className="text-xs text-gray-400">{enrollment.lead_company}</p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.color}`}>
                        <StatusIcon className="w-3 h-3" />
                        {config.label}
                      </span>
                      {enrollment.failed_reason && (
                        <p className="text-xs text-red-500 mt-0.5 max-w-[200px] truncate" title={enrollment.failed_reason}>
                          {enrollment.failed_reason}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      {isPipeline && phase ? (
                        <div>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${phase.bg} ${phase.color}`}>
                            {phase.label}
                          </span>
                          {enrollment.messages_in_phase > 0 && (
                            <span className="text-xs text-gray-400 ml-1">
                              ({enrollment.messages_in_phase}/2 msgs)
                            </span>
                          )}
                        </div>
                      ) : isPipeline ? (
                        <span className="text-xs text-gray-400">Awaiting connection</span>
                      ) : (
                        <span className="text-sm text-gray-700">
                          Step {enrollment.current_step_order}
                        </span>
                      )}
                    </td>
                    {isPipeline && (
                      <td className="px-4 py-2.5">
                        <span className="text-sm text-gray-600">
                          {enrollment.last_response_at ? formatRelative(enrollment.last_response_at) : '-'}
                        </span>
                      </td>
                    )}
                    <td className="px-4 py-2.5">
                      {isPipeline ? (
                        <span className="text-sm text-gray-600">
                          {enrollment.total_messages_sent || 0}
                          {enrollment.nurture_count > 0 && (
                            <span className="text-xs text-amber-500 ml-1">
                              ({enrollment.nurture_count} nurture)
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-sm text-gray-600">
                          {enrollment.status === 'active' ? formatRelative(enrollment.next_step_due_at) : '-'}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs text-gray-500">
                        {formatDate(enrollment.enrolled_at)}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
