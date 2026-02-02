import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  MessageSquare,
  Send,
  Loader2,
  RefreshCw,
  User,
  Building2,
  Clock,
  Sparkles,
  ChevronRight,
  AlertCircle
} from 'lucide-react'
import {
  getLinkedInChats,
  getChatMessages,
  sendChatMessage,
  getLeads,
  generateConversationReply,
  type Lead,
} from '../services/api'

// Unipile API attendee structure
interface Attendee {
  display_name?: string
  first_name?: string
  last_name?: string
  provider_id?: string
  identifier?: string
}

// Unipile API chat structure
interface Chat {
  id: string
  object?: string
  account_id?: string
  provider_id?: string
  attendees?: Attendee[]
  // Alternative field names for the contact name
  name?: string
  display_name?: string
  // Time fields - Unipile can use different field names
  last_activity_at?: string
  last_message_at?: string
  timestamp?: string
  updated_at?: string
  unread_count?: number
}

// Unipile API message structure
interface Message {
  id: string
  text?: string
  body?: string
  content?: string
  sender?: string | { provider_id?: string; identifier?: string }
  sender_id?: string
  sender_provider_id?: string
  // Time fields
  timestamp?: string
  sent_at?: string
  created_at?: string
  date?: string
  // Outbound detection - Unipile uses is_sender as number (1=outbound, 0=inbound)
  is_sender?: number | boolean
  is_outbound?: boolean
  from_me?: boolean
}

function formatTime(dateString: string | undefined) {
  if (!dateString) return ''

  const date = new Date(dateString)

  // Check if the date is valid
  if (isNaN(date.getTime())) {
    // Try parsing as timestamp (seconds)
    const timestamp = parseInt(dateString)
    if (!isNaN(timestamp)) {
      const fromTimestamp = new Date(timestamp * 1000)
      if (!isNaN(fromTimestamp.getTime())) {
        return formatValidDate(fromTimestamp)
      }
    }
    return ''
  }

  return formatValidDate(date)
}

