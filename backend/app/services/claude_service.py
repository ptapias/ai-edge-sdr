"""
Claude AI service for NL processing, lead scoring, and message generation.
"""
import json
import logging
from typing import Dict, Any, Optional

from anthropic import Anthropic

from ..config import get_settings
from ..schemas.search import ApifyFilters, NLToFiltersResponse
from ..schemas.lead import LeadScoring

logger = logging.getLogger(__name__)
settings = get_settings()


class ClaudeService:
    """Service for Claude AI interactions."""

    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"

    def natural_language_to_filters(self, query: str) -> NLToFiltersResponse:
        """
        Convert natural language query to Apify filters.

        Args:
            query: Natural language search query (e.g., "CEOs tech Spain 50 employees")

        Returns:
            NLToFiltersResponse with structured filters
        """
        system_prompt = """You are a lead search query parser. Convert natural language queries into structured filters for LinkedIn lead search.

Output JSON with these fields (use null if not mentioned):
- contact_job_title: array of job titles (e.g., ["CEO", "CTO", "Founder"])
- contact_seniority: array of seniority levels (e.g., ["Director", "VP", "C-Level"])
- contact_location: array of locations for the person
- company_industry: array of industries - MUST use ONLY these exact values: "information technology & services", "computer software", "internet", "computer hardware", "computer networking", "computer & network security", "computer games", "semiconductors", "telecommunications", "wireless", "e-learning", "online media", "marketing & advertising", "management consulting", "financial services", "banking", "investment management", "investment banking", "venture capital & private equity", "capital markets", "insurance", "accounting", "real estate", "commercial real estate", "construction", "architecture & planning", "civil engineering", "mechanical or industrial engineering", "electrical/electronic manufacturing", "industrial automation", "machinery", "building materials", "retail", "wholesale", "consumer goods", "consumer electronics", "consumer services", "apparel & fashion", "luxury goods & jewelry", "cosmetics", "food & beverages", "food production", "restaurants", "hospitality", "leisure, travel & tourism", "airlines/aviation", "aviation & aerospace", "automotive", "transportation/trucking/railroad", "logistics & supply chain", "warehousing", "package/freight delivery", "maritime", "railroad manufacture", "shipbuilding", "health, wellness & fitness", "hospital & health care", "medical practice", "medical devices", "pharmaceuticals", "biotechnology", "mental health care", "veterinary", "alternative medicine", "education management", "higher education", "primary/secondary education", "professional training & coaching", "research", "human resources", "staffing & recruiting", "legal services", "law practice", "law enforcement", "judiciary", "government administration", "government relations", "public policy", "public safety", "military", "defense & space", "international affairs", "nonprofit organization management", "civic & social organization", "philanthropy", "fund-raising", "religious institutions", "entertainment", "media production", "broadcast media", "motion pictures & film", "music", "performing arts", "animation", "sports", "recreational facilities & services", "sporting goods", "gambling & casinos", "arts & crafts", "fine art", "photography", "graphic design", "design", "publishing", "newspapers", "writing & editing", "translation & localization", "printing", "libraries", "museums & institutions", "oil & energy", "mining & metals", "chemicals", "plastics", "utilities", "renewables & environment", "environmental services", "paper & forest products", "agriculture", "farming", "ranching", "dairy", "fishery", "wine & spirits", "tobacco", "nanotechnology", "outsourcing/offshoring", "events services", "facilities services", "security & investigations", "business supplies & equipment", "packaging & containers", "market research", "public relations & communications", "program development", "executive office", "individual & family services", "think tanks", "political organization", "international trade & development", "alternative dispute resolution", "supermarkets", "textiles", "glass, ceramics & concrete", "furniture", "information services"
- company_size: array of size ranges - use ONLY: "1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+"
- company_location: array of company locations
- interpretation: brief explanation of how you understood the query
- confidence: 0-1 confidence score

IMPORTANT MAPPINGS:
- "tech" or "technology" → ["computer software", "information technology & services", "internet"]
- "SaaS" or "software" → ["computer software", "internet"]
- "AI" or "artificial intelligence" → ["computer software", "information technology & services"]
- "startups" → use small company sizes like "11-50", "51-200"
- "enterprise" → use large sizes like "1001-5000", "5001-10000", "10001+"

Spanish country names should be translated (España → Spain).
Use lowercase for all industry values exactly as shown above."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Parse this lead search query: {query}"}
            ]
        )

        # Parse the response
        response_text = message.content[0].text

        try:
            # Try to extract JSON from response
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text

            data = json.loads(json_str.strip())

            filters = ApifyFilters(
                contact_job_title=data.get("contact_job_title"),
                contact_seniority=data.get("contact_seniority"),
                contact_location=data.get("contact_location"),
                company_industry=data.get("company_industry"),
                company_size=data.get("company_size"),
                company_location=data.get("company_location"),
            )

            return NLToFiltersResponse(
                filters=filters,
                interpretation=data.get("interpretation", "Query parsed successfully"),
                confidence=data.get("confidence", 0.8)
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            # Return basic filters if parsing fails
            return NLToFiltersResponse(
                filters=ApifyFilters(),
                interpretation=f"Could not fully parse query, using defaults. Raw: {response_text[:200]}",
                confidence=0.3
            )

    def score_lead(
        self,
        lead_data: Dict[str, Any],
        business_context: Optional[Dict[str, Any]] = None
    ) -> LeadScoring:
        """
        Score a lead based on fit with business profile.

        Args:
            lead_data: Lead information dictionary
            business_context: Business profile for scoring context

        Returns:
            LeadScoring with score, label, and reason
        """
        context = business_context or {}

        system_prompt = """You are a B2B lead scoring expert. Score leads based on how well they match the ideal customer profile.

