"""AI Bridge layer for the Campus Event Assistant.

Handles communication with the LLM API when credentials are available.
Falls back to a rule-based response generator when they are not.
Never exposes passwords, secrets, payment credentials, or private tokens.
"""

import os
import json
import re
from datetime import datetime


class AIBridge:
    """AI integration layer for the campus assistant.

    When AI API credentials are available, sends structured data
    to the LLM for natural language response generation.
    When credentials are missing, uses a deterministic rule-based
    fallback that never fabricates information.
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AI_API_KEY") or os.getenv("LLM_API_KEY")
        self.model = os.getenv("AI_MODEL", "gpt-4o-mini")
        self.base_url = os.getenv("AI_BASE_URL", "")
        self.available = bool(self.api_key)
        self.fallback_active = not self.available

    def is_available(self):
        """Check if AI API credentials are configured."""
        return self.available

    def get_status_message(self):
        """Return a human-readable status of the AI engine."""
        if self.available:
            return f"🤖 AI Engine: Active ({self.model})"
        return "🤖 AI Engine: Rule-based (API credentials not configured)"

    def generate_response(self, user_message: str, resolved_query: dict) -> str:
        """Generate a natural language response from resolved query data.

        Args:
            user_message: The original user message.
            resolved_query: The output from CampusAssistantService.resolve_query().

        Returns:
            A natural language response string.
        """
        if self.available:
            return self._ai_generate(user_message, resolved_query)
        return self._rule_based_generate(user_message, resolved_query)

    def _ai_generate(self, user_message: str, resolved_query: dict) -> str:
        """Generate response using LLM API."""
        try:
            import openai

            system_prompt = self._build_system_prompt(resolved_query)
            user_prompt = self._build_user_prompt(user_message, resolved_query)

            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url or None,
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=800,
            )

            return response.choices[0].message.content.strip()

        except Exception as exc:
            # If AI API fails, gracefully fall back to rule-based
            return self._rule_based_generate(user_message, resolved_query)

    def _build_system_prompt(self, resolved_query: dict) -> str:
        """Build the system prompt with role context and data."""
        role = resolved_query.get("context", {}).get("role", "student")
        data = resolved_query.get("data")

        # Build data summary for the AI
        data_summary = ""
        if data:
            if isinstance(data, dict):
                data_summary = json.dumps(data, indent=2, default=str)
            else:
                data_summary = str(data)

        return f"""You are the AGC Campus Event Assistant, a helpful and knowledgeable AI assistant for the Amritsar Group of Colleges (AGC) campus event management system.

You are assisting a user with role: {role}.

IMPORTANT RULES:
1. Answer ONLY based on the provided data. NEVER fabricate information.
2. If the data says "I couldn't find that information in ACEMS" or contains an error about access denied, relay that exactly.
3. NEVER mention passwords, secrets, payment credentials, API keys, tokens, or any sensitive information.
4. NEVER expose any raw database queries or internal system details.
5. If data is empty or missing, say "I couldn't find that information in ACEMS."
6. Keep responses concise, friendly, and helpful.
7. Use the user's name from context when appropriate.
8. Format data clearly with bullet points or tables when listing multiple items.
9. For dates, format them in a readable way (e.g., "15 September 2026").
10. If you have relevant data, present it clearly and offer follow-up suggestions.

Here is the structured data retrieved from ACEMS:
---DATA START---
{data_summary}
---DATA END---

