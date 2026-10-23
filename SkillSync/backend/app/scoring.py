def skill_score(proficiency: int, experience: float, assessment: float) -> float:
    return round(0.5 * (proficiency * 2) + 0.3 * experience + 0.2 * assessment, 2)

def general_score(rows) -> float:
    """rows: list of StudentSkill objects"""
    if not rows:
        return 0.0
    total = sum(skill_score(r.proficiency, r.experience_score, r.assessment_score) for r in rows)
    return round(total / len(rows), 2)
def competition_fit(items: list) -> dict:
    """items: [{skill, weight, score, proficiency, min_level, mandatory}]"""
    total_w = sum(i["weight"] for i in items)
    if not total_w:
        return {"score": 0.0, "eligible": False, "missing": [], "breakdown": []}
    score = sum(i["weight"] * i["score"] for i in items) / total_w
    missing = [i["skill"] for i in items if i["mandatory"] and i["proficiency"] < i["min_level"]]
    return {
        "score": round(score, 2),
        "eligible": not missing,
        "missing": missing,
        "breakdown": [{"skill": i["skill"], "weight": i["weight"], "score": i["score"]} for i in items],
    }
def leadership_score(rows, availability_hours: int) -> float:
    if not rows:
        return 0.0
    exp = sum(r.experience_score for r in rows) / len(rows)
    ass = sum(r.assessment_score for r in rows) / len(rows)
    avail = min(10.0, (availability_hours or 0) / 2)   # 20 hours/week = 10
    return round(0.4 * exp + 0.3 * ass + 0.3 * avail, 2)