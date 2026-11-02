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
    fun setInspector(id: String) = viewModelScope.launch { c.repository.setText("inspector", id) }
    fun retrySync() = repo.schedule()

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
