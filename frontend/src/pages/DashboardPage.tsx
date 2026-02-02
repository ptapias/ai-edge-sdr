import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Users, Mail, Flame, Send, Folder, Building2, AlertTriangle, Plus, ArrowRight, Search } from 'lucide-react'
import { getGlobalStats, getCampaigns, getBusinessProfiles } from '../services/api'

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
