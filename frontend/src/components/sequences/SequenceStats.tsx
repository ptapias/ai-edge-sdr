import { useQuery } from '@tanstack/react-query'
import {
  Loader2,
  Users,
  MessageCircle,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  Send,
  MessageSquare,
  Target,
  Sparkles,
  Link2,
  XCircle,
  UserCheck,
} from 'lucide-react'
import { getSequenceStats } from '../../services/api'

interface SequenceStatsProps {
  sequenceId: string
}

const phaseLabels: Record<string, { label: string; color: string; bg: string }> = {
  awaiting_connection: { label: 'Awaiting Connection', color: 'bg-gray-400', bg: 'bg-gray-50' },
  apertura: { label: 'Apertura', color: 'bg-indigo-500', bg: 'bg-indigo-50' },
  calificacion: { label: 'Calificación', color: 'bg-violet-500', bg: 'bg-violet-50' },
  valor: { label: 'Valor', color: 'bg-purple-500', bg: 'bg-purple-50' },
  nurture: { label: 'Nurture', color: 'bg-amber-500', bg: 'bg-amber-50' },
  reactivacion: { label: 'Reactivación', color: 'bg-orange-500', bg: 'bg-orange-50' },
  meeting: { label: 'Meeting Booked', color: 'bg-green-500', bg: 'bg-green-50' },
  parked: { label: 'Parked', color: 'bg-gray-400', bg: 'bg-gray-50' },
  exited: { label: 'Exited', color: 'bg-red-400', bg: 'bg-red-50' },
}

