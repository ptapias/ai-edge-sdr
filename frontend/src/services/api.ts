import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types
export interface Lead {
  id: string
  first_name: string | null
  last_name: string | null
  full_name: string | null
  email: string | null
  email_verified: boolean
  email_status: string | null
  job_title: string | null
  headline: string | null
  company_name: string | null
  company_size: number | null
  company_industry: string | null
  country: string | null
  linkedin_url: string | null
  linkedin_provider_id: string | null
  linkedin_chat_id: string | null
  score: number | null
  score_label: string | null
  score_reason: string | null
  status: string
  linkedin_message: string | null
  email_message: string | null
  notes: string | null
  campaign_id: string | null
  connection_sent_at: string | null
  connected_at: string | null
  last_message_at: string | null
  created_at: string
  updated_at: string
}

export interface LeadStatus {
  value: string
  label: string
  color: string
  order: number
}

export type LeadStatusValue =
  | 'new'
  | 'pending'
  | 'invitation_sent'
  | 'connected'
  | 'in_conversation'
  | 'meeting_scheduled'
  | 'qualified'
  | 'disqualified'
  | 'closed_won'
  | 'closed_lost'

export interface Campaign {
  id: string
  name: string
  description: string | null
  search_query: string | null
  total_leads: number
  verified_leads: number
  contacted_leads: number
  created_at: string
  updated_at: string
}

