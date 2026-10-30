package org.rvi.inspect.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.CloudDone
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material.icons.outlined.Inbox
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
import androidx.compose.material.icons.outlined.ReportProblem
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Stop
import androidx.compose.material.icons.outlined.Straighten
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.rvi.inspect.R
import org.rvi.inspect.domain.DefectClass
import org.rvi.inspect.ui.components.AmbientBackground
import org.rvi.inspect.ui.components.Chip
import org.rvi.inspect.ui.components.Eyebrow
import org.rvi.inspect.ui.components.GhostButton
import org.rvi.inspect.ui.components.GlassCard
import org.rvi.inspect.ui.components.GlassRoundButton
import org.rvi.inspect.ui.components.PrimaryButton
import org.rvi.inspect.ui.theme.Grey

private val Pad = Modifier.statusBarsPadding().navigationBarsPadding().padding(horizontal = 20.dp)

@Composable
private fun TopBar(title: String, trailing: @Composable () -> Unit = {}) {
    Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(title, style = MaterialTheme.typography.titleLarge, color = Grey.White, modifier = Modifier.weight(1f))
        trailing()
    }
}

// ---------------------------------------------------------------- Home
data class HomeState(val name: String, val beatFrom: String, val beatTo: String, val line: String, val patrolType: String,
                     val active: Boolean, val pending: Int, val online: Boolean)

@Composable
fun HomeScreen(s: HomeState, onStart: () -> Unit, onResume: () -> Unit, onSettings: () -> Unit, onReview: () -> Unit) = AmbientBackground {
    Column(Pad.verticalScroll(rememberScrollState())) {
        TopBar(stringResource(R.string.app_name)) {
            Surface(onClick = onReview, shape = CircleShape, color = Grey.GlassFill, contentColor = Grey.White, border = BorderStroke(1.dp, Grey.GlassStroke)) {
                Icon(Icons.Outlined.Inbox, stringResource(R.string.review_inbox), Modifier.padding(12.dp))
            }
            Spacer(Modifier.width(8.dp))
            Surface(onClick = onSettings, shape = CircleShape, color = Grey.GlassFill, contentColor = Grey.White, border = BorderStroke(1.dp, Grey.GlassStroke)) {
                Icon(Icons.Outlined.Settings, stringResource(R.string.settings), Modifier.padding(12.dp))
            }
        }
        Spacer(Modifier.height(24.dp))
        Text(stringResource(R.string.greeting, s.name), style = MaterialTheme.typography.displaySmall, color = Grey.White)
        Spacer(Modifier.height(28.dp))
        GlassCard(Modifier.fillMaxWidth(), strong = true) {
            Eyebrow(stringResource(R.string.today_beat))
            Spacer(Modifier.height(10.dp))
            Text(stringResource(R.string.beat_range, s.beatFrom, s.beatTo, s.line), style = MaterialTheme.typography.headlineSmall, color = Grey.White)
            Spacer(Modifier.height(16.dp))
            HorizontalDivider(color = Grey.GlassStroke)
            Spacer(Modifier.height(16.dp))
            Eyebrow(stringResource(R.string.patrol_type))
            Spacer(Modifier.height(6.dp))
            Text(s.patrolType, style = MaterialTheme.typography.bodyLarge, color = Grey.G200)
            Spacer(Modifier.height(24.dp))
            if (s.active) PrimaryButton(stringResource(R.string.resume_patrol), onResume)
            else PrimaryButton(stringResource(R.string.start_patrol), onStart)
        }
        Spacer(Modifier.height(16.dp))
        GlassCard(Modifier.fillMaxWidth()) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(if (s.online) Icons.Outlined.CloudDone else Icons.Outlined.CloudOff, null, tint = Grey.G200)
                Spacer(Modifier.width(12.dp))
                Text(
                    when { !s.online -> stringResource(R.string.offline); s.pending > 0 -> stringResource(R.string.sync_pending, s.pending); else -> stringResource(R.string.sync_done) },
                    style = MaterialTheme.typography.bodyMedium, color = Grey.G200,
                )
            }
        }
        Spacer(Modifier.height(16.dp))
        Text(stringResource(R.string.ai_disclaimer), style = MaterialTheme.typography.labelMedium, color = Grey.G500)
    }
}

