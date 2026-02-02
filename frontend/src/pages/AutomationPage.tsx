import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Play,
  Pause,
  Settings,
  Clock,
  Calendar,
  Loader2,
  CheckCircle,
  XCircle,
  TrendingUp,
  Send,
  RefreshCw,
  Zap
} from 'lucide-react'
import {
  getAutomationSettings,
  updateAutomationSettings,
  toggleAutomation,
  getAutomationStatus,
  getInvitationStats,
  getInvitationLogs,
  sendNextInvitation,
  generatePendingMessages,
  type AutomationSettings,
  type InvitationLog,
} from '../services/api'

// Days of week for the bitmask
const DAYS = [
  { label: 'Mon', value: 1 },
  { label: 'Tue', value: 2 },
  { label: 'Wed', value: 4 },
  { label: 'Thu', value: 8 },
  { label: 'Fri', value: 16 },
  { label: 'Sat', value: 32 },
  { label: 'Sun', value: 64 },
]

function StatCard({ title, value, subtitle, icon: Icon, color }: {
  title: string
  value: number | string
  subtitle?: string
  icon: React.ElementType
  color: string
}) {
  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-semibold mt-1">{value}</p>
          {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
        </div>
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </div>
  )
}

export default function AutomationPage() {
  const queryClient = useQueryClient()
  const [localSettings, setLocalSettings] = useState<Partial<AutomationSettings>>({})

  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['automation-settings'],
    queryFn: getAutomationSettings,
  })

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['automation-status'],
    queryFn: getAutomationStatus,
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  const { data: stats } = useQuery({
    queryKey: ['invitation-stats'],
    queryFn: getInvitationStats,
  })

  const { data: logs } = useQuery({
    queryKey: ['invitation-logs'],
    queryFn: () => getInvitationLogs(20),
  })

  // Sync local settings with server settings
  useEffect(() => {
    if (settings) {
      setLocalSettings(settings)
    }
  }, [settings])

  const toggleMutation = useMutation({
    mutationFn: toggleAutomation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-settings'] })
      queryClient.invalidateQueries({ queryKey: ['automation-status'] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: updateAutomationSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-settings'] })
    },
  })

  const sendNextMutation = useMutation({
    mutationFn: sendNextInvitation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-status'] })
      queryClient.invalidateQueries({ queryKey: ['invitation-logs'] })
      queryClient.invalidateQueries({ queryKey: ['invitation-stats'] })
    },
  })

  const generateMutation = useMutation({
    mutationFn: () => generatePendingMessages(20),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
    },
  })

  const handleSaveSettings = () => {
    updateMutation.mutate(localSettings)
  }

  const updateLocalSetting = <K extends keyof AutomationSettings>(key: K, value: AutomationSettings[K]) => {
    setLocalSettings(prev => ({ ...prev, [key]: value }))
  }

  const toggleDay = (dayValue: number) => {
    const current = localSettings.working_days ?? settings?.working_days ?? 31
    const newValue = current ^ dayValue
    updateLocalSetting('working_days', newValue)
  }

  const isDayEnabled = (dayValue: number) => {
    const current = localSettings.working_days ?? settings?.working_days ?? 31
    return (current & dayValue) !== 0
  }

  if (settingsLoading || statusLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Automation</h1>
          <p className="text-gray-500 mt-1">Configure automatic LinkedIn outreach</p>
        </div>

        {/* Main Toggle */}
        <button
          onClick={() => toggleMutation.mutate(!settings?.enabled)}
          disabled={toggleMutation.isPending}
          className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium text-white transition-colors ${
            settings?.enabled
              ? 'bg-red-500 hover:bg-red-600'
              : 'bg-green-500 hover:bg-green-600'
          }`}
        >
          {toggleMutation.isPending ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : settings?.enabled ? (
            <Pause className="w-5 h-5" />
          ) : (
            <Play className="w-5 h-5" />
          )}
          {settings?.enabled ? 'Stop Automation' : 'Start Automation'}
        </button>
      </div>

      {/* Status Banner */}
      <div className={`rounded-lg p-4 ${
        status?.enabled && status?.can_send
          ? 'bg-green-50 border border-green-200'
          : status?.enabled
            ? 'bg-yellow-50 border border-yellow-200'
            : 'bg-gray-50 border border-gray-200'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${
              status?.enabled && status?.can_send
                ? 'bg-green-500 animate-pulse'
                : status?.enabled
                  ? 'bg-yellow-500'
                  : 'bg-gray-400'
            }`} />
            <div>
              <p className="font-medium">
                {status?.enabled && status?.can_send
                  ? 'Automation Active'
                  : status?.enabled
                    ? 'Automation Paused'
                    : 'Automation Disabled'}
              </p>
              <p className="text-sm text-gray-600">
                {!status?.enabled
                  ? 'Click "Start Automation" to begin'
                  : !status?.is_working_hour
                    ? 'Outside working hours'
                    : status?.remaining_today === 0
                      ? 'Daily limit reached'
                      : `${status?.remaining_today} invitations remaining today`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
              className="btn btn-secondary flex items-center text-sm"
            >
              {generateMutation.isPending ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Zap className="w-4 h-4 mr-2" />
              )}
              Generate Messages
            </button>
            <button
              onClick={() => sendNextMutation.mutate()}
              disabled={sendNextMutation.isPending || !status?.can_send}
              className="btn btn-primary flex items-center text-sm"
            >
              {sendNextMutation.isPending ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Send className="w-4 h-4 mr-2" />
              )}
              Send Next
            </button>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          title="Today"
          value={stats?.today ?? 0}
          subtitle={`of ${settings?.daily_limit ?? 40} limit`}
          icon={Send}
          color="bg-blue-500"
        />
        <StatCard
          title="This Week"
          value={stats?.this_week ?? 0}
          icon={Calendar}
          color="bg-purple-500"
        />
        <StatCard
          title="This Month"
          value={stats?.this_month ?? 0}
          icon={TrendingUp}
          color="bg-green-500"
        />
        <StatCard
          title="Acceptance Rate"
          value={`${stats?.success_rate ?? 0}%`}
          icon={CheckCircle}
          color="bg-emerald-500"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Settings Card */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center">
              <Settings className="w-5 h-5 mr-2" />
              Settings
            </h2>
            <button
              onClick={handleSaveSettings}
              disabled={updateMutation.isPending}
              className="btn btn-primary btn-sm"
            >
              {updateMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                'Save'
              )}
            </button>
          </div>

          <div className="space-y-4">
            {/* Working Hours */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <Clock className="w-4 h-4 inline mr-1" />
                Working Hours
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="0"
                  max="23"
                  value={localSettings.work_start_hour ?? settings?.work_start_hour ?? 9}
                  onChange={(e) => updateLocalSetting('work_start_hour', parseInt(e.target.value))}
                  className="input w-16"
                />
                <span>:</span>
                <input
                  type="number"
                  min="0"
                  max="59"
                  value={localSettings.work_start_minute ?? settings?.work_start_minute ?? 0}
                  onChange={(e) => updateLocalSetting('work_start_minute', parseInt(e.target.value))}
                  className="input w-16"
                />
                <span className="mx-2">to</span>
                <input
                  type="number"
                  min="0"
                  max="23"
                  value={localSettings.work_end_hour ?? settings?.work_end_hour ?? 18}
                  onChange={(e) => updateLocalSetting('work_end_hour', parseInt(e.target.value))}
                  className="input w-16"
                />
                <span>:</span>
                <input
                  type="number"
                  min="0"
                  max="59"
                  value={localSettings.work_end_minute ?? settings?.work_end_minute ?? 0}
                  onChange={(e) => updateLocalSetting('work_end_minute', parseInt(e.target.value))}
                  className="input w-16"
                />
              </div>
            </div>

            {/* Working Days */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <Calendar className="w-4 h-4 inline mr-1" />
                Working Days
              </label>
              <div className="flex gap-2">
                {DAYS.map((day) => (
                  <button
                    key={day.value}
                    onClick={() => toggleDay(day.value)}
                    className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                      isDayEnabled(day.value)
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {day.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Daily Connection Limit */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Daily Connection Limit
              </label>
              <input
                type="number"
                min="1"
                max="40"
                value={Math.min(localSettings.daily_limit ?? settings?.daily_limit ?? 40, 40)}
                onChange={(e) => updateLocalSetting('daily_limit', Math.min(parseInt(e.target.value) || 1, 40))}
                className="input w-24"
              />
              <p className="text-xs text-gray-500 mt-1">Maximum connection invitations per day (max: 40)</p>
            </div>

            {/* Delay Settings */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Delay Between Invitations (seconds)
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="30"
                  max="3600"
                  value={localSettings.min_delay_seconds ?? settings?.min_delay_seconds ?? 60}
                  onChange={(e) => updateLocalSetting('min_delay_seconds', parseInt(e.target.value))}
                  className="input w-24"
                />
                <span className="text-gray-500">to</span>
                <input
                  type="number"
                  min="60"
                  max="7200"
                  value={localSettings.max_delay_seconds ?? settings?.max_delay_seconds ?? 300}
                  onChange={(e) => updateLocalSetting('max_delay_seconds', parseInt(e.target.value))}
                  className="input w-24"
                />
              </div>
              <p className="text-xs text-gray-500 mt-1">Random delay between each invitation</p>
            </div>

            {/* Minimum Score Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Minimum Lead Score
              </label>
              <input
                type="number"
                min="0"
                max="100"
                value={localSettings.min_lead_score ?? settings?.min_lead_score ?? 0}
                onChange={(e) => updateLocalSetting('min_lead_score', parseInt(e.target.value))}
                className="input w-24"
              />
              <p className="text-xs text-gray-500 mt-1">0 = no filter, 70+ = hot leads only</p>
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Recent Activity</h2>
            <button
              onClick={() => {
                queryClient.invalidateQueries({ queryKey: ['invitation-logs'] })
              }}
              className="text-gray-400 hover:text-gray-600"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {logs && logs.length > 0 ? (
              logs.map((log: InvitationLog) => (
                <div
                  key={log.id}
                  className={`flex items-center justify-between p-3 rounded-lg ${
                    log.success ? 'bg-green-50' : 'bg-red-50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    {log.success ? (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-500" />
                    )}
                    <div>
                      <p className="font-medium text-sm">{log.lead_name}</p>
                      <p className="text-xs text-gray-500">{log.lead_company}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className={`text-xs px-2 py-0.5 rounded ${
                      log.mode === 'automatic'
                        ? 'bg-purple-100 text-purple-700'
                        : 'bg-gray-100 text-gray-700'
                    }`}>
                      {log.mode}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(log.sent_at).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-center text-gray-500 py-8">
                No invitations sent yet
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