export interface BusinessProfile {
  id: string
  name: string
  description: string | null
  ideal_customer: string | null
  target_industries: string | null
  sender_name: string | null
  sender_role: string | null
  sender_company: string | null
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface SearchFilters {
  contact_job_title: string[] | null
  contact_seniority: string[] | null
  contact_location: string[] | null
  company_industry: string[] | null
  company_size: string[] | null
  company_location: string[] | null
  fetch_count: number
}

export interface SearchPreview {
  filters: SearchFilters
  interpretation: string
  confidence: number
}

export interface LeadListResponse {
  total: number
  page: number
  page_size: number
  leads: Lead[]
}

export interface GlobalStats {
  leads: {
    total: number
    verified: number
    hot: number
    contacted: number
  }
  campaigns: number
  business_profiles: number
}

// API functions
export const searchLeads = async (query: string, maxResults = 50) => {
  const response = await api.post('/search/', { query, max_results: maxResults })
  return response.data
}

export const previewSearch = async (query: string): Promise<SearchPreview> => {
  const response = await api.post('/search/preview', { query })
  return response.data
}

export const getLeads = async (
  page = 1,
  pageSize = 50,
  filters?: { campaign_id?: string; status?: string; score_label?: string }
): Promise<LeadListResponse> => {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (filters?.campaign_id) params.append('campaign_id', filters.campaign_id)
  if (filters?.status) params.append('status', filters.status)
  if (filters?.score_label) params.append('score_label', filters.score_label)

  const response = await api.get(`/leads/?${params}`)
  return response.data
}

export const getLead = async (id: string): Promise<Lead> => {
  const response = await api.get(`/leads/${id}`)
  return response.data
}

export const verifyEmails = async (leadIds: string[]) => {
  const response = await api.post('/leads/verify', leadIds)
  return response.data
}

export const qualifyLeads = async (leadIds: string[], businessId?: string) => {
  const params = businessId ? `?business_id=${businessId}` : ''
  const response = await api.post(`/leads/qualify${params}`, leadIds)
  return response.data
}

export const generateLinkedInMessage = async (leadId: string, businessId?: string) => {
  const params = businessId ? `?business_id=${businessId}` : ''
  const response = await api.post(`/leads/${leadId}/message/linkedin${params}`)
  return response.data
}

export const generateEmailMessage = async (leadId: string, businessId?: string) => {
  const params = businessId ? `?business_id=${businessId}` : ''
  const response = await api.post(`/leads/${leadId}/message/email${params}`)
  return response.data
}

export const sendLinkedInConnection = async (leadId: string) => {
  const response = await api.post(`/leads/${leadId}/action/linkedin`)
  return response.data
}

export const getLeadStatuses = async (): Promise<LeadStatus[]> => {
  const response = await api.get('/leads/statuses')
  return response.data
}

export const updateLeadStatus = async (leadId: string, status: LeadStatusValue, notes?: string): Promise<Lead> => {
  const response = await api.patch(`/leads/${leadId}/status`, { status, notes })
  return response.data
}

export const bulkUpdateLeadStatus = async (leadIds: string[], status: LeadStatusValue) => {
  const response = await api.post('/leads/status/bulk', { lead_ids: leadIds, status })
  return response.data
}

export const updateLeadNotes = async (leadId: string, notes: string): Promise<Lead> => {
  const response = await api.patch(`/leads/${leadId}/notes`, { notes })
  return response.data
}

// LinkedIn / Unipile endpoints
export interface LinkedInConnectionStatus {
  success: boolean
  connected: boolean
  data?: {
    id: string
    provider: string
    status: string
  }
  error?: string
}

export interface SendInvitationResult {
  lead_id: string
  lead_name: string
  success: boolean
  error?: string
  data?: unknown
}

export interface BulkInvitationResult {
  total: number
  successful: number
  failed: number
  results: SendInvitationResult[]
}

export const checkLinkedInConnection = async (): Promise<LinkedInConnectionStatus> => {
  const response = await api.get('/linkedin/status')
  return response.data
}

export const sendLinkedInInvitation = async (leadId: string, message?: string): Promise<SendInvitationResult> => {
  const response = await api.post('/linkedin/send-invitation', { lead_id: leadId, message })
  return response.data
}

export const sendBulkInvitations = async (leadIds: string[]): Promise<BulkInvitationResult> => {
  const response = await api.post('/linkedin/send-invitations/bulk', { lead_ids: leadIds })
  return response.data
}

export interface CacheInfo {
  cached: boolean
  is_fresh?: boolean
  expires_in_seconds: number
  last_api_call: string | null
}

export interface ChatsResponse {
  success: boolean
  data: {
    items: unknown[]
  }
  from_cache?: boolean
  cache_info?: CacheInfo
}

export interface ConversationAnalysis {
  level: 'hot' | 'warm' | 'cold'
  reason: string
  next_action: string
}

export const getLinkedInChats = async (limit = 50, forceRefresh = false): Promise<ChatsResponse> => {
  const response = await api.get('/linkedin/chats', {
    params: { limit, force_refresh: forceRefresh }
  })
  return response.data
}

export const getChatMessages = async (chatId: string, limit = 50, forceRefresh = false) => {
  const response = await api.get(`/linkedin/chats/${chatId}/messages`, {
    params: { limit, force_refresh: forceRefresh }
  })
  return response.data
}

export const getLinkedInCacheStatus = async () => {
  const response = await api.get('/linkedin/cache-status')
  return response.data
}

export const analyzeConversation = async (conversationHistory: string): Promise<ConversationAnalysis> => {
  const response = await api.post('/linkedin/analyze-conversation', {
    conversation_history: conversationHistory
  })
  return response.data
}

export const sendChatMessage = async (chatId: string, text: string) => {
  const response = await api.post(`/linkedin/chats/${chatId}/send`, null, { params: { text } })
  return response.data
}

export interface GenerateReplyRequest {
  conversation_history: string
  contact_name: string
  contact_job_title?: string
  contact_company?: string
}

export const generateConversationReply = async (request: GenerateReplyRequest) => {
  const response = await api.post('/linkedin/generate-reply', request)
  return response.data
}

// Automation endpoints
export interface AutomationSettings {
  id: string
  enabled: boolean
  work_start_hour: number
  work_start_minute: number
  work_end_hour: number
  work_end_minute: number
  working_days: number
  daily_limit: number
  min_delay_seconds: number
  max_delay_seconds: number
  min_lead_score: number
  target_statuses: string
  target_campaign_id: string | null
  invitations_sent_today: number
  last_invitation_at: string | null
  last_reset_date: string | null
  created_at: string
  updated_at: string
}

export interface AutomationStatus {
  enabled: boolean
  is_working_hour: boolean
  can_send: boolean
  invitations_sent_today: number
  daily_limit: number
  remaining_today: number
  next_invitation_in_seconds: number | null
}

export interface InvitationStats {
  today: number
  this_week: number
  this_month: number
  total: number
  success_rate: number
  by_day: Array<{ date: string; count: number; successful: number }>
}

export interface InvitationLog {
  id: string
  lead_id: string
  lead_name: string | null
  lead_company: string | null
  lead_job_title: string | null
  lead_linkedin_url: string | null
  message_preview: string | null
  campaign_id: string | null
  campaign_name: string | null
  success: boolean
  error_message: string | null
  sent_at: string
  mode: string
}

export interface QueueLead {
  lead_id: string
  lead_name: string
  job_title: string | null
  company: string | null
  linkedin_url: string | null
  message_preview: string | null
  score: number | null
  score_label: string | null
  campaign_id: string | null
  campaign_name: string | null
}

export interface InvitationQueue {
  total_eligible: number
  queue: QueueLead[]
  settings: {
    target_campaign_id: string | null
    min_lead_score: number
    target_statuses: string[]
  }
}

export const getAutomationSettings = async (): Promise<AutomationSettings> => {
  const response = await api.get('/automation/settings')
  return response.data
}

export const updateAutomationSettings = async (settings: Partial<AutomationSettings>): Promise<AutomationSettings> => {
  const response = await api.patch('/automation/settings', settings)
  return response.data
}

export const toggleAutomation = async (enabled: boolean): Promise<AutomationSettings> => {
  const response = await api.post('/automation/toggle', null, { params: { enabled } })
  return response.data
}

export const getAutomationStatus = async (): Promise<AutomationStatus> => {
  const response = await api.get('/automation/status')
  return response.data
}

export const sendNextInvitation = async () => {
  const response = await api.post('/automation/send-next')
  return response.data
}

export const getInvitationLogs = async (limit = 50, mode?: string, success?: boolean): Promise<InvitationLog[]> => {
  const params: Record<string, unknown> = { limit }
  if (mode) params.mode = mode
  if (success !== undefined) params.success = success
  const response = await api.get('/automation/logs', { params })
  return response.data
}

export const getInvitationStats = async (): Promise<InvitationStats> => {
  const response = await api.get('/automation/stats')
  return response.data
}

export const generatePendingMessages = async (limit = 10) => {
  const response = await api.post('/automation/generate-messages', null, { params: { limit } })
  return response.data
}

export const getInvitationQueue = async (limit = 10): Promise<InvitationQueue> => {
  const response = await api.get('/automation/queue', { params: { limit } })
  return response.data
}

export const getCampaigns = async (): Promise<Campaign[]> => {
  const response = await api.get('/campaigns/')
  return response.data
}

export const getCampaign = async (id: string): Promise<Campaign> => {
  const response = await api.get(`/campaigns/${id}`)
  return response.data
}

export const getCampaignStats = async (id: string) => {
  const response = await api.get(`/campaigns/${id}/stats`)
  return response.data
}

export const getBusinessProfiles = async (): Promise<BusinessProfile[]> => {
  const response = await api.get('/business-profiles/')
  return response.data
}

export const createBusinessProfile = async (profile: Partial<BusinessProfile>) => {
  const response = await api.post('/business-profiles/', profile)
  return response.data
}

export const updateBusinessProfile = async (id: string, profile: Partial<BusinessProfile>) => {
  const response = await api.patch(`/business-profiles/${id}`, profile)
  return response.data
}

export const getGlobalStats = async (): Promise<GlobalStats> => {
  const response = await api.get('/stats')
  return response.data
}

export default api