// ---------------------------------------------------------------- Kit check
@Composable
fun KitCheckScreen(checked: List<Boolean>, onToggle: (Int) -> Unit, onConfirm: () -> Unit) = AmbientBackground {
    val items = listOf(R.string.kit_flags, R.string.kit_detonators, R.string.kit_tools, R.string.kit_spares, R.string.kit_book, R.string.kit_gps)
    Column(Pad) {
        TopBar(stringResource(R.string.kit_check))
        Text(stringResource(R.string.kit_check_hint), style = MaterialTheme.typography.bodyMedium, color = Grey.G300)
        Spacer(Modifier.height(20.dp))
        GlassCard(Modifier.fillMaxWidth(), padding = 8.dp) {
            items.forEachIndexed { i, r ->
                Surface(onClick = { onToggle(i) }, color = androidx.compose.ui.graphics.Color.Transparent, contentColor = Grey.White, shape = RoundedCornerShape(16.dp)) {
                    Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(if (checked[i]) Icons.Outlined.CheckCircle else Icons.Outlined.RadioButtonUnchecked, null, tint = if (checked[i]) Grey.White else Grey.G500)
                        Spacer(Modifier.width(14.dp))
                        Text(stringResource(r), style = MaterialTheme.typography.bodyLarge, color = if (checked[i]) Grey.White else Grey.G300)
                    }
                }
            }
        }
        Spacer(Modifier.weight(1f))
        PrimaryButton(stringResource(R.string.kit_confirm), onConfirm, enabled = checked.all { it })
        Spacer(Modifier.height(16.dp))
    }
}

// ---------------------------------------------------------------- Patrol HUD (camera preview behind = real translucency)
@Composable
fun PatrolHud(km: String, findings: Int, listening: Boolean, heard: String?, onCapture: () -> Unit, onVoice: () -> Unit,
              onDanger: () -> Unit, onEnd: () -> Unit, background: @Composable () -> Unit) {
    Box(Modifier.fillMaxSize().background(Grey.G950)) {
        background()
        Column(Pad.fillMaxSize()) {
            GlassCard(Modifier.fillMaxWidth().padding(top = 12.dp), strong = true, padding = 16.dp) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(10.dp).background(Grey.White, CircleShape))
                    Spacer(Modifier.width(10.dp))
                    Text(stringResource(R.string.patrol_live), style = MaterialTheme.typography.labelLarge, color = Grey.White, modifier = Modifier.weight(1f))
                    Text(stringResource(R.string.findings_count, findings), style = MaterialTheme.typography.labelMedium, color = Grey.G200)
                }
                Spacer(Modifier.height(8.dp))
                Text(stringResource(R.string.km_now, km), style = MaterialTheme.typography.displaySmall, color = Grey.White)
            }
            Spacer(Modifier.weight(1f))
            if (listening || heard != null) {
                GlassCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                    Text(if (listening) stringResource(R.string.listening) else "“$heard”", style = MaterialTheme.typography.bodyLarge, color = Grey.White)
                    Text(stringResource(R.string.say_command), style = MaterialTheme.typography.labelMedium, color = Grey.G400)
                }
                Spacer(Modifier.height(12.dp))
            }
            GlassCard(Modifier.fillMaxWidth().padding(bottom = 12.dp), padding = 18.dp) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.Bottom) {
                    GlassRoundButton(Icons.Outlined.ReportProblem, stringResource(R.string.danger_title).trimEnd('?'), onDanger, size = 60.dp)
                    GlassRoundButton(Icons.Outlined.CameraAlt, stringResource(R.string.capture), onCapture, size = 88.dp, filled = true)
                    GlassRoundButton(Icons.Outlined.Mic, stringResource(R.string.voice), onVoice, size = 60.dp)
                }
                Spacer(Modifier.height(14.dp))
                GhostButton(stringResource(R.string.end_patrol), onEnd, Modifier.fillMaxWidth(), Icons.Outlined.Stop)
            }
        }
    }
}