Now respond to the user's query based ONLY on this data."""

    def _build_user_prompt(self, user_message: str, resolved_query: dict) -> str:
        """Build the user prompt."""
        intent = resolved_query.get("intent", "general")
        error = resolved_query.get("error")

        prompt_parts = [f"User asked: {user_message}"]

        if error:
            prompt_parts.append(f"\nSystem note: {error}")

        return "\n".join(prompt_parts)

    def _rule_based_generate(self, user_message: str, resolved_query: dict) -> str:
        """Generate response using deterministic rules when AI API is unavailable.

        This NEVER fabricates information. It only reports what's in the data.
        """
        intent = resolved_query.get("intent", "general")
        data = resolved_query.get("data")
        error = resolved_query.get("error")
        context = resolved_query.get("context", {})
        role = context.get("role", "student")
        user_name = context.get("user_name", "there")

        # Handle errors first
        if error:
            return error

        if not data:
            return "I couldn't find that information in ACEMS."

        # Route based on intent
        if intent in ("upcoming_events", "events_this_week", "technical_events", "events_by_category"):
            return self._format_events(data, user_name)

        elif intent == "my_registrations":
            return self._format_registrations(data, user_name)

        elif intent == "next_event":
            return self._format_next_event(data, user_name)

        elif intent == "attendance_count":
            return self._format_attendance(data, user_name)

        elif intent == "certificates":
            return self._format_certificates(data, user_name)

        elif intent in ("organizer_events", "my_events"):
            return self._format_organizer_events(data, user_name)

        elif intent == "event_registrations":
            return self._format_registrations_for_event(data, user_name)

        elif intent == "seats_left":
            return self._format_seats(data, user_name)

        elif intent == "volunteers":
            return self._format_volunteers(data, user_name)

        elif intent in ("weekly_events", "campus_events"):
            return self._format_events(data, user_name)

        elif intent == "venue_utilization":
            return self._format_venues(data, user_name)

        elif intent == "event_conflicts":
            return self._format_conflicts(data, user_name)

        elif intent == "recommendations":
            return self._format_recommendations(data, user_name)

        elif intent == "user_stats":
            return self._format_user_stats(data, user_name)

        elif intent == "announcements":
            return self._format_announcements(data, user_name)

        elif intent == "profile":
            return self._format_profile(data, user_name)

        elif intent == "unauthorized":
            return data if isinstance(data, str) else "I couldn't find that information in ACEMS."

        else:
            # Default: try to present whatever data we have
            return self._format_generic(data, user_name)

    def _format_events(self, data: dict, user_name: str) -> str:
        """Format events data for display."""
        events = data.get("events", []) if isinstance(data, dict) else []
        count = data.get("count", len(events)) if isinstance(data, dict) else len(events)

        if not events:
            return "I couldn't find that information in ACEMS."

        lines = [f"Here are {count} upcoming event{'s' if count != 1 else ''}:"]
        for e in events:
            fee_info = f", Fee: ₹{e['fee']}" if e.get("fee", 0) > 0 else ""
            lines.append(
                f"• {e['title']} ({e.get('category', 'N/A')}) — "
                f"{e.get('date', 'N/A')} at {e.get('start_time', 'N/A')}, "
                f"{e.get('venue', 'N/A')} | Seats left: {e.get('seats_left', 'N/A')}{fee_info}"
            )
        lines.append(f"\nLet me know if you'd like details about any of these!")
        return "\n".join(lines)

    def _format_registrations(self, data: dict, user_name: str) -> str:
        """Format registrations data for display."""
        regs = data.get("registrations", []) if isinstance(data, dict) else []
        count = data.get("count", len(regs)) if isinstance(data, dict) else len(regs)

        if not regs:
            return "I couldn't find that information in ACEMS. You haven't registered for any events yet."

        lines = [f"You have {count} registration{'s' if count != 1 else ''}:"]
        for r in regs:
            status_emoji = "✅" if r["status"] == "confirmed" else "⏳" if r["status"] == "pending" else "❌"
            attended_emoji = "✔" if r["attended"] else " "
            lines.append(
                f"{status_emoji} {r['event_title']} — {r['event_date']} at {r['event_venue']} | "
                f"Status: {r['status']} | Attended: {attended_emoji}"
            )
        return "\n".join(lines)

    def _format_next_event(self, data: dict | None, user_name: str) -> str:
        """Format next event data."""
        if not data:
            return "I couldn't find that information in ACEMS. You don't have any upcoming events registered."

        return (
            f"Your next event is:\n"
            f"🎯 **{data['title']}** ({data.get('category', 'N/A')})\n"
            f"📅 Date: {data['date']}\n"
            f"⏰ Time: {data.get('start_time', 'N/A')}\n"
            f"📍 Venue: {data.get('venue', 'N/A')}\n"
            f"Status: {data.get('status', 'N/A')}"
        )

    def _format_attendance(self, data: dict, user_name: str) -> str:
        """Format attendance count data."""
        if not data:
            return "I couldn't find that information in ACEMS."

        return (
            f"Your attendance summary:\n"
            f"✅ Attended: {data.get('attended', 0)} event{'s' if data.get('attended', 0) != 1 else ''}\n"
            f"📋 Total registered: {data.get('total_registered', 0)} event{'s' if data.get('total_registered', 0) != 1 else ''}\n"
            f"📅 Upcoming: {data.get('upcoming', 0)} event{'s' if data.get('upcoming', 0) != 1 else ''}"
        )

    def _format_certificates(self, data: dict, user_name: str) -> str:
        """Format certificates data."""
        certs = data.get("certificates", []) if isinstance(data, dict) else []
        count = data.get("count", len(certs)) if isinstance(data, dict) else len(certs)

        if not certs:
            return "I couldn't find that information in ACEMS. You don't have any certificates yet."

        lines = [f"You have {count} certificate{'s' if count != 1 else ''}:"]
        for c in certs:
            verified_badge = " ✅ Verified" if c.get("verified") else " ⏳ Pending"
            lines.append(
                f"🎓 {c['achievement']} — {c['event_title']} ({c['event_date']}){verified_badge}"
            )
        return "\n".join(lines)

    def _format_organizer_events(self, data: dict, user_name: str) -> str:
        """Format organizer events data."""
        events = data.get("events", []) if isinstance(data, dict) else []
        count = data.get("count", len(events)) if isinstance(data, dict) else len(events)

        if not events:
            return "I couldn't find that information in ACEMS. You don't have any events organized yet."

        lines = [f"You have {count} event{'s' if count != 1 else ''}:"]
        for e in events:
            lines.append(
                f"• {e['title']} ({e.get('category', 'N/A')}) — "
                f"{e.get('date', 'N/A')} | {e.get('registered', 0)}/{e.get('capacity', 'N/A')} registered | "
                f"Seats left: {e.get('seats_left', 'N/A')} | Status: {e.get('status', 'N/A')}"
            )
        return "\n".join(lines)

    def _format_registrations_for_event(self, data: dict, user_name: str) -> str:
        """Format registrations for a specific event."""
        if "error" in data:
            return data["error"]

        regs = data.get("registrations", [])
        stats = data.get("stats", {})

        if not regs:
            return "No students registered for this event yet."

        lines = [f"Registrations for this event:"]
        for r in regs:
            status_emoji = "✅" if r["status"] == "confirmed" else "⏳" if r["status"] == "pending" else "❌"
            attended_emoji = "✔" if r["attended"] else " "
            lines.append(
                f"{status_emoji} {r['student_name']} (Roll: {r['roll_no']}) — "
                f"Status: {r['status']} | Attended: {attended_emoji}"
            )

        if stats:
            lines.append("")
            lines.append("📊 Statistics:")
            for k, v in stats.items():
                lines.append(f"  {k}: {v}")

        return "\n".join(lines)

    def _format_seats(self, data: dict, user_name: str) -> str:
        """Format seat availability data."""
        if "error" in data:
            return data["error"]

        if not data:
            return "I couldn't find that information in ACEMS."

        is_full = "🔴 FULL" if data.get("is_full") else "🟢 Available"
        return (
            f"Seat availability for {data.get('title', 'event')}:\n"
            f"Capacity: {data.get('capacity', 'N/A')}\n"
            f"Registered: {data.get('registered', 0)}\n"
            f"Seats left: {data.get('seats_left', 0)}\n"
            f"Status: {is_full}"
        )

    def _format_volunteers(self, data: dict, user_name: str) -> str:
        """Format volunteers data."""
        if "error" in data:
            return data["error"]

        volunteers = data.get("volunteers", [])
        count = data.get("count", len(volunteers))

        if not volunteers:
            return "No volunteers assigned to this event yet."

        lines = [f"Volunteers ({count}):"]
        for v in volunteers:
            status_emoji = "✅" if v["status"].lower() == "assigned" else " "
            lines.append(
                f"{status_emoji} {v['name']} — {v['task']} ({v['status']})"
            )
        return "\n".join(lines)

    def _format_venues(self, data: dict, user_name: str) -> str:
        """Format venue utilization data."""
        venues = data.get("venues", []) if isinstance(data, dict) else []

        if not venues:
            return "I couldn't find that information in ACEMS."

        lines = ["Venue utilization:"]
        for v in venues:
            bar = "█" * int(v.get("utilization_pct", 0) / 10) + "░" * (10 - int(v.get("utilization_pct", 0) // 10))
            label = "🔴 Heavily utilized" if v.get("utilization_pct", 0) > 80 else "🟡 Moderate" if v.get("utilization_pct", 0) > 50 else "🟢 Available"
            lines.append(
                f"• {v['venue_name']} ({v.get('building', 'N/A')}) — "
                f"Utilization: {bar} {v.get('utilization_pct', 0)}% — {label}"
            )
        return "\n".join(lines)

    def _format_conflicts(self, data: dict, user_name: str) -> str:
        """Format event conflict data."""
        conflicts = data.get("conflicts", []) if isinstance(data, dict) else []
        count = data.get("count", len(conflicts)) if isinstance(data, dict) else len(conflicts)

        if not conflicts:
            return "No event conflicts detected this week. All schedules look clear!"

        lines = [f"⚠️ {count} potential conflict{'s' if count != 1 else ''} detected:"]
        for c in conflicts:
            severity_emoji = "🔴" if c.get("severity") == "high" else "🟡" if c.get("severity") == "medium" else "🟢"
            lines.append(
                f"{severity_emoji} {c['event_1']['title']} vs {c['event_2']['title']}\n"
                f"   Date: {c.get('date', 'N/A')} | Venue: {c.get('venue', 'N/A')} | Type: {c.get('type', 'N/A')}"
            )
        return "\n".join(lines)

    def _format_recommendations(self, data: dict, user_name: str) -> str:
        """Format recommendations data."""
        recs = data.get("recommendations", []) if isinstance(data, dict) else []

        if not recs:
            return "I couldn't find that information in ACEMS."

        lines = [f"Based on your profile, you might enjoy these {len(recs)} event{'s' if len(recs) != 1 else ''}:"]
        for r in recs:
            score_bar = "★" * int(r.get("score", 0) / 10) + "☆" * (10 - int(r.get("score", 0) // 10))
            lines.append(
                f"• {r['title']} ({r.get('category', 'N/A')}) — "
                f"{r.get('date', 'N/A')} at {r.get('venue', 'N/A')} | "
                f"Match: {score_bar} ({r.get('score', 0)}%)"
            )
        return "\n".join(lines)

    def _format_user_stats(self, data: dict, user_name: str) -> str:
        """Format user statistics."""
        if not data:
            return "I couldn't find that information in ACEMS."

        lines = ["Campus user statistics:"]
        for k, v in data.items():
            label = k.replace("_", " ").title()
            lines.append(f"• {label}: {v}")
        return "\n".join(lines)

    def _format_announcements(self, data: dict, user_name: str) -> str:
        """Format announcements data."""
        announcements = data.get("announcements", []) if isinstance(data, dict) else []

        if not announcements:
            return "I couldn't find that information in ACEMS."

        lines = ["📢 Latest announcements:"]
        for a in announcements:
            lines.append(f"• {a['title']} ({a.get('category', 'N/A')}) — {a.get('published_at', 'N/A')}")
        return "\n".join(lines)

    def _format_profile(self, data: dict, user_name: str) -> str:
        """Format user profile data."""
        if not data:
            return "I couldn't find that information in ACEMS."

        lines = ["Your profile:"]
        for k, v in data.items():
            if k == "name":
                continue
            label = k.replace("_", " ").title()
            lines.append(f"• {label}: {v}")
        return "\n".join(lines)

    def _format_generic(self, data: dict, user_name: str) -> str:
        """Generic formatter for unknown intents."""
        if isinstance(data, dict) and "error" in data:
            return data["error"]
        if not data:
            return "I couldn't find that information in ACEMS."
        return f"Here's what I found: {data}"
