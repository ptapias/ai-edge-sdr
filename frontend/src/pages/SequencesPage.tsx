import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  GitBranch,
  Plus,
  Loader2,
  Play,
  Pause,
  Archive,
  Trash2,
  Users,
  MessageCircle,
  CheckCircle2,
  ChevronRight,
  Settings2,
  UserPlus
} from 'lucide-react'
import {
  getSequences,
  getSequence,
  createSequence,
  deleteSequence,
  updateSequenceStatus,
  getBusinessProfiles,
} from '../services/api'
import type { SequenceListItem, Sequence, BusinessProfile, SequenceCreateData } from '../services/api'
import SequenceBuilder from '../components/sequences/SequenceBuilder'
import EnrollLeadsModal from '../components/sequences/EnrollLeadsModal'
import EnrollmentTable from '../components/sequences/EnrollmentTable'
import SequenceStats from '../components/sequences/SequenceStats'

type DetailTab = 'steps' | 'enrolled' | 'stats'

const statusColors: Record<string, { bg: string; text: string; dot: string }> = {
  draft: { bg: 'bg-gray-100', text: 'text-gray-700', dot: 'bg-gray-400' },
  active: { bg: 'bg-green-100', text: 'text-green-700', dot: 'bg-green-500' },
  paused: { bg: 'bg-yellow-100', text: 'text-yellow-700', dot: 'bg-yellow-500' },
  archived: { bg: 'bg-gray-100', text: 'text-gray-500', dot: 'bg-gray-400' },
}