/** Protect-first guidance. It never replaces protection; it records that it was done. */
@Composable
fun DangerSheet(protectedDone: Boolean, smDone: Boolean, onProtected: () -> Unit, onSm: () -> Unit, onContinue: () -> Unit) {
    Box(Modifier.fillMaxSize().background(Grey.Scrim), contentAlignment = Alignment.BottomCenter) {
        GlassCard(Pad.fillMaxWidth().padding(bottom = 16.dp), strong = true) {
            Text(stringResource(R.string.danger_title), style = MaterialTheme.typography.headlineSmall, color = Grey.White)
            Spacer(Modifier.height(12.dp))
            Text(stringResource(R.string.danger_body), style = MaterialTheme.typography.bodyLarge, color = Grey.G200)
            Spacer(Modifier.height(18.dp))
            CheckRow(stringResource(R.string.danger_protected), protectedDone, onProtected)
            CheckRow(stringResource(R.string.danger_sm), smDone, onSm)
            Spacer(Modifier.height(16.dp))
            PrimaryButton(stringResource(R.string.capture), onContinue, icon = Icons.Outlined.CameraAlt, enabled = protectedDone && smDone)
        }
    }
}

@Composable
private fun CheckRow(text: String, done: Boolean, onClick: () -> Unit) {
    Surface(onClick = onClick, color = androidx.compose.ui.graphics.Color.Transparent, contentColor = Grey.White) {
        Row(Modifier.fillMaxWidth().padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(if (done) Icons.Outlined.CheckCircle else Icons.Outlined.RadioButtonUnchecked, null)
            Spacer(Modifier.width(12.dp))
            Text(text, style = MaterialTheme.typography.bodyLarge)
        }
    }
}

// ---------------------------------------------------------------- Classify & locate
data class ClassifyState(val lang: String, val query: String, val suggested: List<DefectClass>, val results: List<DefectClass>,
                         val selected: DefectClass?, val qualityOk: Boolean?, val km: String, val line: String, val rail: String,
                         val action: String, val note: String, val gnss: String?)

