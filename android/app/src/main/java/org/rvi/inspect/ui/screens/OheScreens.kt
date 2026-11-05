package org.rvi.inspect.ui.screens

import android.graphics.BitmapFactory
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.rvi.inspect.R
import org.rvi.inspect.data.FoundServer
import org.rvi.inspect.data.Prompt
import org.rvi.inspect.ui.OheSummary
import org.rvi.inspect.ui.components.*
import org.rvi.inspect.ui.theme.GeistMono
import org.rvi.inspect.ui.theme.Ink

private val Edge = Modifier.statusBarsPadding().navigationBarsPadding()

fun promptRes(p: Prompt): Int = when (p) {
    Prompt.ZOOM -> R.string.prompt_zoom
    Prompt.PLATE -> R.string.prompt_plate
    Prompt.WHOLE -> R.string.prompt_whole
    Prompt.SQUARE -> R.string.prompt_square
    Prompt.BLUR -> R.string.prompt_blur
    Prompt.DARK -> R.string.prompt_dark
    Prompt.BRIGHT -> R.string.prompt_bright
}

// ---------------------------------------------------------------------------------------------------------------- shared

@Composable
private fun AppMark(size: Int = 52) = Image(painterResource(R.drawable.ontrack_icon), "OnTrack.AI",
    Modifier.size(size.dp).clip(RoundedCornerShape((size * 0.28f).dp)))

@Composable
private fun BackBar(title: String, sub: String?, onBack: () -> Unit) = Row(Modifier.fillMaxWidth().padding(16.dp, 8.dp), verticalAlignment = Alignment.CenterVertically) {
    IconCircle(Icons.AutoMirrored.Outlined.ArrowBack, "Back", onBack)
    Spacer(Modifier.width(12.dp))
    Column {
        Text(title, style = MaterialTheme.typography.titleMedium, color = Ink.Ink)
        if (sub != null) Text(sub, style = MaterialTheme.typography.bodyMedium, color = Ink.Body)
    }
}

/** "Connected · laptop" / "Not connected" chip; tapping it opens the server finder. */
@Composable
fun ServerChip(ok: Boolean?, host: String, onClick: () -> Unit, dark: Boolean = false) {
    val label = when (ok) { true -> stringResource(R.string.g_server_connected, host); false -> stringResource(R.string.g_server_offline); null -> stringResource(R.string.g_server_searching) }
    val dot = when (ok) { true -> Ink.Mint; false -> Ink.Safety; null -> Ink.Amber }
    Row(Modifier.clip(RoundedCornerShape(50)).glass(RoundedCornerShape(50), dark = dark).clickable(onClick = onClick).padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(8.dp).clip(CircleShape).background(dot))
        Spacer(Modifier.width(8.dp))
        Text(label, style = MaterialTheme.typography.labelMedium, color = if (dark) Ink.White else Ink.Ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

/** Finder for the laptop server: found servers (one tap) and a typed address. */
@Composable
fun ServerPanel(current: String, searching: Boolean, found: List<FoundServer>, onFind: () -> Unit, onUse: (String) -> Unit) {
    var typed by remember(current) { mutableStateOf(current.removePrefix("http://").trimEnd('/')) }
    GlassCard(Modifier.fillMaxWidth(), strong = true) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.ohe_server), style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            Pill(stringResource(R.string.g_find_server), onFind, kind = PillKind.Ink, icon = Icons.Outlined.Wifi, height = 44.dp, enabled = !searching)
        }
        if (searching) Text(stringResource(R.string.g_server_searching), style = MaterialTheme.typography.bodyMedium, color = Ink.Body, modifier = Modifier.padding(top = 8.dp))
        found.forEach { f ->
            Spacer(Modifier.height(8.dp))
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Ink.ElectricTint).clickable { onUse(f.url) }.padding(14.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Computer, null, tint = Ink.ElectricDeep)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(f.name, style = MaterialTheme.typography.titleMedium, color = Ink.Ink)
                    Mono(f.url, size = 12, color = Ink.ElectricDeep)
                }
                Icon(Icons.AutoMirrored.Outlined.ArrowForward, null, tint = Ink.ElectricDeep)
            }
        }
        if (!searching && found.isEmpty()) Text(stringResource(R.string.g_server_none), style = MaterialTheme.typography.bodyMedium, color = Ink.Body, modifier = Modifier.padding(top = 8.dp))
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(typed, { typed = it }, Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(18.dp),
            placeholder = { Text(stringResource(R.string.g_server_hint)) }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            colors = OutlinedTextFieldDefaults.colors(focusedContainerColor = Ink.White, unfocusedContainerColor = Color(0xCCFFFFFF)))
        Spacer(Modifier.height(8.dp))
        Pill(stringResource(R.string.g_server_use), { onUse(typed) }, Modifier.fillMaxWidth(), PillKind.Glass, height = 48.dp)
    }
}

// --------------------------------------------------------------------------------------------------------------- sign in

data class SignInState(val id: String, val pinLength: Int, val busy: Boolean, val message: String?, val server: String, val serverOk: Boolean?,
                       val searching: Boolean, val found: List<FoundServer>, val hindi: Boolean, val showServer: Boolean)

