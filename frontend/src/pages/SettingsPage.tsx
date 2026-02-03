import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Edit2, Check, X, Loader2, Linkedin, Unlink, AlertCircle, CheckCircle, Mail, Lock, ShieldCheck } from 'lucide-react'
import {
  getBusinessProfiles,
  createBusinessProfile,
  updateBusinessProfile,
  type BusinessProfile,
} from '../services/api'
import { authApi, type LinkedInAccount, type LinkedInConnectResponse } from '../services/authApi'

export default function SettingsPage() {
  const [isCreating, setIsCreating] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: profiles, isLoading } = useQuery({
    queryKey: ['business-profiles'],
    queryFn: getBusinessProfiles,
  })

  const createMutation = useMutation({
    mutationFn: createBusinessProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business-profiles'] })
      setIsCreating(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<BusinessProfile> }) =>
      updateBusinessProfile(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business-profiles'] })
      setEditingId(null)
    },
  })

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* LinkedIn Connection Section */}
      <LinkedInConnectionSection />

      {/* Business Profiles Section */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Business Profiles</h2>
            <p className="text-gray-500 mt-1">Configure your business profiles for AI scoring</p>
          </div>
          <button
            className="btn btn-primary flex items-center"
            onClick={() => setIsCreating(true)}
            disabled={isCreating}
          >
            <Plus className="w-4 h-4 mr-2" />
            New Profile
          </button>
        </div>

        {/* New Profile Form */}
        {isCreating && (
          <ProfileForm
            onSubmit={(data) => createMutation.mutate(data)}
            onCancel={() => setIsCreating(false)}
            isLoading={createMutation.isPending}
          />
        )}

        {/* Profiles List */}
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        ) : profiles && profiles.length > 0 ? (
          <div className="space-y-4">
            {profiles.map((profile) =>
              editingId === profile.id ? (
                <ProfileForm
                  key={profile.id}
                  profile={profile}
                  onSubmit={(data) => updateMutation.mutate({ id: profile.id, data })}
                  onCancel={() => setEditingId(null)}
                  isLoading={updateMutation.isPending}
                />
              ) : (
                <ProfileCard
                  key={profile.id}
                  profile={profile}
                  onEdit={() => setEditingId(profile.id)}
                />
              )
            )}
          </div>
        ) : (
          <div className="card text-center py-12 text-gray-500">
            <p>No business profiles yet</p>
            <p className="text-sm mt-1">Create a profile to personalize lead scoring</p>
          </div>
        )}
      </div>
    </div>
  )
}

