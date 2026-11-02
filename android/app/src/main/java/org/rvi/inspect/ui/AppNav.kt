package org.rvi.inspect.ui

import android.Manifest
import android.view.HapticFeedbackConstants
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.os.LocaleListCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import org.rvi.inspect.R
import org.rvi.inspect.domain.Command
import org.rvi.inspect.domain.CommandMatcher
import org.rvi.inspect.ui.screens.BookRow
import org.rvi.inspect.ui.screens.ClassifyScreen
import org.rvi.inspect.ui.screens.ClassifyState
import org.rvi.inspect.ui.screens.DangerSheet
import org.rvi.inspect.ui.screens.HomeScreen
import org.rvi.inspect.ui.screens.HomeState
import org.rvi.inspect.ui.screens.OheEndScreen
import org.rvi.inspect.ui.screens.OheHomeScreen
import org.rvi.inspect.ui.screens.OheHomeState
import org.rvi.inspect.ui.screens.OheHud
import org.rvi.inspect.ui.screens.OheHudState
import org.rvi.inspect.ui.screens.OheNoteSheet
import org.rvi.inspect.ui.screens.promptRes
import org.rvi.inspect.ui.screens.KitCheckScreen
import org.rvi.inspect.ui.screens.PatrolHud
import org.rvi.inspect.ui.screens.ReviewItem
import org.rvi.inspect.ui.screens.ReviewScreen
import org.rvi.inspect.ui.screens.SettingsScreen
import org.rvi.inspect.ui.screens.SettingsState
import org.rvi.inspect.ui.screens.SummaryScreen
import org.rvi.inspect.voice.VoiceController

/** Most frequent combined-patrol findings first: track (Phase 1 UC-01/02/03) then OHE (RDSO TI/MI/0060 6.1(4)). */
val SUGGESTED = listOf("PW-FS-001", "EL-OH-004", "PW-RL-008", "EL-OH-001", "PW-FS-002", "EL-OH-008", "EL-OH-014", "PW-JT-001", "PW-BF-007")

fun currentLang(): String = AppCompatDelegate.getApplicationLocales().get(0)?.language ?: java.util.Locale.getDefault().language

