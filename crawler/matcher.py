# crawler/matcher.py
import json
import re

from crawler.database import DEFAULT_DB_PATH, get_connection, init_database


DEFAULT_PREFERENCES_PATH = "config/user_preferences.json"


def run_matching_analysis(
    preferences_path=DEFAULT_PREFERENCES_PATH,
    db_path=DEFAULT_DB_PATH,
    limit=None,
):
    init_database(db_path)
    preferences = load_preferences(preferences_path)

    with get_connection(db_path) as conn:
        user_profile_id = upsert_user_profile(conn, preferences["profile_name"])
        save_keyword_preferences(conn, user_profile_id, preferences)
        jobs = get_match_candidate_jobs(conn, limit=limit)
        clear_non_detail_match_results(conn, user_profile_id)

        result = {
            "profile_id": user_profile_id,
            "target": len(jobs),
            "analyzed": 0,
        }

        for job in jobs:
            analysis = analyze_job(job, preferences)
            upsert_match_result(conn, user_profile_id, job["id"], analysis)
            result["analyzed"] += 1

    return result


def load_preferences(preferences_path=DEFAULT_PREFERENCES_PATH):
    with open(preferences_path, "r", encoding="utf-8") as f:
        preferences = json.load(f)

    preferences.setdefault("profile_name", "Default Radar")
    preferences.setdefault("preferences", {})
    preferences.setdefault("weights", {})
    preferences.setdefault("recommendation_levels", [])
    ensure_preference_defaults(preferences["preferences"])
    return preferences


def upsert_user_profile(conn, profile_name):
    row = conn.execute(
        """
        SELECT id
        FROM user_profiles
        WHERE name = ?
        ORDER BY id
        LIMIT 1
        """,
        (profile_name,),
    ).fetchone()
    if row:
        conn.execute(
            """
            UPDATE user_profiles
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (row["id"],),
        )
        return row["id"]

    cursor = conn.execute(
        """
        INSERT INTO user_profiles (name)
        VALUES (?)
        """,
        (profile_name,),
    )
    return cursor.lastrowid


def save_keyword_preferences(conn, user_profile_id, preferences):
    for category, preference_type, keyword, weight in iter_preference_keywords(preferences):
        cleaned = clean_text(keyword)
        if not cleaned:
            continue

        stored_type = f"{category}:{preference_type}"
        conn.execute(
            """
            INSERT INTO user_preference_keywords (
                user_profile_id, keyword, preference_type, weight
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_profile_id, keyword, preference_type)
            DO UPDATE SET
                weight = excluded.weight,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_profile_id, cleaned, stored_type, weight),
        )


def get_match_candidate_jobs(conn, limit=None):
    sql = """
        SELECT
            id,
            title,
            location,
            career,
            education,
            employment_type,
            summary_text,
            description_text,
            main_tasks,
            qualifications,
            preferred_conditions,
            benefits,
            skill_candidates,
            detail_status
        FROM job_postings
        WHERE source = 'jobkorea'
          AND detail_status = 'success'
          AND detail_collected_at IS NOT NULL
          AND (
                deadline_date IS NULL
                OR deadline_date = ''
                OR deadline_date >= date('now', '+9 hours')
              )
        ORDER BY
            detail_collected_at DESC,
            id DESC
    """
    params = []
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    return conn.execute(sql, params).fetchall()


def clear_non_detail_match_results(conn, user_profile_id):
    conn.execute(
        """
        DELETE FROM job_match_results
        WHERE job_posting_id IN (
                SELECT id
                FROM job_postings
                WHERE source = 'jobkorea'
                  AND (
                        detail_status IS NULL
                        OR detail_status != 'success'
                        OR detail_collected_at IS NULL
                  )
          )
        """
    )


