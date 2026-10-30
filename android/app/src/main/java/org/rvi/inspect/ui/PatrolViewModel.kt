package org.rvi.inspect.ui

import android.annotation.SuppressLint
import android.app.Application
import android.graphics.BitmapFactory
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
import org.rvi.inspect.RviApp
import org.rvi.inspect.data.FindingEntity
import org.rvi.inspect.data.PatrolEntity
import org.rvi.inspect.data.UserSettings
import org.rvi.inspect.domain.QualityGate
import java.io.File

/** Draft finding being composed after a capture (UI state). */
data class Draft(
    val imagePath: String? = null,
    val quality: QualityGate.Result? = null,
    val classId: String? = null,
    val km: String = "",
    val line: String = "UP",
    val rail: String = "L",
    val action: String = "",
    val note: String = "",
    val protectedAt: Long? = null,
    val smInformedAt: Long? = null,
    val lat: Double? = null,
    val lon: Double? = null,
    val accuracy: Float? = null,
)

@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
class PatrolViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = (app as RviApp).container.repository
    val taxonomy get() = repo.taxonomy

    val settings: StateFlow<UserSettings?> = repo.settings.stateIn(viewModelScope, SharingStarted.Eagerly, null)
    val activePatrol: StateFlow<PatrolEntity?> = repo.activePatrol.stateIn(viewModelScope, SharingStarted.Eagerly, null)
    val pending = repo.pendingCount.stateIn(viewModelScope, SharingStarted.Eagerly, 0)
    val findings: StateFlow<List<FindingEntity>> = repo.activePatrol
        .flatMapLatest { p -> if (p == null) flowOf(emptyList()) else repo.findings(p.id) }
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())
    val recent = repo.recentFindings.stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    val draft = MutableStateFlow(Draft())

    fun startPatrol(type: String, from: String, to: String, line: String) = viewModelScope.launch {
        val s = settings.value ?: return@launch
        repo.startPatrol(PatrolEntity(patrolType = type, inspectorId = s.inspectorId, role = s.role, beatFromKm = from,
            beatToKm = to, line = line, kitCheckOk = true))
    }

    fun endPatrol() = viewModelScope.launch { activePatrol.value?.let { repo.endPatrol(it.id) } }

    fun toggle(key: String, v: Boolean) = viewModelScope.launch { repo.setToggle(key, v) }

    /** Called after CameraX saved the JPEG: run the on-device quality gate and fetch a location fix. */
    fun onCaptured(file: File) = viewModelScope.launch {
        val q = assessFile(file)
        draft.value = Draft(imagePath = file.absolutePath, quality = q, line = activePatrol.value?.line ?: "UP")
        locate()
    }

    @SuppressLint("MissingPermission") // permission requested by the capture screen before use
    private suspend fun locate() = runCatching {
        val loc = LocationServices.getFusedLocationProviderClient(getApplication<Application>())
            .getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, null).await()
        if (loc != null) draft.value = draft.value.copy(lat = loc.latitude, lon = loc.longitude, accuracy = loc.accuracy)
    }

    fun update(f: (Draft) -> Draft) { draft.value = f(draft.value) }

    fun saveDraft(lang: String): Boolean {
        val d = draft.value
        val p = activePatrol.value ?: return false
        val c = d.classId?.let { id -> taxonomy.classes.firstOrNull { it.id == id } } ?: return false
        if (c.protect_first && (d.protectedAt == null || d.smInformedAt == null)) return false
        if (d.km.isBlank()) return false
        viewModelScope.launch {
            repo.saveFinding(FindingEntity(patrolId = p.id, classId = c.id, kmReference = d.km, line = d.line, railSide = d.rail,
                lat = d.lat, lon = d.lon, gnssAccuracyM = d.accuracy, note = d.note, noteLanguage = lang, actionTaken = d.action,
                lineProtectedAt = d.protectedAt, smInformedAt = d.smInformedAt, imagePath = d.imagePath,
                qualityPassed = d.quality?.passed ?: false, qualityReasons = d.quality?.reasons?.joinToString(",").orEmpty()))
            draft.value = Draft(line = d.line)
        }
        return true
    }

    companion object {
        fun assessFile(file: File): QualityGate.Result {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeFile(file.absolutePath, bounds)
            val sample = maxOf(1, maxOf(bounds.outWidth, bounds.outHeight) / 1024)
            val bmp = BitmapFactory.decodeFile(file.absolutePath, BitmapFactory.Options().apply { inSampleSize = sample })
                ?: return QualityGate.Result(0.0, 0.0, 1.0, listOf("unreadable_image"))
            val px = IntArray(bmp.width * bmp.height)
            bmp.getPixels(px, 0, bmp.width, 0, 0, bmp.width, bmp.height)
            val luma = IntArray(px.size) { i -> val c = px[i]; ((c shr 16 and 0xFF) * 299 + (c shr 8 and 0xFF) * 587 + (c and 0xFF) * 114) / 1000 }
            return QualityGate.assess(luma, bmp.width, bmp.height, minOf(bounds.outWidth, bounds.outHeight))
        }
    }
}