@Composable
fun SignInScreen(st: SignInState, onId: (String) -> Unit, onDigit: (Char) -> Unit, onBackspace: () -> Unit, onSubmit: () -> Unit,
                 onLang: (Boolean) -> Unit, onToggleServer: () -> Unit, onFind: () -> Unit, onUseServer: (String) -> Unit) {
    Aura(glows = listOf(Glow(Ink.Electric, 0f, 0f, 0.95f), Glow(Ink.Aqua, 1f, 0.2f, 0.7f, 0.5f), Glow(Ink.Amber, 0.2f, 1f, 0.8f, 0.35f))) {
        Column(Edge.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 22.dp)) {
            Spacer(Modifier.height(16.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                AppMark()
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text("OnTrack.AI", style = MaterialTheme.typography.titleLarge, color = Ink.Ink)
                    Text(stringResource(R.string.ohe_app_eyebrow), style = MaterialTheme.typography.bodyMedium, color = Ink.Muted)
                }
                Row(Modifier.glass(RoundedCornerShape(50)).padding(4.dp)) {
                    LangPill("EN", !st.hindi) { onLang(false) }
                    LangPill("हिं", st.hindi) { onLang(true) }
                }
            }
            Spacer(Modifier.height(14.dp))
            ServerChip(st.serverOk, st.server.removePrefix("http://").trimEnd('/'), onToggleServer)
            AnimatedVisibility(st.showServer) {
                Column { Spacer(Modifier.height(10.dp)); ServerPanel(st.server, st.searching, st.found, onFind, onUseServer) }
            }
            Spacer(Modifier.height(22.dp))
            Text(stringResource(R.string.g_signin_title), style = MaterialTheme.typography.displaySmall, color = Ink.Ink)
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(st.id, onId, Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(18.dp),
                label = { Text(stringResource(R.string.g_signin_id)) },
                textStyle = MaterialTheme.typography.bodyLarge.copy(fontFamily = GeistMono, fontWeight = FontWeight.SemiBold),
                colors = OutlinedTextFieldDefaults.colors(focusedContainerColor = Ink.White, unfocusedContainerColor = Color(0xB3FFFFFF)))
            Spacer(Modifier.height(18.dp))
            Row(Modifier.fillMaxWidth().semantics { contentDescription = "PIN, ${st.pinLength} digits entered" }, horizontalArrangement = Arrangement.Center) {
                val slots = maxOf(4, st.pinLength)
                for (i in 0 until slots) {
                    val on = i < st.pinLength
                    val cur = i == st.pinLength
                    Box(Modifier.padding(horizontal = 6.dp).size(48.dp, 56.dp).clip(RoundedCornerShape(16.dp))
                        .background(if (on) Ink.ElectricTint else Color(0x8CFFFFFF))
                        .border(if (cur) 2.dp else 1.dp, if (cur) Ink.Electric else Ink.GlassEdge, RoundedCornerShape(16.dp)), contentAlignment = Alignment.Center) {
                        Box(Modifier.size(12.dp).scale(if (on) 1f else 0.6f).clip(CircleShape).background(if (on) Ink.Electric else Color(0x2E0E1020)))
                    }
                }
            }
            Spacer(Modifier.height(18.dp))
            val keys = listOf('1', '2', '3', '4', '5', '6', '7', '8', '9', ' ', '0', '<')
            keys.chunked(3).forEach { row ->
                Row(Modifier.fillMaxWidth().padding(vertical = 5.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    row.forEach { k ->
                        if (k == ' ') Spacer(Modifier.weight(1f).height(64.dp))
                        else Surface(onClick = { if (k == '<') onBackspace() else onDigit(k) }, shape = RoundedCornerShape(22.dp),
                            color = if (k == '<') Color(0x55FFFFFF) else Color(0xA6FFFFFF), contentColor = Ink.Ink,
                            border = androidx.compose.foundation.BorderStroke(1.dp, Ink.GlassEdge),
                            modifier = Modifier.weight(1f).height(64.dp).semantics { contentDescription = if (k == '<') "Delete" else "$k" }) {
                            Box(contentAlignment = Alignment.Center) {
                                if (k == '<') Icon(Icons.Outlined.Backspace, null) else Text("$k", fontSize = 26.sp, fontWeight = FontWeight.SemiBold)
                            }
                        }
                    }
                }
            }
            Spacer(Modifier.height(14.dp))
            Pill(stringResource(R.string.g_continue), onSubmit, Modifier.fillMaxWidth(), PillKind.Primary, Icons.AutoMirrored.Outlined.ArrowForward,
                enabled = st.pinLength >= 4 && st.id.isNotBlank() && !st.busy)
            Spacer(Modifier.height(10.dp))
            Text(st.message ?: stringResource(R.string.g_signin_offline), style = MaterialTheme.typography.bodyMedium,
                color = if (st.message != null) Ink.SafetyText else Ink.Muted, modifier = Modifier.align(Alignment.CenterHorizontally))
            Spacer(Modifier.height(20.dp))
        }
    }
}

@Composable
private fun LangPill(t: String, on: Boolean, onClick: () -> Unit) = Surface(onClick = onClick, shape = RoundedCornerShape(50),
    color = if (on) Ink.White else Color.Transparent, shadowElevation = if (on) 2.dp else 0.dp, modifier = Modifier.heightIn(min = 40.dp)) {
    Box(contentAlignment = Alignment.Center) { Text(t, Modifier.padding(horizontal = 12.dp), style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold)) }
}

// ------------------------------------------------------------------------------------------------------------------ home

data class OheHomeState(val name: String, val territory: String, val active: Boolean, val pending: Int, val lastPatrol: String?,
                        val lastSigned: Boolean, val updateVersion: String?, val updating: Boolean, val serverOk: Boolean?, val serverHost: String,
                        val appVersion: String = "")

@Composable
fun OheHomeScreen(st: OheHomeState, onStart: () -> Unit, onResume: () -> Unit, onLastReport: () -> Unit, onUpdate: () -> Unit,
                  onProfile: () -> Unit, onServer: () -> Unit) {
    Aura(glows = GlowsHome) {
        RouteMap(Modifier.fillMaxWidth().height(470.dp))
        Column(Edge.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(16.dp, 10.dp), verticalAlignment = Alignment.CenterVertically) {
                Row(Modifier.weight(1f).height(54.dp).glass(RoundedCornerShape(50), strong = true).padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.Place, null, tint = Ink.Electric, modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(10.dp))
                    Column {
                        Text(stringResource(R.string.ohe_section), style = MaterialTheme.typography.labelMedium, color = Ink.Muted)
                        Mono(st.territory, size = 14)
                    }
                }
                Spacer(Modifier.width(10.dp))
                Surface(onClick = onProfile, shape = CircleShape, color = Ink.Ink, contentColor = Ink.Signal, modifier = Modifier.size(54.dp)) {
                    Box(contentAlignment = Alignment.Center) { Text(st.name.take(2).uppercase(), fontWeight = FontWeight.Bold, fontSize = 16.sp) }
                }
            }
            Row(Modifier.padding(horizontal = 16.dp)) { ServerChip(st.serverOk, st.serverHost, onServer) }
            Spacer(Modifier.weight(1f))
            Column(Modifier.padding(horizontal = 10.dp).padding(bottom = 96.dp).fillMaxWidth().glass(SheetShape, strong = true).padding(18.dp, 20.dp)) {
                Eyebrow(stringResource(R.string.g_today))
                Spacer(Modifier.height(4.dp))
                Text(stringResource(R.string.g_greet, st.name), style = MaterialTheme.typography.headlineMedium, color = Ink.Ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Spacer(Modifier.height(14.dp))
                if (st.active) Pill(stringResource(R.string.ohe_resume), onResume, Modifier.fillMaxWidth(), PillKind.Primary, Icons.Outlined.PlayArrow, height = 66.dp)
                else SwipeToStart(stringResource(R.string.g_swipe_start), onStart)
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Column(Modifier.weight(1f).clip(RoundedCornerShape(22.dp)).background(Color(0xB3FFFFFF)).border(1.dp, Ink.White, RoundedCornerShape(22.dp))
                        .clickable(enabled = st.lastPatrol != null, onClick = onLastReport).padding(14.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(stringResource(R.string.g_last_patrol), style = MaterialTheme.typography.labelMedium, color = Ink.Muted, modifier = Modifier.weight(1f))
                            Box(Modifier.size(8.dp).clip(CircleShape).background(if (st.lastSigned) Ink.Mint else if (st.lastPatrol != null) Ink.Amber else Color(0x330E1020)))
                        }
                        Spacer(Modifier.height(6.dp))
                        Text(st.lastPatrol ?: stringResource(R.string.g_no_patrol_yet), style = MaterialTheme.typography.titleMedium, color = Ink.Ink, maxLines = 2)
                        Spacer(Modifier.height(6.dp))
                        Text(if (st.pending == 0) stringResource(R.string.ohe_all_uploaded) else stringResource(R.string.ohe_pending, st.pending),
                            style = MaterialTheme.typography.bodyMedium, color = Ink.Body, maxLines = 2)
                    }
                    if (st.updateVersion != null) {
                        Column(Modifier.weight(1f).clip(RoundedCornerShape(22.dp)).background(Ink.Ink).clickable(enabled = !st.updating, onClick = onUpdate).padding(14.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(stringResource(R.string.g_app_update), style = MaterialTheme.typography.labelMedium, color = Color(0xFFB8BCD0), modifier = Modifier.weight(1f))
                                StatusChip(stringResource(R.string.g_new), Tone.Now)
                            }
                            Spacer(Modifier.height(6.dp))
                            Mono(st.updateVersion, color = Ink.White, size = 15)
                            Spacer(Modifier.height(6.dp))
                            Text(if (st.updating) stringResource(R.string.update_downloading) else stringResource(R.string.g_tap_install),
                                style = MaterialTheme.typography.bodyMedium, color = Color(0xFFB8BCD0))
                        }
                    }
                }
            }
        }
    }
}