Score 0-100:
- 80-100 (hot): Excellent fit, high decision-making power, right company size/industry
- 50-79 (warm): Good potential, some matching criteria, worth pursuing
- 0-49 (cold): Poor fit, wrong industry/size, low priority

Output JSON:
{
  "score": number (0-100),
  "label": "hot" | "warm" | "cold",
  "reason": "Brief explanation (2-3 sentences max)"
}

Consider:
- Job title and seniority (decision maker?)
- Company size (matches target?)
- Industry relevance
- Location match
- Company description alignment"""

        user_content = f"""Score this lead:

Lead:
- Name: {lead_data.get('first_name', '')} {lead_data.get('last_name', '')}
- Job Title: {lead_data.get('job_title', 'Unknown')}
- Seniority: {lead_data.get('seniority_level', 'Unknown')}
- Company: {lead_data.get('company_name', 'Unknown')}
- Industry: {lead_data.get('company_industry', 'Unknown')}
- Company Size: {lead_data.get('company_size', 'Unknown')}
- Location: {lead_data.get('country', 'Unknown')}

Business Context:
- Target Customer: {context.get('ideal_customer', 'Tech companies, decision makers')}
- Target Industries: {context.get('target_industries', 'Any')}
- Target Company Size: {context.get('target_company_sizes', 'Any')}
- Target Titles: {context.get('target_job_titles', 'Any')}"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )

        response_text = message.content[0].text

        try:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text

            data = json.loads(json_str.strip())

            return LeadScoring(
                score=data.get("score", 50),
                label=data.get("label", "warm"),
                reason=data.get("reason", "No specific reason provided")
            )

        except json.JSONDecodeError:
            logger.error(f"Failed to parse scoring response: {response_text[:200]}")
            return LeadScoring(
                score=50,
                label="warm",
                reason="Could not parse AI response, defaulting to warm"
            )

    def generate_linkedin_message(
        self,
        lead_data: Dict[str, Any],
        sender_context: Optional[Dict[str, Any]] = None,
        strategy: str = "hybrid"
    ) -> str:
        """
        Generate a personalized LinkedIn connection message.

        Strategies:
        - "hybrid": Auto-detect based on seniority (direct for seniors, gradual for others)
        - "direct": Mention AI Edge newsletter sponsorship directly
        - "gradual": Build rapport first, no pitch

        Args:
            lead_data: Lead information
            sender_context: Sender's business context
            strategy: "hybrid", "direct", or "gradual"

        Returns:
            Connection message (max 300 characters)
        """
        context = sender_context or {}

        # Determine effective strategy for hybrid mode
        effective_strategy = strategy
        if strategy == "hybrid":
            job_title = (lead_data.get("job_title", "") or "").lower()
            headline = (lead_data.get("headline", "") or "").lower()
            combined = f"{job_title} {headline}"

            senior_keywords = [
                "director", "vp", "vice president", "founder", "co-founder",
                "cmo", "ceo", "cto", "coo", "chief", "head of", "svp",
                "senior vice", "managing director", "partner", "owner",
                "president", "head of growth", "head of marketing",
            ]
            effective_strategy = "direct" if any(kw in combined for kw in senior_keywords) else "gradual"

        if effective_strategy == "direct":
            system_prompt = """You are a LinkedIn outreach specialist for AI Edge, a newsletter with 30,000+ subscribers (entrepreneurs, founders, tech professionals building with AI). You write connection requests to sell newsletter sponsorship packages.

RULES:
- MAXIMUM 300 characters (hard limit)
- Mention AI Edge newsletter and its audience briefly
- Reference their specific role/company/industry and why it's a fit
- Single clear value prop: reach AI-focused decision-makers
- Direct, honest, no fluff
- NO flattery, NO superlatives, NO buzzwords

CONTEXT:
- Newsletter: AI Edge (EN) / IA al Dia (ES) - 30K+ subscribers
- Audience: entrepreneurs, founders, tech professionals building with AI
- 43%+ open rate, proven results
- Packages range $200-$1,250/issue
- You're offering competitive introductory pricing

Output ONLY the message, nothing else."""
        else:
            system_prompt = """You are a LinkedIn connection request writer. Write brief, honest messages that show genuine curiosity about the person's work in AI/tech.

RULES:
- MAXIMUM 300 characters (hard limit)
- Connect based on shared interest in AI/tech
- Reference their specific work, role, or company
- Show genuine curiosity about what they're building
- DO NOT mention newsletters, sponsorships, or selling anything
- NO flattery or ass-kissing
- NO superlatives or excessive praise

GOOD phrases:
- "Curious about how you're using AI at..."
- "Noticed you're building..."
- "Interested in your approach to..."
- "Your work on [specific thing] caught my eye"

BAD phrases (never use):
- "Impressed by your work"
- "Amazing profile"
- "Love your content"
- "Excited to connect"
- "collaboration" or "opportunity"

Output ONLY the message, nothing else."""

        user_content = f"""Write a connection message for:

Contact:
- Name: {lead_data.get('first_name', '')}
- Job Title: {lead_data.get('job_title', '')}
- Headline: {lead_data.get('headline', '')}
- Company: {lead_data.get('company_name', '')}
- Company Website: {lead_data.get('company_website', '')}
- Industry: {lead_data.get('company_industry', '')}
- Company Size: {lead_data.get('company_size', '')}

Sender Context:
- Name: {context.get('sender_name', 'Pablo')}
- Role: {context.get('sender_role', 'Founder')}
- Company: {context.get('sender_company', 'AI Edge Newsletter')}
- Context: {context.get('sender_context', 'AI newsletter with 30K+ subscribers')}"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=150,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )

        result = message.content[0].text.strip()

        # Clean up any markdown formatting
        result = result.replace("```", "").replace("`", "").replace("**", "").replace("*", "").strip()

        # Ensure max 300 characters
        if len(result) > 300:
            truncate_point = result[:297].rfind(" ")
            if truncate_point > 0:
                result = result[:truncate_point] + "..."
            else:
                result = result[:297] + "..."

        return result

    def generate_email_message(
        self,
        lead_data: Dict[str, Any],
        sender_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Generate a personalized cold email.

        Args:
            lead_data: Lead information
            sender_context: Sender's business context

        Returns:
            Dictionary with 'subject' and 'body' keys
        """
        context = sender_context or {}

        system_prompt = """You are a cold email writer. Write brief, value-focused emails.

RULES:
- Subject line: 5-8 words, intriguing but not clickbait
- Body: 3-5 sentences max
- Focus on VALUE for them, not features
- One clear CTA
- Professional but conversational tone
- NO buzzwords or corporate speak

Output JSON:
{
  "subject": "Email subject line",
  "body": "Email body text"
}"""

        user_content = f"""Write a cold email for:

Contact:
- Name: {lead_data.get('first_name', '')} {lead_data.get('last_name', '')}
- Job Title: {lead_data.get('job_title', '')}
- Company: {lead_data.get('company_name', '')}
- Industry: {lead_data.get('company_industry', '')}

Sender:
- Name: {context.get('sender_name', '')}
- Role: {context.get('sender_role', '')}
- Company: {context.get('sender_company', '')}
- Value Proposition: {context.get('value_proposition', '')}"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )

        response_text = message.content[0].text

        try:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text

            return json.loads(json_str.strip())

        except json.JSONDecodeError:
            logger.error(f"Failed to parse email response: {response_text[:200]}")
            return {
                "subject": "Quick question",
                "body": response_text[:500]
            }

    def generate_conversation_reply(
        self,
        conversation_history: str,
        contact_info: Dict[str, Any],
        sender_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a contextual reply for an ongoing LinkedIn conversation.

        Args:
            conversation_history: Formatted conversation history
            contact_info: Information about the contact (name, job_title, company)
            sender_context: Sender's business context

        Returns:
            Reply message
        """
        context = sender_context or {}

        system_prompt = """You are Pablo's AI assistant for LinkedIn conversations. You help continue conversations naturally.

CONTEXT:
- You're helping Pablo (the sender) respond to LinkedIn messages
- Goal: Build genuine professional relationships, explore potential collaboration
- Tone: Direct, curious, professional but not corporate

RULES:
- Keep replies SHORT (2-4 sentences max)
- Reference what they said specifically
- Ask thoughtful follow-up questions when appropriate
- Show genuine interest in their work
- NO flattery or fake enthusiasm
- NO sales pitch unless they're clearly interested
- Avoid clichés like "excited to" or "love that"

If they asked a question, answer it directly.
If they shared something, acknowledge it genuinely and dig deeper if interesting.
If the conversation is stalling, ask a specific question about their work.

Output ONLY the reply message, nothing else."""

        user_content = f"""Generate a reply for this conversation:

CONVERSATION HISTORY:
{conversation_history}

CONTACT INFO:
- Name: {contact_info.get('name', 'Contact')}
- Job Title: {contact_info.get('job_title', 'Unknown')}
- Company: {contact_info.get('company', 'Unknown')}

SENDER (Pablo) CONTEXT:
- Role: {context.get('sender_role', 'Founder')}
- Company: {context.get('sender_company', '')}
- Context: {context.get('sender_context', '')}

Write the reply:"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )

        result = message.content[0].text.strip()

        # Clean up any markdown formatting
        result = result.replace("```", "").replace("`", "").strip()

        return result

    def analyze_conversation_sentiment(
        self,
        conversation_text: str
    ) -> Dict[str, Any]:
        """
        Analyze a conversation to determine engagement level.

        IMPORTANT: Only call this when there are NEW messages to save API costs.

        Args:
            conversation_text: Formatted conversation text

        Returns:
            Dictionary with:
            - level: "hot" | "warm" | "cold"
            - reason: Brief explanation
            - next_action: Suggested next step
        """
        system_prompt = """You are a sales conversation analyst. Analyze LinkedIn conversations to determine engagement level.

