package org.rvi.inspect.domain

import org.apache.commons.text.similarity.LevenshteinDistance

/** Closed command vocabulary (English + Hindi, incl. common Hinglish). Speech is transcribed by the
 *  platform recogniser; this maps the transcript to an intent with a fuzzy match (Apache Commons Text).
 *  Safety: no command can report a protect-first defect or bypass protection – those always need a tap. */
sealed interface Command {
    data object Capture : Command
    data object StartPatrol : Command
    data object EndPatrol : Command
    data object Next : Command
    data object Repeat : Command
    data object Danger : Command // opens protection guidance only; never automates protection
    data object Save : Command
    data object Cancel : Command
    data class Defect(val classId: String) : Command
    data class Note(val text: String) : Command
}

object CommandMatcher {
    private val lev = LevenshteinDistance(3)

    private val phrases: Map<Command, List<String>> = mapOf(
        Command.Capture to listOf("capture", "take photo", "photo", "click", "फोटो लो", "फोटो", "फ़ोटो लो", "तस्वीर लो", "कैप्चर"),
        Command.StartPatrol to listOf("start patrol", "start", "गश्त शुरू", "पेट्रोल शुरू", "शुरू करो"),
        Command.EndPatrol to listOf("end patrol", "finish patrol", "stop patrol", "गश्त समाप्त", "गश्त खत्म", "पेट्रोल खत्म"),
        Command.Next to listOf("next", "अगला", "आगे"),
        Command.Repeat to listOf("repeat", "again", "दोहराओ", "फिर से"),
        Command.Danger to listOf("danger", "emergency", "खतरा", "आपातकाल", "इमरजेंसी"),
        Command.Save to listOf("save", "done", "सहेजो", "सेव", "ठीक है"),
        Command.Cancel to listOf("cancel", "रद्द", "रद्द करो", "कैंसल"),
        Command.Defect("PW-FS-001") to listOf("missing clip", "clip missing", "missing erc", "erc missing", "क्लिप गायब", "ईआरसी गायब", "ERC गायब"),
        Command.Defect("PW-FS-002") to listOf("broken clip", "broken erc", "क्लिप टूटा", "ईआरसी टूटा"),
        Command.Defect("PW-JT-001") to listOf("missing bolt", "fish bolt missing", "बोल्ट गायब", "फिश बोल्ट गायब"),
        Command.Defect("PW-JT-003") to listOf("cracked fishplate", "broken fishplate", "फिशप्लेट टूटी", "फिश प्लेट टूटी"),
        Command.Defect("PW-SL-001") to listOf("broken sleeper", "cracked sleeper", "स्लीपर टूटा", "स्लीपर में दरार"),
        Command.Defect("PW-FS-004") to listOf("missing liner", "liner missing", "लाइनर गायब"),
        Command.Defect("PW-BF-007") to listOf("blocked drain", "drain blocked", "नाली बंद", "नाली अवरुद्ध"),
        Command.Defect("PW-BF-008") to listOf("vegetation", "grass", "झाड़ियाँ", "घास"),
        Command.Defect("PW-BF-010") to listOf("encroachment", "अतिक्रमण"),
        Command.Defect("PW-RL-008") to listOf("usfd mark", "one red cross", "यूएसएफडी", "लाल क्रॉस"),
    )

    private val notePrefixes = listOf("note", "remark", "टिप्पणी", "नोट")

    private fun words(s: String) = s.split(' ').count { it.isNotBlank() }

    fun normalise(s: String) = s.lowercase().replace(Regex("[।,.!?]"), " ").replace(Regex("\\s+"), " ").trim()

    /** Returns the best-matching command or null. Exact/contained phrases win; otherwise edit distance <= 2 on short phrases. */
    fun match(transcript: String): Command? {
        val t = normalise(transcript)
        if (t.isEmpty()) return null
        notePrefixes.firstOrNull { t.startsWith("$it ") }?.let { return Command.Note(transcript.trim().substringAfter(' ')) }
        var best: Command? = null
        var bestScore = Int.MAX_VALUE
        var bestLen = 0
        for ((cmd, list) in phrases) for (p in list) {
            val pn = normalise(p)
            val score = when {
                t == pn -> 0
                // phrase inside a short utterance ("please take photo"), not a long unrelated sentence
                t.contains(pn) && pn.length >= 4 && words(t) <= words(pn) + 2 -> 1
                else -> lev.apply(t, pn).let { if (it < 0) 99 else it + 1 }
            }
            // lower score wins; on a tie the longer (more specific) phrase wins
            if (score <= 3 && (score < bestScore || (score == bestScore && pn.length > bestLen))) {
                best = cmd; bestScore = score; bestLen = pn.length
            }
        }
        return best
    }
}
