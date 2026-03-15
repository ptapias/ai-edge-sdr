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
        strategy: str = "hybrid",
        experiment_prompt: Optional[str] = None
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

            # True C-level / decision-makers who control budgets
            clevel_keywords = [
                "cmo", "ceo", "cto", "coo", "cfo", "chief",
                "founder", "co-founder", "cofounder",
                "owner", "president", "managing director",
                "svp", "senior vice president",
            ]
            # Senior but not necessarily C-level — use warm intro, not hard pitch
            senior_keywords = [
                "vp", "vice president",
                "director", "head of", "partner",
            ]

            if any(kw in combined for kw in clevel_keywords):
                effective_strategy = "direct"
            elif any(kw in combined for kw in senior_keywords):
                effective_strategy = "warm"
            else:
                effective_strategy = "gradual"

        if effective_strategy == "direct":
            # C-level: brief professional intro, zero pitch
            system_prompt = """You are writing a LinkedIn connection request on behalf of the sender. The goal is to establish a genuine professional connection.

RULES:
- MAXIMUM 300 characters (hard limit)
- Introduce yourself briefly (name and role only)
- Reference something specific about THEIR company or role that genuinely caught your attention
- Give ONE clear reason why connecting makes sense professionally
- DO NOT mention AI, tech, newsletters, automation, sponsorships, or any product/service
- DO NOT ask about their business challenges or how they use technology
- DO NOT ask for a meeting or call
- NO flattery, NO superlatives, NO buzzwords

TONE: One professional reaching out to another. Short, genuine, human. Like someone you met at a conference saying "Hey, I saw you run X, I do something similar, let's stay in touch."

CRITICAL: NEVER invent information about the sender. Use ONLY the name, role, company and context provided. If role says "Fundador", never say "CEO" or "Director". If a field is empty, skip it.

- LANGUAGE DETECTION: Look at the lead's headline, job title, and company name. If they are in Spanish, write the ENTIRE message in Spanish (Spain, tuteo). If they are in ANY other language (English, French, Portuguese, German, etc.), write the ENTIRE message in English. This is critical — match the lead's profile language.
- NEVER use forward slashes (/) to separate words or concepts (e.g. "marketing/ventas" is wrong, write "marketing y ventas").
- NEVER use dashes or double dashes (-, --) as separators or bullet points in the message. These patterns look very AI-generated.

Output ONLY the message, nothing else."""
        elif effective_strategy == "warm":
            # Senior/directors: warm genuine intro, no business pitch
            system_prompt = """You are writing a LinkedIn connection request on behalf of the sender. The goal is to establish a genuine professional connection with someone in a senior role.

RULES:
- MAXIMUM 300 characters (hard limit)
- Reference something specific about their work, company, or role
- Show genuine curiosity about what they do (their industry, their company, their projects)
- DO NOT mention AI, tech, newsletters, automation, or any product/service
- DO NOT ask about their business challenges or how they use technology
- DO NOT ask for a meeting or call
- NO flattery, NO superlatives, NO buzzwords

TONE: Warm and genuine. Like a professional who genuinely found their work interesting. Think "Hey, I saw your company does X, that's really interesting" not "I work in AI and want to know how you use it."

CRITICAL: NEVER invent information about the sender. Use ONLY the name, role, company and context provided. If role says "Fundador", never say "CEO" or "Director". If a field is empty, skip it.

- LANGUAGE DETECTION: Look at the lead's headline, job title, and company name. If they are in Spanish, write the ENTIRE message in Spanish (Spain, tuteo). If they are in ANY other language (English, French, Portuguese, German, etc.), write the ENTIRE message in English. This is critical — match the lead's profile language.
- NEVER use forward slashes (/) to separate words or concepts (e.g. "marketing/ventas" is wrong, write "marketing y ventas").
- NEVER use dashes or double dashes (-, --) as separators or bullet points in the message. These patterns look very AI-generated.

Output ONLY the message, nothing else."""
        else:
            # Gradual: pure rapport, no mention of newsletter or business
            system_prompt = """You are writing a LinkedIn connection request. Write a brief, genuine message to connect with this person professionally.

RULES:
- MAXIMUM 300 characters (hard limit)
- Reference something specific about their work, role, company, or industry
- Show genuine interest in what they do as a professional
- DO NOT mention AI, tech, newsletters, automation, or any product/service
- DO NOT ask about their business challenges or how they use technology
- NO flattery or ass-kissing
- NO superlatives or excessive praise

GOOD examples:
- "Hola X, vi que diriges Y en Z. Me parece un proyecto muy interesante, me encantaria conectar."
- "Hi X, noticed you work in [their industry] at [company]. Would love to connect."
- "X, your background in [their field] caught my attention. Let's connect!"

BAD examples (NEVER do this):
- "Curious about how you're using AI at..." (this is selling)
- "Are you seeing AI tools impact..." (this is selling)
- "Interested in your approach to tech/automation..." (this is selling)
- "Impressed by your work" (flattery)
- "collaboration" or "opportunity" (sales language)

CRITICAL: NEVER invent information about the sender. Use ONLY the name, role, company and context provided. If role says "Fundador", never say "CEO" or "Director". If a field is empty, skip it.

- LANGUAGE DETECTION: Look at the lead's headline, job title, and company name. If they are in Spanish, write the ENTIRE message in Spanish (Spain, tuteo). If they are in ANY other language (English, French, Portuguese, German, etc.), write the ENTIRE message in English. This is critical — match the lead's profile language.
- NEVER use forward slashes (/) to separate words or concepts (e.g. "marketing/ventas" is wrong, write "marketing y ventas").
- NEVER use dashes or double dashes (-, --) as separators or bullet points in the message. These patterns look very AI-generated.

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
- Role: {context.get('sender_role', '')}
- Company: {context.get('sender_company', '')}
- Context: {context.get('sender_context', '')}"""

        # AutoOutreach: override system_prompt if experiment template provided
        if experiment_prompt:
            system_prompt = experiment_prompt
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

    DEFAULT_REPLY_PROMPT = """You are an AI assistant helping respond to LinkedIn conversations naturally.

CONTEXT:
- You are helping the sender respond to LinkedIn messages
- Goal: Build genuine professional relationships through real curiosity
- Tone: Direct, curious, warm but professional. Like a smart friend, not a salesperson.

CRITICAL RULES:
- Keep replies SHORT (2-4 sentences max)
- RESPOND TO WHAT THEY ACTUALLY SAID - acknowledge their specific words
- Ask thoughtful follow-up questions about THEIR world, not yours
- Show genuine interest in their work, their challenges, their perspective
- NEVER sell, pitch, or mention your product/service unless THEY bring it up first
- NO flattery or fake enthusiasm
- Avoid cliches like "excited to", "love that", "that's amazing"
- NEVER invent information about the sender - only use what is provided

STRATEGY:
- Phase 1 (first 2-3 messages): Pure curiosity. Learn about them. Zero selling.
- Phase 2 (if they share pain points): Empathize, ask deeper questions. Still no selling.
- Phase 3 (only if they explicitly ask or show clear interest): Then and only then, share how you might help.

If they asked a question, answer it directly and briefly.
If they shared something, acknowledge it genuinely and dig deeper.
If the conversation is stalling, ask a specific question about their market or daily challenges.

Output ONLY the reply message, nothing else."""

    def generate_conversation_reply(
        self,
        conversation_history: str,
        contact_info: Dict[str, Any],
        sender_context: Optional[Dict[str, Any]] = None,
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        Generate a contextual reply for an ongoing LinkedIn conversation.
        """
        context = sender_context or {}

        system_prompt = custom_prompt or self.DEFAULT_REPLY_PROMPT

        user_content = f"""Generate a reply for this conversation:

CONVERSATION HISTORY:
{conversation_history}

CONTACT INFO:
- Name: {contact_info.get('name', 'Contact')}
- Job Title: {contact_info.get('job_title', 'Unknown')}
- Company: {contact_info.get('company', 'Unknown')}

SENDER (Pablo) CONTEXT:
- Role: {context.get('sender_role', '')}
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


    def generate_smart_pipeline_message(
        self,
        lead_data: Dict[str, Any],
        sender_context: Dict[str, Any],
        conversation_history: str,
        current_phase: str,
        rejection_context: Optional[str] = None,
    ) -> str:
        """
        Generate a message for Smart Pipeline based on current phase and conversation.
        """
        phase_guidelines = {
            "apertura": """PHASE: APERTURA (Opening)
- Goal: Start a genuine conversation. NO selling whatsoever.
- Ask about THEIR world: their market, their daily challenges, what they're seeing
- Reference something specific from their profile or their company
- Be curious, warm, brief (2-3 sentences max)
- Example tone: "I noticed you're in [market] — how's the [specific aspect] looking right now?"
""",
            "calificacion": """PHASE: CALIFICACION (Qualification)
- Goal: Discover pain points naturally. Still NO selling.
- Dig deeper into what they shared. Ask about specific challenges.
- Listen for signals: missed opportunities, time wasted, scaling issues
- Keep it conversational, not like an interview (2-3 sentences)
- Example: "That's interesting — when you mention [pain], how are you handling that currently?"
""",
            "valor": """PHASE: VALOR (Value)
- Goal: Connect their pain to a potential solution. Soft introduction only.
- Only if they've revealed a real pain point in previous messages
- Share a relevant insight or how others solve similar problems
- Suggest a brief call to explore, no pressure (2-3 sentences)
- Example: "Some agencies I know solved [their pain] by [approach]. Would a 15-min call make sense to explore if something similar could work for you?"
""",
            "nurture": """PHASE: NURTURE
- Goal: Stay on their radar without being annoying. Light value-add.
- Share something genuinely useful: an article, a market insight, a trend
- Very brief, no ask (1-2 sentences)
- Space these out: only send every 6-8 weeks
- Example: "Saw this [insight] and thought of your situation with [their context]. Hope things are going well."
""",
            "reactivacion": """PHASE: REACTIVACION (Reactivation)
- Goal: Last attempt after long silence (30+ days)
- Acknowledge the silence, give an easy out
- One final value proposition, very soft (2-3 sentences)
- Example: "Hey [name], I know it's been a while. Just wanted to check in — if [topic] isn't relevant anymore, no worries at all."
""",
        }

        phase_guide = phase_guidelines.get(current_phase, phase_guidelines["apertura"])

        system_prompt = f"""You are an AI assistant helping craft LinkedIn messages for a smart outreach pipeline.

{phase_guide}

CRITICAL RULES:
- LANGUAGE: Look at the lead's headline, job title, and company. If in Spanish, write in Spanish (Spain, tuteo: tu/te, not usted). If in ANY other language, write in English.
- Keep messages SHORT: 2-4 sentences max, under 600 characters.
- RESPOND TO what they said in the conversation — do not ignore their words.
- NEVER invent information about the sender. Only use what is provided.
- NEVER use emojis excessively (max 0-1 per message).
- Sound like a real person, not a bot. No corporate speak.
- If the phase says "no selling", absolutely do NOT mention products/services.

- NEVER use forward slashes (/) to separate words or concepts (e.g. "marketing/ventas" is wrong, write "marketing y ventas").
- NEVER use dashes or double dashes (-, --) as separators or bullet points in the message. These patterns look very AI-generated.

Output ONLY the message text, nothing else."""

        rejection_note = ""
        if rejection_context:
            rejection_note = "\n\nNOTE: " + rejection_context + ". Generate a DIFFERENT message that avoids the same issues."

        user_content = f"""Generate a LinkedIn message for this lead:

LEAD:
- Name: {lead_data.get('first_name', '')} {lead_data.get('last_name', '')}
- Title: {lead_data.get('job_title', '')}
- Company: {lead_data.get('company_name', '')}
- Industry: {lead_data.get('company_industry', '')}
- City: {lead_data.get('city', '')}

SENDER:
- Name: {sender_context.get('sender_name', '')}
- Role: {sender_context.get('sender_role', '')}
- Company: {sender_context.get('sender_company', '')}
- Context: {sender_context.get('sender_context', '')}

CONVERSATION SO FAR:
{conversation_history or '(No previous messages — this is the first follow-up after connecting)'}
{rejection_note}

Write the message:"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )

        result = message.content[0].text.strip()
        result = result.replace("```", "").replace("`", "").strip()
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]

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

- LANGUAGE DETECTION: Look at the lead's headline, job title, and company name. If they are in Spanish, write the ENTIRE message in Spanish (Spain, tuteo). If they are in ANY other language (English, French, Portuguese, German, etc.), write the ENTIRE message in English. This is critical — match the lead's profile language.
- NEVER use forward slashes (/) to separate words or concepts (e.g. "marketing/ventas" is wrong, write "marketing y ventas").
- NEVER use dashes or double dashes (-, --) as separators or bullet points in the message. These patterns look very AI-generated.

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
