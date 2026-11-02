package org.rvi.inspect.ui.screens

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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.CloudDone
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material.icons.outlined.EditNote
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Stop
import androidx.compose.material.icons.outlined.ZoomIn
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import org.rvi.inspect.R
import org.rvi.inspect.data.Prompt
import org.rvi.inspect.ui.OheSummary
import org.rvi.inspect.ui.components.AmbientBackground
import org.rvi.inspect.ui.components.Eyebrow
import org.rvi.inspect.ui.components.GhostButton
import org.rvi.inspect.ui.components.GlassCard
import org.rvi.inspect.ui.components.GlassRoundButton
import org.rvi.inspect.ui.components.PrimaryButton
import org.rvi.inspect.ui.theme.Grey

private val OPad = Modifier.statusBarsPadding().navigationBarsPadding().padding(horizontal = 20.dp)

fun promptRes(p: Prompt): Int = when (p) {
    Prompt.ZOOM -> R.string.prompt_zoom
    Prompt.PLATE -> R.string.prompt_plate
    Prompt.WHOLE -> R.string.prompt_whole
    Prompt.BLUR -> R.string.prompt_blur
    Prompt.DARK -> R.string.prompt_dark
    Prompt.BRIGHT -> R.string.prompt_bright
}

data class OheHomeState(val inspector: String, val territory: String, val server: String, val active: Boolean, val pending: Int)

@Composable
fun OheHomeScreen(st: OheHomeState, onTerritory: (String) -> Unit, onServer: (String) -> Unit, onInspector: (String) -> Unit,
                  onStart: () -> Unit, onResume: () -> Unit, onSettings: () -> Unit, onLastReport: (() -> Unit)?) {
    AmbientBackground {
        Column(OPad.fillMaxSize().verticalScroll(rememberScrollState())) {
            Spacer(Modifier.height(20.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Eyebrow(stringResource(R.string.ohe_app_eyebrow))
                    Text(stringResource(R.string.ohe_app_title), style = MaterialTheme.typography.headlineMedium, color = Grey.White)
                }
                GlassRoundButton(Icons.Outlined.Settings, stringResource(R.string.settings), onSettings, size = 48.dp)
            }
            Spacer(Modifier.height(20.dp))
            GlassCard(Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.ohe_how), style = MaterialTheme.typography.bodyLarge, color = Grey.G200)
            }
            Spacer(Modifier.height(16.dp))
            GlassCard(Modifier.fillMaxWidth()) {
                Field(stringResource(R.string.ohe_inspector), st.inspector, onInspector)
                Spacer(Modifier.height(10.dp))
                Field(stringResource(R.string.ohe_section), st.territory, onTerritory)
                Spacer(Modifier.height(10.dp))
                Field(stringResource(R.string.ohe_server), st.server, onServer)
            }
            Spacer(Modifier.height(16.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(if (st.pending == 0) Icons.Outlined.CloudDone else Icons.Outlined.CloudOff, null, tint = Grey.G300, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text(if (st.pending == 0) stringResource(R.string.ohe_all_uploaded) else stringResource(R.string.ohe_pending, st.pending),
                    style = MaterialTheme.typography.labelMedium, color = Grey.G300)
            }
            Spacer(Modifier.weight(1f, fill = true))
            Spacer(Modifier.height(20.dp))
            if (st.active) PrimaryButton(stringResource(R.string.ohe_resume), onResume, Modifier.fillMaxWidth(), Icons.Outlined.PlayArrow)
            else PrimaryButton(stringResource(R.string.ohe_start), onStart, Modifier.fillMaxWidth(), Icons.Outlined.PlayArrow)
            if (onLastReport != null) {
                Spacer(Modifier.height(10.dp))
                GhostButton(stringResource(R.string.ohe_last_patrol), onLastReport, Modifier.fillMaxWidth())
            }
            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun Field(label: String, value: String, onChange: (String) -> Unit) {
    OutlinedTextField(value, onChange, Modifier.fillMaxWidth(), label = { Text(label) }, singleLine = true)
}

data class OheHudState(val photos: Int, val uploaded: Int, val flagged: Int, val alerts: Int, val notes: Int, val prompt: Prompt?,
                       val listening: Boolean, val heard: String?)

@Composable
fun OheHud(st: OheHudState, onCapture: () -> Unit, onVoice: () -> Unit, onNote: () -> Unit, onEnd: () -> Unit, background: @Composable () -> Unit) {
    Box(Modifier.fillMaxSize().background(Grey.G950)) {
        background()
        Column(OPad.fillMaxSize()) {
            GlassCard(Modifier.fillMaxWidth().padding(top = 12.dp), strong = true, padding = 16.dp) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(10.dp).background(Grey.White, CircleShape))
                    Spacer(Modifier.width(10.dp))
                    Text(stringResource(R.string.ohe_live), style = MaterialTheme.typography.labelLarge, color = Grey.White, modifier = Modifier.weight(1f))
                    Text(stringResource(R.string.ohe_uploaded_of, st.uploaded, st.photos), style = MaterialTheme.typography.labelMedium, color = Grey.G200)
                }
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(18.dp)) {
                    Stat(st.photos.toString(), stringResource(R.string.ohe_photos))
                    Stat(st.flagged.toString(), stringResource(R.string.ohe_flagged))
                    Stat(st.alerts.toString(), stringResource(R.string.ohe_urgent))
                    Stat(st.notes.toString(), stringResource(R.string.ohe_notes))
                }
            }
            Spacer(Modifier.weight(1f))
            st.prompt?.let { p ->
                // Retake request: solid, high contrast, never asks the user to approach live equipment.
                Row(Modifier.fillMaxWidth().background(Grey.G900, org.rvi.inspect.ui.components.GlassShape)
                    .border(1.dp, Grey.White, org.rvi.inspect.ui.components.GlassShape).padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.ZoomIn, null, tint = Grey.White)
                    Spacer(Modifier.width(10.dp))
                    Text(stringResource(promptRes(p)), style = MaterialTheme.typography.bodyLarge, color = Grey.White)
                }
                Spacer(Modifier.height(12.dp))
            }
            if (st.listening || st.heard != null) {
                GlassCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                    Text(if (st.listening) stringResource(R.string.listening) else "“${st.heard}”", style = MaterialTheme.typography.bodyLarge, color = Grey.White)
                    Text(stringResource(R.string.ohe_say_command), style = MaterialTheme.typography.labelMedium, color = Grey.G400)
                }
                Spacer(Modifier.height(12.dp))
            }
            GlassCard(Modifier.fillMaxWidth().padding(bottom = 12.dp), padding = 18.dp) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.Bottom) {
                    GlassRoundButton(Icons.Outlined.EditNote, stringResource(R.string.ohe_note), onNote, size = 60.dp)
                    GlassRoundButton(Icons.Outlined.CameraAlt, stringResource(R.string.capture), onCapture, size = 88.dp, filled = true)
                    GlassRoundButton(Icons.Outlined.Mic, stringResource(R.string.voice), onVoice, size = 60.dp)
                }
                Spacer(Modifier.height(14.dp))
                GhostButton(stringResource(R.string.end_patrol), onEnd, Modifier.fillMaxWidth(), Icons.Outlined.Stop)
            }
        }
    }
}

