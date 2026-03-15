"""
ExperimentService — Core engine of the AutoOutreach self-improving loop.

Implements the Karpathy autoresearch pattern:
1. Establish baseline
2. Propose a change (via Claude)
3. Run experiment (batch of connections)
4. Evaluate results
5. Keep or discard
6. Loop
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from anthropic import Anthropic
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..config import get_settings
from ..models.experiment import OutreachExperiment, OutreachExperimentLead
from ..models.lead import Lead
from ..models.business_profile import BusinessProfile

logger = logging.getLogger(__name__)
settings = get_settings()

# The DEFAULT prompt template — this is the "baseline train.py"
DEFAULT_CONNECTION_PROMPT = """You are writing a LinkedIn connection request message on behalf of the sender.
Your goal is to get the recipient to ACCEPT the connection request.

RULES:
- MAXIMUM 300 characters (HARD LIMIT - count carefully)
- Write in Spanish (Spain). Use "tú" (tuteo), never "usted"
- Reference something SPECIFIC from their profile (role, company, industry, city)
- Be genuinely curious about their work — ask a short question or make an observation
- Keep it natural and conversational, like a real person would write
- DO NOT sell anything, mention products, or pitch services
- DO NOT ask for meetings or calls
- DO NOT use flattery, superlatives, or buzzwords
- DO NOT use emojis excessively (max 0-1)
- NO "Estimado/a", NO corporate language
- Short sentences. Direct. Human.

TONE: Like a colleague in the same industry reaching out — not a salesperson.

CRITICAL: NEVER invent or fabricate information about the sender.
- Only use the sender name, role, company, and context EXACTLY as provided
- If the sender role says "Fundador", do NOT say "CEO", "Director", or anything else
- If a field is empty, do not mention it at all
- Do NOT add titles, credentials, or claims that are not in the sender context