def analyze_job(job, preferences):
    pref = preferences["preferences"]
    weights = preferences["weights"]
    context = build_match_context(job)

    score = weights.get("base_score", 10)
    matched_keywords = []
    missing_keywords = []
    positive_reasons = []
    negative_reasons = []

    if job["detail_status"] == "success":
        bonus = weights.get("detail_completed_bonus", 5)
        score += bonus
        positive_reasons.append(f"상세 페이지 수집 완료: +{bonus}점")

    score += score_job_category(context, pref, weights, matched_keywords, missing_keywords, positive_reasons, negative_reasons)
    score += score_location(context, pref, weights, matched_keywords, missing_keywords, positive_reasons, negative_reasons)
    score += score_career(context, pref, weights, matched_keywords, missing_keywords, positive_reasons, negative_reasons)
    score += score_education(context, pref, weights, matched_keywords, missing_keywords, positive_reasons, negative_reasons)
    score += score_employment_type(context, pref, weights, matched_keywords, missing_keywords, positive_reasons, negative_reasons)
    score += score_career_goal_boosts(
        context,
        pref,
        weights,
        matched_keywords,
        positive_reasons,
    )
    score += score_fullstack_combination(context, pref, weights, matched_keywords, positive_reasons)
    score += score_skill_keywords(context, pref, weights, matched_keywords, missing_keywords, positive_reasons)
    score += score_low_priority_qa(context, pref, weights, matched_keywords, negative_reasons)
    score += score_penalties(context, pref, weights, matched_keywords, negative_reasons)

    raw_score = int(round(score))
    match_score = apply_score_compression(raw_score, weights)
    recommendation_level = get_recommendation_level(
        match_score,
        preferences.get("recommendation_levels", []),
    )

    return {
        "raw_score": raw_score,
        "match_score": match_score,
        "matched_keywords": unique_preserve_order(matched_keywords),
        "missing_keywords": unique_preserve_order(missing_keywords),
        "positive_reasons": positive_reasons,
        "negative_reasons": negative_reasons,
        "recommendation_level": recommendation_level,
        "reason": build_reason(match_score, recommendation_level, positive_reasons, negative_reasons),
    }


def score_job_category(context, pref, weights, matched_keywords, missing_keywords, positive_reasons, negative_reasons):
    job_pref = pref["job_categories"]
    score = 0

    primary = job_pref.get("primary", "")
    if contains_keyword(context["job_text"], primary):
        value = weights.get("job_primary", 25)
        score += value
        matched_keywords.append(primary)
        positive_reasons.append(f"{primary} 직무 일치: +{value}점")

    matched = match_any(context["job_text"], job_pref.get("preferred", []))
    if matched:
        low_priority = job_pref.get("low_priority", [])
        value = (
            weights.get("job_low_priority", 3)
            if matched in low_priority
            else weights.get("job_preferred", 18)
        )
        score += value
        matched_keywords.append(matched)
        positive_reasons.append(f"JobKorea 희망 직무 '{matched}' 일치: +{value}점")
        return score

    penalty = weights.get("missing_job_category", -15)
    score += penalty
    missing_keywords.append(primary or "AI·개발·데이터")
    negative_reasons.append(f"AI·개발·데이터 계열 직무를 확인하지 못했습니다: {penalty}점")
    return score


def score_location(context, pref, weights, matched_keywords, missing_keywords, positive_reasons, negative_reasons):
    return score_preferred_avoid_category(
        label="근무지역",
        text=context["location_text"],
        preferred=pref["locations"]["preferred"],
        avoid=pref["locations"]["avoid"],
        preferred_weight=weights.get("location_preferred", 18),
        missing_weight=weights.get("missing_location", -12),
        avoid_weight=weights.get("avoid_location", -20),
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        positive_reasons=positive_reasons,
        negative_reasons=negative_reasons,
    )


def score_career(context, pref, weights, matched_keywords, missing_keywords, positive_reasons, negative_reasons):
    career_text = expand_career_text(context["career_text"])
    return score_preferred_avoid_category(
        label="경력",
        text=career_text,
        preferred=pref["career"]["preferred"],
        avoid=pref["career"]["avoid"],
        preferred_weight=weights.get("career_preferred", 16),
        missing_weight=weights.get("missing_career", -10),
        avoid_weight=weights.get("avoid_career", -20),
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        positive_reasons=positive_reasons,
        negative_reasons=negative_reasons,
    )


def score_education(context, pref, weights, matched_keywords, missing_keywords, positive_reasons, negative_reasons):
    return score_preferred_avoid_category(
        label="학력",
        text=context["education_text"],
        preferred=pref["education"]["preferred"],
        avoid=pref["education"]["avoid"],
        preferred_weight=weights.get("education_preferred", 10),
        missing_weight=weights.get("missing_education", -4),
        avoid_weight=weights.get("avoid_education", -10),
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        positive_reasons=positive_reasons,
        negative_reasons=negative_reasons,
    )