@Composable
private fun Stat(value: String, label: String) = Column {
    Text(value, style = MaterialTheme.typography.headlineSmall, color = Grey.White)
    Text(label, style = MaterialTheme.typography.labelSmall, color = Grey.G400)
}

/** Dictated or typed note. Kept apart from inspection: the server never reads notes when assessing photos (HLD I-06). */
@Composable
fun OheNoteSheet(text: String, onText: (String) -> Unit, onDictate: () -> Unit, onSave: () -> Unit, onCancel: () -> Unit) {
    Box(Modifier.fillMaxSize().background(Color(0xE6000000)), contentAlignment = Alignment.BottomCenter) {
        Column(OPad.fillMaxWidth().padding(bottom = 16.dp).background(Grey.G900, org.rvi.inspect.ui.components.GlassShape)
            .border(1.dp, Grey.GlassStroke, org.rvi.inspect.ui.components.GlassShape).padding(20.dp)) {
            Text(stringResource(R.string.ohe_note_title), style = MaterialTheme.typography.headlineSmall, color = Grey.White)
            Spacer(Modifier.height(6.dp))
            Text(stringResource(R.string.ohe_note_isolated), style = MaterialTheme.typography.bodyMedium, color = Grey.G300)
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(text, onText, Modifier.fillMaxWidth(), minLines = 3)
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                GhostButton(stringResource(R.string.voice), onDictate, Modifier.weight(1f), Icons.Outlined.Mic)
                PrimaryButton(stringResource(R.string.ohe_save_note), onSave, Modifier.weight(1f))
            }
            Spacer(Modifier.height(8.dp))
            GhostButton(stringResource(R.string.ohe_cancel), onCancel, Modifier.fillMaxWidth())
        }
    }
}

@Composable
fun OheEndScreen(s: OheSummary, onRetry: () -> Unit, onHome: () -> Unit) {
    AmbientBackground {
        Column(OPad.fillMaxSize().verticalScroll(rememberScrollState())) {
            Spacer(Modifier.height(24.dp))
            Eyebrow(stringResource(R.string.ohe_end_eyebrow))
            Text(if (s.reportId != null) stringResource(R.string.ohe_report_ready) else stringResource(R.string.ohe_report_waiting),
                style = MaterialTheme.typography.headlineMedium, color = Grey.White)
            Spacer(Modifier.height(16.dp))
            GlassCard(Modifier.fillMaxWidth()) {
                Line(stringResource(R.string.ohe_photos), "${s.photos}")
                Line(stringResource(R.string.ohe_uploaded), "${s.uploaded} / ${s.photos}")
                Line(stringResource(R.string.ohe_notes), "${s.notes}")
                if (s.reportId != null) {
                    Line(stringResource(R.string.ohe_masts_expected), "${s.expected ?: "—"}")
                    Line(stringResource(R.string.ohe_masts_evidenced), "${s.evidenced ?: "—"}")
                    Line(stringResource(R.string.ohe_with_findings), "${s.withFindings ?: "—"}")
                    Line(stringResource(R.string.ohe_not_assessable), "${s.notAssessable ?: "—"}")
                    Line(stringResource(R.string.ohe_urgent), "${s.alerts ?: "—"}")
                    Spacer(Modifier.height(8.dp))
                    Text(stringResource(R.string.ohe_report_id, s.reportId), style = MaterialTheme.typography.labelSmall, color = Grey.G400)
                }
            }
            Spacer(Modifier.height(12.dp))
            Text(stringResource(R.string.ohe_next_step), style = MaterialTheme.typography.bodyMedium, color = Grey.G300)
            Spacer(Modifier.height(20.dp))
            if (s.reportId == null) {
                GhostButton(stringResource(R.string.ohe_retry), onRetry, Modifier.fillMaxWidth(), Icons.Outlined.Refresh)
                Spacer(Modifier.height(10.dp))
            }
            PrimaryButton(stringResource(R.string.ohe_done), onHome, Modifier.fillMaxWidth())
            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun Line(label: String, value: String) = Row(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
    Text(label, style = MaterialTheme.typography.bodyLarge, color = Grey.G200, modifier = Modifier.weight(1f))
    Text(value, style = MaterialTheme.typography.bodyLarge, color = Grey.White)
}