export default function SequenceStats({ sequenceId }: SequenceStatsProps) {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['sequence-stats', sequenceId],
    queryFn: () => getSequenceStats(sequenceId),
    refetchInterval: 30000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-40">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="flex flex-col items-center justify-center h-40 text-gray-500">
        <AlertCircle className="w-8 h-8 mb-2 text-gray-300" />
        <p className="text-sm">No stats available</p>
      </div>
    )
  }

  const isPipeline = stats.sequence_mode === 'smart_pipeline'

  return (
    <div className="space-y-6">
      {/* Summary Cards - 2 rows */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <StatCard
          label="Enrolled"
          value={stats.total_enrolled}
          icon={Users}
          color="blue"
        />
        <StatCard
          label="Invitations Sent"
          value={stats.invitations_sent}
          icon={Send}
          color="indigo"
          subtext={`${stats.total_enrolled - stats.invitations_sent - stats.failed} pending`}
        />
        <StatCard
          label="Connected"
          value={stats.connected}
          icon={UserCheck}
          color="green"
          subtext={stats.invitations_sent > 0 ? `${stats.acceptance_rate}% acceptance` : undefined}
        />
        <StatCard
          label="In Progress"
          value={stats.active}
          icon={TrendingUp}
          color="cyan"
          subtext={stats.paused > 0 ? `${stats.paused} paused` : undefined}
        />
        <StatCard
          label="Replied"
          value={stats.replied}
          icon={MessageCircle}
          color="orange"
          subtext={stats.total_enrolled > 0 ? `${stats.reply_rate}% rate` : undefined}
        />
        {stats.failed > 0 ? (
          <StatCard
            label="Failed"
            value={stats.failed}
            icon={XCircle}
            color="red"
          />
        ) : (
          <StatCard
            label={isPipeline ? "Meetings" : "Completed"}
            value={isPipeline ? (stats.phase_breakdown?.meeting || 0) : stats.completed}
            icon={isPipeline ? Target : CheckCircle2}
            color="emerald"
          />
        )}
      </div>

      {/* Phase Funnel (Pipeline mode) */}
      {isPipeline && stats.phase_breakdown && stats.total_enrolled > 0 && (
        <div className="border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-4 h-4 text-purple-600" />
            <h4 className="text-sm font-semibold text-gray-900">Phase Funnel</h4>
          </div>
          <div className="space-y-3">
            {Object.entries(stats.phase_breakdown).map(([phase, count]) => {
              const config = phaseLabels[phase]
              if (!config || count === 0) return null
              return (
                <FunnelBar
                  key={phase}
                  label={config.label}
                  count={count as number}
                  total={stats.total_enrolled}
                  color={config.color}
                />
              )
            })}
          </div>
        </div>
      )}

      {/* Step-by-step Progress (classic mode) */}
      {!isPipeline && stats.steps_breakdown && stats.steps_breakdown.length > 0 && (
        <div className="border rounded-lg p-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-4">Step Progress</h4>
          <div className="space-y-4">
            {stats.steps_breakdown.map((step: any) => {
              const isConnection = step.step_type === 'connection_request'

              return (
                <div key={step.step_order} className="border rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-3">
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${
                      isConnection ? 'bg-blue-100' : 'bg-purple-100'
                    }`}>
                      {isConnection
                        ? <Link2 className="w-3.5 h-3.5 text-blue-600" />
                        : <MessageSquare className="w-3.5 h-3.5 text-purple-600" />
                      }
                    </div>
                    <span className="text-sm font-medium text-gray-900">
                      Step {step.step_order}: {step.label}
                    </span>
                  </div>

                  {isConnection ? (
                    <>
                      {/* Connection request step detail */}
                      <div className="grid grid-cols-4 gap-2 text-center">
                        <MiniStat
                          label="Sent"
                          value={step.sent}
                          total={stats.total_enrolled}
                          color="text-blue-600"
                        />
                        <MiniStat
                          label="Accepted"
                          value={step.connected}
                          total={step.sent}
                          color="text-green-600"
                        />
                        <MiniStat
                          label="Pending"
                          value={step.pending}
                          color="text-gray-500"
                        />
                        <MiniStat
                          label="Failed"
                          value={step.failed}
                          color="text-red-500"
                        />
                      </div>
                      {/* Progress bar */}
                      <div className="mt-3 flex h-2.5 rounded-full overflow-hidden bg-gray-100">
                        {step.connected > 0 && (
                          <div
                            className="bg-green-500"
                            style={{ width: `${(step.connected / stats.total_enrolled) * 100}%` }}
                            title={`${step.connected} accepted`}
                          />
                        )}
                        {(step.sent - step.connected) > 0 && (
                          <div
                            className="bg-blue-400"
                            style={{ width: `${((step.sent - step.connected) / stats.total_enrolled) * 100}%` }}
                            title={`${step.sent - step.connected} awaiting acceptance`}
                          />
                        )}
                        {step.pending > 0 && (
                          <div
                            className="bg-gray-300"
                            style={{ width: `${(step.pending / stats.total_enrolled) * 100}%` }}
                            title={`${step.pending} not yet sent`}
                          />
                        )}
                        {step.failed > 0 && (
                          <div
                            className="bg-red-400"
                            style={{ width: `${(step.failed / stats.total_enrolled) * 100}%` }}
                            title={`${step.failed} failed`}
                          />
                        )}
                      </div>
                      <div className="mt-1.5 flex gap-3 text-[10px] text-gray-400">
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" />Accepted</span>
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-400" />Awaiting</span>
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-gray-300" />Not sent</span>
                        {step.failed > 0 && (
                          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400" />Failed</span>
                        )}
                      </div>
                    </>
                  ) : (
                    <>
                      {/* Follow-up step detail */}
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <MiniStat
                          label="Sent"
                          value={step.sent}
                          total={step.reached}
                          color="text-purple-600"
                        />
                        <MiniStat
                          label="Pending"
                          value={step.pending}
                          color="text-gray-500"
                        />
                        <MiniStat
                          label="Eligible"
                          value={step.reached}
                          color="text-gray-700"
                        />
                      </div>
                      <div className="mt-3 w-full bg-gray-100 rounded-full h-2.5">
                        <div
                          className="h-2.5 rounded-full bg-purple-500 transition-all"
                          style={{ width: `${step.reached > 0 ? (step.sent / step.reached * 100) : 0}%` }}
                        />
                      </div>
                    </>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Outcomes summary */}
      {stats.total_enrolled > 0 && (stats.replied > 0 || stats.completed > 0 || stats.failed > 0) && (
        <div className="border rounded-lg p-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Outcomes</h4>
          <div className="space-y-2">
            {stats.replied > 0 && (
              <FunnelBar label="Replied (exited flow)" count={stats.replied} total={stats.total_enrolled} color="bg-orange-500" />
            )}
            {stats.completed > 0 && (
              <FunnelBar label="Completed all steps" count={stats.completed} total={stats.total_enrolled} color="bg-green-500" />
            )}
            {stats.failed > 0 && (
              <FunnelBar label="Failed" count={stats.failed} total={stats.total_enrolled} color="bg-red-400" />
            )}
            {stats.withdrawn > 0 && (
              <FunnelBar label="Withdrawn" count={stats.withdrawn} total={stats.total_enrolled} color="bg-gray-400" />
            )}
          </div>
        </div>
      )}

      {/* Empty state */}
      {stats.total_enrolled === 0 && (
        <div className="flex flex-col items-center justify-center py-8 text-gray-500">
          <TrendingUp className="w-12 h-12 mb-3 text-gray-300" />
          <p className="text-sm font-medium">No data yet</p>
          <p className="text-xs mt-1">Enroll leads to see sequence performance</p>
        </div>
      )}
    </div>
  )
}

// Sub-components

function StatCard({
  label,
  value,
  icon: Icon,
  color,
  subtext,
}: {
  label: string
  value: number
  icon: typeof Users
  color: string
  subtext?: string
}) {
  const colorMap: Record<string, { bg: string; text: string; icon: string }> = {
    blue: { bg: 'bg-blue-50', text: 'text-blue-700', icon: 'text-blue-500' },
    indigo: { bg: 'bg-indigo-50', text: 'text-indigo-700', icon: 'text-indigo-500' },
    green: { bg: 'bg-green-50', text: 'text-green-700', icon: 'text-green-500' },
    cyan: { bg: 'bg-cyan-50', text: 'text-cyan-700', icon: 'text-cyan-500' },
    orange: { bg: 'bg-orange-50', text: 'text-orange-700', icon: 'text-orange-500' },
    emerald: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: 'text-emerald-500' },
    red: { bg: 'bg-red-50', text: 'text-red-700', icon: 'text-red-500' },
  }
  const c = colorMap[color] || colorMap.blue

  return (
    <div className={`rounded-lg p-3 ${c.bg}`}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-4 h-4 ${c.icon}`} />
        <span className="text-xs font-medium text-gray-600">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${c.text}`}>{value}</p>
      {subtext && <p className="text-xs text-gray-500 mt-0.5">{subtext}</p>}
    </div>
  )
}

function MiniStat({
  label,
  value,
  total,
  color,
}: {
  label: string
  value: number
  total?: number
  color: string
}) {
  return (
    <div>
      <p className={`text-lg font-bold ${color}`}>{value}</p>
      <p className="text-[10px] text-gray-500 uppercase font-medium">{label}</p>
      {total != null && total > 0 && (
        <p className="text-[10px] text-gray-400">{(value / total * 100).toFixed(0)}%</p>
      )}
    </div>
  )
}

function FunnelBar({
  label,
  count,
  total,
  color,
}: {
  label: string
  count: number
  total: number
  color: string
}) {
  const pct = total > 0 ? (count / total * 100) : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-gray-700">{label}</span>
        <span className="text-sm font-medium text-gray-900">
          {count} <span className="text-gray-400 text-xs">({pct.toFixed(1)}%)</span>
        </span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2.5">
        <div
          className={`h-2.5 rounded-full transition-all ${color}`}
          style={{ width: `${Math.max(pct, 1)}%` }}
        />
      </div>
    </div>
  )
}
