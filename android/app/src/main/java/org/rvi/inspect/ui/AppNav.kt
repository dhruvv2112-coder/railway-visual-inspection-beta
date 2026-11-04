package org.rvi.inspect.ui

import android.Manifest
import android.view.HapticFeedbackConstants
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.os.LocaleListCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import kotlinx.coroutines.delay
import org.rvi.inspect.R
import org.rvi.inspect.domain.Command
import org.rvi.inspect.domain.CommandMatcher
import org.rvi.inspect.ui.components.FloatingTabBar
import org.rvi.inspect.ui.components.Tab
import org.rvi.inspect.ui.components.Tone
import org.rvi.inspect.ui.screens.*
import org.rvi.inspect.voice.VoiceController
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** Kept for the earlier combined-patrol screens and tests. */
val SUGGESTED = listOf("PW-FS-001", "EL-OH-004", "PW-RL-008", "EL-OH-001", "PW-FS-002", "EL-OH-008", "EL-OH-014", "PW-JT-001", "PW-BF-007")

fun currentLang(): String = AppCompatDelegate.getApplicationLocales().get(0)?.language ?: java.util.Locale.getDefault().language

private val dayFmt = DateTimeFormatter.ofPattern("EEE d MMM · HH:mm")
private fun whenText(ms: Long?) = ms?.let { Instant.ofEpochMilli(it).atZone(ZoneId.systemDefault()).format(dayFmt) } ?: ""
private fun whenIso(iso: String?) = iso?.let { runCatching { java.time.LocalDateTime.parse(iso.take(19)).atZone(ZoneId.of("UTC")).withZoneSameInstant(ZoneId.systemDefault()).format(dayFmt) }.getOrNull() } ?: ""

