package org.rvi.inspect.ui

import android.annotation.SuppressLint
import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive
import org.rvi.inspect.RviApp
import org.rvi.inspect.data.Hashing
import org.rvi.inspect.data.OheCaptureEntity
import org.rvi.inspect.data.OheSessionEntity
import org.rvi.inspect.data.Prompt
import org.rvi.inspect.data.UserSettings
import java.io.File

/** Counts shown on the end-of-patrol screen (RPT-02 summary from the server, or local counts while offline). */
data class OheSummary(val photos: Int, val uploaded: Int, val notes: Int, val reportId: String?, val expected: Int?, val evidenced: Int?,
                      val withFindings: Int?, val notAssessable: Int?, val alerts: Int?)

fun summaryFrom(session: OheSessionEntity?, caps: List<OheCaptureEntity>, notes: Int): OheSummary {
    val j = session?.summaryJson?.let { runCatching { Json.parseToJsonElement(it) as JsonObject }.getOrNull() }
    fun n(k: String) = j?.get(k)?.jsonPrimitive?.intOrNull
    return OheSummary(caps.size, caps.count { it.uploaded }, notes, session?.reportId, n("expected_assets"), n("evidenced_assets"),
        n("with_findings"), n("not_assessable"), n("alerts"))
}

@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
class OheViewModel(app: Application) : AndroidViewModel(app) {
    private val c = (app as RviApp).container
    private val repo = c.ohe
    val settings: StateFlow<UserSettings?> = c.repository.settings.stateIn(viewModelScope, SharingStarted.Eagerly, null)
    val active: StateFlow<OheSessionEntity?> = repo.active.stateIn(viewModelScope, SharingStarted.Eagerly, null)
    val latest: StateFlow<OheSessionEntity?> = repo.latest.stateIn(viewModelScope, SharingStarted.Eagerly, null)
    val pending = repo.pending.stateIn(viewModelScope, SharingStarted.Eagerly, 0)
    val captures: StateFlow<List<OheCaptureEntity>> = repo.latest
        .flatMapLatest { s -> if (s == null) flowOf(emptyList()) else repo.captures(s.id) }
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())
    val notes: StateFlow<Int> = repo.latest
        .flatMapLatest { s -> if (s == null) flowOf(0) else repo.notes(s.id) }
        .stateIn(viewModelScope, SharingStarted.Eagerly, 0)

    /** The latest request to retake (local quality check first, then the server's answer once uploaded). */
    val prompt = MutableStateFlow<Prompt?>(null)

    fun start(territory: String) = viewModelScope.launch { repo.start(territory.ifBlank { "SEC-DEMO-01" }) }

    fun end() = viewModelScope.launch { active.value?.let { repo.end(it.id) } }

    fun note(text: String) = viewModelScope.launch {
        val s = active.value ?: return@launch
        if (text.isNotBlank()) repo.addNote(s.id, text.trim())
    }

    fun setServer(url: String) = viewModelScope.launch { c.repository.setText("server", url) }

    // ---- laptop server: reachability and Wi-Fi discovery ----
    val sessions: StateFlow<List<OheSessionEntity>> = repo.sessions.stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())
    val serverOk = MutableStateFlow<Boolean?>(null)
    val searching = MutableStateFlow(false)
    val found = MutableStateFlow<List<org.rvi.inspect.data.FoundServer>>(emptyList())
    private val discovery = org.rvi.inspect.data.Discovery(app)

    /** Which way the phone reaches the laptop now: true = over the internet (tunnel), false = same Wi-Fi. */
    val viaInternet = MutableStateFlow(false)

    /** Keep a working route to the laptop: the current address, then the saved internet address, then the newest
     *  signed address on the relay (after a laptop restart), then Wi-Fi discovery. */
    fun checkServer() = viewModelScope.launch {
        val s = c.repository.settings.first()
        val D = org.rvi.inspect.data.Discovery
        if (s.serverUrl.isNotBlank() && D.reachable(s.serverUrl)) { serverOk.value = true; viaInternet.value = !D.isLocal(s.serverUrl); return@launch }
        if (s.remoteUrl.isNotBlank() && s.remoteUrl != s.serverUrl && D.reachable(s.remoteUrl)) { switchTo(s.remoteUrl); return@launch }
        val relayed = D.relayAddress(s.relayServer, s.relayTopic, s.relayKey)
        if (relayed != null && D.reachable(relayed)) { c.repository.setText("remote", relayed); switchTo(relayed); return@launch }
        serverOk.value = false
    }

    private suspend fun switchTo(url: String) {
        c.repository.setText("server", url)
        serverOk.value = true
        viaInternet.value = !org.rvi.inspect.data.Discovery.isLocal(url)
        repo.schedule()
    }

    /** Look for laptops on this Wi-Fi for a few seconds; if exactly one answers and none is set up yet, use it. */
    fun findServers(autoPick: Boolean = false) = viewModelScope.launch {
        if (searching.value) return@launch
        searching.value = true; found.value = emptyList()
        kotlinx.coroutines.withTimeoutOrNull(6000) {
            discovery.find().collect { f -> if (found.value.none { it.url == f.url }) found.value = found.value + f }
        }
        searching.value = false
        val cur = c.repository.settings.first().serverUrl
        if (autoPick && found.value.size == 1 && serverOk.value != true && found.value[0].url != cur) useServer(found.value[0].url)
    }

    fun useServer(raw: String) = viewModelScope.launch {
        val url = org.rvi.inspect.data.Discovery.normalise(raw)
        if (url.isBlank()) return@launch
        c.repository.setText("server", url)
        serverOk.value = null
        serverOk.value = org.rvi.inspect.data.Discovery.reachable(url)
        viaInternet.value = !org.rvi.inspect.data.Discovery.isLocal(url)
        if (serverOk.value == true) { repo.schedule(); if (!c.repository.settings.first().token.isBlank()) repo.pair() }
    }

    fun setTpc(n: String) = viewModelScope.launch { c.repository.setText("tpc", n) }
    fun toggle(k: String, v: Boolean) = viewModelScope.launch { c.repository.setToggle(k, v) }

    // ---- server lists: reports, alerts, one report ----
    val reports = MutableStateFlow<List<org.rvi.inspect.data.ReportRow>?>(null)
    val alerts = MutableStateFlow<List<org.rvi.inspect.data.AlertRow>?>(null)
    val report = MutableStateFlow<org.rvi.inspect.data.ReportDetail?>(null)
    val reportError = MutableStateFlow<String?>(null)
    val readAlerts = MutableStateFlow<Set<String>>(emptySet())

    fun loadReports() = viewModelScope.launch { reports.value = runCatching { repo.reports() }.getOrNull() ?: reports.value }
    fun loadAlerts() = viewModelScope.launch { alerts.value = runCatching { repo.alerts() }.getOrNull() ?: alerts.value }
    fun loadReport(rid: String) = viewModelScope.launch {
        reportError.value = null
        runCatching { repo.report(rid) }.onSuccess { report.value = it }.onFailure { reportError.value = it.message ?: "Not reachable" }
    }
    fun markAlertsRead() { readAlerts.value = readAlerts.value + (alerts.value.orEmpty().map { it.findingId }) }
    fun markAlertRead(id: String) { readAlerts.value = readAlerts.value + id }
    fun setInspector(id: String) = viewModelScope.launch { c.repository.setText("inspector", id) }
    fun retrySync() = repo.schedule()

    /** Sign-in message for the home screen: null = nothing to show. */
    val signMsg = MutableStateFlow<String?>(null)
    val signingIn = MutableStateFlow(false)
    val userName = MutableStateFlow("")
    fun signIn(id: String, pin: String, onOk: () -> Unit = {}) = viewModelScope.launch {
        signingIn.value = true; signMsg.value = null
        try { val out = repo.signIn(id, pin); userName.value = out.name.ifBlank { out.id }; signMsg.value = null; onOk() }
        catch (e: java.io.IOException) { signMsg.value = "Server not reachable – check Wi-Fi and the server address"; serverOk.value = false }
        catch (e: Exception) { signMsg.value = e.message ?: "Sign-in failed" }
        signingIn.value = false
    }
    fun signOut() = viewModelScope.launch { repo.signOut(); signMsg.value = null }

    /** Newer build on the server (null = up to date or not known). */
    val update = MutableStateFlow<org.rvi.inspect.data.AppRelease?>(null)
    val updating = MutableStateFlow(false)
    fun checkUpdate() = viewModelScope.launch {
        val r = repo.latestRelease()
        update.value = r.takeIf { org.rvi.inspect.data.isNewer(org.rvi.inspect.BuildConfig.VERSION_CODE, it) }
    }
    fun installUpdate() = viewModelScope.launch {
        val r = update.value ?: return@launch
        val (url, token) = repo.serverAndToken()
        updating.value = true
        org.rvi.inspect.data.Updater(getApplication()).download(url, token, r) { updating.value = false }
    }

    /** After CameraX saved the JPEG: hash it, check quality on the phone, attach a location fix, queue it. No
     *  classification and no confirmation: the server decides what the photo shows (HLD: no per-asset confirmation). */
    fun onCaptured(file: File) = viewModelScope.launch {
        val s = active.value ?: return@launch
        val q = PatrolViewModel.assessFile(file)
        prompt.value = if (q.passed) null else Prompt.fromLocal(q.reasons)
        val loc = locate()
        repo.addCapture(OheCaptureEntity(sessionId = s.id, path = file.absolutePath, sha256 = Hashing.sha256(file),
            lat = loc?.first, lon = loc?.second, accuracyM = loc?.third, localQualityOk = q.passed, localReasons = q.reasons.joinToString(",")))
    }

    /** Server prompt for the newest uploaded photo, if any (shown until the next capture). */
    fun serverPrompt(caps: List<OheCaptureEntity>): Prompt? =
        caps.lastOrNull()?.takeIf { it.uploaded }?.prompt?.let { runCatching { Prompt.valueOf(it) }.getOrNull() }

    @SuppressLint("MissingPermission") // permission requested by AppNav before the camera opens
    private suspend fun locate(): Triple<Double, Double, Float>? = runCatching {
        LocationServices.getFusedLocationProviderClient(getApplication<Application>())
            .getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, null).await()
            ?.let { Triple(it.latitude, it.longitude, it.accuracy) }
    }.getOrNull()
}