@Composable
fun ClassifyScreen(s: ClassifyState, onQuery: (String) -> Unit, onSelect: (DefectClass) -> Unit, onKm: (String) -> Unit,
                   onLine: (String) -> Unit, onRail: (String) -> Unit, onAction: (String) -> Unit, onNote: (String) -> Unit,
                   onDictate: () -> Unit, onSave: () -> Unit) = AmbientBackground {
    LazyColumn(Pad.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { TopBar(stringResource(R.string.classify)) }
        item {
            s.qualityOk?.let { ok ->
                GlassCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(if (ok) Icons.Outlined.CheckCircle else Icons.Outlined.ReportProblem, null, tint = Grey.White)
                        Spacer(Modifier.width(10.dp))
                        Text(stringResource(if (ok) R.string.quality_ok else R.string.quality_retake), style = MaterialTheme.typography.bodyMedium, color = Grey.White)
                    }
                }
            }
        }
        item { GlassField(s.query, onQuery, stringResource(R.string.search_defects), leading = { Icon(Icons.Outlined.Search, null, tint = Grey.G400) }) }
        if (s.query.isBlank() && s.suggested.isNotEmpty()) item {
            Eyebrow(stringResource(R.string.suggested))
            Spacer(Modifier.height(8.dp))
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(s.suggested, key = { it.id }) { c -> Chip(c.label.forLang(s.lang), selected = s.selected?.id == c.id) { onSelect(c) } }
            }
        }
        item { Eyebrow(stringResource(R.string.all_defects)) }
        items(s.results.take(12), key = { it.id }) { c -> DefectRow(c, s.lang, s.selected?.id == c.id) { onSelect(c) } }
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Eyebrow(stringResource(R.string.location))
                Spacer(Modifier.height(10.dp))
                GlassField(s.km, onKm, stringResource(R.string.km_post))
                s.gnss?.let { Text(it, style = MaterialTheme.typography.labelMedium, color = Grey.G400, modifier = Modifier.padding(top = 6.dp)) }
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(stringResource(R.string.line), style = MaterialTheme.typography.labelMedium, color = Grey.G400)
                    listOf("UP", "DN", "LOOP").forEach { Chip(it, s.line == it) { onLine(it) } }
                }
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(stringResource(R.string.rail), style = MaterialTheme.typography.labelMedium, color = Grey.G400)
                    Chip(stringResource(R.string.rail_left), s.rail == "L") { onRail("L") }
                    Chip(stringResource(R.string.rail_right), s.rail == "R") { onRail("R") }
                    Chip(stringResource(R.string.rail_both), s.rail == "B") { onRail("B") }
                }
            }
        }
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                GlassField(s.action, onAction, stringResource(R.string.action_taken))
                Spacer(Modifier.height(10.dp))
                GlassField(s.note, onNote, stringResource(R.string.note))
                Spacer(Modifier.height(10.dp))
                GhostButton(stringResource(R.string.dictate), onDictate, icon = Icons.Outlined.Mic)
            }
        }
        item {
            PrimaryButton(stringResource(R.string.save_finding), onSave, enabled = s.selected != null && s.km.isNotBlank())
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun DefectRow(c: DefectClass, lang: String, selected: Boolean, onClick: () -> Unit) {
    Surface(onClick = onClick, shape = RoundedCornerShape(18.dp), color = if (selected) Grey.GlassFillStrong else Grey.GlassFill,
        contentColor = Grey.White, border = BorderStroke(1.dp, if (selected) Grey.White else Grey.GlassStroke), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(c.label.forLang(lang), style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text("${c.id} · ${c.focus_unit}", style = MaterialTheme.typography.labelMedium, color = Grey.G400, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (c.protect_first) Tag(stringResource(R.string.protect_first), Icons.Outlined.ReportProblem)
                if (c.needs_measurement) Tag(stringResource(R.string.needs_measurement), Icons.Outlined.Straighten)
            }
            Spacer(Modifier.width(8.dp))
            Box(Modifier.size(28.dp).border(1.dp, Grey.GlassStroke, CircleShape), contentAlignment = Alignment.Center) {
                Text(c.category, style = MaterialTheme.typography.labelMedium, color = Grey.G200)
            }
        }
    }
}

@Composable
private fun Tag(text: String, icon: androidx.compose.ui.graphics.vector.ImageVector) {
    Row(Modifier.padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, Modifier.size(14.dp), tint = Grey.G200)
        Spacer(Modifier.width(6.dp))
        Text(text, style = MaterialTheme.typography.labelSmall, color = Grey.G200)
    }
}

@Composable
fun GlassField(value: String, onChange: (String) -> Unit, label: String, leading: (@Composable () -> Unit)? = null) {
    OutlinedTextField(value, onChange, Modifier.fillMaxWidth(), label = { Text(label) }, leadingIcon = leading, singleLine = true,
        shape = RoundedCornerShape(16.dp), textStyle = MaterialTheme.typography.bodyLarge,
        colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Grey.White, unfocusedBorderColor = Grey.GlassStroke,
            focusedContainerColor = Grey.GlassFill, unfocusedContainerColor = Grey.GlassFill, focusedLabelColor = Grey.White,
            unfocusedLabelColor = Grey.G400, cursorColor = Grey.White, focusedTextColor = Grey.White, unfocusedTextColor = Grey.White))
}

// ---------------------------------------------------------------- Summary (keyman book)
data class BookRow(val km: String, val defect: String, val action: String, val protectedFirst: Boolean)

@Composable
fun SummaryScreen(rows: List<BookRow>, onSubmit: () -> Unit) = AmbientBackground {
    Column(Pad.fillMaxSize()) {
        TopBar(stringResource(R.string.summary))
        Eyebrow(stringResource(R.string.keyman_book))
        Spacer(Modifier.height(10.dp))
        GlassCard(Modifier.fillMaxWidth().weight(1f), padding = 4.dp) {
            LazyColumn {
                items(rows) { r ->
                    Column(Modifier.padding(16.dp)) {
                        Text("km ${r.km}", style = MaterialTheme.typography.labelMedium, color = Grey.G400)
                        Text(r.defect, style = MaterialTheme.typography.titleMedium, color = Grey.White)
                        if (r.action.isNotBlank()) Text(r.action, style = MaterialTheme.typography.bodyMedium, color = Grey.G300)
                    }
                    HorizontalDivider(color = Grey.GlassStroke)
                }
            }
        }
        Spacer(Modifier.height(16.dp))
        PrimaryButton(stringResource(R.string.submit), onSubmit)
        Spacer(Modifier.height(16.dp))
    }
}

