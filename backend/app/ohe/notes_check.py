"""Cross-check AI findings against the patroller's voice / typed notes (EN, HI, Hinglish).

The notes never change what the AI assessed (HLD I-06 isolation holds for the assessment itself); this layer only
compares the two afterwards and reports agreement, so a reviewer sees where the patroller and the AI agree, where
only the AI saw something, and where the patroller reported something the AI did not see."""
import re
from datetime import UTC, datetime, timedelta

# condition -> words a patroller would say for it (lower-case; Devanagari as spoken by Android hi-IN dictation)
TOPICS: dict[str, list[str]] = {
    "insulator_visible_damage": ["insulator", "इंसुलेटर", "इन्सुलेटर", "crack", "chipped", "broken insulator", "flashover",
                                 "टूटा", "टूटी", "दरार", "चटका"],
    "foreign_object": ["kite", "पतंग", "patang", "plastic", "polythene", "पॉलीथिन", "पन्नी", "cloth", "कपड़ा", "kapda",
                       "nest", "घोंसला", "ghonsla", "balloon", "गुब्बारा", "foreign"],
    "vegetation_near_ohe": ["tree", "पेड़", "ped", "branch", "डाली", "डाल", "टहनी", "bush", "झाड़ी", "jhadi", "vegetation",
                            "creeper", "बेल", "grass", "घास"],
    "visible_corrosion": ["rust", "जंग", "zang", "corrosion", "corroded"],
    "mast_lean": ["lean", "tilt", "झुका", "झुकी", "टेढ़ा", "tedha", "jhuka", "bent mast"],
    "loose_stone": ["stone", "पत्थर", "patthar", "boulder", "rock", "चट्टान"],
    "scrap_metal": ["scrap", "rod", "सरिया", "loha", "लोहा", "metal", "pipe", "पाइप", "wire coil"],
    "animal_near_track": ["cow", "गाय", "dog", "कुत्ता", "animal", "जानवर", "monkey", "बंदर", "buffalo", "भैंस", "goat", "बकरी"],
    "fire_or_smoke": ["fire", "आग", "aag", "smoke", "धुआं", "धुआँ", "burning", "जल रहा"],
    "waterlogging": ["water", "पानी", "pani", "waterlogging", "जलभराव", "flood", "puddle"],
}
# conditions that the same words cover (one note word can confirm a related AI condition)
ALIASES = {"scene_foreign_object": "foreign_object", "branch_near_ohe": "vegetation_near_ohe",
           "creeper_on_structure": "vegetation_near_ohe", "anomaly": None}
ALL_OK = ["no defect", "no problem", "all ok", "all okay", "all fine", "everything fine", "koi kami nahi", "sab theek",
          "कोई कमी नहीं", "सब ठीक", "ठीक है", "कोई समस्या नहीं"]
WINDOW = timedelta(minutes=10)


def topic_of(condition: str | None) -> str | None:
    if not condition:
        return None
    return ALIASES.get(condition, condition) if condition in ALIASES else condition


def _has(t: str, w: str) -> bool:
    # Latin words as whole words ("rod" must not match "road"); Devanagari as written (inflections attach)
    return re.search(r"\b" + re.escape(w) + r"s?\b", t) is not None if w.isascii() else w in t


def topics(text: str) -> set[str]:
    t = re.sub(r"\s+", " ", text.lower())
    return {c for c, words in TOPICS.items() if any(_has(t, w) for w in words)}


def says_all_ok(text: str) -> bool:
    t = text.lower()
    return any(_has(t, p) for p in ALL_OK) and not topics(text)


def _aware(d) -> datetime | None:
    if d is None:
        return None
    if isinstance(d, str):
        d = datetime.fromisoformat(d)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def cross_check(findings: list[dict], notes: list[dict], media_time: dict[str, datetime]) -> dict:
    """findings: report findings (need 'condition', 'media_ids'); notes: {'id','text','at'}; media_time: media id ->
    capture time. Adds 'note_check' to each finding and returns the report section."""
    ns = [{"id": n["id"], "text": n["text"], "at": _aware(n.get("at")), "topics": topics(n["text"]),
           "ok": says_all_ok(n["text"])} for n in notes]
    timed = all(n["at"] is not None for n in ns)

    def near(f, n):
        if not timed or n["at"] is None:
            return True               # no times: compare across the whole patrol
        ts = [_aware(media_time.get(m)) for m in f.get("media_ids", [])]
        return any(t is not None and abs(t - n["at"]) <= WINDOW for t in ts) or not any(ts)

    used: set[tuple[str, str]] = set()
    for f in findings:
        tp = topic_of(f.get("condition"))
        agree = [n for n in ns if tp and tp in n["topics"] and near(f, n)]
        deny = [n for n in ns if n["ok"] and near(f, n)]
        if agree:
            f["note_check"] = {"state": "matches_note", "notes": [n["id"] for n in agree], "T": 1.0}
            used |= {(n["id"], tp) for n in agree}
        elif deny:
            f["note_check"] = {"state": "conflicts_with_note", "notes": [n["id"] for n in deny], "T": 0.0,
                               "statement": "The patroller's note says no problem here; the AI found one. Check the photo."}
        else:
            f["note_check"] = {"state": "ai_only", "notes": [], "T": None}
        f["confidence_level"] = level(f)
    note_only = [{"note_id": n["id"], "topic": tp, "text": n["text"][:200], "at": n["at"]}
                 for n in ns for tp in sorted(n["topics"]) if (n["id"], tp) not in used]
    st = lambda s: sum(f.get("note_check", {}).get("state") == s for f in findings)
    return {"state": "compared" if ns else "no_notes", "notes": len(ns),
            "matches_note": st("matches_note"), "ai_only": st("ai_only"), "conflicts_with_note": st("conflicts_with_note"),
            "note_only": note_only,
            "statement": ("No patroller notes for this patrol; findings are AI only." if not ns else
                          f"{st('matches_note')} findings match the patroller's notes, {st('ai_only')} are AI only, "
                          f"{st('conflicts_with_note')} conflict with a note; {len(note_only)} things the patroller "
                          "mentioned were not found by the AI and need a look.")}


def level(f: dict) -> dict:
    """One confidence level for a finding from the confidence vector: model score (calibrated when fitted) x photo
    quality, raised when the patroller's note agrees and lowered when it conflicts. Labels: High / Medium / Low."""
    c = f.get("confidence", {})
    score = c.get("C")
    if score is None:
        return {"label": "Low", "score": None, "basis": "no model score"}
    score = float(score) * (1.0 if (c.get("Q") or 1.0) >= 1.0 else 0.8)
    t = (f.get("note_check") or {}).get("T")
    if t == 1.0:
        score = min(1.0, score + 0.15)
    elif t == 0.0:
        score = max(0.0, score - 0.2)
    label = "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"
    basis = [c.get("calibration", "uncalibrated"), "photo quality ok" if (c.get("Q") or 1) >= 1 else "photo quality low"]
    if t == 1.0:
        basis.append("matches patroller note")
    elif t == 0.0:
        basis.append("conflicts with patroller note")
    return {"label": label, "score": round(score, 3), "basis": ", ".join(basis)}