/** Stylised section map: the line, the masts (done, urgent, next, to do) and a pulsing "you are here". */
@Composable
private fun RouteMap(modifier: Modifier) {
    val p = if (LocalMotion.current) {
        val t = rememberInfiniteTransition(label = "pulse")
        t.animateFloat(0f, 1f, infiniteRepeatable(tween(2000), RepeatMode.Restart), label = "p").value
    } else 0.4f
    Canvas(modifier) {
        val w = size.width; val h = size.height
        fun pt(fx: Float, fy: Float) = Offset(fx * w, fy * h)
        drawLine(Color(0x8CFFFFFF), pt(-0.05f, 0.15f), pt(1.05f, 0.3f), 22.dp.toPx())
        drawLine(Color(0x73FFFFFF), pt(0.23f, -0.02f), pt(0.38f, 1.02f), 14.dp.toPx())
        drawLine(Color(0x73FFFFFF), pt(0.77f, -0.02f), pt(0.67f, 1.02f), 10.dp.toPx())
        val path = Path().apply {
            moveTo(-0.03f * w, 0.85f * h)
            cubicTo(0.2f * w, 0.79f * h, 0.36f * w, 0.64f * h, 0.51f * w, 0.57f * h)
            cubicTo(0.66f * w, 0.5f * h, 0.85f * w, 0.4f * h, 1.03f * w, 0.34f * h)
        }
        drawPath(path, Color.White, style = Stroke(20.dp.toPx(), cap = StrokeCap.Round))
        drawPath(path, Ink.Electric, style = Stroke(3.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(28f, 22f))))
        val masts = listOf(0.15f to 0.81f, 0.32f to 0.71f, 0.49f to 0.585f, 0.66f to 0.5f, 0.82f to 0.43f, 0.96f to 0.36f)
        masts.forEachIndexed { i, (x, y) ->
            val c = pt(x, y)
            val fill = when (i) { 0, 1 -> Ink.Ink; 2 -> Color(0xFFFF6A2C); else -> Color.White }
            drawCircle(Color.White, 9.dp.toPx(), c)
            drawCircle(fill, 7.dp.toPx(), c)
            if (i > 2) drawCircle(if (i == 3) Ink.Electric else Color(0xFF8C93B0), 7.dp.toPx(), c, style = Stroke(3.dp.toPx()))
        }
        val me = pt(0.57f, 0.6f)
        drawCircle(Ink.Electric.copy(alpha = 0.45f * (1 - p)), (8 + 26 * p).dp.toPx(), me)
        drawCircle(Color.White, 10.dp.toPx(), me)
        drawCircle(Ink.Electric, 7.dp.toPx(), me)
    }
}

// ----------------------------------------------------------------------------------------------------------------- start

data class StartState(val territory: String)

@Composable
fun StartSheet(st: StartState, onTerritory: (String) -> Unit, onClose: () -> Unit, onStart: () -> Unit) {
    val checks = remember { mutableStateListOf(true, true, true) }
    Aura(glows = listOf(Glow(Color(0xFF5B6BFF), 0f, 0f, 0.9f, 0.6f), Glow(Color(0xFFFF8A4C), 1f, 0.25f, 0.8f, 0.45f)), base = Color(0xFFC9CFE6)) {
        Column(Edge.fillMaxSize()) {
            Row(Modifier.padding(16.dp, 10.dp)) { IconCircle(Icons.Outlined.Close, "Close", onClose) }
            Spacer(Modifier.weight(1f))
            Column(Modifier.padding(8.dp).fillMaxWidth().glass(SheetShape, strong = true).verticalScroll(rememberScrollState()).padding(18.dp, 16.dp)) {
                Box(Modifier.align(Alignment.CenterHorizontally).size(40.dp, 5.dp).clip(CircleShape).background(Color(0x2E0E1020)))
                Spacer(Modifier.height(12.dp))
                Text(stringResource(R.string.g_start_title), style = MaterialTheme.typography.headlineMedium, color = Ink.Ink)
                Spacer(Modifier.height(14.dp))
                OutlinedTextField(st.territory, onTerritory, Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(18.dp),
                    label = { Text(stringResource(R.string.ohe_section)) }, leadingIcon = { Icon(Icons.Outlined.Place, null, tint = Ink.Electric) },
                    textStyle = MaterialTheme.typography.bodyLarge.copy(fontFamily = GeistMono, fontWeight = FontWeight.SemiBold),
                    colors = OutlinedTextFieldDefaults.colors(focusedContainerColor = Ink.White, unfocusedContainerColor = Color(0xCCFFFFFF)))
                Spacer(Modifier.height(16.dp))
                Eyebrow(stringResource(R.string.g_before_walk), Ink.Muted)
                Spacer(Modifier.height(8.dp))
                listOf(R.string.g_chk_battery, R.string.g_chk_tpc, R.string.g_chk_data).forEachIndexed { i, r ->
                    val on = checks[i]
                    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp).clip(RoundedCornerShape(18.dp)).background(if (on) Color(0xD9FFFFFF) else Color(0x66FFFFFF))
                        .border(1.dp, if (on) Ink.White else Ink.Hair, RoundedCornerShape(18.dp)).clickable { checks[i] = !on }.padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(26.dp).clip(RoundedCornerShape(9.dp)).background(if (on) Ink.Mint else Color(0x2E0E1020)), contentAlignment = Alignment.Center) {
                            if (on) Icon(Icons.Outlined.Check, null, tint = Ink.White, modifier = Modifier.size(18.dp))
                        }
                        Spacer(Modifier.width(12.dp))
                        Text(stringResource(r), style = MaterialTheme.typography.titleMedium, color = Ink.Ink)
                    }
                }
                Spacer(Modifier.height(12.dp))
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Color(0xFFFFE8DA)).padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.Bolt, null, tint = Color(0xFFB5390B))
                    Spacer(Modifier.width(10.dp))
                    Text(stringResource(R.string.g_live_warning), style = MaterialTheme.typography.bodyMedium, color = Color(0xFF7A2606))
                }
                Spacer(Modifier.height(16.dp))
                Pill(stringResource(R.string.g_open_camera), onStart, Modifier.fillMaxWidth(), PillKind.Primary, Icons.Outlined.PhotoCamera, height = 62.dp)
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------------------ camera HUD

enum class ToastKind { Saved, Uploading, Checked, Flagged, Retake, Nothing, Failed }
data class Thumb(val path: String, val uploaded: Boolean, val flagged: Boolean)

data class OheHudState(val photos: Int, val uploaded: Int, val flagged: Int, val alerts: Int, val notes: Int, val prompt: Prompt?,
                       val listening: Boolean, val heard: String?, val territory: String = "", val zoom: Float = 1f, val maxZoom: Float = 5f,
                       val toast: ToastKind? = null, val thumbs: List<Thumb> = emptyList(), val serverOk: Boolean? = null,
                       val seen: List<Pair<String, Int>> = emptyList())