OUTPUT JSON:
{
  "level": "hot" | "warm" | "cold",
  "reason": "1 sentence explanation",
  "next_action": "Suggested next step"
}

CRITERIA:
HOT (high engagement):
- They asked about your product/service
- They proposed a meeting/call
- They're asking pricing or availability
- They shared their specific needs/problems
- Multiple back-and-forth with substance

WARM (moderate engagement):
- They're responding but with short answers
- Some interest but no clear intent yet
- Asking general questions
- Polite engagement but not driving forward

COLD (low/no engagement):
- One-word responses
- Long gaps between replies
- Deflecting or changing subject
- No questions back
- "Thanks but not interested" signals

Be direct and concise."""

        user_content = f"""Analyze this LinkedIn conversation:

{conversation_text}

Determine engagement level:"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}]
            )

            response_text = message.content[0].text

            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text

            return json.loads(json_str.strip())

        except Exception as e:
            logger.error(f"Failed to analyze conversation: {e}")
            return {
                "level": "warm",
                "reason": "Could not analyze conversation",
                "next_action": "Continue engagement"
            }

    def detect_buying_signals(
        self,
        conversation_text: str
    ) -> Dict[str, Any]:
        """
        Detect buying signals in a conversation.

        Args:
            conversation_text: Formatted conversation text

        Returns:
            Dictionary with signals, signal_strength, sentiment, summary
        """
        system_prompt = """You are a sales intelligence analyst. Analyze LinkedIn conversations to detect buying signals for newsletter sponsorship sales.

CONTEXT: We sell sponsorship packages for AI Edge newsletter (30K+ subscribers, 43%+ open rate).
Packages: Featured Tool ($200), Tutorial Sponsor ($275), Spotlight ($325), Primary ($1,250).

OUTPUT JSON:
{
  "signals": ["list of specific buying signals detected"],
  "signal_strength": "strong" | "moderate" | "weak" | "none",
  "sentiment": "hot" | "warm" | "cold",
  "summary": "1-2 sentence summary of buyer intent"
}

BUYING SIGNALS (strong):
- Asking about pricing, packages, or availability
- Requesting media kit or audience demographics
- Mentioning budget or marketing spend
- Proposing a call or meeting to discuss
- Asking about case studies or results

BUYING SIGNALS (moderate):
- Showing interest in the newsletter/audience
- Asking about content types or formats
- Mentioning their marketing goals
- Engaging with multiple questions

BUYING SIGNALS (weak):
- General positive responses
- Asking general questions about AI
- Polite but non-committal engagement

Be specific about which signals you detect."""

        user_content = f"""Analyze this conversation for buying signals:

{conversation_text}"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}]
            )

            response_text = message.content[0].text

            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text

            return json.loads(json_str.strip())

        except Exception as e:
            logger.error(f"Failed to detect buying signals: {e}")
            return {
                "signals": [],
                "signal_strength": "none",
                "sentiment": "warm",
                "summary": "Could not analyze conversation"
            }

    def recommend_stage_transition(
        self,
        lead_data: Dict[str, Any],
        conversation_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get AI recommendation for lead stage transition.

        Args:
            lead_data: Lead information including current stage
            conversation_text: Optional conversation text for context

        Returns:
            Dictionary with should_advance, recommended_stage, reason, suggested_action
        """
        system_prompt = """You are a sales pipeline advisor. Based on lead data and conversation history, recommend whether to advance a lead to a new stage.

PIPELINE STAGES (in order):
1. new - No contact made
2. pending - Awaiting invitation
3. invitation_sent - LinkedIn invite sent
4. connected - Connected on LinkedIn
5. in_conversation - Active discussion
6. meeting_scheduled - Meeting set up
7. qualified - Ready to close
8. closed_won - Deal done
9. disqualified - Not a fit
10. closed_lost - Deal lost

OUTPUT JSON:
{
  "should_advance": true/false,
  "recommended_stage": "stage_value",
  "reason": "1-2 sentence explanation",
  "suggested_action": "Specific next step to take"
}

Be practical and conservative - only recommend advancing when there's clear evidence."""

        conversation_section = ""
        if conversation_text:
            conversation_section = f"\nConversation:\n{conversation_text}"

        user_content = f"""Evaluate this lead for stage transition:

Lead:
- Name: {lead_data.get('name', 'Unknown')}
- Title: {lead_data.get('job_title', 'Unknown')}
- Company: {lead_data.get('company', 'Unknown')}
- Current Stage: {lead_data.get('current_stage', 'new')}
- AI Score: {lead_data.get('score', 'N/A')} ({lead_data.get('score_label', 'unscored')})
- Has Conversation: {lead_data.get('has_conversation', False)}
- Connected: {lead_data.get('connected', False)}
- Invitation Sent: {lead_data.get('invitation_sent', False)}
{conversation_section}"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}]
            )

            response_text = message.content[0].text

            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text

            return json.loads(json_str.strip())

        except Exception as e:
            logger.error(f"Failed to get stage recommendation: {e}")
            return {
                "should_advance": False,
                "recommended_stage": lead_data.get("current_stage", "new"),
                "reason": "Could not analyze lead data",
                "suggested_action": "Review lead manually"
            }

    def generate_sequence_follow_up(
        self,
        lead_data: Dict[str, Any],
        sender_context: Optional[Dict[str, Any]] = None,
        step_context: Optional[str] = None,
        conversation_history: Optional[str] = None,
        step_number: int = 2,
        total_steps: int = 3,
    ) -> str:
        """
        Generate a contextual follow-up message for a sequence step.

        Args:
            lead_data: Contact information
            sender_context: Sender's business context
            step_context: Optional guidance for this specific step
            conversation_history: Previous messages in the conversation
            step_number: Current step in the sequence (2+)
            total_steps: Total steps in the sequence

        Returns:
            Generated follow-up message string
        """
        sender_name = sender_context.get("sender_name", "there") if sender_context else "there"
        sender_role = sender_context.get("sender_role", "") if sender_context else ""
        sender_company = sender_context.get("sender_company", "") if sender_context else ""
        sender_extra = sender_context.get("sender_context", "") if sender_context else ""

        contact_name = lead_data.get("first_name", "there")
        contact_title = lead_data.get("job_title", "professional")
        contact_company = lead_data.get("company_name", "your company")
        contact_industry = lead_data.get("company_industry", "")

        system_prompt = f"""You are {sender_name}, {sender_role} at {sender_company}.
{sender_extra}