function LinkedInConnectionSection() {
  const [showConnectForm, setShowConnectForm] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pendingCheckpoint, setPendingCheckpoint] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: linkedInAccount, isLoading } = useQuery({
    queryKey: ['linkedin-account'],
    queryFn: authApi.getLinkedInAccount,
  })

  const connectMutation = useMutation({
    mutationFn: authApi.connectLinkedIn,
    onSuccess: (data: LinkedInConnectResponse) => {
      if (data.connected) {
        // Successfully connected
        queryClient.invalidateQueries({ queryKey: ['linkedin-account'] })
        setShowConnectForm(false)
        setEmail('')
        setPassword('')
        setError(null)
        setPendingCheckpoint(null)
      } else if (data.requires_checkpoint) {
        // Need 2FA/OTP
        setPendingCheckpoint(data.checkpoint_type)
        setError(null)
      }
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Failed to connect LinkedIn account')
    },
  })

  const checkpointMutation = useMutation({
    mutationFn: authApi.solveLinkedInCheckpoint,
    onSuccess: (data: LinkedInConnectResponse) => {
      if (data.connected) {
        // Successfully connected
        queryClient.invalidateQueries({ queryKey: ['linkedin-account'] })
        setShowConnectForm(false)
        setEmail('')
        setPassword('')
        setVerificationCode('')
        setError(null)
        setPendingCheckpoint(null)
      } else if (data.requires_checkpoint) {
        // Another checkpoint needed
        setPendingCheckpoint(data.checkpoint_type)
        setVerificationCode('')
      }
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Invalid verification code')
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: authApi.disconnectLinkedIn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['linkedin-account'] })
    },
  })

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    connectMutation.mutate({ username: email, password })
  }

  const handleVerifyCode = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    checkpointMutation.mutate({ code: verificationCode })
  }

  const handleCancel = () => {
    setShowConnectForm(false)
    setEmail('')
    setPassword('')
    setVerificationCode('')
    setError(null)
    setPendingCheckpoint(null)
  }

  if (isLoading) {
    return (
      <div className="card">
        <div className="flex items-center gap-3">
          <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
          <span className="text-gray-500">Loading LinkedIn status...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-900">LinkedIn Connection</h2>
        <p className="text-gray-500 mt-1">Connect your LinkedIn account to send invitations and messages</p>
      </div>

      <div className="card">
        {linkedInAccount?.is_connected ? (
          <LinkedInConnectedCard
            account={linkedInAccount}
            onDisconnect={() => disconnectMutation.mutate()}
            isDisconnecting={disconnectMutation.isPending}
          />
        ) : showConnectForm ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Linkedin className="w-5 h-5 text-[#0A66C2]" />
                {pendingCheckpoint ? 'Verify Your Identity' : 'Connect LinkedIn'}
              </h3>
              <button
                className="text-gray-400 hover:text-gray-600"
                onClick={handleCancel}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {error && (
              <div className="rounded-md bg-red-50 p-4">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-red-400" />
                  <div className="ml-3">
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                </div>
              </div>
            )}

            {pendingCheckpoint ? (
              // 2FA/OTP Verification Form
              <form onSubmit={handleVerifyCode} className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <ShieldCheck className="w-5 h-5 text-blue-600 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-blue-800">
                        Verification Required
                      </p>
                      <p className="text-sm text-blue-700 mt-1">
                        {pendingCheckpoint === '2FA' && 'Enter the code from your authenticator app.'}
                        {pendingCheckpoint === 'OTP' && 'Enter the code sent to your email or phone.'}
                        {pendingCheckpoint === 'IN_APP_VALIDATION' && 'Please approve the login request in your LinkedIn app, then enter any code shown.'}
                        {!['2FA', 'OTP', 'IN_APP_VALIDATION'].includes(pendingCheckpoint || '') && `Enter the verification code (${pendingCheckpoint}).`}
                      </p>
                      <p className="text-xs text-blue-600 mt-2">
                        You have 5 minutes to complete this verification.
                      </p>
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Verification Code
                  </label>
                  <input
                    type="text"
                    className="input text-center text-2xl tracking-widest"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ''))}
                    placeholder="000000"
                    maxLength={8}
                    autoFocus
                    required
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={handleCancel}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary flex items-center"
                    disabled={checkpointMutation.isPending || verificationCode.length < 4}
                  >
                    {checkpointMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Verifying...
                      </>
                    ) : (
                      <>
                        <Check className="w-4 h-4 mr-2" />
                        Verify
                      </>
                    )}
                  </button>
                </div>
              </form>
            ) : (
              // Email/Password Form
              <form onSubmit={handleConnect} className="space-y-4">
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                  <p className="text-sm text-gray-600">
                    Enter your LinkedIn credentials to connect your account.
                    Your password is sent securely and is never stored.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    LinkedIn Email
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Mail className="h-5 w-5 text-gray-400" />
                    </div>
                    <input
                      type="email"
                      className="input pl-10"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="your.email@example.com"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    LinkedIn Password
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Lock className="h-5 w-5 text-gray-400" />
                    </div>
                    <input
                      type="password"
                      className="input pl-10"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Your LinkedIn password"
                      required
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={handleCancel}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary flex items-center"
                    disabled={connectMutation.isPending}
                  >
                    {connectMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Connecting...
                      </>
                    ) : (
                      <>
                        <Linkedin className="w-4 h-4 mr-2" />
                        Connect LinkedIn
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center">
                <Linkedin className="w-6 h-6 text-gray-400" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">LinkedIn Not Connected</h3>
                <p className="text-sm text-gray-500">
                  Connect your LinkedIn account to send invitations and messages
                </p>
              </div>
            </div>
            <button
              className="btn btn-primary flex items-center"
              onClick={() => setShowConnectForm(true)}
            >
              <Linkedin className="w-4 h-4 mr-2" />
              Connect LinkedIn
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function LinkedInConnectedCard({
  account,
  onDisconnect,
  isDisconnecting,
}: {
  account: LinkedInAccount
  onDisconnect: () => void
  isDisconnecting: boolean
}) {
  const [showConfirm, setShowConfirm] = useState(false)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-[#0A66C2] rounded-full flex items-center justify-center">
            <Linkedin className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-gray-900">
                {account.account_name || 'LinkedIn Connected'}
              </h3>
              <span className="flex items-center gap-1 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                <CheckCircle className="w-3 h-3" />
                Connected
              </span>
            </div>
            {account.linkedin_email && (
              <p className="text-sm text-gray-500">{account.linkedin_email}</p>
            )}
            {account.connected_at && (
              <p className="text-xs text-gray-400">
                Connected on {new Date(account.connected_at).toLocaleDateString()}
              </p>
            )}
          </div>
        </div>

        {showConfirm ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Disconnect?</span>
            <button
              className="btn btn-secondary text-sm py-1 px-3"
              onClick={() => setShowConfirm(false)}
              disabled={isDisconnecting}
            >
              Cancel
            </button>
            <button
              className="btn bg-red-600 hover:bg-red-700 text-white text-sm py-1 px-3 flex items-center"
              onClick={onDisconnect}
              disabled={isDisconnecting}
            >
              {isDisconnecting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Unlink className="w-4 h-4 mr-1" />
                  Confirm
                </>
              )}
            </button>
          </div>
        ) : (
          <button
            className="text-gray-400 hover:text-red-600 p-2"
            onClick={() => setShowConfirm(true)}
            title="Disconnect LinkedIn"
          >
            <Unlink className="w-5 h-5" />
          </button>
        )}
      </div>
    </div>
  )
}

