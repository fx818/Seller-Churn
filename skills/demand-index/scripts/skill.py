"""SKILL 4 — DemandIndexSkill: Buyer demand health in seller's category+city."""
from churn_analysis.skills.base_skill import Skill, SkillResult

HIGH_RISK_CITIES = {
    "lucknow", "kanpur", "saharanpur", "surat", "jaipur",
    "agra", "meerut", "bareilly", "moradabad",
}
HIGH_RISK_CATEGORIES = {
    "apparel", "textile", "textiles", "garments", "fabric", "cloth",
    "readymade", "saree", "kurti", "leggings",
}


def _linear_slope(values: list) -> float:
    """Simple slope of values over their index positions."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(values) / n
    num   = sum((x - mx) * (y - my) for x, y in zip(xs, values))
    denom = sum((x - mx) ** 2 for x in xs)
    return round(num / denom, 4) if denom else 0.0


class DemandIndexSkill(Skill):
    name = "demand-index"
    version = "1.0"
    required_inputs = ["glid"]
    optional_inputs = [
        "city", "enterprise", "ctype", "mcats",
        "total_bl_market", "total_paid_market", "monthly_enq",
    ]

    def invoke(self, inputs: dict) -> SkillResult:
        city           = (inputs.get("city") or "").lower().strip()
        enterprise     = (inputs.get("enterprise") or "").strip()
        ctype          = (inputs.get("ctype") or "").strip()
        mcats          = inputs.get("mcats") or []
        total_bl       = inputs.get("total_bl_market") or 0
        total_paid     = inputs.get("total_paid_market") or 1
        monthly_enq    = inputs.get("monthly_enq") or []

        # Market BL per paid seller
        bl_per_seller = round(total_bl / max(total_paid, 1), 2)

        # Trend slope over monthly_enq
        slope = _linear_slope(monthly_enq) if monthly_enq else 0.0
        if slope > 0.5:
            trend = "growing"
        elif slope < -0.5:
            trend = "declining"
        else:
            trend = "flat"

        # City risk prior
        is_high_risk_city = city in HIGH_RISK_CITIES
        city_risk_prior   = 15 if is_high_risk_city else 0

        # Category risk
        mcat_lower = " ".join(m.lower() for m in mcats)
        is_high_risk_cat = any(kw in mcat_lower for kw in HIGH_RISK_CATEGORIES)
        is_proprietor    = "proprietor" in enterprise.lower()

        # Demand index: 0=bad, 100=great
        # Base: market bl density
        if bl_per_seller >= 20:
            base = 80
        elif bl_per_seller >= 10:
            base = 60
        elif bl_per_seller >= 5:
            base = 40
        else:
            base = 20

        # Adjust for trend
        trend_adj = 15 if trend == "growing" else (-15 if trend == "declining" else 0)
        # Adjust for city + category risk
        risk_adj = -(city_risk_prior + (10 if is_high_risk_cat and is_proprietor else 0))

        demand_index = max(0, min(100, base + trend_adj + risk_adj))

        if demand_index >= 60:
            demand_tier = "Green"
        elif demand_index >= 35:
            demand_tier = "Amber"
        else:
            demand_tier = "Red"

        if demand_tier == "Red":
            recommended_action = "Suggest national geography expansion; highlight metro buyer demand"
        elif demand_tier == "Amber":
            recommended_action = "Expand to nearby cities; improve catalog to capture existing demand"
        else:
            recommended_action = "Focus on reply rate and CQS to convert available leads"

        explanation = (
            f"Market has {bl_per_seller} BLs per paid seller, trend is {trend}."
            + (f" High-risk city ({city}) adds downward prior." if is_high_risk_city else "")
        )

        return SkillResult(
            success=True,
            data={
                "demand_index":       demand_index,
                "demand_tier":        demand_tier,
                "market_bl_per_seller": bl_per_seller,
                "trend":              trend,
                "trend_slope":        slope,
                "is_high_risk_city":  is_high_risk_city,
                "city_risk_prior":    city_risk_prior,
                "is_high_risk_category": is_high_risk_cat,
                "demand_explanation": explanation,
                "recommended_action": recommended_action,
            },
            confidence=0.75 if total_bl > 0 else 0.3,
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False,
            data={"demand_index": None, "demand_tier": "Unknown"},
            error=str(error), confidence=0.1, used_fallback=True,
        )