You are writing follow-up message #{step_number} of {total_steps} in a LinkedIn outreach sequence to {contact_name}, {contact_title} at {contact_company}.

RULES:
- Keep it SHORT (2-4 sentences max, under 500 characters)
- Reference the previous conversation naturally
- Be genuinely interesting, NOT pushy or salesy
- NO generic "just following up" or "checking in" openers
- Each message should add NEW value or ask a specific question
- Match the tone of the conversation so far
- Sound human and natural, not robotic
- Use the contact's first name

{f'STEP GUIDANCE: {step_context}' if step_context else ''}

{f'CONVERSATION SO FAR:{chr(10)}{conversation_history}' if conversation_history else ''}

Output ONLY the message text, nothing else. No quotes, no labels."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Write the follow-up message for {contact_name} ({contact_title} at {contact_company}, {contact_industry} industry)."
                    }
                ]
            )

            message = response.content[0].text.strip()
            # Remove any wrapping quotes
            if message.startswith('"') and message.endswith('"'):
                message = message[1:-1]

            logger.info(f"Generated sequence follow-up (step {step_number}/{total_steps}) for {contact_name}: {len(message)} chars")
            return message

        except Exception as e:
            logger.error(f"Failed to generate sequence follow-up: {e}")
            return f"Hi {contact_name}, wanted to follow up on our connection. Would love to hear your thoughts!"

    # ──────────────────────────────────────────────────────────────
    # Smart Pipeline Methods (5-phase response-driven outreach)
    # ──────────────────────────────────────────────────────────────

    def analyze_phase_response(
        self,
        conversation_history: str,
        current_phase: str,
        lead_data: dict,
        sender_context: dict | None = None,
        messages_in_phase: int = 0,
    ) -> dict:
        """
        Core AI analysis engine for the smart pipeline.

        Analyzes the lead's latest response in context of the current phase
        and returns a structured decision on what to do next.

        Args:
            conversation_history: Full conversation formatted as "You: ... / Contact: ..."
            current_phase: Current pipeline phase (apertura, calificacion, valor, nurture, reactivacion)
            lead_data: Dict with first_name, job_title, company_name, company_industry
            sender_context: Sender's business context (name, role, company, context)
            messages_in_phase: Number of outbound messages already sent in this phase

        Returns:
            dict with keys: outcome, reason, sentiment, buying_signals,
                  signal_strength, next_phase, suggested_angle
        """
        contact_name = lead_data.get("first_name", "the contact")
        contact_title = lead_data.get("job_title", "professional")
        contact_company = lead_data.get("company_name", "their company")
        contact_industry = lead_data.get("company_industry", "")

        sender_name = sender_context.get("sender_name", "") if sender_context else ""
        sender_company = sender_context.get("sender_company", "") if sender_context else ""
        sender_extra = sender_context.get("sender_context", "") if sender_context else ""

        phase_rules = {
            "apertura": """APERTURA (Phase 1 – Opening):
- You sent a genuine curiosity question. No pitch was made.
- ADVANCE to calificacion if: lead responds with engagement, asks back, shows willingness to chat, shares info about their work.
- STAY if: lead responds briefly but not negatively (max 2 messages in this phase).
- NURTURE if: lead responds coldly or dismissively but doesn't explicitly refuse.
- EXIT if: lead explicitly says "not interested", "don't contact me", or similar rejection.""",

            "calificacion": """CALIFICACION (Phase 2 – Qualification):
- You asked a qualifying question about their business growth, marketing strategy, or investment plans.
- ADVANCE to valor if: lead reveals growth signals (scaling, investing in marketing, launching campaigns, expanding audience, looking for visibility).
- STAY if: lead engages but hasn't revealed growth signals yet (max 2 messages in this phase).
- NURTURE if: lead says they're consolidating, cutting costs, not investing right now, or shows no growth signals.
- PARK if: lead's business/industry has zero fit with newsletter sponsorship (completely different target audience).
- EXIT if: explicit rejection.""",

            "valor": """VALOR (Phase 3 – Value Proposition):
- You connected their specific need with your newsletter sponsorship offering.
- MEETING if: lead asks about pricing, wants details, suggests a call, asks for media kit, shows clear purchase intent.
- STAY if: lead is interested but hasn't committed to next step yet (max 2 messages in this phase).
- NURTURE if: lead says "not right now", "maybe later", "interesting but timing isn't right".
- PARK if: lead explicitly declines the offering but remains polite.
- EXIT if: explicit rejection or negative response.""",

            "nurture": """NURTURE (Phase 4 – Long-term light touch):
- You've been sending periodic check-ins every 6-8 weeks.
- ADVANCE to calificacion if: lead re-engages with business discussion, mentions new projects, growth, or marketing plans.
- ADVANCE to valor if: lead directly asks about your offering or shows purchase intent.
- STAY if: lead responds neutrally (continue nurturing).
- PARK if: no response after this touch and nurture count is high.
- EXIT if: explicit rejection.""",

            "reactivacion": """REACTIVACION (Phase 5 – Reactivation after 30+ days silence):
- Lead went silent for 30+ days. You're re-opening with a fresh angle.
- ADVANCE to calificacion if: lead re-engages positively, responds to the new angle.
- NURTURE if: lead responds but is lukewarm.
- PARK if: still no response.
- EXIT if: explicit rejection.""",
        }

        phase_context = phase_rules.get(current_phase, phase_rules["apertura"])

        system_prompt = f"""You are an AI sales development analyst evaluating a LinkedIn conversation.

CONTEXT:
- Sender: {sender_name} from {sender_company}
  {sender_extra}
- Contact: {contact_name}, {contact_title} at {contact_company} ({contact_industry})
- Current phase: {current_phase.upper()}
- Messages sent in this phase: {messages_in_phase}

PHASE RULES:
{phase_context}

IMPORTANT CONSTRAINTS:
- Maximum 2 outbound messages per phase. If messages_in_phase >= 2 and the lead hasn't given a clear positive signal, you MUST recommend NURTURE (not STAY).
- Phase advancement is ALWAYS based on the lead's response content, never on time elapsed.
- Be conservative with ADVANCE – the lead must show genuine interest or fit, not just politeness.
- MEETING is only for clear next-step intent (pricing, call, details request).

CONVERSATION HISTORY:
{conversation_history}

Analyze the lead's LATEST response and return a JSON object with EXACTLY these keys:
- "outcome": one of "advance", "stay", "nurture", "park", "meeting", "exit"
- "reason": 1-2 sentence explanation of your decision
- "sentiment": one of "hot", "warm", "cold"
- "buying_signals": array of detected signals (e.g. ["scaling marketing", "interested in visibility"]) or empty array
- "signal_strength": one of "strong", "moderate", "weak", "none"
- "next_phase": the phase to move to if advancing (e.g. "calificacion", "valor") or null if not advancing
- "suggested_angle": brief guidance for the next message to send (1 sentence)

Output ONLY valid JSON, no markdown formatting, no explanation outside the JSON."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": "Analyze the latest response and provide your phase transition decision as JSON.",
                    }
                ],
            )

            raw = response.content[0].text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            import json as _json
            analysis = _json.loads(raw)

            # Validate required keys
            required = {"outcome", "reason", "sentiment", "buying_signals", "signal_strength", "next_phase", "suggested_angle"}
            if not required.issubset(analysis.keys()):
                missing = required - analysis.keys()
                logger.warning(f"Phase analysis missing keys {missing}, using defaults")
                for key in missing:
                    analysis[key] = None if key != "buying_signals" else []

            # Enforce max 2 messages per phase
            if messages_in_phase >= 2 and analysis.get("outcome") == "stay":
                logger.info(f"Overriding 'stay' → 'nurture' because messages_in_phase={messages_in_phase} >= 2")
                analysis["outcome"] = "nurture"
                analysis["reason"] = f"Max messages in phase reached ({messages_in_phase}). Moving to nurture."
                analysis["next_phase"] = "nurture"

            logger.info(
                f"Phase analysis for {contact_name} ({current_phase}): "
                f"outcome={analysis['outcome']}, sentiment={analysis.get('sentiment')}, "
                f"signals={analysis.get('buying_signals')}"
            )
            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze phase response: {e}")
            # Safe fallback: stay in current phase
            return {
                "outcome": "stay",
                "reason": f"Analysis failed: {str(e)}",
                "sentiment": "warm",
                "buying_signals": [],
                "signal_strength": "none",
                "next_phase": None,
                "suggested_angle": "Continue the conversation naturally.",
            }

    def generate_phase_message(
        self,
        phase: str,
        lead_data: dict,
        sender_context: dict | None = None,
        conversation_history: str = "",
        phase_analysis: dict | None = None,
        messages_in_phase: int = 0,
    ) -> str:
        """
        Generate a phase-appropriate message for the smart pipeline.

        Each phase has a distinct tone, goal, and constraint set.

        Args:
            phase: Pipeline phase (apertura, calificacion, valor, nurture, reactivacion)
            lead_data: Dict with first_name, job_title, company_name, company_industry
            sender_context: Sender's business context
            conversation_history: Previous messages
            phase_analysis: Claude's analysis result (for context on what angle to take)
            messages_in_phase: How many messages already sent in this phase

        Returns:
            Generated message string
        """
        contact_name = lead_data.get("first_name", "there")
        contact_title = lead_data.get("job_title", "professional")
        contact_company = lead_data.get("company_name", "your company")
        contact_industry = lead_data.get("company_industry", "")

        sender_name = sender_context.get("sender_name", "") if sender_context else ""
        sender_role = sender_context.get("sender_role", "") if sender_context else ""
        sender_company = sender_context.get("sender_company", "") if sender_context else ""
        sender_extra = sender_context.get("sender_context", "") if sender_context else ""

        suggested_angle = ""
        if phase_analysis and phase_analysis.get("suggested_angle"):
            suggested_angle = f"\nSUGGESTED ANGLE: {phase_analysis['suggested_angle']}"

        # Phase-specific prompt configurations
        phase_prompts = {
            "apertura": {
                "goal": "Get a genuine response. Ask a curiosity-driven question about their work, industry, or a recent trend.",
                "tone": "Curious, genuine, peer-to-peer. Like a fellow professional who finds their work interesting.",
                "rules": [
                    "Do NOT mention your company, product, newsletter, or anything you sell",
                    "Do NOT pitch or hint at a pitch",
                    "Ask ONE specific question about their work, role, industry challenge, or a trend you noticed",
                    "Reference something specific about them (title, company, industry) to show genuine interest",
                    "Keep it to 2-3 sentences maximum",
                    "Sound like a real human, not a bot or sales rep",
                    "If this is message 2, acknowledge their response and ask a natural follow-up",
                ],
                "max_chars": 300,
                "mentions_offering": False,
            },
            "calificacion": {
                "goal": "Discover if they're in growth/investment mode. Ask about their business priorities, marketing plans, or growth strategy.",
                "tone": "Conversational, insightful. Like a peer sharing industry knowledge.",
                "rules": [
                    "Do NOT mention your company, product, or offering yet",
                    "Ask a question that naturally reveals if they're investing in growth/marketing/visibility",
                    "Frame it around industry trends or shared challenges",
                    "Keep it to 2-3 sentences maximum",
                    "Build on the conversation history naturally",
                    "If this is message 2, try a different angle to qualify them",
                ],
                "max_chars": 350,
                "mentions_offering": False,
            },
            "valor": {
                "goal": "Connect their specific need/pain point with your newsletter sponsorship offering. Make it relevant to THEM.",
                "tone": "Direct but not pushy. Consultative, showing how you can specifically help them.",
                "rules": [
                    "NOW you can mention your newsletter (AI Edge) and its audience (30K+ AI/tech professionals)",
                    "Connect THEIR specific need (from conversation) with what your newsletter sponsorship offers",
                    "Be specific about the value: targeted audience, engagement rates, decision-maker reach",
                    "Include a clear but soft call to action (e.g., 'happy to share our media kit', 'worth a quick chat?')",
                    "Keep it to 3-5 sentences maximum",
                    "Do NOT be generic – reference what THEY told you about their needs",
                    "If this is message 2, address any hesitation and add a new value angle",
                ],
                "max_chars": 500,
                "mentions_offering": True,
            },
            "nurture": {
                "goal": "Maintain the relationship with a light touch. Share something valuable, no pressure.",
                "tone": "Friendly, brief, zero pressure. Like a colleague sharing something interesting.",
                "rules": [
                    "Do NOT pitch or sell anything",
                    "Share a brief insight, congratulate on something, or ask a light question",
                    "Keep it to 1-2 sentences maximum",
                    "Feel natural and human, not automated",
                    "Vary the approach – don't repeat the same format",
                    "Reference something from your previous conversation if possible",
                ],
                "max_chars": 200,
                "mentions_offering": False,
            },
            "reactivacion": {
                "goal": "Re-open a conversation that went silent 30+ days ago with a fresh angle.",
                "tone": "Direct, fresh, low-pressure. Acknowledge the gap without being awkward.",
                "rules": [
                    "Do NOT say 'just following up' or 'checking in' – use a fresh angle",
                    "Try a new approach: share a relevant insight, ask about a recent change, or reference an industry event",
                    "Keep it to 2-3 sentences maximum",
                    "Make it easy for them to respond (ask a simple question)",
                    "You MAY briefly mention your offering if the previous conversation reached valor phase",
                    "Sound natural, not desperate",
                ],
                "max_chars": 300,
                "mentions_offering": False,  # unless previous conversation reached valor
            },
        }

        phase_config = phase_prompts.get(phase, phase_prompts["apertura"])

        rules_text = "\n".join(f"- {r}" for r in phase_config["rules"])

        system_prompt = f"""You are {sender_name}, {sender_role} at {sender_company}.
{sender_extra}

