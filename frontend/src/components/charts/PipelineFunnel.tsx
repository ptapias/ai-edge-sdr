import { useNavigate } from 'react-router-dom'

interface FunnelStage {
  stage: string
  count: number
  cumulative: number
  rate: number
  conversion_from_previous?: number
}

const STAGE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  new: { label: 'New', color: 'bg-gray-500', bg: 'bg-gray-100' },
  invitation_sent: { label: 'Invited', color: 'bg-blue-500', bg: 'bg-blue-100' },
  connected: { label: 'Connected', color: 'bg-green-500', bg: 'bg-green-100' },
  in_conversation: { label: 'In Conversation', color: 'bg-purple-500', bg: 'bg-purple-100' },
  meeting_scheduled: { label: 'Meeting', color: 'bg-orange-500', bg: 'bg-orange-100' },
  qualified: { label: 'Qualified', color: 'bg-emerald-500', bg: 'bg-emerald-100' },
  closed_won: { label: 'Won', color: 'bg-green-600', bg: 'bg-green-100' },
}

export default function PipelineFunnel({
  funnel,
  total,
}: {
  funnel: FunnelStage[]
  total: number
}) {
  const navigate = useNavigate()
  const maxCount = Math.max(...funnel.map(s => s.count), 1)

  return (
    <div className="space-y-3">
      {funnel.map((stage) => {
        const config = STAGE_CONFIG[stage.stage] || { label: stage.stage, color: 'bg-gray-400', bg: 'bg-gray-50' }
        const widthPercent = total > 0 ? Math.max((stage.count / maxCount) * 100, stage.count > 0 ? 8 : 0) : 0

        return (
          <button
            key={stage.stage}
            onClick={() => navigate(`/leads?status=${stage.stage}`)}
            className="w-full flex items-center gap-4 group hover:bg-gray-50 rounded-lg p-2 -mx-2 transition-colors text-left"
          >
            <div className="w-32 flex-shrink-0">
              <p className="text-sm font-medium text-gray-700 group-hover:text-blue-600 transition-colors">
                {config.label}
              </p>
            </div>
            <div className="flex-1">
              <div className="h-8 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full ${config.color} rounded-full transition-all duration-500 flex items-center justify-end px-3`}
                  style={{ width: `${widthPercent}%` }}
                >
                  {stage.count > 0 && widthPercent > 15 && (
                    <span className="text-white text-xs font-medium">{stage.count}</span>
                  )}
                </div>
              </div>
            </div>
            <div className="w-16 text-right flex-shrink-0">
              <span className="text-sm font-semibold text-gray-900">{stage.count}</span>
            </div>
            {stage.conversion_from_previous !== undefined && (
              <div className="w-16 text-right flex-shrink-0">
                <span className="text-xs text-gray-500">{stage.conversion_from_previous}%</span>
              </div>
            )}
          </button>
        )
      })}
    </div>
  )
}