Output ONLY the message text, nothing else."""


class ExperimentService:
    """Service for managing outreach experiments."""

    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"

    def get_default_prompt(self) -> str:
        """Return the default connection message prompt template."""
        return DEFAULT_CONNECTION_PROMPT

    def get_next_experiment_number(self, db: Session, user_id: str) -> int:
        """Get the next sequential experiment number for this user."""
        max_num = db.query(func.max(OutreachExperiment.experiment_number)).filter(
            OutreachExperiment.user_id == user_id
        ).scalar()
        return (max_num or 0) + 1

    def get_current_baseline(self, db: Session, user_id: str) -> Optional[OutreachExperiment]:
        """Get the most recent kept experiment (current baseline)."""
        return db.query(OutreachExperiment).filter(
            OutreachExperiment.user_id == user_id,
            OutreachExperiment.decision.in_(["keep", "baseline"])
        ).order_by(desc(OutreachExperiment.experiment_number)).first()

    def get_active_experiment(self, db: Session, user_id: str) -> Optional[OutreachExperiment]:
        """Get the currently running experiment, if any."""
        return db.query(OutreachExperiment).filter(
            OutreachExperiment.user_id == user_id,
            OutreachExperiment.status.in_(["running", "evaluating"])
        ).first()

    def create_baseline(self, db: Session, user_id: str, prompt_template: Optional[str] = None) -> OutreachExperiment:
        """Create the initial baseline experiment."""
        exp_num = self.get_next_experiment_number(db, user_id)
        experiment = OutreachExperiment(
            user_id=user_id,
            experiment_number=exp_num,
            experiment_name=f"exp-{exp_num:03d}-baseline",
            hypothesis="Baseline measurement — current prompt template performance",
            change_description="Initial baseline, no changes",
            prompt_template=prompt_template or DEFAULT_CONNECTION_PROMPT,
            status="baseline",
            decision="baseline",
            batch_size=25,
        )
        db.add(experiment)
        db.commit()
        db.refresh(experiment)
        logger.info(f"[AutoOutreach] Created baseline experiment #{exp_num}")
        return experiment

    def create_experiment(
        self,
        db: Session,
        user_id: str,
        name: str,
        hypothesis: str,
        prompt_template: str,
        change_description: str,
        batch_size: int = 25
    ) -> OutreachExperiment:
        """Create a new experiment with a modified prompt template."""
        # Check no other experiment is running
        active = self.get_active_experiment(db, user_id)
        if active:
            raise ValueError(f"Experiment #{active.experiment_number} is still running. Wait for it to complete.")

        baseline = self.get_current_baseline(db, user_id)
        baseline_rate = baseline.acceptance_rate if baseline else None

        exp_num = self.get_next_experiment_number(db, user_id)
        experiment = OutreachExperiment(
            user_id=user_id,
            experiment_number=exp_num,
            experiment_name=name or f"exp-{exp_num:03d}",
            hypothesis=hypothesis,
            change_description=change_description,
            prompt_template=prompt_template,
            status="running",
            decision="pending",
            batch_size=batch_size,
            baseline_acceptance_rate=baseline_rate,
            baseline_response_rate=baseline.response_rate if baseline else None,
            started_at=datetime.utcnow(),
        )
        db.add(experiment)
        db.commit()
        db.refresh(experiment)
        logger.info(f"[AutoOutreach] Created experiment #{exp_num}: {name}")
        return experiment

    def start_experiment(self, db: Session, experiment_id: str) -> OutreachExperiment:
        """Mark an experiment as running (start sending)."""
        exp = db.query(OutreachExperiment).filter(OutreachExperiment.id == experiment_id).first()
        if not exp:
            raise ValueError("Experiment not found")
        exp.status = "running"
        exp.started_at = datetime.utcnow()
        db.commit()
        db.refresh(exp)
        return exp

    def register_lead_sent(
        self,
        db: Session,
        experiment_id: str,
        lead_id: str,
        message: str
    ) -> OutreachExperimentLead:
        """Register that a connection message was sent to a lead as part of an experiment."""
        exp_lead = OutreachExperimentLead(
            experiment_id=experiment_id,
            lead_id=lead_id,
            message_sent=message,
            sent_at=datetime.utcnow(),
        )
        db.add(exp_lead)

        # Increment sent count
        exp = db.query(OutreachExperiment).filter(OutreachExperiment.id == experiment_id).first()
        if exp:
            exp.connections_sent = (exp.connections_sent or 0) + 1
        db.commit()
        db.refresh(exp_lead)
        return exp_lead

    def record_acceptance(self, db: Session, lead_id: str):
        """Record that a lead accepted a connection — update their experiment entry."""
        exp_lead = db.query(OutreachExperimentLead).filter(
            OutreachExperimentLead.lead_id == lead_id,
            OutreachExperimentLead.accepted.is_(None)
        ).order_by(desc(OutreachExperimentLead.created_at)).first()

        if exp_lead:
            exp_lead.accepted = True
            exp_lead.accepted_at = datetime.utcnow()

            # Increment experiment accepted count
            exp = db.query(OutreachExperiment).filter(
                OutreachExperiment.id == exp_lead.experiment_id
            ).first()
            if exp:
                exp.connections_accepted = (exp.connections_accepted or 0) + 1
            db.commit()
            logger.info(f"[AutoOutreach] Lead {lead_id[:8]} accepted — experiment #{exp.experiment_number if exp else '?'}")

    def record_response(self, db: Session, lead_id: str):
        """Record that a lead responded to a message."""
        exp_lead = db.query(OutreachExperimentLead).filter(
            OutreachExperimentLead.lead_id == lead_id,
            OutreachExperimentLead.responded.is_(None)
        ).order_by(desc(OutreachExperimentLead.created_at)).first()

        if exp_lead:
            exp_lead.responded = True
            exp_lead.responded_at = datetime.utcnow()

            exp = db.query(OutreachExperiment).filter(
                OutreachExperiment.id == exp_lead.experiment_id
            ).first()
            if exp:
                exp.responses_received = (exp.responses_received or 0) + 1
            db.commit()
            logger.info(f"[AutoOutreach] Lead {lead_id[:8]} responded — experiment #{exp.experiment_number if exp else '?'}")

    def evaluate_experiment(self, db: Session, experiment_id: str) -> Dict[str, Any]:
        """
        Evaluate an experiment's results and make a KEEP/DISCARD decision.
        This is the equivalent of comparing val_bpb in autoresearch.
        """
        exp = db.query(OutreachExperiment).filter(OutreachExperiment.id == experiment_id).first()
        if not exp:
            raise ValueError("Experiment not found")

        # Count actual results from experiment_leads
        sent = db.query(OutreachExperimentLead).filter(
            OutreachExperimentLead.experiment_id == experiment_id,
            OutreachExperimentLead.sent_at.isnot(None)
        ).count()

        accepted = db.query(OutreachExperimentLead).filter(
            OutreachExperimentLead.experiment_id == experiment_id,
            OutreachExperimentLead.accepted == True
        ).count()

        responded = db.query(OutreachExperimentLead).filter(
            OutreachExperimentLead.experiment_id == experiment_id,
            OutreachExperimentLead.responded == True
        ).count()

        # Calculate rates
        acceptance_rate = (accepted / sent * 100) if sent > 0 else 0.0
        response_rate = (responded / sent * 100) if sent > 0 else 0.0

        # Update experiment
        exp.connections_sent = sent
        exp.connections_accepted = accepted
        exp.responses_received = responded
        exp.acceptance_rate = round(acceptance_rate, 1)
        exp.response_rate = round(response_rate, 1)
        exp.evaluated_at = datetime.utcnow()
        exp.status = "evaluating"

        # Decision logic (the core of autoresearch pattern)
        if exp.status == "baseline" or exp.decision == "baseline":
            exp.decision = "baseline"
            exp.status = "baseline"
        elif exp.baseline_acceptance_rate is not None and sent >= 10:
            if acceptance_rate > exp.baseline_acceptance_rate:
                exp.decision = "keep"
                exp.status = "kept"
                exp.improvement_acceptance = round(acceptance_rate - exp.baseline_acceptance_rate, 1)
                if exp.baseline_response_rate is not None:
                    exp.improvement_response = round(response_rate - exp.baseline_response_rate, 1)
                logger.info(f"[AutoOutreach] Experiment #{exp.experiment_number} KEPT: "
                           f"{acceptance_rate:.1f}% > {exp.baseline_acceptance_rate:.1f}% baseline")
            else:
                exp.decision = "discard"
                exp.status = "discarded"
                exp.improvement_acceptance = round(acceptance_rate - exp.baseline_acceptance_rate, 1)
                if exp.baseline_response_rate is not None:
                    exp.improvement_response = round(response_rate - exp.baseline_response_rate, 1)
                logger.info(f"[AutoOutreach] Experiment #{exp.experiment_number} DISCARDED: "
                           f"{acceptance_rate:.1f}% <= {exp.baseline_acceptance_rate:.1f}% baseline")
        else:
            # Not enough data yet or no baseline — just record
            exp.decision = "pending"
            exp.status = "evaluating"

        db.commit()
        db.refresh(exp)

        return {
            "experiment_id": exp.id,
            "experiment_number": exp.experiment_number,
            "connections_sent": sent,
            "connections_accepted": accepted,
            "responses_received": responded,
            "acceptance_rate": round(acceptance_rate, 1),
            "response_rate": round(response_rate, 1),
            "baseline_acceptance_rate": exp.baseline_acceptance_rate,
            "decision": exp.decision,
            "improvement_acceptance": exp.improvement_acceptance,
            "improvement_response": exp.improvement_response,
        }

    def propose_next_experiment(self, db: Session, user_id: str) -> Dict[str, Any]:
        """
        Use Claude to analyze past experiments and propose the next prompt variation.
        This is the 'agent proposes a change to train.py' step.
        """
        # Get all past experiments for context
        experiments = db.query(OutreachExperiment).filter(
            OutreachExperiment.user_id == user_id
        ).order_by(OutreachExperiment.experiment_number).all()

        if not experiments:
            # No experiments yet — propose creating a baseline
            return {
                "proposed_name": "exp-001-baseline",
                "hypothesis": "Establish baseline acceptance rate with current prompt",
                "change_description": "No changes — measuring current performance",
                "prompt_template": DEFAULT_CONNECTION_PROMPT,
                "analysis": "No experiments yet. First step: establish a baseline by sending connections with the default prompt template and measuring acceptance rate over 3-5 days."
            }

        # Build experiment history for Claude
        history_lines = []
        for exp in experiments:
            status_icon = {"keep": "KEPT", "discard": "DISCARDED", "baseline": "BASELINE"}.get(exp.decision, "PENDING")
            history_lines.append(
                f"#{exp.experiment_number} | {exp.experiment_name} | "
                f"Accept: {exp.acceptance_rate or '??'}% | Resp: {exp.response_rate or '??'}% | "
                f"Sent: {exp.connections_sent} | Status: {status_icon} | "
                f"Change: {exp.change_description or 'N/A'}"
            )

        # Get current best prompt (last kept or baseline)
        current_baseline = self.get_current_baseline(db, user_id)
        current_prompt = current_baseline.prompt_template if current_baseline else DEFAULT_CONNECTION_PROMPT

        # Get sample messages and their outcomes from the most recent experiment
        recent_exp = experiments[-1]
        sample_leads = db.query(OutreachExperimentLead).filter(
            OutreachExperimentLead.experiment_id == recent_exp.id
        ).limit(15).all()

        message_outcomes = []
        for sl in sample_leads:
            lead = db.query(Lead).filter(Lead.id == sl.lead_id).first()
            outcome = "ACCEPTED" if sl.accepted else ("REJECTED/PENDING" if sl.accepted is False else "PENDING")
            message_outcomes.append(
                f"- [{outcome}] To: {lead.job_title or '?'} at {lead.company_name or '?'} | "
                f"Message: \"{sl.message_sent or 'N/A'}\""
            )

        # Get business profile for context
        profile = db.query(BusinessProfile).filter(
            BusinessProfile.user_id == user_id,
            BusinessProfile.is_default == True
        ).first()

        profile_context = ""
        if profile:
            profile_context = f"""
