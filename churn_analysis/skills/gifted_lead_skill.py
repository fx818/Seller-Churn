"""Gifted Lead Skill — select best qualifying Buy Lead for at-risk seller."""
from datetime import datetime, timedelta, timezone

from .base_skill import Skill, SkillResult


class GiftedLeadSkill(Skill):
    name = "gifted_lead"
    required_inputs = ["glid"]
    optional_inputs = ["hotleads_data", "rca_category", "city", "mcats", "enq_30d"]

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _parse_dt(self, dt_str: str) -> datetime:
        """Parse ISO or common datetime strings; return UTC-aware datetime."""
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(dt_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValueError(f"Unrecognised datetime format: {dt_str!r}")

    def _hours_old(self, posted_dt_str: str, now: datetime) -> float:
        posted = self._parse_dt(posted_dt_str)
        return (now - posted).total_seconds() / 3600.0

    def _rca_routing_bonus(self, lead: dict, rca_category: str, seller_city: str, mcats: list) -> float:
        """Return 1.0 if lead matches RCA routing preference, else 0.5."""
        buyer_city = (lead.get("buyer_city") or "").strip().lower()
        order_value = float(lead.get("order_value") or 0)
        product = (lead.get("product") or "").lower()

        if rca_category == "NO_LEADS":
            return 1.0 if buyer_city != seller_city.lower() else 0.5
        if rca_category == "LOW_ENGAGEMENT":
            # Recency bonus already encoded in score; routing bonus = 1 unconditionally
            # (smallest response window == highest recency == highest recency_bonus already)
            return 1.0
        if rca_category == "PEER_GAP":
            # Caller will pick max order_value; signal it here
            return 1.0 if order_value > 0 else 0.5
        if rca_category == "POOR_CATALOG":
            for mcat in mcats:
                if mcat.lower() in product:
                    return 1.0
            return 0.5
        # default
        return 1.0 if order_value > 0 else 0.5

    # ------------------------------------------------------------------
    # invoke
    # ------------------------------------------------------------------

    def invoke(self, inputs: dict) -> SkillResult:
        hotleads_data = inputs.get("hotleads_data") or {}
        rca_category = (inputs.get("rca_category") or "").upper()
        seller_city = (inputs.get("city") or "").strip()
        mcats = inputs.get("mcats") or []
        if isinstance(mcats, str):
            mcats = [m.strip() for m in mcats.split(",") if m.strip()]

        # Validate hotleads response shape
        if not hotleads_data:
            return SkillResult(
                success=True,
                data={
                    "lead_found": False,
                    "reason": "No hotleads data available",
                    "fallback": "Use peer comparison data as value demonstration",
                    "total_qualifying": 0,
                },
                confidence=0.5,
            )

        items = []
        try:
            items = hotleads_data.get("data", {}).get("items", []) or []
        except AttributeError:
            pass

        if not items:
            return SkillResult(
                success=True,
                data={
                    "lead_found": False,
                    "reason": "No hotleads data available",
                    "fallback": "Use peer comparison data as value demonstration",
                    "total_qualifying": 0,
                },
                confidence=0.5,
            )

        now = datetime.now(timezone.utc)

        # --- Qualification gate ---
        qualifying = []
        for lead in items:
            posted_dt_str = lead.get("posted_dt") or ""
            if not posted_dt_str:
                continue

            try:
                hours = self._hours_old(posted_dt_str, now)
            except ValueError:
                continue

            # Gate 1: within 72 hours
            if hours > 72:
                continue

            # Gate 2: buyer_verified (default True if missing)
            buyer_verified = lead.get("buyer_verified")
            if buyer_verified is None:
                buyer_verified = True
            if buyer_verified is False:
                continue

            # Gate 3: distribution_count < max_distribution (default eligible if missing)
            dist_count = lead.get("distribution_count")
            max_dist = lead.get("max_distribution")
            if dist_count is not None and max_dist is not None:
                if int(dist_count) >= int(max_dist):
                    continue

            # Gate 4: order_value parseable and >= 0
            try:
                order_value = float(lead.get("order_value") or 0)
            except (TypeError, ValueError):
                continue
            if order_value < 0:
                continue

            qualifying.append((lead, hours, order_value))

        if not qualifying:
            # Determine specific reason
            all_hours = []
            for lead in items:
                try:
                    all_hours.append(self._hours_old(lead.get("posted_dt") or "", now))
                except ValueError:
                    pass
            if all_hours and min(all_hours) > 72:
                reason = "No leads within 72h"
            else:
                reason = "No leads pass qualification criteria"

            return SkillResult(
                success=True,
                data={
                    "lead_found": False,
                    "reason": reason,
                    "fallback": "Use peer comparison data as value demonstration",
                    "total_qualifying": 0,
                },
                confidence=0.8,
            )

        # --- Normalise order_value for scoring ---
        max_ov = max(ov for _, _, ov in qualifying) or 1.0

        scored = []
        for lead, hours, order_value in qualifying:
            order_value_normalized = (order_value / max_ov) if max_ov > 0 else 0.0
            recency_bonus = 1.0 - (hours / 72.0)
            rca_bonus = self._rca_routing_bonus(lead, rca_category, seller_city, mcats)
            score = (
                order_value_normalized * 0.4
                + rca_bonus * 0.4
                + recency_bonus * 0.2
            )
            scored.append((score, lead, hours, order_value))

        # --- Pick best ---
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_lead, best_hours, best_ov = scored[0]

        urgency = "high" if best_hours <= 24 else ("medium" if best_hours <= 48 else "low")
        follow_up_dt = now + timedelta(hours=48)
        follow_up_schedule = follow_up_dt.strftime("%Y-%m-%d")

        buyer_verified_out = best_lead.get("buyer_verified")
        if buyer_verified_out is None:
            buyer_verified_out = True

        return SkillResult(
            success=True,
            data={
                "lead_found": True,
                "buyer_city": best_lead.get("buyer_city", ""),
                "product": best_lead.get("product", ""),
                "order_value": best_ov,
                "buyer_verified": buyer_verified_out,
                "posted_hours_ago": round(best_hours, 1),
                "urgency": urgency,
                "follow_up_schedule": follow_up_schedule,
                "rca_routing_used": rca_category or "DEFAULT",
                "total_qualifying": len(qualifying),
            },
            confidence=0.9,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=True,
            data={
                "lead_found": False,
                "reason": "No hotleads data available",
                "fallback": "Use peer comparison data as value demonstration",
                "total_qualifying": 0,
            },
            confidence=0.1,
            used_fallback=True,
        )
