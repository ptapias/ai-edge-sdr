import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Users, Mail, Flame, Send, Folder, Building2, AlertTriangle, Plus, ArrowRight, Search,
  TrendingUp, Clock, CheckCircle, Calendar, Zap, Upload, MessageSquare, Target, LayoutGrid
} from 'lucide-react'
import {
  getGlobalStats, getCampaigns, getBusinessProfiles, getInvitationStats, getAutomationStatus,
  getConversionFunnel, getTemperatureDistribution, getResponseTracking, getActivityTimeline,
  getCampaignAnalytics,
} from '../services/api'
import PipelineFunnel from '../components/charts/PipelineFunnel'
import TemperatureChart from '../components/charts/TemperatureChart'
import ActivityChart from '../components/charts/ActivityChart'
import FocusLeads from '../components/FocusLeads'

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  subtitle,
}: {
  title: string
  value: number | string
  icon: React.ElementType
  color: string
  subtitle?: string
}) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-semibold mt-1">{value}</p>
          {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
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
    refetchInterval: 30000,
  })

  const { data: funnelData } = useQuery({
    queryKey: ['conversion-funnel'],
    queryFn: getConversionFunnel,
  })

  const { data: temperatureData } = useQuery({
    queryKey: ['temperature-distribution'],
    queryFn: getTemperatureDistribution,
  })

  const { data: responseData } = useQuery({
    queryKey: ['response-tracking'],
    queryFn: getResponseTracking,
  })

  const { data: activityData } = useQuery({
    queryKey: ['activity-timeline'],
    queryFn: () => getActivityTimeline('30d'),
  })

  const { data: campaignAnalytics } = useQuery({
    queryKey: ['campaign-analytics'],
    queryFn: getCampaignAnalytics,
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
        <p className="text-gray-500 mt-1">Pipeline overview and lead intelligence</p>
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

      {/* Section 1: Pipeline Funnel (full width) */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Pipeline Funnel</h2>
          <Link to="/pipeline" className="text-blue-600 hover:text-blue-800 text-sm font-medium flex items-center">
            <LayoutGrid className="w-4 h-4 mr-1" />
            Kanban View
          </Link>
        </div>
        {funnelData ? (
          <PipelineFunnel funnel={funnelData.funnel} total={funnelData.total} />
        ) : (
          <div className="text-center py-8 text-gray-400">Loading pipeline data...</div>
        )}
      </div>

      {/* Section 2: Key Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="Response Rate"
          value={`${responseData?.response_rate ?? 0}%`}
          icon={TrendingUp}
          color="bg-green-500"
          subtitle={`${responseData?.connected ?? 0} connected / ${responseData?.contacted ?? 0} contacted`}
        />
        <StatCard
          title="Avg. Time to Connect"
          value={responseData?.avg_days_to_connect !== null ? `${responseData?.avg_days_to_connect}d` : 'N/A'}
          icon={Clock}
          color="bg-blue-500"
          subtitle="Days from invitation to connection"
        />
        <StatCard
          title="Active Conversations"
          value={responseData?.in_conversation ?? 0}
          icon={MessageSquare}
          color="bg-purple-500"
          subtitle={`${responseData?.conversation_rate ?? 0}% of connections`}
        />
      </div>

      {/* Section 3: Temperature + Activity */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Lead Temperature</h2>
          {temperatureData ? (
            <TemperatureChart distribution={temperatureData.distribution} />
          ) : (
            <div className="text-center py-8 text-gray-400">Loading...</div>
          )}
        </div>
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">30-Day Activity</h2>
          {activityData ? (
            <ActivityChart timeline={activityData.timeline} />
          ) : (
            <div className="text-center py-8 text-gray-400">Loading...</div>
          )}
        </div>
      </div>

      {/* Section 4: Focus Leads + Automation */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Focus Leads Widget */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center">
              <Target className="w-5 h-5 mr-2 text-blue-600" />
              Focus Leads
            </h2>
            <Link to="/leads" className="text-blue-600 hover:text-blue-800 text-sm font-medium">
              View All
            </Link>
          </div>
          <FocusLeads />
        </div>

        {/* Automation + Quick Actions */}
        <div className="space-y-4">
          {/* Automation Status */}
          <Link
            to="/automation"
            className={`card border-2 block ${
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
            <div className="mt-2 flex items-center gap-4 text-sm">
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
      </div>

      {/* Section 5: Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
              <p className="text-sm text-gray-500">Find new leads with AI</p>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-blue-600" />
          </div>
        </Link>

        <Link
          to="/import"
          className="card hover:shadow-md transition-shadow group cursor-pointer"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-purple-100 rounded-lg group-hover:bg-purple-200 transition-colors">
              <Upload className="w-6 h-6 text-purple-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-gray-900">Import CSV</h3>
              <p className="text-sm text-gray-500">Upload leads from a file</p>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-purple-600" />
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
              <p className="text-sm text-gray-500">Score and contact leads</p>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-green-600" />
          </div>
        </Link>
      </div>

      {/* Section 6: Campaign Comparison */}
      {campaignAnalytics && campaignAnalytics.campaigns.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Campaign Performance</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Campaign</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-gray-500 uppercase">Leads</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-gray-500 uppercase">Hot</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-gray-500 uppercase">Contacted</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-gray-500 uppercase">Responded</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-gray-500 uppercase">Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {campaignAnalytics.campaigns.slice(0, 10).map((c) => (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="py-2 px-3">
                      <Link to={`/leads?campaign_id=${c.id}`} className="font-medium text-gray-900 hover:text-blue-600">
                        {c.name}
                      </Link>
                    </td>
                    <td className="text-right py-2 px-3 text-gray-600">{c.total_leads}</td>
                    <td className="text-right py-2 px-3">
                      <span className="text-orange-600 font-medium">{c.score_breakdown.hot || 0}</span>
                    </td>
                    <td className="text-right py-2 px-3 text-gray-600">{c.contacted}</td>
                    <td className="text-right py-2 px-3 text-gray-600">{c.responded}</td>
                    <td className="text-right py-2 px-3">
                      <span className={`font-medium ${c.response_rate > 30 ? 'text-green-600' : c.response_rate > 0 ? 'text-yellow-600' : 'text-gray-400'}`}>
                        {c.response_rate}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Section 7: Stats Grid + Recent Campaigns */}
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
            <p className="text-sm mt-1">Search for leads or import a CSV to get started</p>
          </div>
        )}
      </div>
    </div>
  )
}