// ---------------------------------------------------------------- Review inbox (JE/SSE)
data class ReviewItem(val id: String, val km: String, val defect: String, val category: String, val by: String, val note: String)

@Composable
fun ReviewScreen(list: List<ReviewItem>, severity: Map<String, String>, onSeverity: (String, String) -> Unit, onConfirm: (String) -> Unit, onReject: (String) -> Unit) = AmbientBackground {
    LazyColumn(Pad.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { TopBar(stringResource(R.string.review_inbox)) }
        item { Text(stringResource(R.string.ai_disclaimer), style = MaterialTheme.typography.labelMedium, color = Grey.G400) }
        items(list, key = { r -> r.id }) { item ->
            GlassCard(Modifier.fillMaxWidth()) {
                Row { Text("km ${item.km}", style = MaterialTheme.typography.labelMedium, color = Grey.G400, modifier = Modifier.weight(1f)); Text(item.by, style = MaterialTheme.typography.labelMedium, color = Grey.G400) }
                Spacer(Modifier.height(6.dp))
                Text(item.defect, style = MaterialTheme.typography.titleMedium, color = Grey.White)
                if (item.note.isNotBlank()) Text(item.note, style = MaterialTheme.typography.bodyMedium, color = Grey.G300)
                Spacer(Modifier.height(12.dp))
                Eyebrow(stringResource(R.string.severity))
                Spacer(Modifier.height(6.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("RF-P1", "RF-P2", "RF-P3", "RF-P4").forEach { sv -> Chip(sv, severity[item.id] == sv) { onSeverity(item.id, sv) } }
                }
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    GhostButton(stringResource(R.string.reject), { onReject(item.id) }, Modifier.weight(1f))
                    PrimaryButton(stringResource(R.string.confirm), { onConfirm(item.id) }, Modifier.weight(1f), enabled = severity[item.id] != null)
                }
            }
        }
    }
}

// ---------------------------------------------------------------- Settings
data class SettingsState(val lang: String, val voice: Boolean, val tts: Boolean, val largeText: Boolean, val haptics: Boolean)

@Composable
fun SettingsScreen(s: SettingsState, onLang: (String) -> Unit, onToggle: (String, Boolean) -> Unit) = AmbientBackground {
    Column(Pad.verticalScroll(rememberScrollState())) {
        TopBar(stringResource(R.string.settings))
        GlassCard(Modifier.fillMaxWidth()) {
            Eyebrow(stringResource(R.string.language))
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Chip("English", s.lang.startsWith("en")) { onLang("en-IN") }
                Chip("हिन्दी", s.lang.startsWith("hi")) { onLang("hi-IN") }
            }
        }
        Spacer(Modifier.height(14.dp))
        GlassCard(Modifier.fillMaxWidth(), padding = 8.dp) {
            Toggle(stringResource(R.string.voice_commands), s.voice) { onToggle("voice", it) }
            Toggle(stringResource(R.string.spoken_feedback), s.tts) { onToggle("tts", it) }
            Toggle(stringResource(R.string.large_text), s.largeText) { onToggle("large", it) }
            Toggle(stringResource(R.string.haptics), s.haptics) { onToggle("haptics", it) }
        }
    }
}

@Composable
private fun Toggle(text: String, on: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(text, style = MaterialTheme.typography.bodyLarge, color = Grey.White, modifier = Modifier.weight(1f))
        Switch(on, onChange, colors = SwitchDefaults.colors(checkedThumbColor = Grey.G950, checkedTrackColor = Grey.White,
            uncheckedThumbColor = Grey.G300, uncheckedTrackColor = Grey.G800, uncheckedBorderColor = Grey.G700))
    }
}