@Composable
fun OheHud(st: OheHudState, onCapture: () -> Unit, onVoice: () -> Unit, onNote: () -> Unit, onEnd: () -> Unit,
           onZoom: (Float) -> Unit = {}, onDanger: () -> Unit = {}, onDismissPrompt: () -> Unit = {}, background: @Composable () -> Unit) {
    Box(Modifier.fillMaxSize().background(Color(0xFF10142A))) {
        background()
        Box(Modifier.fillMaxWidth().height(160.dp).background(Brush.verticalGradient(listOf(Color(0x660E1020), Color.Transparent))))
        Box(Modifier.fillMaxWidth().height(300.dp).align(Alignment.BottomCenter).background(Brush.verticalGradient(listOf(Color.Transparent, Color(0x990E1020)))))
        Column(Edge.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(12.dp, 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Surface(onClick = onEnd, shape = RoundedCornerShape(50), color = Ink.DarkGlass, contentColor = Ink.White,
                    border = androidx.compose.foundation.BorderStroke(1.dp, Ink.DarkEdge), modifier = Modifier.height(44.dp)) {
                    Row(Modifier.padding(horizontal = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(10.dp).clip(RoundedCornerShape(3.dp)).background(Color(0xFFFF5A36)))
                        Spacer(Modifier.width(8.dp)); Text(stringResource(R.string.g_end), style = MaterialTheme.typography.labelLarge)
                    }
                }
                Row(Modifier.weight(1f).height(44.dp).glass(RoundedCornerShape(50), dark = true).padding(horizontal = 14.dp),
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center) {
                    LiveDot()
                    Spacer(Modifier.width(8.dp))
                    Mono(st.territory.ifBlank { "—" }, color = Ink.White, size = 13)
                    Text("  ·  ${st.uploaded}/${st.photos}", style = MaterialTheme.typography.labelMedium, color = Ink.White)
                }
                IconCircle(Icons.Outlined.Warning, stringResource(R.string.g_danger), onDanger, size = 44.dp, bg = Color(0xD9FF5A36), tint = Ink.White)
            }
            Spacer(Modifier.weight(1f))
            AnimatedVisibility(st.toast != null && (st.prompt == null || st.toast != ToastKind.Checked), enter = slideInVertically { it } + fadeIn(), exit = fadeOut()) {
                st.toast?.let { HudToast(it, st.seen) }
            }
            st.prompt?.let { p -> RetakeCard(p, onDismissPrompt) }
            if (st.listening || st.heard != null) {
                Row(Modifier.padding(horizontal = 14.dp, vertical = 6.dp).fillMaxWidth().glass(RoundedCornerShape(22.dp), dark = true).padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.GraphicEq, null, tint = Ink.Signal)
                    Spacer(Modifier.width(10.dp))
                    Column {
                        Text(if (st.listening) stringResource(R.string.listening) else "“${st.heard}”", style = MaterialTheme.typography.titleMedium, color = Ink.White)
                        Text(stringResource(R.string.ohe_say_command), style = MaterialTheme.typography.bodyMedium, color = Color(0xFFD9DCF0))
                    }
                }
            }
            Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Row(Modifier.weight(1f).glass(RoundedCornerShape(22.dp), dark = true).padding(8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (st.thumbs.isEmpty()) Text(stringResource(R.string.ohe_say_command), style = MaterialTheme.typography.bodyMedium, color = Color(0xFFD9DCF0),
                        modifier = Modifier.padding(6.dp))
                    st.thumbs.takeLast(4).forEach { ThumbView(it) }
                }
                Spacer(Modifier.width(8.dp))
                Column(Modifier.glass(RoundedCornerShape(30.dp), dark = true).padding(5.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    listOf(5f, 3f, 1f).filter { it == 1f || it <= st.maxZoom + 0.01f }.forEach { z ->
                        val on = kotlin.math.abs(st.zoom - z) < 0.2f
                        Surface(onClick = { onZoom(z) }, shape = CircleShape, color = if (on) Ink.Signal else Color.Transparent, contentColor = if (on) Ink.Ink else Ink.White,
                            modifier = Modifier.size(44.dp).semantics { contentDescription = "Zoom ${z.toInt()}x" }) {
                            Box(contentAlignment = Alignment.Center) { Text("${z.toInt()}×", fontWeight = FontWeight.Bold) }
                        }
                    }
                }
            }
            Row(Modifier.fillMaxWidth().padding(horizontal = 32.dp, vertical = 10.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                IconCircle(Icons.Outlined.Mic, stringResource(R.string.voice), onVoice, size = 60.dp, dark = true,
                    bg = if (st.listening) Ink.Signal else null, tint = if (st.listening) Ink.Ink else null)
                Surface(onClick = onCapture, shape = CircleShape, color = Color(0x40FFFFFF), modifier = Modifier.size(90.dp)
                    .border(4.dp, Ink.White, CircleShape).semantics { contentDescription = "Take photo" }) {
                    Box(contentAlignment = Alignment.Center) { Box(Modifier.size(70.dp).clip(CircleShape).background(Ink.White)) }
                }
                IconCircle(Icons.Outlined.EditNote, stringResource(R.string.ohe_note), onNote, size = 60.dp, dark = true)
            }
            Spacer(Modifier.height(6.dp))
        }
    }
}

@Composable
private fun LiveDot() {
    val a = if (LocalMotion.current) {
        val t = rememberInfiniteTransition(label = "live")
        t.animateFloat(1f, 0.25f, infiniteRepeatable(tween(700), RepeatMode.Reverse), label = "a").value
    } else 1f
    Box(Modifier.size(8.dp).clip(CircleShape).background(Color(0xFFFF5A36).copy(alpha = a)))
}

@Composable
private fun ThumbView(t: Thumb) {
    var bmp by remember(t.path) { mutableStateOf<ImageBitmap?>(null) }
    LaunchedEffect(t.path) {
        bmp = withContext(Dispatchers.IO) {
            runCatching { BitmapFactory.decodeFile(t.path, BitmapFactory.Options().apply { inSampleSize = 16 })?.asImageBitmap() }.getOrNull()
        }
    }
    Box(Modifier.size(50.dp)) {
        Box(Modifier.fillMaxSize().clip(RoundedCornerShape(14.dp)).background(Color(0xFF5A5FA8))
            .border(2.dp, if (t.flagged) Color(0xFFFF5A36) else Color(0x66FFFFFF), RoundedCornerShape(14.dp))) {
            bmp?.let { Image(it, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
        }
        Text(if (t.uploaded) "✓✓" else "✓", Modifier.align(Alignment.BottomEnd).offset(4.dp, 4.dp).clip(RoundedCornerShape(8.dp)).background(Ink.Ink)
            .padding(horizontal = 5.dp, vertical = 1.dp), color = if (t.uploaded) Color(0xFF7FB2FF) else Color(0xFFD9DCF0), fontSize = 10.sp, fontWeight = FontWeight.ExtraBold)
    }
}

/** Readable name for a detector class ("insulator_defect" -> "Damaged insulator"). */
@Composable
fun clsLabel(cls: String): String = when (cls) {
    "insulator" -> stringResource(R.string.g_cls_insulator)
    "insulator_defect" -> stringResource(R.string.g_cls_insulator_defect)
    "bird_nest" -> stringResource(R.string.g_cls_bird_nest)
    "vegetation" -> stringResource(R.string.g_cls_vegetation)
    "mast" -> stringResource(R.string.g_cls_mast)
    "foreign_object" -> stringResource(R.string.g_cls_foreign_object)
    "corrosion" -> stringResource(R.string.g_cls_corrosion)
    else -> cls.replace('_', ' ').replaceFirstChar { it.uppercase() }
}

@Composable
private fun HudToast(k: ToastKind, seen: List<Pair<String, Int>> = emptyList()) {
    val (bg, icon, title, sub) = when (k) {
        ToastKind.Checked -> Quad(Ink.Mint, Icons.Outlined.Check, R.string.g_toast_checked, R.string.g_toast_checked_sub)
        ToastKind.Flagged -> Quad(Ink.Safety, Icons.Outlined.Flag, R.string.g_toast_flagged, R.string.g_toast_flagged_sub)
        ToastKind.Uploading -> Quad(Ink.Electric, Icons.Outlined.CloudUpload, R.string.g_toast_uploading, R.string.g_toast_saved_sub)
        ToastKind.Nothing -> Quad(Ink.Amber, Icons.Outlined.CropFree, R.string.g_toast_nothing, R.string.g_toast_nothing_sub)
        ToastKind.Failed -> Quad(Ink.Amber, Icons.Outlined.Warning, R.string.g_toast_failed, R.string.g_toast_failed_sub)
        else -> Quad(Ink.Electric, Icons.Outlined.Check, R.string.g_toast_saved, R.string.g_toast_saved_sub)
    }
    val showSeen = k in setOf(ToastKind.Checked, ToastKind.Flagged, ToastKind.Nothing)
    val saw = seen.map { (c, n) -> clsLabel(c) + if (n > 1) " ×$n" else "" }.joinToString(", ")
    Row(Modifier.padding(horizontal = 14.dp, vertical = 6.dp).fillMaxWidth().glass(RoundedCornerShape(22.dp), strong = true).padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(38.dp).clip(RoundedCornerShape(12.dp)).background(bg), contentAlignment = Alignment.Center) { Icon(icon, null, tint = Ink.White) }
        Spacer(Modifier.width(12.dp))
        Column {
            Text(stringResource(title), style = MaterialTheme.typography.titleMedium, color = Ink.Ink)
            if (showSeen) Text(if (saw.isNotEmpty()) stringResource(R.string.g_toast_saw, saw) else stringResource(R.string.g_toast_saw_none),
                style = MaterialTheme.typography.bodyMedium, color = Ink.Ink, fontWeight = FontWeight.SemiBold)
            Text(stringResource(sub), style = MaterialTheme.typography.bodyMedium, color = Ink.Body)
        }
    }
}

private data class Quad(val a: Color, val b: androidx.compose.ui.graphics.vector.ImageVector, val c: Int, val d: Int)

/** Retake request: one plain instruction, never "move closer". Spoken aloud by the caller. */
@Composable
private fun RetakeCard(p: Prompt, onDismiss: () -> Unit) {
    val icon = when (p) {
        Prompt.ZOOM, Prompt.PLATE -> Icons.Outlined.ZoomIn
        Prompt.WHOLE -> Icons.Outlined.CropFree
        Prompt.SQUARE -> Icons.Outlined.CenterFocusStrong
        Prompt.BLUR -> Icons.Outlined.BlurOn
        Prompt.DARK -> Icons.Outlined.Lightbulb
        Prompt.BRIGHT -> Icons.Outlined.WbSunny
    }
    Column(Modifier.padding(horizontal = 12.dp, vertical = 6.dp).fillMaxWidth().glass(RoundedCornerShape(30.dp), strong = true).padding(16.dp)) {
        Row(verticalAlignment = Alignment.Top) {
            Box(Modifier.size(48.dp).clip(RoundedCornerShape(16.dp)).background(Ink.Signal), contentAlignment = Alignment.Center) { Icon(icon, null, tint = Ink.Ink) }
            Spacer(Modifier.width(12.dp))
            Text(stringResource(promptRes(p)), style = MaterialTheme.typography.titleMedium, color = Ink.Ink, modifier = Modifier.weight(1f))
        }
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Pill(stringResource(R.string.g_skip), onDismiss, Modifier.weight(1f), PillKind.Glass, height = 48.dp)
            Pill(stringResource(R.string.g_retake), onDismiss, Modifier.weight(1.3f), PillKind.Primary, Icons.Outlined.PhotoCamera, height = 48.dp)
        }
    }
}

// ---------------------------------------------------------------------------------------------------------------- urgent

@Composable
fun UrgentSheet(asset: String?, step: Int, onCallTpc: () -> Unit, onContinue: () -> Unit) {
    Aura(glows = GlowsUrgent, base = Color(0xFF1A0E14)) {
        Column(Edge.fillMaxSize()) {
            Column(Modifier.padding(20.dp, 24.dp)) {
                Text(stringResource(R.string.g_urgent_title).uppercase(), Modifier.clip(RoundedCornerShape(50)).background(Color(0x2EFFFFFF))
                    .border(1.dp, Color(0x59FFFFFF), RoundedCornerShape(50)).padding(horizontal = 12.dp, vertical = 6.dp), color = Ink.White, style = MaterialTheme.typography.labelSmall)
                Spacer(Modifier.height(10.dp))
                Text(stringResource(R.string.g_urgent_seen, asset ?: stringResource(R.string.g_urgent_here)), style = MaterialTheme.typography.headlineMedium, color = Ink.White)
            }
            Spacer(Modifier.weight(1f))
            Column(Modifier.padding(8.dp).fillMaxWidth().glass(SheetShape, strong = true).padding(18.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(R.string.g_urgent_told, R.string.g_urgent_coord, R.string.g_urgent_sse).forEachIndexed { i, r ->
                        Column(Modifier.weight(1f)) {
                            Box(Modifier.fillMaxWidth().height(5.dp).clip(CircleShape).background(if (i < step) Ink.Safety else Color(0x1F0E1020)))
                            Spacer(Modifier.height(6.dp))
                            Text(stringResource(r), style = MaterialTheme.typography.labelMedium, color = if (i < step) Ink.Ink else Ink.Muted)
                        }
                    }
                }
                Spacer(Modifier.height(14.dp))
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(Color(0xFFFFE8DA)).padding(14.dp)) {
                    Icon(Icons.Outlined.Warning, null, tint = Color(0xFFB5390B))
                    Spacer(Modifier.width(10.dp))
                    Column {
                        Text(stringResource(R.string.g_urgent_keep_clear), style = MaterialTheme.typography.titleMedium, color = Color(0xFF7A2606))
                        Text(stringResource(R.string.g_urgent_body), style = MaterialTheme.typography.bodyMedium, color = Color(0xFF7A2606))
                    }
                }
                Spacer(Modifier.height(14.dp))
                Pill(stringResource(R.string.call_tpc), onCallTpc, Modifier.fillMaxWidth(), PillKind.Safety, Icons.Outlined.Call, height = 62.dp)
                Spacer(Modifier.height(10.dp))
                Pill(stringResource(R.string.g_continue_patrol), onContinue, Modifier.fillMaxWidth(), PillKind.Glass, height = 54.dp)
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------------------------ note

/** Dictated or typed note. Kept apart from inspection: the server never reads notes when assessing photos (HLD I-06). */
@Composable
fun OheNoteSheet(text: String, onText: (String) -> Unit, onDictate: () -> Unit, onSave: () -> Unit, onCancel: () -> Unit, listening: Boolean = false) {
    Box(Modifier.fillMaxSize().background(Color(0x990E1020)), contentAlignment = Alignment.BottomCenter) {
        Column(Edge.padding(8.dp).fillMaxWidth().glass(SheetShape, strong = true).padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.ohe_note_title), style = MaterialTheme.typography.headlineSmall, color = Ink.Ink, modifier = Modifier.weight(1f))
                IconCircle(Icons.Outlined.Close, stringResource(R.string.ohe_cancel), onCancel, size = 44.dp)
            }
            Text(stringResource(R.string.ohe_note_isolated), style = MaterialTheme.typography.bodyMedium, color = Ink.Body)
            Spacer(Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(text, onText, Modifier.weight(1f), shape = RoundedCornerShape(28.dp), maxLines = 4,
                    colors = OutlinedTextFieldDefaults.colors(focusedContainerColor = Ink.White, unfocusedContainerColor = Color(0xD9FFFFFF)))
                Spacer(Modifier.width(10.dp))
                IconCircle(Icons.Outlined.Mic, stringResource(R.string.voice), onDictate, size = 60.dp, bg = if (listening) Ink.Safety else Ink.Ink, tint = Ink.White)
            }
            Spacer(Modifier.height(12.dp))
            Pill(stringResource(R.string.ohe_save_note), onSave, Modifier.fillMaxWidth(), PillKind.Primary, enabled = text.isNotBlank())
        }
    }
}

// ------------------------------------------------------------------------------------------------------------ end/summary

@Composable
fun OheEndScreen(s: OheSummary, onRetry: () -> Unit, onHome: () -> Unit, onTrack: (() -> Unit)? = null) {
    Aura(glows = GlowsMint, base = Color(0xFFEAF3F1)) {
        Column(Edge.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
            Spacer(Modifier.height(24.dp))
            Box(Modifier.align(Alignment.CenterHorizontally).size(84.dp).clip(CircleShape).background(Ink.Mint), contentAlignment = Alignment.Center) {
                Icon(Icons.Outlined.Check, null, tint = Ink.White, modifier = Modifier.size(44.dp))
            }
            Spacer(Modifier.height(12.dp))
            Text(stringResource(R.string.g_summary_title), style = MaterialTheme.typography.displaySmall, color = Ink.Ink, modifier = Modifier.align(Alignment.CenterHorizontally))
            Spacer(Modifier.height(18.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Tile("${s.evidenced ?: "—"}/${s.expected ?: "—"}", stringResource(R.string.g_masts), Ink.Ink, Ink.White, Modifier.weight(1f))
                Tile("${s.photos}", stringResource(R.string.g_photos), Color(0x99FFFFFF), Ink.Ink, Modifier.weight(1f))
                Tile("${s.alerts ?: 0}", stringResource(R.string.g_urgent_n), Ink.SafetyTint, Ink.SafetyText, Modifier.weight(1f))
            }
            Spacer(Modifier.height(12.dp))
            val done = s.photos > 0 && s.uploaded >= s.photos
            GlassCard(Modifier.fillMaxWidth(), strong = true) {
                Row { Text(if (done) stringResource(R.string.g_upload_all) else stringResource(R.string.g_upload_some), style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                    Mono("${s.uploaded} / ${s.photos}", color = Ink.ElectricDeep) }
                Spacer(Modifier.height(10.dp))
                Box(Modifier.fillMaxWidth().height(10.dp).clip(CircleShape).background(Color(0x140E1020))) {
                    Box(Modifier.fillMaxWidth(if (s.photos == 0) 0f else s.uploaded / s.photos.toFloat()).fillMaxHeight().clip(CircleShape).background(if (done) Ink.Mint else Ink.Electric))
                }
                Spacer(Modifier.height(8.dp))
                Text(if (s.reportId != null) stringResource(R.string.ohe_next_step) else stringResource(R.string.g_upload_close), style = MaterialTheme.typography.bodyMedium, color = Ink.Body)
            }
            if (s.reportId != null) {
                Spacer(Modifier.height(12.dp))
                GlassCard(Modifier.fillMaxWidth()) {
                    Line(stringResource(R.string.g_no_defect), "${(s.evidenced ?: 0) - (s.withFindings ?: 0) - (s.notAssessable ?: 0)}", Ink.Mint)
                    Line(stringResource(R.string.ohe_with_findings), "${s.withFindings ?: 0}", Ink.Safety)
                    Line(stringResource(R.string.g_could_not), "${s.notAssessable ?: 0}", Color(0xFF8C93B0))
                    Line(stringResource(R.string.ohe_notes), "${s.notes}", Ink.Electric)
                }
            }
            Spacer(Modifier.height(20.dp))
            if (s.reportId == null) { Pill(stringResource(R.string.ohe_retry), onRetry, Modifier.fillMaxWidth(), PillKind.Glass, Icons.Outlined.Refresh); Spacer(Modifier.height(10.dp)) }
            if (onTrack != null && s.reportId != null) { Pill(stringResource(R.string.g_track_report), onTrack, Modifier.fillMaxWidth(), PillKind.Primary, Icons.AutoMirrored.Outlined.ArrowForward); Spacer(Modifier.height(10.dp)) }
            Pill(stringResource(R.string.ohe_done), onHome, Modifier.fillMaxWidth(), PillKind.Glass)
            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun Tile(v: String, k: String, bg: Color, fg: Color, m: Modifier) = Column(m.clip(RoundedCornerShape(22.dp)).background(bg)
    .border(1.dp, Color(0xD9FFFFFF), RoundedCornerShape(22.dp)).padding(vertical = 14.dp), horizontalAlignment = Alignment.CenterHorizontally) {
    Mono(v, color = fg, size = 22); Text(k, style = MaterialTheme.typography.bodyMedium, color = fg)
}

@Composable
private fun Line(label: String, value: String, dot: Color) = Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
    Box(Modifier.size(10.dp).clip(CircleShape).background(dot)); Spacer(Modifier.width(10.dp))
    Text(label, style = MaterialTheme.typography.bodyLarge, color = Ink.Ink, modifier = Modifier.weight(1f))
    Text(value, style = MaterialTheme.typography.titleMedium, color = Ink.Ink)
}

// --------------------------------------------------------------------------------------------------------------- patrols

data class PatrolRow(val key: String, val title: String, val sub: String, val status: String, val tone: Tone, val fresh: Boolean, val reportId: String?)

@Composable
fun PatrolsScreen(rows: List<PatrolRow>, offline: Boolean, onOpen: (PatrolRow) -> Unit, onRefresh: () -> Unit) {
    var filter by remember { mutableIntStateOf(0) }
    var q by remember { mutableStateOf("") }
    val labels = listOf(stringResource(R.string.filter_all), stringResource(R.string.g_st_uploading), stringResource(R.string.g_st_review), stringResource(R.string.g_st_signed))
    val tones = listOf(null, Tone.Info, Tone.Urgent, Tone.Ok)
    val shown = rows.filter { (filter == 0 || it.tone == tones[filter]) && (q.isBlank() || (it.title + it.sub).contains(q, true)) }
    Aura(glows = listOf(Glow(Color(0xFFB06BFF), 1f, 0f, 0.8f, 0.35f), Glow(Ink.Aqua, 0f, 0.55f, 0.8f, 0.35f)), base = Ink.Mist2) {
        Column(Edge.fillMaxSize()) {
            Column(Modifier.padding(16.dp, 12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(stringResource(R.string.g_patrols_title), style = MaterialTheme.typography.displaySmall, color = Ink.Ink, modifier = Modifier.weight(1f))
                    IconCircle(Icons.Outlined.Refresh, "Refresh", onRefresh)
                }
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(q, { q = it }, Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(50),
                    leadingIcon = { Icon(Icons.Outlined.Search, null) }, placeholder = { Text(stringResource(R.string.g_search)) },
                    colors = OutlinedTextFieldDefaults.colors(focusedContainerColor = Ink.White, unfocusedContainerColor = Color(0x99FFFFFF)))
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { labels.forEachIndexed { i, l -> Chip(l, filter == i) { filter = i } } }
                if (offline) { Spacer(Modifier.height(8.dp)); Text(stringResource(R.string.g_server_offline), style = MaterialTheme.typography.bodyMedium, color = Ink.SafetyText) }
            }
            LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(12.dp, 0.dp, 12.dp, 110.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (shown.isEmpty()) item { Text(stringResource(R.string.g_empty_patrols), Modifier.padding(24.dp), style = MaterialTheme.typography.bodyLarge, color = Ink.Body) }
                items(shown, key = { it.key }) { r ->
                    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Color(0x9EFFFFFF)).border(1.dp, Ink.GlassEdge, RoundedCornerShape(24.dp))
                        .clickable { onOpen(r) }.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(56.dp).clip(CircleShape).background(if (r.fresh) Brush.sweepGradient(listOf(Ink.Electric, Ink.Aqua, Ink.Amber, Color(0xFFFF5A36), Ink.Electric))
                            else Brush.linearGradient(listOf(Color(0x1A0E1020), Color(0x1A0E1020)))).padding(3.dp)) {
                            Box(Modifier.fillMaxSize().clip(CircleShape).background(Ink.White).border(2.dp, Ink.White, CircleShape), contentAlignment = Alignment.Center) {
                                Mono(r.title.substringBefore(" · ").filter { it.isDigit() }.takeLast(4).ifBlank { r.title.take(3) }, size = 12)
                            }
                        }
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(r.title, style = MaterialTheme.typography.titleMedium, color = Ink.Ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Spacer(Modifier.height(4.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(r.sub, style = MaterialTheme.typography.bodyMedium, color = Ink.Body, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                                Spacer(Modifier.width(6.dp)); StatusChip(r.status, r.tone)
                            }
                        }
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------------------------------------------- report

data class ReportUi(val title: String, val sub: String, val reached: Int, val signedBy: String?, val amendments: List<String>,
                    val findings: List<Pair<String, Boolean>>, val error: String?,
                    val patrollerSignoff: Boolean = false, val canSignOff: Boolean = false, val signing: Boolean = false)

@Composable
fun ReportScreen(r: ReportUi, onBack: () -> Unit, onRefresh: () -> Unit, onSignOff: () -> Unit = {}) {
    // patroller mode (draft): AI analysis + the patroller signs off; SSE mode adds "Reviewed by SSE"
    val steps = if (r.patrollerSignoff) listOf(R.string.g_step_captured, R.string.g_step_uploaded, R.string.g_step_checked, R.string.g_step_signed_off)
        else listOf(R.string.g_step_captured, R.string.g_step_uploaded, R.string.g_step_checked, R.string.g_step_reviewed, R.string.g_step_signed)
    val signed = r.reached >= steps.size
    Aura(glows = GlowsCool, base = Ink.Mist2) {
        Column(Edge.fillMaxSize().verticalScroll(rememberScrollState())) {
            BackBar(r.title, r.sub, onBack)
            Column(Modifier.padding(12.dp).fillMaxWidth().clip(RoundedCornerShape(30.dp)).background(Brush.linearGradient(listOf(Ink.Ink, if (signed) Color(0xFF0B4D3A) else Color(0xFF1B2470))))
                .padding(18.dp)) {
                Text(stringResource(R.string.g_report_now).uppercase(), style = MaterialTheme.typography.labelSmall, color = Color(0xFFB8BCD0))
                Text(when { signed -> stringResource(R.string.g_signed_by, r.signedBy ?: "SSE"); r.patrollerSignoff -> stringResource(R.string.g_await_signoff)
                    else -> stringResource(R.string.g_with_sse) }, style = MaterialTheme.typography.headlineSmall, color = Ink.White)
                Text(r.error ?: stringResource(if (r.patrollerSignoff && !signed) R.string.g_signoff_hint else R.string.g_review_time),
                    style = MaterialTheme.typography.bodyMedium, color = Color(0xFFD3D6E6))
                if (r.canSignOff) {
                    Spacer(Modifier.height(14.dp))
                    Pill(stringResource(if (r.signing) R.string.g_signing_off else R.string.g_sign_off), onSignOff, Modifier.fillMaxWidth(),
                        PillKind.Signal, Icons.Outlined.Check, enabled = !r.signing)
                }
            }
            Column(Modifier.padding(horizontal = 12.dp).fillMaxWidth().glass(RoundedCornerShape(28.dp)).padding(16.dp, 8.dp)) {
                steps.forEachIndexed { i, res ->
                    val done = i < r.reached; val now = i == r.reached
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 10.dp)) {
                        Box(Modifier.size(26.dp).clip(CircleShape).background(if (done) Ink.Ink else Ink.White)
                            .border(3.dp, if (done) Ink.Ink else if (now) Ink.Electric else Color(0xFFC4C8D8), CircleShape), contentAlignment = Alignment.Center) {
                            if (done) Icon(Icons.Outlined.Check, null, tint = Ink.White, modifier = Modifier.size(14.dp))
                        }
                        Spacer(Modifier.width(14.dp))
                        Text(stringResource(res), style = MaterialTheme.typography.titleMedium.copy(fontWeight = if (now) FontWeight.ExtraBold else FontWeight.Bold),
                            color = if (now) Ink.ElectricDeep else if (done) Ink.Ink else Ink.Muted)
                    }
                }
            }
            if (r.findings.isNotEmpty() || r.amendments.isNotEmpty()) {
                Spacer(Modifier.height(12.dp))
                GlassCard(Modifier.padding(horizontal = 12.dp).fillMaxWidth(), strong = true) {
                    Eyebrow(stringResource(R.string.g_findings), Ink.Muted)
                    r.findings.forEach { (f, urgent) ->
                        Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                            if (urgent) { StatusChip(stringResource(R.string.ohe_urgent), Tone.Urgent); Spacer(Modifier.width(8.dp)) }
                            Text(f, style = MaterialTheme.typography.bodyLarge, color = Ink.Ink)
                        }
                    }
                    r.amendments.forEach { a ->
                        Spacer(Modifier.height(10.dp))
                        Text("${stringResource(R.string.g_amended)}: $a", Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFFFFF4E0)).padding(12.dp),
                            style = MaterialTheme.typography.bodyMedium, color = Color(0xFF6B3A00))
                    }
                }
            }
            Spacer(Modifier.height(16.dp))
            Pill(stringResource(R.string.g_refresh), onRefresh, Modifier.padding(horizontal = 12.dp).fillMaxWidth(), PillKind.Glass, Icons.Outlined.Refresh)
            Spacer(Modifier.height(24.dp))
        }
    }
}

// ---------------------------------------------------------------------------------------------------------------- alerts

data class AlertUi(val id: String, val title: String, val sub: String, val unread: Boolean, val urgent: Boolean, val sessionId: String)

@Composable
fun AlertsScreen(rows: List<AlertUi>, offline: Boolean, onOpen: (AlertUi) -> Unit, onMarkAll: () -> Unit) {
    val unread = rows.count { it.unread }
    Aura(glows = GlowsWarm, base = Ink.Mist2) {
        Column(Edge.fillMaxSize()) {
            Row(Modifier.padding(16.dp, 12.dp), verticalAlignment = Alignment.Bottom) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.g_alerts_title), style = MaterialTheme.typography.displaySmall, color = Ink.Ink)
                    Text(if (unread > 0) stringResource(R.string.g_alerts_new, unread) else stringResource(R.string.g_alerts_none), style = MaterialTheme.typography.bodyMedium, color = Ink.Body)
                }
                Pill(stringResource(R.string.g_mark_read), onMarkAll, kind = PillKind.Glass, height = 42.dp)
            }
            if (offline) Text(stringResource(R.string.g_server_offline), Modifier.padding(horizontal = 16.dp), style = MaterialTheme.typography.bodyMedium, color = Ink.SafetyText)
            LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(12.dp, 8.dp, 12.dp, 110.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (rows.isEmpty()) item {
                    Column(Modifier.fillMaxWidth().padding(40.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Outlined.Check, null, tint = Ink.Mint, modifier = Modifier.size(40.dp))
                        Text(stringResource(R.string.g_alerts_none), style = MaterialTheme.typography.titleMedium)
                    }
                }
                items(rows, key = { it.id }) { a ->
                    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(26.dp)).background(if (a.unread) Color(0xD1FFFFFF) else Color(0x73FFFFFF))
                        .border(1.dp, Ink.GlassEdge, RoundedCornerShape(26.dp)).clickable { onOpen(a) }.padding(14.dp)) {
                        Box(Modifier.size(46.dp).clip(RoundedCornerShape(16.dp)).background(if (a.urgent) Ink.Safety else Ink.Electric), contentAlignment = Alignment.Center) {
                            Icon(if (a.urgent) Icons.Outlined.Warning else Icons.Outlined.Notifications, null, tint = Ink.White)
                        }
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(a.title, style = MaterialTheme.typography.titleMedium.copy(fontWeight = if (a.unread) FontWeight.ExtraBold else FontWeight.SemiBold), color = Ink.Ink)
                            Text(a.sub, style = MaterialTheme.typography.bodyMedium, color = Ink.Body)
                            Text(stringResource(R.string.g_view_report), style = MaterialTheme.typography.labelMedium, color = if (a.urgent) Ink.SafetyText else Ink.ElectricDeep)
                        }
                        if (a.unread) Box(Modifier.size(10.dp).clip(CircleShape).background(Ink.Electric))
                    }
                }
            }
        }
    }
}

