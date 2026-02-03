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
  Zap,
  Users,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  Target,
  Filter,
  Globe
} from 'lucide-react'
import {
  getAutomationSettings,
  updateAutomationSettings,
  toggleAutomation,
  getAutomationStatus,
  getInvitationStats,
  getInvitationLogs,
  getInvitationQueue,
  sendNextInvitation,
  generatePendingMessages,
  getCampaigns,
  type AutomationSettings,
  type InvitationLog,
  type QueueLead,
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

// Common timezones
const TIMEZONES = [
  { value: 'Europe/Madrid', label: 'Madrid (GMT+1)' },
  { value: 'Europe/London', label: 'London (GMT)' },
  { value: 'Europe/Paris', label: 'Paris (GMT+1)' },
  { value: 'Europe/Berlin', label: 'Berlin (GMT+1)' },
  { value: 'Europe/Rome', label: 'Rome (GMT+1)' },
  { value: 'Europe/Amsterdam', label: 'Amsterdam (GMT+1)' },
  { value: 'Europe/Lisbon', label: 'Lisbon (GMT)' },
  { value: 'America/New_York', label: 'New York (GMT-5)' },
  { value: 'America/Los_Angeles', label: 'Los Angeles (GMT-8)' },
  { value: 'America/Chicago', label: 'Chicago (GMT-6)' },
  { value: 'America/Mexico_City', label: 'Mexico City (GMT-6)' },
  { value: 'America/Sao_Paulo', label: 'São Paulo (GMT-3)' },
  { value: 'America/Buenos_Aires', label: 'Buenos Aires (GMT-3)' },
  { value: 'Asia/Tokyo', label: 'Tokyo (GMT+9)' },
  { value: 'Asia/Shanghai', label: 'Shanghai (GMT+8)' },
  { value: 'Asia/Singapore', label: 'Singapore (GMT+8)' },
  { value: 'Asia/Dubai', label: 'Dubai (GMT+4)' },
  { value: 'Australia/Sydney', label: 'Sydney (GMT+11)' },
]

// Generate hour options
const HOURS = Array.from({ length: 24 }, (_, i) => ({
  value: i,
  label: i.toString().padStart(2, '0')
}))

// Generate minute options (15 min intervals)
const MINUTES = [
  { value: 0, label: '00' },
  { value: 15, label: '15' },
  { value: 30, label: '30' },
  { value: 45, label: '45' },
]

// Detect user's timezone
const detectTimezone = (): string => {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
    // Check if it's in our list
    if (TIMEZONES.some(t => t.value === tz)) {
      return tz
    }
    return 'Europe/Madrid' // Default fallback
  } catch {
    return 'Europe/Madrid'
  }
}

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

function QueueLeadCard({ lead }: { lead: QueueLead }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border rounded-lg p-3 hover:bg-gray-50 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-gray-900 truncate">{lead.lead_name}</p>
            {lead.score_label && (
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                lead.score_label === 'hot' ? 'bg-red-100 text-red-700' :
                lead.score_label === 'warm' ? 'bg-orange-100 text-orange-700' :
                'bg-blue-100 text-blue-700'
              }`}>
                {lead.score_label}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 truncate">{lead.job_title}</p>
          <p className="text-xs text-gray-400 truncate">{lead.company}</p>
          {lead.campaign_name && (
            <p className="text-xs text-purple-600 mt-1">
              <Target className="w-3 h-3 inline mr-1" />
              {lead.campaign_name}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {lead.linkedin_url && (
            <a
              href={lead.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-500 hover:text-blue-700"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-gray-400 hover:text-gray-600"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>
      {expanded && lead.message_preview && (
        <div className="mt-2 p-2 bg-gray-50 rounded text-xs text-gray-600">
          <MessageSquare className="w-3 h-3 inline mr-1" />
          {lead.message_preview}
        </div>
      )}
    </div>
  )
}

function InvitationLogCard({ log }: { log: InvitationLog }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className={`flex flex-col p-3 rounded-lg ${
        log.success ? 'bg-green-50' : 'bg-red-50'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {log.success ? (
            <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
          ) : (
            <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          )}
          <div className="min-w-0 flex-1">
            <p className="font-medium text-sm truncate">{log.lead_name}</p>
            <p className="text-xs text-gray-500 truncate">
              {log.lead_job_title && `${log.lead_job_title} • `}{log.lead_company}
            </p>
            {log.campaign_name && (
              <p className="text-xs text-purple-600 truncate">
                <Target className="w-3 h-3 inline mr-1" />
                {log.campaign_name}
              </p>
            )}
          </div>
        </div>
        <div className="text-right flex-shrink-0 ml-2">
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
      {log.message_preview && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-gray-500 hover:text-gray-700 mt-2 flex items-center"
        >
          {expanded ? <ChevronUp className="w-3 h-3 mr-1" /> : <ChevronDown className="w-3 h-3 mr-1" />}
          {expanded ? 'Hide message' : 'Show message'}
        </button>
      )}
      {expanded && log.message_preview && (
        <div className="mt-2 p-2 bg-white/50 rounded text-xs text-gray-600 border border-gray-200">
          {log.message_preview}
        </div>
      )}
      {!log.success && log.error_message && (
        <p className="text-xs text-red-600 mt-2">Error: {log.error_message}</p>
      )}
    </div>
  )
}