def score_employment_type(context, pref, weights, matched_keywords, missing_keywords, positive_reasons, negative_reasons):
    return score_preferred_avoid_category(
        label="고용형태",
        text=context["employment_text"],
        preferred=pref["employment_types"]["preferred"],
        avoid=pref["employment_types"]["avoid"],
        preferred_weight=weights.get("employment_type_preferred", 16),
        missing_weight=weights.get("missing_employment_type", -10),
        avoid_weight=weights.get("avoid_employment_type", -25),
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        positive_reasons=positive_reasons,
        negative_reasons=negative_reasons,
    )


def score_skill_keywords(context, pref, weights, matched_keywords, missing_keywords, positive_reasons):
    score = 0
    weight = weights.get("skill_preferred", 4)
    bonus_cap = weights.get("skill_bonus_cap", 20)

    for keyword in pref["skill_keywords"]["preferred"]:
        if contains_keyword(context["skill_text"], keyword):
            matched_keywords.append(keyword)
            awarded = min(weight, max(0, bonus_cap - score))
            if awarded > 0:
                score += awarded
                positive_reasons.append(
                    f"보조 기술 키워드 '{keyword}' 확인: +{awarded}점"
                )
        else:
            missing_keywords.append(keyword)

    return score


def score_career_goal_boosts(
    context,
    pref,
    weights,
    matched_keywords,
    positive_reasons,
):
    score = 0
    boost_groups = pref.get("career_goal_boosts", {})
    bonus_cap = weights.get("career_goal_bonus_cap", 30)

    for group in boost_groups.values():
        label = group.get("label", "커리어 목표")
        weight = group.get("weight", 0)
        keywords = group.get("keywords", [])
        matched = match_any(context["all_text"], keywords)
        if not matched:
            continue

        matched_keywords.append(matched)
        awarded = min(weight, max(0, bonus_cap - score))
        if awarded > 0:
            score += awarded
            positive_reasons.append(
                f"{label} 관련 키워드 '{matched}' 일치: +{awarded}점"
            )

    return score


def score_fullstack_combination(context, pref, weights, matched_keywords, positive_reasons):
    boost_groups = pref.get("career_goal_boosts", {})
    frontend = boost_groups.get("frontend_web", {}).get("keywords", [])
    backend = boost_groups.get("backend", {}).get("keywords", [])

    if match_any(context["all_text"], frontend) and match_any(context["all_text"], backend):
        value = weights.get("fullstack_combination_bonus", 10)
        matched_keywords.append("frontend+backend")
        positive_reasons.append(f"프론트엔드와 백엔드 키워드 동시 확인: +{value}점")
        return value

    return 0


def score_low_priority_qa(context, pref, weights, matched_keywords, negative_reasons):
    boost_groups = pref.get("career_goal_boosts", {})
    qa_keywords = boost_groups.get("qa_experience", {}).get("keywords", [])
    primary_groups = [
        boost_groups.get("frontend_web", {}).get("keywords", []),
        boost_groups.get("backend", {}).get("keywords", []),
        boost_groups.get("fullstack_web_service", {}).get("keywords", []),
        boost_groups.get("ai_llm_automation", {}).get("keywords", []),
        boost_groups.get("pm_service_planning", {}).get("keywords", []),
    ]

    qa_matched = match_any(context["all_text"], qa_keywords)
    if not qa_matched:
        return 0

    has_growth_keyword = any(match_any(context["all_text"], keywords) for keywords in primary_groups)
    if has_growth_keyword:
        return 0

    penalty = weights.get("qa_only_penalty", -18)
    matched_keywords.append(qa_matched)
    negative_reasons.append(f"단순 QA/테스트 중심 공고로 판단되어 우선순위 하향: {penalty}점")
    return penalty


def score_penalties(context, pref, weights, matched_keywords, negative_reasons):
    score = 0
    severity_weights = {
        "critical": weights.get("penalty_critical", -45),
        "major": weights.get("penalty_major", -25),
        "minor": weights.get("penalty_minor", -10),
    }

    for severity, keywords in pref["penalties"].items():
        penalty = severity_weights.get(severity, -10)
        for keyword in keywords:
            if contains_keyword(context["all_text"], keyword):
                matched_keywords.append(keyword)
                score += penalty
                negative_reasons.append(f"감점 키워드({severity}) '{keyword}' 감지: {penalty}점")

    return score


