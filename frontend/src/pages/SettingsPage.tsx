import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Edit2, Check, X, Loader2 } from 'lucide-react'
import {
  getBusinessProfiles,
  createBusinessProfile,
  updateBusinessProfile,
  type BusinessProfile,
} from '../services/api'

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
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
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