Business Context:
- Target: {profile.ideal_customer or 'N/A'}
- Industries: {profile.target_industries or 'N/A'}
- Value Prop: {profile.value_proposition or 'N/A'}
- Sender: {profile.sender_name} — {profile.sender_role}
"""

        analysis_prompt = f"""You are an expert at optimizing LinkedIn cold outreach messages for maximum acceptance rate.

You're running an automated experiment loop (inspired by Karpathy's autoresearch):
- Each experiment tests ONE small change to the prompt template
- We measure acceptance_rate (% of connection requests accepted)
- If the new rate beats the baseline → KEEP. Otherwise → DISCARD.
- Changes must be SMALL and TESTABLE — one variable at a time.

{profile_context}

## Experiment History (results.tsv equivalent):
{chr(10).join(history_lines)}

## Current Prompt Template (the "train.py" equivalent):
```
{current_prompt}
```

## Recent Messages and Outcomes:
{chr(10).join(message_outcomes) if message_outcomes else "No message data yet."}

## Your Task:
Analyze the experiment history and message outcomes. Propose ONE specific, small change to the prompt template that could improve acceptance rate.

Think about:
- Which messages got accepted vs rejected? What patterns do you see?
- What's working in the current prompt? Keep that.
- What ONE thing could we tweak? (tone, structure, length, personalization approach, opening style, etc.)
- Be specific — don't say "make it more personal", say exactly HOW.