You are writing a LinkedIn message to {contact_name}, {contact_title} at {contact_company} ({contact_industry}).

PHASE: {phase.upper()}
GOAL: {phase_config['goal']}
TONE: {phase_config['tone']}
MESSAGE NUMBER IN THIS PHASE: {messages_in_phase + 1}

RULES:
{rules_text}
- MAXIMUM {phase_config['max_chars']} characters
- Write in the SAME LANGUAGE as the conversation (if they wrote in Spanish, respond in Spanish; if English, respond in English)
- Output ONLY the message text. No quotes, no labels, no explanation.
{suggested_angle}

{f'CONVERSATION SO FAR:{chr(10)}{conversation_history}' if conversation_history else ''}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=400,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Write the {phase} phase message for {contact_name} ({contact_title} at {contact_company}).",
                    }
                ],
            )

            message = response.content[0].text.strip()
            # Remove wrapping quotes
            if message.startswith('"') and message.endswith('"'):
                message = message[1:-1]

            # Enforce character limit
            max_chars = phase_config["max_chars"]
            if len(message) > max_chars + 50:  # Small tolerance
                logger.warning(
                    f"Phase message too long ({len(message)} chars, max {max_chars}). Truncating."
                )
                # Try to cut at last sentence boundary
                truncated = message[:max_chars]
                last_period = truncated.rfind(".")
                last_question = truncated.rfind("?")
                cut_point = max(last_period, last_question)
                if cut_point > max_chars * 0.5:
                    message = truncated[: cut_point + 1]
                else:
                    message = truncated

            logger.info(
                f"Generated {phase} phase message for {contact_name}: "
                f"{len(message)} chars, msg #{messages_in_phase + 1}"
            )
            return message

        except Exception as e:
            logger.error(f"Failed to generate {phase} phase message: {e}")
            # Minimal fallback per phase
            fallbacks = {
                "apertura": f"Hi {contact_name}, I noticed your work at {contact_company} — what's been the biggest shift in your industry lately?",
                "calificacion": f"That's interesting, {contact_name}. What are your biggest priorities for growth this year?",
                "valor": f"{contact_name}, based on what you've shared, I think our AI Edge newsletter (30K+ subscribers) could help with visibility. Worth a quick chat?",
                "nurture": f"Hi {contact_name}, hope things are going well at {contact_company}!",
                "reactivacion": f"Hi {contact_name}, been a while! Curious how things have evolved at {contact_company}.",
            }
            return fallbacks.get(phase, f"Hi {contact_name}, how are things going?")