export default function AutomationPage() {
  const queryClient = useQueryClient()
  const [localSettings, setLocalSettings] = useState<Partial<AutomationSettings>>({})
  const [showSettings, setShowSettings] = useState(false)

  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['automation-settings'],
    queryFn: getAutomationSettings,
  })

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['automation-status'],
    queryFn: getAutomationStatus,
    refetchInterval: 10000,
  })

  const { data: stats } = useQuery({
    queryKey: ['invitation-stats'],
    queryFn: getInvitationStats,
  })

  const { data: logs } = useQuery({
    queryKey: ['invitation-logs'],
    queryFn: () => getInvitationLogs(30),
  })

  const { data: queue, isLoading: queueLoading } = useQuery({
    queryKey: ['invitation-queue'],
    queryFn: () => getInvitationQueue(10),
    refetchInterval: 30000,
  })

  const { data: campaigns } = useQuery({
    queryKey: ['campaigns'],
    queryFn: getCampaigns,
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
      queryClient.invalidateQueries({ queryKey: ['invitation-queue'] })
    },
  })

  const sendNextMutation = useMutation({
    mutationFn: sendNextInvitation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-status'] })
      queryClient.invalidateQueries({ queryKey: ['invitation-logs'] })
      queryClient.invalidateQueries({ queryKey: ['invitation-stats'] })
      queryClient.invalidateQueries({ queryKey: ['invitation-queue'] })
    },
  })

  const generateMutation = useMutation({
    mutationFn: () => generatePendingMessages(20),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['invitation-queue'] })
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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Automatic Connections</h1>
          <p className="text-gray-500 mt-1">Send personalized LinkedIn connection requests automatically</p>
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
          {settings?.enabled ? 'Stop' : 'Start'}
        </button>
      </div>

      {/* Campaign Selector */}
      <div className="bg-white rounded-lg border p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-gray-400" />
              <span className="font-medium text-gray-700">Target Campaign:</span>
            </div>
            <select
              value={localSettings.target_campaign_id ?? settings?.target_campaign_id ?? ''}
              onChange={(e) => {
                updateLocalSetting('target_campaign_id', e.target.value || null)
                // Save immediately
                updateMutation.mutate({ ...localSettings, target_campaign_id: e.target.value || null })
              }}
              className="input w-64"
            >
              <option value="">All Campaigns</option>
              {campaigns?.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>
                  {campaign.name} ({campaign.total_leads} leads)
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm text-gray-500">Eligible leads</p>
              <p className="text-xl font-semibold text-gray-900">{queue?.total_eligible ?? 0}</p>
            </div>
            <Users className="w-8 h-8 text-blue-500" />
          </div>
        </div>
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
                  ? 'Click "Start" to begin sending connections'
                  : !status?.is_working_hour
                    ? 'Outside working hours'
                    : status?.remaining_today === 0
                      ? 'Daily limit reached'
                      : `${status?.remaining_today} connections remaining today`}
              </p>
            </div>
            {status?.current_time && (
              <div className="ml-4 pl-4 border-l border-gray-300 text-sm text-gray-600">
                <Clock className="w-4 h-4 inline mr-1" />
                <span className="font-medium">{status.current_time}</span>
                <span className="text-gray-400 text-xs ml-1">
                  ({status.timezone?.split('/').pop()?.replace('_', ' ')})
                </span>
              </div>
            )}
            {status?.scheduler_running && (
              <div className="ml-4 pl-4 border-l border-gray-300">
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
                  <span className="w-2 h-2 bg-green-500 rounded-full mr-1.5 animate-pulse"></span>
                  Auto-sending
                </span>
              </div>
            )}
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
          title="Send Success"
          value={`${stats?.success_rate ?? 0}%`}
          subtitle="API success rate"
          icon={CheckCircle}
          color="bg-emerald-500"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Queue Preview */}
        <div className="card lg:col-span-1">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center">
              <Users className="w-5 h-5 mr-2 text-blue-500" />
              Next in Queue
            </h2>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ['invitation-queue'] })}
              className="text-gray-400 hover:text-gray-600"
            >
              <RefreshCw className={`w-4 h-4 ${queueLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {queue?.queue && queue.queue.length > 0 ? (
              queue.queue.map((lead) => (
                <QueueLeadCard key={lead.lead_id} lead={lead} />
              ))
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Users className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                <p>No leads in queue</p>
                <p className="text-xs text-gray-400 mt-1">
                  Make sure leads have LinkedIn URL and generated message
                </p>
              </div>
            )}
          </div>

          {queue?.total_eligible && queue.total_eligible > 10 && (
            <p className="text-xs text-gray-500 text-center mt-3">
              +{queue.total_eligible - 10} more leads waiting
            </p>
          )}
        </div>

        {/* Recent Activity */}
        <div className="card lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Recent Invitations</h2>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ['invitation-logs'] })}
              className="text-gray-400 hover:text-gray-600"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {logs && logs.length > 0 ? (
              logs.map((log: InvitationLog) => (
                <InvitationLogCard key={log.id} log={log} />
              ))
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Send className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                <p>No invitations sent yet</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Settings (Collapsible) */}
      <div className="card">
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="w-full flex items-center justify-between"
        >
          <h2 className="text-lg font-semibold flex items-center">
            <Settings className="w-5 h-5 mr-2" />
            Settings
          </h2>
          {showSettings ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </button>

        {showSettings && (
          <div className="mt-4 space-y-6">
            {/* Timezone & Working Hours Row */}
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Timezone */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Globe className="w-4 h-4 inline mr-1" />
                    Timezone
                  </label>
                  <select
                    value={localSettings.timezone ?? settings?.timezone ?? detectTimezone()}
                    onChange={(e) => updateLocalSetting('timezone', e.target.value)}
                    className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-lg text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                  >
                    {TIMEZONES.map((tz) => (
                      <option key={tz.value} value={tz.value}>
                        {tz.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Working Hours - Modern Time Picker */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Clock className="w-4 h-4 inline mr-1" />
                    Working Hours
                  </label>
                  <div className="flex items-center gap-2">
                    {/* Start Time */}
                    <div className="flex items-center bg-white border border-gray-200 rounded-lg overflow-hidden">
                      <select
                        value={localSettings.work_start_hour ?? settings?.work_start_hour ?? 9}
                        onChange={(e) => updateLocalSetting('work_start_hour', parseInt(e.target.value))}
                        className="px-3 py-2.5 bg-transparent border-0 text-gray-900 font-medium focus:ring-0 focus:outline-none appearance-none cursor-pointer"
                      >
                        {HOURS.map((h) => (
                          <option key={h.value} value={h.value}>{h.label}</option>
                        ))}
                      </select>
                      <span className="text-gray-400 font-medium">:</span>
                      <select
                        value={localSettings.work_start_minute ?? settings?.work_start_minute ?? 0}
                        onChange={(e) => updateLocalSetting('work_start_minute', parseInt(e.target.value))}
                        className="px-3 py-2.5 bg-transparent border-0 text-gray-900 font-medium focus:ring-0 focus:outline-none appearance-none cursor-pointer"
                      >
                        {MINUTES.map((m) => (
                          <option key={m.value} value={m.value}>{m.label}</option>
                        ))}
                      </select>
                    </div>

                    <span className="text-gray-400 font-medium px-2">→</span>

                    {/* End Time */}
                    <div className="flex items-center bg-white border border-gray-200 rounded-lg overflow-hidden">
                      <select
                        value={localSettings.work_end_hour ?? settings?.work_end_hour ?? 18}
                        onChange={(e) => updateLocalSetting('work_end_hour', parseInt(e.target.value))}
                        className="px-3 py-2.5 bg-transparent border-0 text-gray-900 font-medium focus:ring-0 focus:outline-none appearance-none cursor-pointer"
                      >
                        {HOURS.map((h) => (
                          <option key={h.value} value={h.value}>{h.label}</option>
                        ))}
                      </select>
                      <span className="text-gray-400 font-medium">:</span>
                      <select
                        value={localSettings.work_end_minute ?? settings?.work_end_minute ?? 0}
                        onChange={(e) => updateLocalSetting('work_end_minute', parseInt(e.target.value))}
                        className="px-3 py-2.5 bg-transparent border-0 text-gray-900 font-medium focus:ring-0 focus:outline-none appearance-none cursor-pointer"
                      >
                        {MINUTES.map((m) => (
                          <option key={m.value} value={m.value}>{m.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              {/* Working Days - Same Row */}
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Calendar className="w-4 h-4 inline mr-1" />
                  Working Days
                </label>
                <div className="flex gap-2">
                  {DAYS.map((day) => (
                    <button
                      key={day.value}
                      onClick={() => toggleDay(day.value)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                        isDayEnabled(day.value)
                          ? 'bg-blue-500 text-white shadow-sm'
                          : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
                      }`}
                    >
                      {day.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Daily Limit */}
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Daily Connection Limit
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="1"
                    max="40"
                    value={Math.min(localSettings.daily_limit ?? settings?.daily_limit ?? 40, 40)}
                    onChange={(e) => updateLocalSetting('daily_limit', Math.min(parseInt(e.target.value) || 1, 40))}
                    className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
                  />
                  <span className="text-xl font-semibold text-gray-900 w-10 text-right">
                    {Math.min(localSettings.daily_limit ?? settings?.daily_limit ?? 40, 40)}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-2">Maximum: 40 per day (LinkedIn limit)</p>
              </div>

              {/* Delay Settings */}
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Delay Between Invitations
                </label>
                <div className="flex items-center gap-2">
                  <select
                    value={localSettings.min_delay_seconds ?? settings?.min_delay_seconds ?? 60}
                    onChange={(e) => updateLocalSetting('min_delay_seconds', parseInt(e.target.value))}
                    className="flex-1 px-3 py-2 bg-white border border-gray-200 rounded-lg text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value={30}>30s</option>
                    <option value={60}>1 min</option>
                    <option value={120}>2 min</option>
                    <option value={180}>3 min</option>
                    <option value={300}>5 min</option>
                  </select>
                  <span className="text-gray-400">→</span>
                  <select
                    value={localSettings.max_delay_seconds ?? settings?.max_delay_seconds ?? 300}
                    onChange={(e) => updateLocalSetting('max_delay_seconds', parseInt(e.target.value))}
                    className="flex-1 px-3 py-2 bg-white border border-gray-200 rounded-lg text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value={60}>1 min</option>
                    <option value={180}>3 min</option>
                    <option value={300}>5 min</option>
                    <option value={600}>10 min</option>
                    <option value={900}>15 min</option>
                  </select>
                </div>
                <p className="text-xs text-gray-500 mt-2">Random delay between each invitation</p>
              </div>

              {/* Minimum Score */}
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Minimum Lead Score
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="10"
                    value={localSettings.min_lead_score ?? settings?.min_lead_score ?? 0}
                    onChange={(e) => updateLocalSetting('min_lead_score', parseInt(e.target.value))}
                    className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
                  />
                  <span className="text-xl font-semibold text-gray-900 w-10 text-right">
                    {localSettings.min_lead_score ?? settings?.min_lead_score ?? 0}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  {(localSettings.min_lead_score ?? settings?.min_lead_score ?? 0) === 0
                    ? 'All leads'
                    : (localSettings.min_lead_score ?? settings?.min_lead_score ?? 0) >= 70
                      ? 'Hot leads only'
                      : 'Warm & hot leads'}
                </p>
              </div>
            </div>

            <div className="flex justify-end pt-4 border-t">
              <button
                onClick={handleSaveSettings}
                disabled={updateMutation.isPending}
                className="btn btn-primary"
              >
                {updateMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : null}
                Save Settings
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