Return JSON:
{{
  "proposed_name": "exp-NNN-short-description",
  "hypothesis": "Changing X because Y should improve acceptance because Z",
  "change_description": "Changed: [specific diff from current prompt]",
  "prompt_template": "[THE FULL NEW PROMPT TEMPLATE]",
  "analysis": "Detailed analysis of what I observed and why this change should help"
}}"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system="You are an expert growth hacker and copywriter specializing in LinkedIn outreach optimization. Always respond with valid JSON.",
            messages=[{"role": "user", "content": analysis_prompt}]
        )

        response_text = message.content[0].text

        try:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text

            proposal = json.loads(json_str.strip())

            # Fix experiment number in name
            next_num = self.get_next_experiment_number(db, user_id)
            if "proposed_name" in proposal:
                proposal["proposed_name"] = f"exp-{next_num:03d}-{proposal['proposed_name'].split('-', 2)[-1] if '-' in proposal['proposed_name'] else proposal['proposed_name']}"

            return proposal

        except json.JSONDecodeError:
            logger.error(f"Failed to parse Claude proposal: {response_text[:300]}")
            return {
                "proposed_name": f"exp-{self.get_next_experiment_number(db, user_id):03d}-auto",
                "hypothesis": "Auto-generated proposal",
                "change_description": response_text[:500],
                "prompt_template": current_prompt,
                "analysis": response_text
            }

    def get_active_prompt_template(self, db: Session, user_id: str) -> str:
        """
        Get the prompt template to use for the next connection message.
        If an experiment is running, use its template. Otherwise use the current baseline.
        """
        # Check for active experiment
        active = self.get_active_experiment(db, user_id)
        if active:
            return active.prompt_template

        # Use current baseline
        baseline = self.get_current_baseline(db, user_id)
        if baseline:
            return baseline.prompt_template

        # Fallback to default
        return DEFAULT_CONNECTION_PROMPT

    def get_active_experiment_id(self, db: Session, user_id: str) -> Optional[str]:
        """Get the ID of the currently running experiment, if any."""
        active = self.get_active_experiment(db, user_id)
        return active.id if active else None

    def get_dashboard_stats(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Get dashboard statistics for the experiments page."""
        experiments = db.query(OutreachExperiment).filter(
            OutreachExperiment.user_id == user_id
        ).order_by(OutreachExperiment.experiment_number).all()

        if not experiments:
            return {
                "total_experiments": 0,
                "kept_count": 0,
                "discarded_count": 0,
                "running_count": 0,
                "current_baseline_rate": None,
                "best_ever_rate": None,
                "total_improvement": None,
                "experiments": [],
            }

        kept = [e for e in experiments if e.decision == "keep"]
        discarded = [e for e in experiments if e.decision == "discard"]
        running = [e for e in experiments if e.status in ("running", "evaluating")]
        baselines = [e for e in experiments if e.decision == "baseline"]

        # Current baseline rate
        current_baseline = self.get_current_baseline(db, user_id)
        current_rate = current_baseline.acceptance_rate if current_baseline else None

        # Best ever rate
        rates = [e.acceptance_rate for e in experiments if e.acceptance_rate is not None]
        best_rate = max(rates) if rates else None

        # Total improvement from first baseline
        first_baseline = baselines[0] if baselines else None
        total_improvement = None
        if first_baseline and first_baseline.acceptance_rate is not None and current_rate is not None:
            total_improvement = round(current_rate - first_baseline.acceptance_rate, 1)

        return {
            "total_experiments": len(experiments),
            "kept_count": len(kept),
            "discarded_count": len(discarded),
            "running_count": len(running),
            "current_baseline_rate": current_rate,
            "best_ever_rate": best_rate,
            "total_improvement": total_improvement,
            "experiments": experiments,
        }
