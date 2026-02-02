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
        sender_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a personalized LinkedIn connection message.

        Args:
            lead_data: Lead information
            sender_context: Sender's business context

        Returns:
            Connection message (max 300 characters)
        """
        context = sender_context or {}

        system_prompt = """You are a LinkedIn connection request writer. Write brief, honest messages that show genuine curiosity.

RULES:
- MAXIMUM 300 characters (hard limit)
- Direct and honest tone
- Show genuine interest in their work
- NO flattery or ass-kissing
- NO superlatives or excessive praise
- NO mentions of "collaboration" or "opportunity"

GOOD phrases:
- "Curious about..."
- "Interested in learning..."
- "Noticed you're building..."
- "Following your work on..."

BAD phrases (never use):
- "Impressed by your work"
- "Amazing profile"
- "Great insights"
- "Love your content"
- "Excited to connect"

Output ONLY the message, nothing else."""

        user_content = f"""Write a connection message for:

Contact:
- Name: {lead_data.get('first_name', '')}
- Job Title: {lead_data.get('job_title', '')}
- Company: {lead_data.get('company_name', '')}
- Industry: {lead_data.get('company_industry', '')}

Sender Context:
- Name: {context.get('sender_name', 'there')}
- Role: {context.get('sender_role', '')}
- Company: {context.get('sender_company', '')}
- Context: {context.get('sender_context', '')}"""

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