// --------------------------------------------------------------------------------------------------------------- profile

data class ProfileState(val name: String, val id: String, val role: String, val hindi: Boolean, val tts: Boolean, val haptics: Boolean, val large: Boolean,
                        val tpc: String, val server: String, val serverOk: Boolean?, val version: String, val updateVersion: String?, val updating: Boolean,
                        val searching: Boolean, val found: List<FoundServer>)

@Composable
fun ProfileScreen(st: ProfileState, onLang: (Boolean) -> Unit, onToggle: (String, Boolean) -> Unit, onTpc: (String) -> Unit,
                  onFind: () -> Unit, onUseServer: (String) -> Unit, onUpdate: () -> Unit, onSignOut: () -> Unit) {
    var tpc by remember(st.tpc) { mutableStateOf(st.tpc) }
    Aura(glows = listOf(Glow(Ink.Amber, 1f, 0f, 0.8f, 0.4f), Glow(Ink.Electric, 0f, 0.55f, 0.8f, 0.35f)), base = Ink.Mist2) {
        Column(Edge.fillMaxSize().verticalScroll(rememberScrollState()).padding(12.dp).padding(bottom = 100.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(30.dp)).background(Brush.linearGradient(listOf(Ink.Ink, Color(0xFF1B2470)))).padding(18.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(64.dp).clip(CircleShape).background(Brush.sweepGradient(listOf(Ink.Electric, Ink.Aqua, Ink.Amber, Color(0xFFFF5A36), Ink.Electric))).padding(3.dp)) {
                    Box(Modifier.fillMaxSize().clip(CircleShape).background(Ink.Ink), contentAlignment = Alignment.Center) {
                        Text(st.name.take(2).uppercase(), color = Ink.Signal, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                    }
                }
                Spacer(Modifier.width(14.dp))
                Column {
                    Text(st.name, style = MaterialTheme.typography.titleLarge, color = Ink.White)
                    Text(stringResource(R.string.g_role, st.role, st.id), style = MaterialTheme.typography.bodyMedium, color = Color(0xFFC9CCE0))
                }
            }
            GlassCard(Modifier.fillMaxWidth(), strong = true) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(46.dp).clip(RoundedCornerShape(16.dp)).background(if (st.updateVersion != null) Ink.Electric else Ink.Mint), contentAlignment = Alignment.Center) {
                        Icon(if (st.updateVersion != null) Icons.Outlined.Download else Icons.Outlined.Check, null, tint = Ink.White)
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(if (st.updateVersion != null) stringResource(R.string.update_available, st.updateVersion) else stringResource(R.string.g_up_to_date), style = MaterialTheme.typography.titleMedium)
                        Text(stringResource(R.string.app_version, st.version), style = MaterialTheme.typography.bodyMedium, color = Ink.Body)
                    }
                }
                if (st.updateVersion != null) {
                    Spacer(Modifier.height(12.dp))
                    Pill(if (st.updating) stringResource(R.string.update_downloading) else stringResource(R.string.update_install), onUpdate, Modifier.fillMaxWidth(),
                        PillKind.Primary, enabled = !st.updating, height = 50.dp)
                    Text(stringResource(R.string.g_photos_safe), style = MaterialTheme.typography.bodyMedium, color = Ink.Muted, modifier = Modifier.padding(top = 6.dp))
                }
            }
            GlassCard(Modifier.fillMaxWidth()) {
                Eyebrow(stringResource(R.string.language) + " · भाषा", Ink.Muted)
                Spacer(Modifier.height(10.dp))
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(50)).background(Color(0x120E1020)).padding(4.dp)) {
                    listOf("English" to false, "हिंदी" to true).forEach { (t, h) ->
                        val on = st.hindi == h
                        Surface(onClick = { onLang(h) }, shape = RoundedCornerShape(50), color = if (on) Ink.White else Color.Transparent,
                            shadowElevation = if (on) 2.dp else 0.dp, modifier = Modifier.weight(1f).height(44.dp)) {
                            Box(contentAlignment = Alignment.Center) { Text(t, style = MaterialTheme.typography.labelLarge) }
                        }
                    }
                }
            }
            GlassCard(Modifier.fillMaxWidth(), padding = 6.dp) {
                ToggleRow(stringResource(R.string.g_speak), stringResource(R.string.g_speak_sub), st.tts) { onToggle("tts", it) }
                ToggleRow(stringResource(R.string.g_buzz), stringResource(R.string.g_buzz_sub), st.haptics) { onToggle("haptics", it) }
                ToggleRow(stringResource(R.string.g_large), null, st.large) { onToggle("large", it) }
                Column(Modifier.padding(12.dp)) {
                    OutlinedTextField(tpc, { tpc = it; onTpc(it) }, Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(18.dp),
                        label = { Text(stringResource(R.string.g_tpc_number)) }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                        colors = OutlinedTextFieldDefaults.colors(focusedContainerColor = Ink.White, unfocusedContainerColor = Color(0xCCFFFFFF)))
                }
            }
            ServerChip(st.serverOk, st.server.removePrefix("http://").trimEnd('/'), onFind)
            ServerPanel(st.server, st.searching, st.found, onFind, onUseServer)
            Pill(stringResource(R.string.ohe_sign_out), onSignOut, Modifier.fillMaxWidth(), PillKind.Glass, Icons.Outlined.Logout)
        }
    }
}

@Composable
private fun ToggleRow(title: String, sub: String?, on: Boolean, onChange: (Boolean) -> Unit) =
    Row(Modifier.fillMaxWidth().clickable { onChange(!on) }.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold), color = Ink.Ink)
            if (sub != null) Text(sub, style = MaterialTheme.typography.bodyMedium, color = Ink.Muted)
        }
        Switch(on, onChange, colors = SwitchDefaults.colors(checkedTrackColor = Ink.Mint, checkedThumbColor = Ink.White))
    }