export default function SequencesPage() {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<DetailTab>('steps')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEnrollModal, setShowEnrollModal] = useState(false)

  // Fetch sequences list
  const { data: sequences, isLoading: listLoading } = useQuery({
    queryKey: ['sequences'],
    queryFn: () => getSequences(),
  })

  // Fetch selected sequence detail
  const { data: selectedSequence, isLoading: detailLoading } = useQuery({
    queryKey: ['sequence', selectedId],
    queryFn: () => getSequence(selectedId!),
    enabled: !!selectedId,
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteSequence,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sequences'] })
      setSelectedId(null)
    },
  })

  // Status mutation
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateSequenceStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sequences'] })
      queryClient.invalidateQueries({ queryKey: ['sequence', selectedId] })
    },
  })

  const handleDelete = (id: string) => {
    if (confirm('Delete this sequence? This cannot be undone.')) {
      deleteMutation.mutate(id)
    }
  }

  const handleStatusChange = (id: string, status: string) => {
    statusMutation.mutate({ id, status })
  }

  return (
    <div className="h-[calc(100vh-8rem)]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Sequences</h1>
          <p className="text-gray-500">Automated LinkedIn outreach workflows</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          New Sequence
        </button>
      </div>

      <div className="flex h-[calc(100%-4rem)] bg-white rounded-xl border overflow-hidden">
        {/* Sequence List (Left Panel) */}
        <div className="w-80 border-r flex flex-col">
          <div className="p-4 border-b">
            <h2 className="font-semibold text-gray-900">Sequences</h2>
            <p className="text-xs text-gray-500">{sequences?.length || 0} sequences</p>
          </div>

          {listLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            </div>
          ) : !sequences || sequences.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-4 text-center">
              <GitBranch className="w-12 h-12 text-gray-300 mb-3" />
              <p className="text-gray-500 text-sm">No sequences yet</p>
              <p className="text-xs text-gray-400 mt-1">
                Create a sequence to automate your outreach
              </p>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto">
              {sequences.map((seq: SequenceListItem) => {
                const isSelected = selectedId === seq.id
                const colors = statusColors[seq.status] || statusColors.draft

                return (
                  <button
                    key={seq.id}
                    onClick={() => { setSelectedId(seq.id); setActiveTab('steps') }}
                    className={`w-full p-4 text-left border-b hover:bg-gray-50 transition-colors ${
                      isSelected ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-gray-900 truncate">{seq.name}</p>
                          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs ${colors.bg} ${colors.text}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />
                            {seq.status}
                          </span>
                        </div>
                        {seq.description && (
                          <p className="text-xs text-gray-500 truncate mt-0.5">{seq.description}</p>
                        )}
                        <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                          <span className="flex items-center gap-1">
                            <GitBranch className="w-3 h-3" />
                            {seq.steps_count} steps
                          </span>
                          <span className="flex items-center gap-1">
                            <Users className="w-3 h-3" />
                            {seq.active_enrolled} active
                          </span>
                          {seq.replied_count > 0 && (
                            <span className="flex items-center gap-1 text-orange-500">
                              <MessageCircle className="w-3 h-3" />
                              {seq.replied_count}
                            </span>
                          )}
                        </div>
                      </div>
                      <ChevronRight className={`w-4 h-4 flex-shrink-0 mt-0.5 ${isSelected ? 'text-blue-500' : 'text-gray-400'}`} />
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Detail Panel (Right) */}
        <div className="flex-1 flex flex-col">
          {selectedId && selectedSequence ? (
            <>
              {/* Detail Header */}
              <div className="p-4 border-b flex items-center justify-between flex-shrink-0">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-gray-900">{selectedSequence.name}</h3>
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${
                      statusColors[selectedSequence.status]?.bg || 'bg-gray-100'
                    } ${statusColors[selectedSequence.status]?.text || 'text-gray-700'}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${statusColors[selectedSequence.status]?.dot || 'bg-gray-400'}`} />
                      {selectedSequence.status}
                    </span>
                  </div>
                  {selectedSequence.description && (
                    <p className="text-sm text-gray-500 mt-0.5">{selectedSequence.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {/* Status actions */}
                  {selectedSequence.status === 'draft' && selectedSequence.steps.length > 0 && (
                    <button
                      onClick={() => handleStatusChange(selectedSequence.id, 'active')}
                      disabled={statusMutation.isPending}
                      className="btn btn-primary text-sm flex items-center gap-1.5"
                    >
                      <Play className="w-3.5 h-3.5" />
                      Activate
                    </button>
                  )}
                  {selectedSequence.status === 'active' && (
                    <button
                      onClick={() => handleStatusChange(selectedSequence.id, 'paused')}
                      disabled={statusMutation.isPending}
                      className="btn btn-secondary text-sm flex items-center gap-1.5"
                    >
                      <Pause className="w-3.5 h-3.5" />
                      Pause
                    </button>
                  )}
                  {selectedSequence.status === 'paused' && (
                    <button
                      onClick={() => handleStatusChange(selectedSequence.id, 'active')}
                      disabled={statusMutation.isPending}
                      className="btn btn-primary text-sm flex items-center gap-1.5"
                    >
                      <Play className="w-3.5 h-3.5" />
                      Resume
                    </button>
                  )}
                  {(selectedSequence.status === 'draft' || selectedSequence.status === 'paused') && (
                    <button
                      onClick={() => handleStatusChange(selectedSequence.id, 'archived')}
                      disabled={statusMutation.isPending}
                      className="btn btn-secondary text-sm flex items-center gap-1.5 text-gray-500"
                    >
                      <Archive className="w-3.5 h-3.5" />
                      Archive
                    </button>
                  )}

                  {/* Enroll leads */}
                  {(selectedSequence.status === 'active' || selectedSequence.status === 'draft') && (
                    <button
                      onClick={() => setShowEnrollModal(true)}
                      className="btn btn-secondary text-sm flex items-center gap-1.5"
                    >
                      <UserPlus className="w-3.5 h-3.5" />
                      Enroll Leads
                    </button>
                  )}

                  {/* Delete - only drafts with no enrollments */}
                  {selectedSequence.status === 'draft' && selectedSequence.total_enrolled === 0 && (
                    <button
                      onClick={() => handleDelete(selectedSequence.id)}
                      disabled={deleteMutation.isPending}
                      className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                      title="Delete sequence"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>

              {/* Tabs */}
              <div className="border-b flex-shrink-0">
                <div className="flex">
                  <TabButton
                    label="Steps"
                    icon={Settings2}
                    active={activeTab === 'steps'}
                    count={selectedSequence.steps.length}
                    onClick={() => setActiveTab('steps')}
                  />
                  <TabButton
                    label="Enrolled Leads"
                    icon={Users}
                    active={activeTab === 'enrolled'}
                    count={selectedSequence.active_enrolled}
                    onClick={() => setActiveTab('enrolled')}
                  />
                  <TabButton
                    label="Stats"
                    icon={CheckCircle2}
                    active={activeTab === 'stats'}
                    onClick={() => setActiveTab('stats')}
                  />
                </div>
              </div>

              {/* Tab content */}
              <div className="flex-1 overflow-y-auto p-4">
                {detailLoading ? (
                  <div className="flex items-center justify-center h-40">
                    <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                  </div>
                ) : (
                  <>
                    {activeTab === 'steps' && (
                      <SequenceBuilder sequence={selectedSequence} />
                    )}
                    {activeTab === 'enrolled' && (
                      <EnrollmentTable
                        sequenceId={selectedSequence.id}
                        isActive={selectedSequence.status === 'active'}
                      />
                    )}
                    {activeTab === 'stats' && (
                      <SequenceStats sequenceId={selectedSequence.id} />
                    )}
                  </>
                )}
              </div>
            </>
          ) : detailLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
              <GitBranch className="w-16 h-16 mb-4" />
              <p className="text-lg">Select a sequence</p>
              <p className="text-sm">Choose a sequence from the list or create a new one</p>
            </div>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateSequenceModal
          onClose={() => setShowCreateModal(false)}
          onCreated={(id) => {
            setSelectedId(id)
            setShowCreateModal(false)
          }}
        />
      )}

      {/* Enroll Modal */}
      {showEnrollModal && selectedSequence && (
        <EnrollLeadsModal
          sequenceId={selectedSequence.id}
          sequenceName={selectedSequence.name}
          onClose={() => setShowEnrollModal(false)}
        />
      )}
    </div>
  )
}

// Tab button component
function TabButton({
  label,
  icon: Icon,
  active,
  count,
  onClick,
}: {
  label: string
  icon: typeof Settings2
  active: boolean
  count?: number
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
        active
          ? 'border-blue-500 text-blue-600'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
      }`}
    >
      <Icon className="w-4 h-4" />
      {label}
      {count !== undefined && count > 0 && (
        <span className={`ml-1 px-1.5 py-0.5 rounded-full text-xs ${
          active ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
        }`}>
          {count}
        </span>
      )}
    </button>
  )
}

// Create Sequence Modal
function CreateSequenceModal({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: (id: string) => void
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [businessId, setBusinessId] = useState('')
  const [strategy, setStrategy] = useState('hybrid')

  const { data: profiles } = useQuery({
    queryKey: ['business-profiles'],
    queryFn: getBusinessProfiles,
  })

  const createMutation = useMutation({
    mutationFn: (data: SequenceCreateData) => createSequence(data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['sequences'] })
      onCreated(result.id)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    createMutation.mutate({
      name: name.trim(),
      description: description.trim() || undefined,
      business_id: businessId || undefined,
      message_strategy: strategy,
    })
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full">
        <div className="p-4 border-b">
          <h3 className="text-lg font-semibold text-gray-900">New Sequence</h3>
          <p className="text-sm text-gray-500">Create an automated outreach workflow</p>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Newsletter Sponsorship Outreach"
              className="input"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Briefly describe this sequence..."
              className="input resize-none h-20"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Business Profile</label>
            <select
              value={businessId}
              onChange={(e) => setBusinessId(e.target.value)}
              className="input"
            >
              <option value="">Select profile (for AI context)</option>
              {profiles?.map((p: BusinessProfile) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Message Strategy</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="input"
            >
              <option value="hybrid">Hybrid (balanced approach)</option>
              <option value="direct">Direct (straight to the point)</option>
              <option value="gradual">Gradual (build relationship first)</option>
            </select>
            <p className="text-xs text-gray-400 mt-1">
              Determines the AI's tone for generating messages
            </p>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || createMutation.isPending}
              className="btn btn-primary flex items-center gap-2"
            >
              {createMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              Create Sequence
            </button>
          </div>

          {createMutation.isError && (
            <p className="text-red-500 text-sm">
              Failed to create sequence. Please try again.
            </p>
          )}
        </form>
      </div>
    </div>
  )
}
