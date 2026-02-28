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
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Enrolled"
          value={stats.total_enrolled}
          icon={Users}
          color="blue"
        />
        <StatCard
          label="Active"
          value={stats.active}
          icon={TrendingUp}
          color="green"
        />
        <StatCard
          label={isPipeline ? "Meetings" : "Replied"}
          value={isPipeline ? (stats.phase_breakdown?.meeting || 0) : stats.replied}
          icon={isPipeline ? Target : MessageCircle}
          color="orange"
          subtext={stats.total_enrolled > 0 ? `${stats.reply_rate.toFixed(1)}% rate` : undefined}
        />
        <StatCard
          label={isPipeline ? "Parked" : "Completed"}
          value={isPipeline ? (stats.parked || 0) : stats.completed}
          icon={CheckCircle2}
          color="emerald"
          subtext={isPipeline ? undefined : (stats.total_enrolled > 0 ? `${stats.completion_rate.toFixed(1)}% rate` : undefined)}
        />
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
                  count={count}
                  total={stats.total_enrolled}
                  color={config.color}
                />
              )
            })}
          </div>
        </div>
      )}

      {/* Classic Conversion Funnel */}
      {!isPipeline && stats.total_enrolled > 0 && (
        <div className="border rounded-lg p-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-4">Conversion Funnel</h4>
          <div className="space-y-3">
            <FunnelBar
              label="Enrolled"
              count={stats.total_enrolled}
              total={stats.total_enrolled}
              color="bg-blue-500"
            />
            <FunnelBar
              label="Active / In Progress"
              count={stats.active}
              total={stats.total_enrolled}
              color="bg-indigo-500"
            />
            <FunnelBar
              label="Completed All Steps"
              count={stats.completed}
              total={stats.total_enrolled}
              color="bg-green-500"
            />
            <FunnelBar
              label="Replied (Conversions)"
              count={stats.replied}
              total={stats.total_enrolled}
              color="bg-orange-500"
            />
            {stats.failed > 0 && (
              <FunnelBar
                label="Failed"
                count={stats.failed}
                total={stats.total_enrolled}
                color="bg-red-400"
              />
            )}
            {stats.withdrawn > 0 && (
              <FunnelBar
                label="Withdrawn"
                count={stats.withdrawn}
                total={stats.total_enrolled}
                color="bg-gray-400"
              />
            )}
          </div>
        </div>
      )}

      {/* Steps Breakdown (classic only) */}
      {!isPipeline && stats.steps_breakdown && stats.steps_breakdown.length > 0 && (
        <div className="border rounded-lg p-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-4">Steps Performance</h4>
          <div className="space-y-3">
            {stats.steps_breakdown.map((step) => {
              const isConnection = step.step_type === 'connection_request'
              const Icon = isConnection ? Send : MessageSquare
              const completionRate = step.reached > 0 ? (step.completed / step.reached * 100) : 0

              return (
                <div key={step.step_order} className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                    isConnection ? 'bg-blue-100' : 'bg-purple-100'
                  }`}>
                    <Icon className={`w-4 h-4 ${isConnection ? 'text-blue-600' : 'text-purple-600'}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-gray-700">
                        Step {step.step_order}: {isConnection ? 'Connection Request' : 'Follow-up'}
                      </span>
                      <span className="text-xs text-gray-500">
                        {step.completed}/{step.reached} ({completionRate.toFixed(0)}%)
                      </span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${
                          isConnection ? 'bg-blue-500' : 'bg-purple-500'
                        }`}
                        style={{ width: `${Math.min(completionRate, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              )
            })}
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
    green: { bg: 'bg-green-50', text: 'text-green-700', icon: 'text-green-500' },
    orange: { bg: 'bg-orange-50', text: 'text-orange-700', icon: 'text-orange-500' },
    emerald: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: 'text-emerald-500' },
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
