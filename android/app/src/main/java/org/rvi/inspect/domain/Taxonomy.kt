package org.rvi.inspect.domain

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
data class Label(val en: String, val hi: String? = null) {
    fun forLang(lang: String) = if (lang.startsWith("hi")) hi ?: en else en
}

@Serializable
data class DefectClass(
    val id: String,
    val category: String,
    val department: String,
    val asset: String,
    val focus_unit: String,
    val label: Label,
    val severity: String,
    val protect_first: Boolean,
    val needs_measurement: Boolean,
    val immediate_action: String,
    val reference: String,
    val beta_enabled: Boolean,
    val domain: String = "track",   // "track" | "ohe" – combined foot patrol
    val danger: String? = null,     // "track" = protect line + SM first; "ohe" = treat as live, TPC first
    val route: String = "",         // supervisor the finding goes to (SSE/P.Way, SSE/TRD …)
)

@Serializable
data class Taxonomy(val version: String, val source: String, val hindi_labels_status: String, val classes: List<DefectClass>) {
    val beta: List<DefectClass> get() = classes.filter { it.beta_enabled }

    /** Simple, transparent search over both languages (no ML). */
    fun search(q: String, lang: String, domain: String = "all"): List<DefectClass> {
        val s = q.trim().lowercase()
        val pool = if (domain == "all") beta else beta.filter { it.domain == domain }
        if (s.isEmpty()) return pool
        return pool.filter { c ->
            listOfNotNull(c.label.en, c.label.hi, c.asset, c.focus_unit, c.id).any { it.lowercase().contains(s) }
        }
    }

    companion object {
        private val json = Json { ignoreUnknownKeys = true }
        fun parse(text: String): Taxonomy = json.decodeFromString(serializer(), text)
    }
}