@Composable
fun AppNav(vm: PatrolViewModel = viewModel(), ovm: OheViewModel = viewModel()) {
    val nav = rememberNavController()
    val context = LocalContext.current
    val view = LocalView.current
    val settings by vm.settings.collectAsState()
    val patrol by vm.activePatrol.collectAsState()
    val pending by vm.pending.collectAsState()
    val findings by vm.findings.collectAsState()
    val draft by vm.draft.collectAsState()
    val lang = currentLang()
    val voiceTag = if (lang == "hi") "hi-IN" else "en-IN"
    val voice = remember { VoiceController(context) }
    val camera = remember { CameraHandle() }
    val vstate by voice.state.collectAsState()
    var heard by remember { mutableStateOf<String?>(null) }
    var danger by remember { mutableStateOf(false) }
    var dangerKind by remember { mutableStateOf<String?>(null) }
    val perms = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { }
    LaunchedEffect(Unit) { perms.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO, Manifest.permission.ACCESS_FINE_LOCATION)) }
    DisposableEffect(Unit) { onDispose { voice.release() } }

    fun confirm(msg: Int) {
        if (settings?.haptics != false) view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
        if (settings?.tts != false) voice.speak(context.getString(msg), voiceTag)
    }

    fun capture() = camera.take(context, onSaved = { f -> vm.onCaptured(f); nav.navigate("classify") }, onError = { })

    fun oheCapture() = camera.take(context, onSaved = { f -> ovm.onCaptured(f) }, onError = { })
    var noteOpen by remember { mutableStateOf(false) }
    var noteText by remember { mutableStateOf("") }

    voice.onResult = { text ->
        heard = text
        val route = nav.currentBackStackEntry?.destination?.route
        if (route == "ohe_hud") {
            // HLD finite command set: photo, note, end patrol. Nothing spoken can classify or confirm a defect.
            when (val c = CommandMatcher.match(text)) {
                Command.Capture -> oheCapture()
                Command.EndPatrol -> { ovm.end(); nav.navigate("ohe_end") { popUpTo("ohe_home") } }
                is Command.Note -> if (noteOpen) noteText = c.text else { ovm.note(c.text); confirm(R.string.saved_offline) }
                else -> if (noteOpen) noteText = text else confirm(R.string.command_not_understood)
            }
        } else when (val c = CommandMatcher.match(text)) {
            Command.Capture -> capture()
            Command.EndPatrol -> { vm.endPatrol(); nav.navigate("summary") }
            Command.Danger -> { dangerKind = null; danger = true }
            is Command.Defect -> vm.update { it.copy(classId = c.classId) }
            is Command.Note -> vm.update { it.copy(note = c.text) }
            Command.Save -> if (vm.saveDraft(lang)) { confirm(R.string.saved_offline); nav.popBackStack() }
            null -> confirm(R.string.command_not_understood)
            else -> {}
        }
    }

    NavHost(nav, startDestination = "ohe_home") {
        composable("ohe_home") {
            val s = settings
            val active by ovm.active.collectAsState()
            val latest by ovm.latest.collectAsState()
            val opending by ovm.pending.collectAsState()
            var territory by remember { mutableStateOf("SEC-DEMO-01") }
            var server by remember(s?.serverUrl) { mutableStateOf(s?.serverUrl ?: "") }
            var inspector by remember(s?.inspectorId) { mutableStateOf(s?.inspectorId ?: "") }
            val signMsg by ovm.signMsg.collectAsState()
            val upd by ovm.update.collectAsState()
            val updating by ovm.updating.collectAsState()
            LaunchedEffect(s?.token, s?.serverUrl) { ovm.checkUpdate() }
            OheHomeScreen(OheHomeState(inspector, territory, server, active != null, opending, !s?.token.isNullOrBlank(), signMsg,
                "${org.rvi.inspect.BuildConfig.VERSION_NAME} (${org.rvi.inspect.BuildConfig.VERSION_CODE})", upd?.versionName, upd?.notes.orEmpty(), updating),
                onTerritory = { territory = it }, onServer = { server = it; ovm.setServer(it) }, onInspector = { inspector = it; ovm.setInspector(it) },
                onStart = { ovm.start(territory); nav.navigate("ohe_hud") }, onResume = { nav.navigate("ohe_hud") },
                onSettings = { nav.navigate("settings") },
                onLastReport = if (active == null && latest?.endedAt != null) ({ nav.navigate("ohe_end") }) else null,
                onSignIn = { pin -> ovm.signIn(inspector, pin) }, onSignOut = { ovm.signOut() }, onUpdate = { ovm.installUpdate() })
        }
        composable("ohe_hud") {
            val caps by ovm.captures.collectAsState()
            val notes by ovm.notes.collectAsState()
            val local by ovm.prompt.collectAsState()
            val last = caps.lastOrNull()
            val prompt = if (last != null && !last.uploaded) local else ovm.serverPrompt(caps) ?: local.takeIf { last?.uploaded != true }
            LaunchedEffect(prompt, caps.size) { prompt?.let { if (settings?.tts != false) voice.speak(context.getString(promptRes(it)), voiceTag) } }
            OheHud(OheHudState(caps.size, caps.count { it.uploaded }, caps.count { it.findings > 0 }, caps.count { it.alert }, notes, prompt,
                vstate is VoiceController.State.Listening, heard),
                onCapture = { oheCapture() }, onVoice = { voice.listen(voiceTag) }, onNote = { noteText = ""; noteOpen = true },
                onEnd = { ovm.end(); nav.navigate("ohe_end") { popUpTo("ohe_home") } }, background = { CameraPreview(camera) })
            if (noteOpen) OheNoteSheet(noteText, { noteText = it }, { voice.listen(voiceTag) },
                onSave = { ovm.note(noteText); noteOpen = false; confirm(R.string.saved_offline) }, onCancel = { noteOpen = false })
        }
        composable("ohe_end") {
            val caps by ovm.captures.collectAsState()
            val notes by ovm.notes.collectAsState()
            val latest by ovm.latest.collectAsState()
            OheEndScreen(summaryFrom(latest, caps, notes), onRetry = { ovm.retrySync() },
                onHome = { nav.navigate("ohe_home") { popUpTo("ohe_home") { inclusive = true } } })
        }
        composable("home") {
            HomeScreen(HomeState(settings?.inspectorId ?: "", patrol?.beatFromKm ?: "1204/0", patrol?.beatToKm ?: "1207/4",
                patrol?.line ?: "UP", context.getString(R.string.role_keyman) + " · CP-01", patrol != null, pending, true),
                onStart = { nav.navigate("kit") }, onResume = { nav.navigate("patrol") },
                onSettings = { nav.navigate("settings") }, onReview = { nav.navigate("review") })
        }
        composable("kit") {
            val checked = remember { mutableStateListOf(*Array(org.rvi.inspect.ui.screens.KIT_ITEMS.size) { false }) }
            KitCheckScreen(checked, { checked[it] = !checked[it] }) {
                vm.startPatrol("CP-01", "1204/0", "1207/4", "UP"); nav.navigate("patrol") { popUpTo("home") }
            }
        }
        composable("patrol") {
            PatrolHud(km = draft.km.ifBlank { patrol?.beatFromKm ?: "—" }, findings = findings.size,
                listening = vstate is VoiceController.State.Listening, heard = heard,
                onCapture = { capture() }, onVoice = { voice.listen(voiceTag) }, onDanger = { dangerKind = null; danger = true },
                onEnd = { vm.endPatrol(); nav.navigate("summary") }, background = { CameraPreview(camera) })
            if (danger) DangerSheet(dangerKind, draft.protectedAt != null, draft.smInformedAt != null, draft.tpcInformedAt != null,
                draft.keptClearAt != null, onKind = { dangerKind = it },
                onProtected = { vm.update { it.copy(protectedAt = System.currentTimeMillis()) } },
                onSm = { vm.update { it.copy(smInformedAt = System.currentTimeMillis()) } },
                onTpc = { vm.update { it.copy(tpcInformedAt = System.currentTimeMillis()) } },
                onClear = { vm.update { it.copy(keptClearAt = System.currentTimeMillis()) } },
                onCallTpc = { context.startActivity(android.content.Intent(android.content.Intent.ACTION_DIAL, android.net.Uri.parse("tel:" + (settings?.tpcNumber ?: "")))) },
                onContinue = { danger = false; capture() })
        }
        composable("classify") {
            var q by remember { mutableStateOf("") }
            var dom by remember { mutableStateOf("all") }
            val tax = vm.taxonomy
            val sel = tax.classes.firstOrNull { it.id == draft.classId }
            ClassifyScreen(ClassifyState(lang, q, SUGGESTED.mapNotNull { id -> tax.beta.firstOrNull { it.id == id } }, tax.search(q, lang, dom), sel,
                draft.quality?.passed, draft.km, draft.line, draft.rail, draft.action, draft.note,
                draft.lat?.let { "GNSS %.5f, %.5f ±%.0f m".format(it, draft.lon, draft.accuracy ?: 0f) }, dom),
                onQuery = { q = it }, onSelect = { c -> vm.update { it.copy(classId = c.id) } }, onKm = { v -> vm.update { it.copy(km = v) } },
                onLine = { v -> vm.update { it.copy(line = v) } }, onRail = { v -> vm.update { it.copy(rail = v) } },
                onAction = { v -> vm.update { it.copy(action = v) } }, onNote = { v -> vm.update { it.copy(note = v) } },
                onDictate = { voice.listen(voiceTag) },
                onSave = { if (vm.saveDraft(lang)) { confirm(R.string.saved_offline); nav.popBackStack() } else { dangerKind = sel?.danger; danger = true } },
                onDomain = { dom = it })
            if (danger) DangerSheet(dangerKind, draft.protectedAt != null, draft.smInformedAt != null, draft.tpcInformedAt != null,
                draft.keptClearAt != null, onKind = { dangerKind = it },
                onProtected = { vm.update { it.copy(protectedAt = System.currentTimeMillis()) } },
                onSm = { vm.update { it.copy(smInformedAt = System.currentTimeMillis()) } },
                onTpc = { vm.update { it.copy(tpcInformedAt = System.currentTimeMillis()) } },
                onClear = { vm.update { it.copy(keptClearAt = System.currentTimeMillis()) } },
                onCallTpc = { context.startActivity(android.content.Intent(android.content.Intent.ACTION_DIAL, android.net.Uri.parse("tel:" + (settings?.tpcNumber ?: "")))) },
                onContinue = { danger = false })
        }
        composable("summary") {
            val tax = vm.taxonomy
            SummaryScreen(findings.map { f -> BookRow(f.kmReference, tax.classes.firstOrNull { it.id == f.classId }?.label?.forLang(lang) ?: f.classId,
                f.actionTaken, f.lineProtectedAt != null, tax.classes.firstOrNull { it.id == f.classId }?.domain ?: "track") }) { nav.navigate("home") { popUpTo("home") { inclusive = true } } }
        }
        composable("review") {
            val recent by vm.recent.collectAsState()
            val sev = remember { mutableStateMapOf<String, String>() }
            val tax = vm.taxonomy
            ReviewScreen(recent.map { f -> ReviewItem(f.id, f.kmReference, tax.classes.firstOrNull { it.id == f.classId }?.label?.forLang(lang) ?: f.classId,
                f.classId.take(5), settings?.inspectorId ?: "", f.note, tax.classes.firstOrNull { it.id == f.classId }?.route ?: "") }, sev, { id, s -> sev[id] = s }, { }, { })
        }
        composable("settings") {
            val s = settings
            SettingsScreen(SettingsState(lang, s?.voice ?: true, s?.tts ?: true, s?.largeText ?: false, s?.haptics ?: true),
                onLang = { tag -> AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(tag)) },
                onToggle = { k, v -> vm.toggle(k, v) })
        }
    }
}