def score_preferred_avoid_category(
    label,
    text,
    preferred,
    avoid,
    preferred_weight,
    missing_weight,
    avoid_weight,
    matched_keywords,
    missing_keywords,
    positive_reasons,
    negative_reasons,
):
    score = 0

    avoided = match_any(text, avoid)
    if avoided:
        score += avoid_weight
        matched_keywords.append(avoided)
        negative_reasons.append(f"{label} 회피 조건 '{avoided}' 감지: {avoid_weight}점")

    matched = match_any(text, preferred)
    if matched:
        score += preferred_weight
        matched_keywords.append(matched)
        positive_reasons.append(f"{label} '{matched}' 일치: +{preferred_weight}점")
        return score

    score += missing_weight
    missing_keywords.extend(preferred)
    negative_reasons.append(f"{label} 희망 조건({', '.join(preferred)})과 일치하는 값을 확인하지 못했습니다: {missing_weight}점")
    return score


def upsert_match_result(conn, user_profile_id, job_posting_id, analysis):
    conn.execute(
        """
        INSERT INTO job_match_results (
            user_profile_id,
            job_posting_id,
            score,
            match_score,
            raw_score,
            matched_keywords_json,
            missing_keywords_json,
            positive_reasons_json,
            negative_reasons_json,
            recommendation_level,
            reason,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(user_profile_id, job_posting_id)
        DO UPDATE SET
            score = excluded.score,
            match_score = excluded.match_score,
            raw_score = excluded.raw_score,
            matched_keywords_json = excluded.matched_keywords_json,
            missing_keywords_json = excluded.missing_keywords_json,
            positive_reasons_json = excluded.positive_reasons_json,
            negative_reasons_json = excluded.negative_reasons_json,
            recommendation_level = excluded.recommendation_level,
            reason = excluded.reason,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            user_profile_id,
            job_posting_id,
            analysis["match_score"],
            analysis["match_score"],
            analysis["raw_score"],
            json.dumps(analysis["matched_keywords"], ensure_ascii=False),
            json.dumps(analysis["missing_keywords"], ensure_ascii=False),
            json.dumps(analysis["positive_reasons"], ensure_ascii=False),
            json.dumps(analysis["negative_reasons"], ensure_ascii=False),
            analysis["recommendation_level"],
            analysis["reason"],
        ),
    )


def iter_preference_keywords(preferences):
    pref = preferences["preferences"]
    weights = preferences["weights"]

    for keyword in pref["job_categories"].get("preferred", []):
        yield "job_categories", "preferred", keyword, weights.get("job_preferred", 18)

    for category in ["locations", "career", "education", "employment_types"]:
        for preference_type, keywords in pref[category].items():
            weight = get_category_weight(category, preference_type, weights)
            for keyword in keywords:
                yield category, preference_type, keyword, weight

    for keyword in pref["skill_keywords"].get("preferred", []):
        yield "skill_keywords", "preferred", keyword, weights.get("skill_preferred", 4)

    for group_name, group in pref.get("career_goal_boosts", {}).items():
        weight = group.get("weight", 0)
        for keyword in group.get("keywords", []):
            yield "career_goal_boosts", group_name, keyword, weight

    for severity, keywords in pref["penalties"].items():
        weight = weights.get(f"penalty_{severity}", -10)
        for keyword in keywords:
            yield "penalties", severity, keyword, weight


def get_category_weight(category, preference_type, weights):
    key_map = {
        ("locations", "preferred"): "location_preferred",
        ("locations", "avoid"): "avoid_location",
        ("career", "preferred"): "career_preferred",
        ("career", "avoid"): "avoid_career",
        ("education", "preferred"): "education_preferred",
        ("education", "avoid"): "avoid_education",
        ("employment_types", "preferred"): "employment_type_preferred",
        ("employment_types", "avoid"): "avoid_employment_type",
    }
    return weights.get(key_map.get((category, preference_type), ""), 1)


def build_match_context(job):
    title = clean_text(job["title"])
    location = clean_text(job["location"])
    career = clean_text(job["career"])
    education = clean_text(job["education"])
    employment_type = clean_text(job["employment_type"])
    summary = clean_text(job["summary_text"])
    description = clean_text(job["description_text"])
    main_tasks = clean_text(job["main_tasks"])
    qualifications = clean_text(job["qualifications"])
    preferred_conditions = clean_text(job["preferred_conditions"])
    benefits = clean_text(job["benefits"])
    skill_candidates = clean_text(job["skill_candidates"])

    detail_text = "\n".join(
        [
            summary,
            description,
            main_tasks,
            qualifications,
            preferred_conditions,
            benefits,
            skill_candidates,
        ]
    )
    all_text = "\n".join([title, location, career, education, employment_type, detail_text])

    return {
        "all_text": all_text,
        "job_text": "\n".join([title, summary, description, main_tasks]),
        "skill_text": "\n".join([title, summary, description, qualifications, skill_candidates]),
        "location_text": location if location else detail_text,
        "career_text": career if career else detail_text,
        "education_text": education if education else detail_text,
        "employment_text": employment_type if employment_type else detail_text,
    }


def expand_career_text(text):
    expanded = clean_text(text)
    match = re.search(r"경력\s*(\d+)년", expanded)
    if not match:
        match = re.search(r"경력(\d+)년", expanded)

    if match:
        year = int(match.group(1))
        expanded += f"\n경력{year}년"
        if 1 <= year <= 3:
            expanded += "\n1~3년"

    return expanded


def match_any(text, keywords):
    for keyword in keywords:
        if contains_keyword(text, keyword):
            return keyword
    return ""


def contains_keyword(text, keyword):
    cleaned_keyword = clean_text(keyword)
    cleaned_text = clean_text(text)
    if not cleaned_keyword or not cleaned_text:
        return False

    if is_ascii_keyword(cleaned_keyword):
        pattern = rf"(?<![A-Za-z0-9]){re.escape(cleaned_keyword)}(?![A-Za-z0-9])"
        return re.search(pattern, cleaned_text, flags=re.IGNORECASE) is not None

    return cleaned_keyword.lower() in cleaned_text.lower()


def is_ascii_keyword(keyword):
    return all(ord(char) < 128 for char in keyword) and any(char.isalpha() for char in keyword)


def get_recommendation_level(score, levels):
    sorted_levels = sorted(levels, key=lambda item: item.get("min_score", 0), reverse=True)
    for item in sorted_levels:
        if score >= item.get("min_score", 0):
            return item.get("level", "low")
    return "low"


def build_reason(score, level, positive_reasons, negative_reasons):
    positive_summary = " ".join(positive_reasons[:5]) or "일치한 희망 조건이 충분하지 않습니다."
    negative_summary = " ".join(negative_reasons[:4]) or "큰 감점 요인은 확인되지 않았습니다."
    return f"점수 {score}점, 추천 등급 {level}. {positive_summary} {negative_summary}"


def clamp_score(score):
    return max(0, min(100, int(round(score))))


def apply_score_compression(score, weights):
    start = float(weights.get("score_compression_start", 75))
    ratio = float(weights.get("score_compression_ratio", 0.25))
    ratio = max(0.0, min(1.0, ratio))

    compressed = score
    if score > start:
        compressed = start + ((score - start) * ratio)

    return clamp_score(compressed)


def unique_preserve_order(values):
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


def clean_text(value):
    return str(value).strip() if value is not None else ""


def ensure_preference_defaults(pref):
    pref.setdefault("job_categories", {})
    pref["job_categories"].setdefault("primary", "AI·개발·데이터")
    pref["job_categories"].setdefault("preferred", [])
    pref.setdefault("locations", {})
    pref["locations"].setdefault("preferred", [])
    pref["locations"].setdefault("avoid", [])
    pref.setdefault("career", {})
    pref["career"].setdefault("preferred", [])
    pref["career"].setdefault("avoid", [])
    pref.setdefault("education", {})
    pref["education"].setdefault("preferred", [])
    pref["education"].setdefault("avoid", [])
    pref.setdefault("employment_types", {})
    pref["employment_types"].setdefault("preferred", [])
    pref["employment_types"].setdefault("avoid", [])
    pref.setdefault("skill_keywords", {})
    pref["skill_keywords"].setdefault("preferred", [])
    pref.setdefault("career_goal_boosts", {})
    pref.setdefault("penalties", {})
    pref["penalties"].setdefault("critical", [])
    pref["penalties"].setdefault("major", [])
    pref["penalties"].setdefault("minor", [])