function formatValidDate(date: Date) {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

// Helper to extract chat name from Unipile response
function getChatName(chat: Chat): string {
  // Try direct name fields first
  if (chat.name) return chat.name
  if (chat.display_name) return chat.display_name

  // Try to get from attendees
  if (chat.attendees && chat.attendees.length > 0) {
    const attendee = chat.attendees[0]
    if (attendee.display_name) return attendee.display_name
    if (attendee.first_name && attendee.last_name) {
      return `${attendee.first_name} ${attendee.last_name}`
    }
    if (attendee.first_name) return attendee.first_name
    if (attendee.identifier) return attendee.identifier
    if (attendee.provider_id) return attendee.provider_id
  }

  return 'Unknown'
}

// Helper to get chat timestamp
function getChatTimestamp(chat: Chat): string | undefined {
  return chat.last_activity_at || chat.last_message_at || chat.timestamp || chat.updated_at
}

// Helper to get attendee provider_id
function getChatAttendeeProviderId(chat: Chat): string | undefined {
  if (chat.attendees && chat.attendees.length > 0) {
    return chat.attendees[0].provider_id || chat.attendees[0].identifier
  }
  return chat.provider_id
}

// Helper to extract message text
function getMessageText(msg: Message): string {
  return msg.text || msg.body || msg.content || ''
}

// Helper to get message timestamp
function getMessageTimestamp(msg: Message): string | undefined {
  return msg.timestamp || msg.sent_at || msg.created_at || msg.date
}

// Helper to check if message is outbound
// Unipile uses is_sender: 1 for outbound, 0 for inbound (as numbers, not booleans)
function isMessageOutbound(msg: Message): boolean {
  // Unipile uses is_sender as number: 1 = outbound, 0 = inbound
  if (typeof msg.is_sender === 'number') return msg.is_sender === 1
  if (typeof msg.is_sender === 'boolean') return msg.is_sender
  if (typeof msg.is_outbound === 'boolean') return msg.is_outbound
  if (typeof msg.from_me === 'boolean') return msg.from_me
  return false
}

export default function InboxPage() {
  const queryClient = useQueryClient()
  const [selectedChat, setSelectedChat] = useState<Chat | null>(null)
  const [messageText, setMessageText] = useState('')
  const [generatingReply, setGeneratingReply] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Fetch chats
  const { data: chatsData, isLoading: chatsLoading, error: chatsError } = useQuery({
    queryKey: ['linkedin-chats'],
    queryFn: () => getLinkedInChats(50),
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  // Fetch messages for selected chat
  const { data: messagesData, isLoading: messagesLoading } = useQuery({
    queryKey: ['chat-messages', selectedChat?.id],
    queryFn: () => getChatMessages(selectedChat!.id, 50),
    enabled: !!selectedChat,
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  // Fetch leads to match with chats
  const { data: leadsData } = useQuery({
    queryKey: ['leads-for-inbox'],
    queryFn: () => getLeads(1, 200),
  })

  // Send message mutation
  const sendMutation = useMutation({
    mutationFn: ({ chatId, text }: { chatId: string; text: string }) =>
      sendChatMessage(chatId, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat-messages', selectedChat?.id] })
      setMessageText('')
    },
  })

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messagesData])

  // Find lead associated with chat
  const findLeadForChat = (chat: Chat): Lead | undefined => {
    if (!leadsData?.leads) return undefined
    const attendeeProviderId = getChatAttendeeProviderId(chat)
    const chatName = getChatName(chat)

    // Try to match by provider ID or name
    return leadsData.leads.find(lead =>
      (attendeeProviderId && lead.linkedin_provider_id === attendeeProviderId) ||
      (lead.first_name && chatName.includes(lead.first_name))
    )
  }

  const handleSendMessage = () => {
    if (!selectedChat || !messageText.trim()) return
    sendMutation.mutate({ chatId: selectedChat.id, text: messageText.trim() })
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const chats = chatsData?.data?.items || chatsData?.data || []
  const messages = messagesData?.data?.items || messagesData?.data || []

  // Sort messages by time
  const sortedMessages = [...messages].sort((a: Message, b: Message) => {
    const timeA = getMessageTimestamp(a)
    const timeB = getMessageTimestamp(b)
    if (!timeA || !timeB) return 0
    return new Date(timeA).getTime() - new Date(timeB).getTime()
  })

  if (chatsError) {
    return (
      <div className="flex flex-col items-center justify-center h-96">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Unable to load chats</h2>
        <p className="text-gray-500 mb-4">
          There was an error connecting to LinkedIn. Please check your Unipile connection.
        </p>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ['linkedin-chats'] })}
          className="btn btn-primary"
        >
          Try Again
        </button>
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-8rem)]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Inbox</h1>
          <p className="text-gray-500">LinkedIn conversations</p>
        </div>
        <button
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['linkedin-chats'] })
            queryClient.invalidateQueries({ queryKey: ['chat-messages'] })
          }}
          className="btn btn-secondary flex items-center"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>

      <div className="flex h-[calc(100%-4rem)] bg-white rounded-xl border overflow-hidden">
        {/* Chat List */}
        <div className="w-80 border-r flex flex-col">
          <div className="p-4 border-b">
            <h2 className="font-semibold text-gray-900">Conversations</h2>
            <p className="text-xs text-gray-500">{chats.length} chats</p>
          </div>

          {chatsLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            </div>
          ) : chats.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-4 text-center">
              <MessageSquare className="w-12 h-12 text-gray-300 mb-3" />
              <p className="text-gray-500">No conversations yet</p>
              <p className="text-xs text-gray-400 mt-1">
                Conversations will appear after connections accept your invitations
              </p>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto">
              {chats.map((chat: Chat) => {
                const lead = findLeadForChat(chat)
                const isSelected = selectedChat?.id === chat.id

                return (
                  <button
                    key={chat.id}
                    onClick={() => setSelectedChat(chat)}
                    className={`w-full p-4 text-left border-b hover:bg-gray-50 transition-colors ${
                      isSelected ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                        <User className="w-5 h-5 text-gray-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <p className="font-medium text-gray-900 truncate">
                            {getChatName(chat) || lead?.first_name || 'Unknown'}
                          </p>
                          {chat.unread_count ? (
                            <span className="w-5 h-5 bg-blue-500 text-white text-xs rounded-full flex items-center justify-center">
                              {chat.unread_count}
                            </span>
                          ) : null}
                        </div>
                        {lead && (
                          <p className="text-xs text-gray-500 truncate flex items-center mt-0.5">
                            <Building2 className="w-3 h-3 mr-1" />
                            {lead.company_name}
                          </p>
                        )}
                        {getChatTimestamp(chat) && (
                          <p className="text-xs text-gray-400 mt-1 flex items-center">
                            <Clock className="w-3 h-3 mr-1" />
                            {formatTime(getChatTimestamp(chat))}
                          </p>
                        )}
                      </div>
                      <ChevronRight className={`w-4 h-4 text-gray-400 ${isSelected ? 'text-blue-500' : ''}`} />
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Chat Window */}
        <div className="flex-1 flex flex-col">
          {selectedChat ? (
            <>
              {/* Chat Header */}
              <div className="p-4 border-b flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center">
                    <User className="w-5 h-5 text-gray-500" />
                  </div>
                  <div>
                    <p className="font-semibold text-gray-900">
                      {getChatName(selectedChat) || findLeadForChat(selectedChat)?.first_name || 'Unknown'}
                    </p>
                    {findLeadForChat(selectedChat) && (
                      <p className="text-sm text-gray-500">
                        {findLeadForChat(selectedChat)?.job_title} at {findLeadForChat(selectedChat)?.company_name}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messagesLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                  </div>
                ) : sortedMessages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-gray-400">
                    <MessageSquare className="w-12 h-12 mb-3" />
                    <p>No messages yet</p>
                    <p className="text-sm">Start the conversation!</p>
                  </div>
                ) : (
                  sortedMessages.map((msg: Message) => {
                    const isOutbound = isMessageOutbound(msg)
                    return (
                      <div
                        key={msg.id}
                        className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[70%] rounded-lg px-4 py-2 ${
                            isOutbound
                              ? 'bg-blue-500 text-white'
                              : 'bg-gray-100 text-gray-900'
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{getMessageText(msg)}</p>
                          <p className={`text-xs mt-1 ${
                            isOutbound ? 'text-blue-200' : 'text-gray-400'
                          }`}>
                            {formatTime(getMessageTimestamp(msg))}
                          </p>
                        </div>
                      </div>
                    )
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Message Input */}
              <div className="p-4 border-t">
                <div className="flex gap-2">
                  <button
                    onClick={async () => {
                      if (!selectedChat || sortedMessages.length === 0) return

                      setGeneratingReply(true)
                      try {
                        // Format conversation history
                        const chatName = getChatName(selectedChat)
                        const lead = findLeadForChat(selectedChat)

                        let conversationHistory = ''
                        for (const msg of sortedMessages) {
                          const sender = isMessageOutbound(msg) ? 'Yo (Pablo)' : chatName
                          const text = getMessageText(msg)
                          conversationHistory += `${sender}: ${text}\n\n`
                        }

                        const response = await generateConversationReply({
                          conversation_history: conversationHistory.trim(),
                          contact_name: chatName,
                          contact_job_title: lead?.job_title || undefined,
                          contact_company: lead?.company_name || undefined
                        })

                        if (response.reply) {
                          setMessageText(response.reply)
                        }
                      } catch (error) {
                        console.error('Failed to generate reply:', error)
                      } finally {
                        setGeneratingReply(false)
                      }
                    }}
                    disabled={generatingReply || sortedMessages.length === 0}
                    className="btn btn-secondary flex items-center"
                    title="Generate AI reply with conversation context"
                  >
                    {generatingReply ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Sparkles className="w-4 h-4" />
                    )}
                  </button>
                  <textarea
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Type a message..."
                    className="flex-1 input resize-none"
                    rows={2}
                  />
                  <button
                    onClick={handleSendMessage}
                    disabled={!messageText.trim() || sendMutation.isPending}
                    className="btn btn-primary flex items-center"
                  >
                    {sendMutation.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                  </button>
                </div>
                {sendMutation.isError && (
                  <p className="text-red-500 text-sm mt-2">
                    Failed to send message. Please try again.
                  </p>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
              <MessageSquare className="w-16 h-16 mb-4" />
              <p className="text-lg">Select a conversation</p>
              <p className="text-sm">Choose a chat from the list to view messages</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