@Composable
fun AppNav(ovm: OheViewModel = viewModel()) {
    val nav = rememberNavController()
    val context = LocalContext.current
    val view = LocalView.current
    val settings by ovm.settings.collectAsState()
    val lang = currentLang()
    val hindi = lang == "hi"
    val voiceTag = if (hindi) "hi-IN" else "en-IN"
    val voice = remember { VoiceController(context) }
    val camera = remember { CameraHandle() }
    val vstate by voice.state.collectAsState()
    var heard by remember { mutableStateOf<String?>(null) }
    val serverOk by ovm.serverOk.collectAsState()
    val searching by ovm.searching.collectAsState()
    val found by ovm.found.collectAsState()
    val alertsList by ovm.alerts.collectAsState()
    val readAlerts by ovm.readAlerts.collectAsState()
    val unread = alertsList.orEmpty().count { it.findingId !in readAlerts }
    val perms = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { }
    LaunchedEffect(Unit) { perms.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO, Manifest.permission.ACCESS_FINE_LOCATION)) }
    DisposableEffect(Unit) { onDispose { voice.release() } }
    // Keep an eye on the server: reachability every 20 s, alerts every 30 s.
    LaunchedEffect(settings?.serverUrl, settings?.token) {
        if (settings == null) return@LaunchedEffect
        ovm.checkServer(); delay(1500)
        if (ovm.serverOk.value != true) ovm.findServers(autoPick = true)
        while (true) {
            delay(20_000); ovm.checkServer(); delay(4000)
            if (ovm.serverOk.value != true) ovm.findServers(autoPick = true)
            if (!settings?.token.isNullOrBlank()) ovm.loadAlerts()
        }
    }
    LaunchedEffect(settings?.token) { if (!settings?.token.isNullOrBlank()) { ovm.loadAlerts(); ovm.loadReports(); ovm.checkUpdate() } }

    fun say(msg: Int) {
        if (settings?.haptics != false) view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
        if (settings?.tts != false) voice.speak(context.getString(msg), voiceTag)
    }
    fun setLang(h: Boolean) = AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(if (h) "hi" else "en"))
    fun oheCapture() = camera.take(context, onSaved = { f -> ovm.onCaptured(f) }, onError = { })
    fun dialTpc() = context.startActivity(android.content.Intent(android.content.Intent.ACTION_DIAL, android.net.Uri.parse("tel:" + (settings?.tpcNumber ?: ""))))
    val viaInternet by ovm.viaInternet.collectAsState()
    val internetLabel = stringResource(R.string.g_via_internet)
    fun host() = if (viaInternet) internetLabel else (settings?.serverUrl ?: "").removePrefix("http://").removePrefix("https://").trimEnd('/')
    var noteOpen by remember { mutableStateOf(false) }
    var noteText by remember { mutableStateOf("") }
    var urgentFor by remember { mutableStateOf<String?>(null) }   // capture id (or "manual") the urgent sheet is showing
    val seenAlerts = remember { mutableStateListOf<String>() }

    voice.onResult = { text ->
        heard = text
        if (nav.currentBackStackEntry?.destination?.route == "hud") {
            // HLD finite command set: photo, note, end patrol. Nothing spoken can classify or confirm a defect.
            when (val c = CommandMatcher.match(text)) {
                Command.Capture -> oheCapture()
                Command.EndPatrol -> { ovm.end(); nav.navigate("end") { popUpTo("home") } }
                is Command.Note -> if (noteOpen) noteText = c.text else { ovm.note(c.text); say(R.string.saved_offline) }
                else -> if (noteOpen) noteText = text else say(R.string.command_not_understood)
            }
        } else if (noteOpen) noteText = text
    }

    val signedIn = !settings?.token.isNullOrBlank()
    if (settings == null) return
    val start = remember { if (signedIn) "home" else "signin" }
    NavHost(nav, startDestination = start) {
        composable("signin") {
            var id by remember(settings?.inspectorId) { mutableStateOf(settings?.inspectorId?.takeIf { it != "CP-0412" } ?: "") }
            var pin by remember { mutableStateOf("") }
            var showServer by remember { mutableStateOf(false) }
            val busy by ovm.signingIn.collectAsState()
            val msg by ovm.signMsg.collectAsState()
            SignInScreen(SignInState(id, pin.length, busy, msg, settings?.serverUrl ?: "", serverOk, searching, found, hindi, showServer || serverOk == false),
                onId = { id = it.uppercase().trim() }, onDigit = { if (pin.length < 8) pin += it }, onBackspace = { pin = pin.dropLast(1) },
                onSubmit = { ovm.signIn(id, pin) { pin = ""; nav.navigate("home") { popUpTo("signin") { inclusive = true } } } },
                onLang = ::setLang, onToggleServer = { showServer = !showServer; if (showServer) ovm.findServers() }, onFind = { ovm.findServers() },
                onUseServer = { ovm.useServer(it) })
        }
        composable("home") {
            val active by ovm.active.collectAsState()
            val latest by ovm.latest.collectAsState()
            val pending by ovm.pending.collectAsState()
            val upd by ovm.update.collectAsState()
            val updating by ovm.updating.collectAsState()
            val name by ovm.userName.collectAsState()
            val last = latest?.takeIf { it.endedAt != null }
            Tabs(nav, Tab.Home, unread) {
                OheHomeScreen(OheHomeState(name.ifBlank { settings?.inspectorId ?: "" }, active?.territory ?: latest?.territory ?: "SEC-1205",
                    active != null, pending, last?.let { "${it.territory} · ${whenText(it.endedAt)}" }, false, upd?.versionName, updating, serverOk, host()),
                    onStart = { nav.navigate("start") }, onResume = { nav.navigate("hud") },
                    onLastReport = { last?.reportId?.let { nav.navigate("report/$it") } ?: nav.navigate("end") },
                    onUpdate = { ovm.installUpdate() }, onProfile = { nav.navigate("profile") }, onServer = { nav.navigate("profile") })
            }
        }
        composable("start") {
            val latest by ovm.latest.collectAsState()
            var territory by remember { mutableStateOf(latest?.territory ?: "SEC-1205") }
            StartSheet(StartState(territory), onTerritory = { territory = it.uppercase() }, onClose = { nav.popBackStack() },
                onStart = { ovm.start(territory); nav.navigate("hud") { popUpTo("home") } })
        }
        composable("hud") {
            val caps by ovm.captures.collectAsState()
            val notes by ovm.notes.collectAsState()
            val local by ovm.prompt.collectAsState()
            val active by ovm.active.collectAsState()
            var zoom by remember { mutableFloatStateOf(1f) }
            var dismissed by remember { mutableStateOf<String?>(null) }
            var toast by remember { mutableStateOf<ToastKind?>(null) }
            val last = caps.lastOrNull()
            val raw = if (last != null && !last.uploaded) local else ovm.serverPrompt(caps) ?: local.takeIf { last?.uploaded != true }
            val prompt = raw.takeIf { last?.id != dismissed }
            LaunchedEffect(prompt, caps.size) { prompt?.let { if (settings?.tts != false) voice.speak(context.getString(promptRes(it)), voiceTag) } }
            LaunchedEffect(last?.id, last?.uploaded, last?.findings) {
                if (last == null) return@LaunchedEffect
                toast = when { !last.uploaded -> if (serverOk == true) ToastKind.Uploading else ToastKind.Saved; last.findings > 0 -> ToastKind.Flagged
                    last.prompt == null && last.imageState != "missing_file" -> ToastKind.Checked; else -> null }
                if (last.uploaded && last.alert && last.id !in seenAlerts) { seenAlerts.add(last.id); urgentFor = last.id; say(R.string.g_urgent_title) }
                delay(4000); toast = null
            }
            Box(Modifier.fillMaxSize()) {
                OheHud(OheHudState(caps.size, caps.count { it.uploaded }, caps.count { it.findings > 0 }, caps.count { it.alert }, notes, prompt,
                    vstate is VoiceController.State.Listening, heard, active?.territory ?: "", zoom, camera.maxZoom().coerceAtLeast(1f), toast,
                    caps.map { Thumb(it.path, it.uploaded, it.findings > 0) }, serverOk),
                    onCapture = { oheCapture() }, onVoice = { voice.listen(voiceTag) }, onNote = { noteText = ""; noteOpen = true },
                    onEnd = { ovm.end(); nav.navigate("end") { popUpTo("home") } }, onZoom = { zoom = camera.zoom(it) },
                    onDanger = { urgentFor = "manual" }, onDismissPrompt = { dismissed = last?.id },
                    background = { CameraPreview(camera) })
                if (noteOpen) OheNoteSheet(noteText, { noteText = it }, { voice.listen(voiceTag) },
                    onSave = { ovm.note(noteText); noteOpen = false; say(R.string.saved_offline) }, onCancel = { noteOpen = false },
                    listening = vstate is VoiceController.State.Listening)
                urgentFor?.let { u -> UrgentSheet(null, if (u == "manual") 0 else 2, onCallTpc = { dialTpc() }, onContinue = { urgentFor = null }) }
            }
        }
        composable("end") {
            val caps by ovm.captures.collectAsState()
            val notes by ovm.notes.collectAsState()
            val latest by ovm.latest.collectAsState()
            OheEndScreen(summaryFrom(latest, caps, notes), onRetry = { ovm.retrySync() },
                onHome = { nav.navigate("home") { popUpTo("home") { inclusive = true } } },
                onTrack = latest?.reportId?.let { rid -> { nav.navigate("report/$rid") } })
        }
        composable("patrols") {
            val sessions by ovm.sessions.collectAsState()
            val reports by ovm.reports.collectAsState()
            LaunchedEffect(Unit) { ovm.loadReports() }
            val stUp = stringResource(R.string.g_st_uploading); val stRev = stringResource(R.string.g_st_review); val stSig = stringResource(R.string.g_st_signed)
            val onPhone = stringResource(R.string.g_this_phone)
            val server = reports.orEmpty().associateBy { it.id }
            val rows = sessions.map { s ->
                val r = s.reportId?.let { server[it] }
                val signed = r?.status == "SIGNED"
                val (st, tone) = when { s.reportId == null -> stUp to Tone.Info; signed -> stSig to Tone.Ok; else -> stRev to Tone.Urgent }
                val sub = r?.let { listOfNotNull(it.masts?.let { m -> "$m masts" }, it.alerts?.takeIf { a -> a > 0 }?.let { a -> "$a urgent" },
                    it.signedBy?.let { b -> "signed by $b" }).joinToString(" · ") } ?: "$onPhone · ${whenText(s.startedAt)}"
                PatrolRow(s.id, "${s.territory} · ${whenText(s.endedAt ?: s.startedAt)}", sub, st, tone, !signed, s.reportId)
            } + reports.orEmpty().filter { r -> sessions.none { it.reportId == r.id } }.map { r ->
                val signed = r.status == "SIGNED"
                PatrolRow(r.id, "${r.territory} · ${whenIso(r.endedAt)}", listOfNotNull(r.masts?.let { "$it masts" }, r.signedBy?.let { "signed by $it" }).joinToString(" · "),
                    if (signed) stSig else stRev, if (signed) Tone.Ok else Tone.Urgent, !signed, r.id)
            }
            Tabs(nav, Tab.Patrols, unread) {
                PatrolsScreen(rows, serverOk == false, onOpen = { r -> r.reportId?.let { nav.navigate("report/$it") } }, onRefresh = { ovm.loadReports(); ovm.retrySync() })
            }
        }
        composable("report/{rid}") { e ->
            val rid = e.arguments?.getString("rid") ?: ""
            val d by ovm.report.collectAsState()
            val err by ovm.reportError.collectAsState()
            LaunchedEffect(rid) { ovm.loadReport(rid) }
            val r = d?.takeIf { it.id == rid }
            val reached = when { r == null -> 3; r.status == "SIGNED" -> 5; r.amendments.isNotEmpty() || r.status == "SUPERSEDED" -> 4; else -> 3 }
            ReportScreen(ReportUi("RPT-01 · ${rid.take(8)}", listOfNotNull(r?.masts?.let { "$it masts" }, r?.alerts?.let { "$it urgent" }).joinToString(" · ").ifBlank { null } ?: "",
                reached, r?.signedBy, r?.amendments.orEmpty(), r?.findings.orEmpty(), err), onBack = { nav.popBackStack() }, onRefresh = { ovm.loadReport(rid) })
        }
        composable("alerts") {
            LaunchedEffect(Unit) { ovm.loadAlerts() }
            val sessions by ovm.sessions.collectAsState()
            val ui = alertsList.orEmpty().map { a ->
                AlertUi(a.findingId, a.what, listOfNotNull(a.territory.ifBlank { null }, a.assetId, whenIso(a.raisedAt).ifBlank { null }).joinToString(" · "),
                    a.findingId !in readAlerts, true, a.sessionId)
            }
            Tabs(nav, Tab.Alerts, unread) {
                AlertsScreen(ui, serverOk == false, onOpen = { a ->
                    ovm.markAlertRead(a.id)
                    val rid = ovm.reports.value.orEmpty().firstOrNull { it.id.isNotBlank() && sessions.any { s -> s.remoteId == a.sessionId && s.reportId == it.id } }?.id
                        ?: sessions.firstOrNull { it.remoteId == a.sessionId }?.reportId
                    rid?.let { nav.navigate("report/$it") }
                }, onMarkAll = { ovm.markAlertsRead() })
            }
        }
        composable("profile") {
            val upd by ovm.update.collectAsState()
            val updating by ovm.updating.collectAsState()
            val name by ovm.userName.collectAsState()
            val s = settings!!
            LaunchedEffect(Unit) { ovm.checkUpdate() }
            Tabs(nav, Tab.Profile, unread) {
                ProfileScreen(ProfileState(name.ifBlank { s.inspectorId }, s.inspectorId, s.role, hindi, s.tts, s.haptics, s.largeText, s.tpcNumber, s.serverUrl, serverOk,
                    "${org.rvi.inspect.BuildConfig.VERSION_NAME} (${org.rvi.inspect.BuildConfig.VERSION_CODE})", upd?.versionName, updating, searching, found),
                    onLang = ::setLang, onToggle = { k, v -> ovm.toggle(k, v) }, onTpc = { ovm.setTpc(it) }, onFind = { ovm.findServers() },
                    onUseServer = { ovm.useServer(it) }, onUpdate = { ovm.installUpdate() },
                    onSignOut = { ovm.signOut(); nav.navigate("signin") { popUpTo(nav.graph.id) { inclusive = true } } })
            }
        }
    }
}

/** Tab screens share the floating glass tab bar. */
@Composable
private fun Tabs(nav: NavHostController, tab: Tab, unread: Int, content: @Composable () -> Unit) {
    Box(Modifier.fillMaxSize()) {
        content()
        val labels = mapOf(Tab.Home to stringResource(R.string.tab_home), Tab.Patrols to stringResource(R.string.tab_patrols),
            Tab.Alerts to stringResource(R.string.tab_alerts), Tab.Profile to stringResource(R.string.tab_profile))
        FloatingTabBar(tab, { t ->
            if (t != tab) nav.navigate(when (t) { Tab.Home -> "home"; Tab.Patrols -> "patrols"; Tab.Alerts -> "alerts"; Tab.Profile -> "profile" }) {
                popUpTo("home") { saveState = true }; launchSingleTop = true; restoreState = true
            }
        }, labels, unread, Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(bottom = 14.dp))
    }
}