function ProfileCard({
  profile,
  onEdit,
}: {
  profile: BusinessProfile
  onEdit: () => void
}) {
  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900">{profile.name}</h3>
            {profile.is_default && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                Default
              </span>
            )}
          </div>
          {profile.description && (
            <p className="text-gray-600 mt-1">{profile.description}</p>
          )}
        </div>
        <button
          className="p-2 text-gray-400 hover:text-gray-600"
          onClick={onEdit}
        >
          <Edit2 className="w-4 h-4" />
        </button>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        {profile.ideal_customer && (
          <div>
            <p className="text-gray-500">Ideal Customer</p>
            <p className="text-gray-900">{profile.ideal_customer}</p>
          </div>
        )}
        {profile.target_industries && (
          <div>
            <p className="text-gray-500">Industries</p>
            <p className="text-gray-900">{profile.target_industries}</p>
          </div>
        )}
        {profile.sender_name && (
          <div>
            <p className="text-gray-500">Sender</p>
            <p className="text-gray-900">
              {profile.sender_name}
              {profile.sender_role && `, ${profile.sender_role}`}
            </p>
          </div>
        )}
        {profile.sender_company && (
          <div>
            <p className="text-gray-500">Company</p>
            <p className="text-gray-900">{profile.sender_company}</p>
          </div>
        )}
      </div>
    </div>
  )
}

function ProfileForm({
  profile,
  onSubmit,
  onCancel,
  isLoading,
}: {
  profile?: BusinessProfile
  onSubmit: (data: Partial<BusinessProfile>) => void
  onCancel: () => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState({
    name: profile?.name || '',
    description: profile?.description || '',
    ideal_customer: profile?.ideal_customer || '',
    target_industries: profile?.target_industries || '',
    sender_name: profile?.sender_name || '',
    sender_role: profile?.sender_role || '',
    sender_company: profile?.sender_company || '',
    is_default: profile?.is_default || false,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <form onSubmit={handleSubmit} className="card space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Profile Name *
          </label>
          <input
            type="text"
            className="input"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <input
            type="text"
            className="input"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Ideal Customer Profile
        </label>
        <textarea
          className="input"
          rows={2}
          placeholder="Describe your ideal customer..."
          value={formData.ideal_customer}
          onChange={(e) => setFormData({ ...formData, ideal_customer: e.target.value })}
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Target Industries
        </label>
        <input
          type="text"
          className="input"
          placeholder="e.g., Technology, SaaS, E-commerce"
          value={formData.target_industries}
          onChange={(e) => setFormData({ ...formData, target_industries: e.target.value })}
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Sender Name
          </label>
          <input
            type="text"
            className="input"
            value={formData.sender_name}
            onChange={(e) => setFormData({ ...formData, sender_name: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Sender Role
          </label>
          <input
            type="text"
            className="input"
            value={formData.sender_role}
            onChange={(e) => setFormData({ ...formData, sender_role: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Sender Company
          </label>
          <input
            type="text"
            className="input"
            value={formData.sender_company}
            onChange={(e) => setFormData({ ...formData, sender_company: e.target.value })}
          />
        </div>
      </div>

      <div className="flex items-center">
        <input
          type="checkbox"
          id="is_default"
          checked={formData.is_default}
          onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
          className="rounded border-gray-300"
        />
        <label htmlFor="is_default" className="ml-2 text-sm text-gray-700">
          Set as default profile
        </label>
      </div>

      <div className="flex justify-end gap-2 pt-4 border-t">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          <X className="w-4 h-4 mr-1" />
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={isLoading}>
          {isLoading ? (
            <Loader2 className="w-4 h-4 mr-1 animate-spin" />
          ) : (
            <Check className="w-4 h-4 mr-1" />
          )}
          Save
        </button>
      </div>
    </form>
  )
}
