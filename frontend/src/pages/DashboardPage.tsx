import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Users, Mail, Flame, Send, Folder, Building2, AlertTriangle, Plus, ArrowRight, Search,
  TrendingUp, Clock, CheckCircle, Calendar, Zap
} from 'lucide-react'
import { getGlobalStats, getCampaigns, getBusinessProfiles, getInvitationStats, getAutomationStatus } from '../services/api'

function StatCard({
  title,
  value,
  icon: Icon,
  color
}: {
  title: string
  value: number | string
  icon: React.ElementType
  color: string
}) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-semibold mt-1">{value}</p>
        </div>
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  )
}

// Simple bar chart component
function MiniBarChart({ data }: { data: Array<{ date: string; count: number; successful: number }> }) {
  const maxCount = Math.max(...data.map(d => d.count), 1)

  return (
    <div className="flex items-end gap-1 h-20">
      {data.slice().reverse().map((day, i) => (
        <div key={i} className="flex-1 flex flex-col items-center">
          <div className="w-full flex flex-col-reverse">
            <div
              className="w-full bg-blue-500 rounded-t"
              style={{ height: `${(day.count / maxCount) * 60}px` }}
              title={`${day.count} sent on ${day.date}`}
            />
          </div>
          <span className="text-[10px] text-gray-400 mt-1">
            {new Date(day.date).toLocaleDateString('en', { weekday: 'short' }).slice(0, 2)}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: getGlobalStats,
  })

  const { data: campaigns, isLoading: campaignsLoading } = useQuery({
    queryKey: ['campaigns'],
    queryFn: getCampaigns,
  })

  const { data: profiles } = useQuery({
    queryKey: ['business-profiles'],
    queryFn: getBusinessProfiles,
  })

  const { data: invitationStats } = useQuery({
    queryKey: ['invitation-stats'],
    queryFn: getInvitationStats,
  })

  const { data: automationStatus } = useQuery({
    queryKey: ['automation-status'],
    queryFn: getAutomationStatus,
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const defaultProfile = profiles?.find(p => p.is_default)
  const hasNoProfile = !profiles || profiles.length === 0

  if (statsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">Overview of your lead generation</p>
      </div>

      {/* Setup Warning - No Business Profile */}
      {hasNoProfile && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-amber-100 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-amber-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-amber-900 text-lg">Setup Required: Business Profile</h3>
              <p className="text-amber-700 mt-1">
                Configure your business profile to enable AI-powered lead scoring and personalized message generation.
                This helps the AI understand your ideal customer and craft relevant outreach.
              </p>
              <Link
                to="/settings"
                className="inline-flex items-center mt-4 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 font-medium"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Business Profile
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Current Business Profile */}
      {defaultProfile && (
        <div className="card bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <Building2 className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-blue-600 font-medium">Active Business Profile</p>
                <h3 className="font-semibold text-gray-900 text-lg">{defaultProfile.name}</h3>
                {defaultProfile.description && (
                  <p className="text-gray-600 mt-1">{defaultProfile.description}</p>
                )}
                {defaultProfile.ideal_customer && (
                  <p className="text-sm text-gray-500 mt-2">
                    <span className="font-medium">Ideal Customer:</span> {defaultProfile.ideal_customer}
                  </p>
                )}
              </div>
            </div>
            <Link
              to="/settings"
              className="text-blue-600 hover:text-blue-800 text-sm font-medium"
            >
              Edit
            </Link>
          </div>
        </div>
      )}

      {/* Automation Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link
          to="/automation"
          className={`card border-2 ${
            automationStatus?.enabled && automationStatus?.can_send
              ? 'border-green-200 bg-green-50'
              : automationStatus?.enabled
                ? 'border-yellow-200 bg-yellow-50'
                : 'border-gray-200'
          }`}
        >
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-lg ${
              automationStatus?.enabled && automationStatus?.can_send
                ? 'bg-green-100'
                : automationStatus?.enabled
                  ? 'bg-yellow-100'
                  : 'bg-gray-100'
            }`}>
              <Zap className={`w-6 h-6 ${
                automationStatus?.enabled && automationStatus?.can_send
                  ? 'text-green-600'
                  : automationStatus?.enabled
                    ? 'text-yellow-600'
                    : 'text-gray-400'
              }`} />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${
                  automationStatus?.enabled && automationStatus?.can_send
                    ? 'bg-green-500 animate-pulse'
                    : automationStatus?.enabled
                      ? 'bg-yellow-500'
                      : 'bg-gray-400'
                }`} />
                <h3 className="font-semibold text-gray-900">
                  {automationStatus?.enabled && automationStatus?.can_send
                    ? 'Automation Active'
                    : automationStatus?.enabled
                      ? 'Automation Paused'
                      : 'Automation Off'}
                </h3>
              </div>
              <p className="text-sm text-gray-500 mt-1">
                {automationStatus?.invitations_sent_today ?? 0} / {automationStatus?.daily_limit ?? 40} today
              </p>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-400" />
          </div>
        </Link>

        {/* Invitations This Week */}
        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-gray-500">This Week</p>
            <Calendar className="w-4 h-4 text-gray-400" />
          </div>
          <p className="text-2xl font-semibold">{invitationStats?.this_week ?? 0}</p>
          <p className="text-xs text-gray-500 mt-1">invitations sent</p>
          {invitationStats?.by_day && (
            <div className="mt-3">
              <MiniBarChart data={invitationStats.by_day} />
            </div>
          )}
        </div>

        {/* Acceptance Rate */}
        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-gray-500">Acceptance Rate</p>
            <TrendingUp className="w-4 h-4 text-gray-400" />
          </div>
          <p className="text-2xl font-semibold text-green-600">{invitationStats?.acceptance_rate ?? 0}%</p>
          <p className="text-xs text-gray-500 mt-1">connections accepted</p>
          <div className="mt-3 flex items-center gap-4 text-sm">
            <span className="flex items-center text-green-600">
              <CheckCircle className="w-4 h-4 mr-1" />
              {invitationStats?.accepted ?? 0} accepted
            </span>
            <span className="flex items-center text-gray-400">
              <Clock className="w-4 h-4 mr-1" />
              {invitationStats?.pending_acceptance ?? 0} pending
            </span>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link
          to="/search"
          className="card hover:shadow-md transition-shadow group cursor-pointer"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-blue-100 rounded-lg group-hover:bg-blue-200 transition-colors">
              <Search className="w-6 h-6 text-blue-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-gray-900">Search Leads</h3>
              <p className="text-sm text-gray-500">Find new leads with natural language</p>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-blue-600 transition-colors" />
          </div>
        </Link>

        <Link
          to="/leads"
          className="card hover:shadow-md transition-shadow group cursor-pointer"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-green-100 rounded-lg group-hover:bg-green-200 transition-colors">
              <Users className="w-6 h-6 text-green-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-gray-900">Manage Leads</h3>
              <p className="text-sm text-gray-500">View, score and contact your leads</p>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-green-600 transition-colors" />
          </div>
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Leads"
          value={stats?.leads.total ?? 0}
          icon={Users}
          color="bg-blue-500"
        />
        <StatCard
          title="Verified Emails"
          value={stats?.leads.verified ?? 0}
          icon={Mail}
          color="bg-green-500"
        />
        <StatCard
          title="Hot Leads"
          value={stats?.leads.hot ?? 0}
          icon={Flame}
          color="bg-orange-500"
        />
        <StatCard
          title="Contacted"
          value={stats?.leads.contacted ?? 0}
          icon={Send}
          color="bg-purple-500"
        />
      </div>

      {/* Recent Campaigns */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Recent Campaigns</h2>
          <Link to="/search" className="text-blue-600 hover:text-blue-800 text-sm font-medium">
            + New Search
          </Link>
        </div>
        {campaignsLoading ? (
          <div className="text-center py-4 text-gray-500">Loading...</div>
        ) : campaigns && campaigns.length > 0 ? (
          <div className="divide-y">
            {campaigns.slice(0, 5).map((campaign) => (
              <Link
                key={campaign.id}
                to={`/leads?campaign_id=${campaign.id}`}
                className="py-3 flex items-center justify-between hover:bg-gray-50 -mx-6 px-6 transition-colors"
              >
                <div>
                  <p className="font-medium text-gray-900">{campaign.name}</p>
                  <p className="text-sm text-gray-500 truncate max-w-md">{campaign.search_query}</p>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-gray-900">{campaign.total_leads} leads</p>
                  <p className="text-sm text-gray-500">
                    {new Date(campaign.created_at).toLocaleDateString()}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <Folder className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No campaigns yet</p>
            <p className="text-sm mt-1">Search for leads to create your first campaign</p>
          </div>
        )}
      </div>
    </div>
  )
}
