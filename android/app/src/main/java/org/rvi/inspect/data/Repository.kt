package org.rvi.inspect.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.rvi.inspect.BuildConfig
import org.rvi.inspect.RviApp
import org.rvi.inspect.domain.Taxonomy
import java.io.File
import java.time.Instant
import java.util.concurrent.TimeUnit

private val Context.prefs by preferencesDataStore("settings")

data class UserSettings(val inspectorId: String, val role: String, val voice: Boolean, val tts: Boolean, val largeText: Boolean, val haptics: Boolean,
                        val tpcNumber: String = "")

class Repository(private val context: Context, private val db: RviDatabase) {

    val taxonomy: Taxonomy by lazy { Taxonomy.parse(context.assets.open("taxonomy.json").bufferedReader().readText()) }

    private object K {
        val inspector = stringPreferencesKey("inspector")
        val role = stringPreferencesKey("role")
        val voice = booleanPreferencesKey("voice")
        val tts = booleanPreferencesKey("tts")
        val large = booleanPreferencesKey("large")
        val haptics = booleanPreferencesKey("haptics")
        val tpc = stringPreferencesKey("tpc_number")
    }

    val settings: Flow<UserSettings> = context.prefs.data.map {
        UserSettings(it[K.inspector] ?: "CP-0412", it[K.role] ?: "Patrol", it[K.voice] ?: true, it[K.tts] ?: true,
            it[K.large] ?: false, it[K.haptics] ?: true, it[K.tpc] ?: "")
    }

    suspend fun setToggle(key: String, value: Boolean) = context.prefs.edit {
        when (key) { "voice" -> it[K.voice] = value; "tts" -> it[K.tts] = value; "large" -> it[K.large] = value; "haptics" -> it[K.haptics] = value }
    }

    val activePatrol = db.patrols().active()
    val pendingCount = db.findings().pendingCount()
    val recentFindings = db.findings().recent()
    fun findings(patrolId: String) = db.findings().forPatrol(patrolId)

    suspend fun startPatrol(p: PatrolEntity) { db.patrols().upsert(p); scheduleSync() }
    suspend fun endPatrol(id: String) {
        db.patrols().get(id)?.let { db.patrols().update(it.copy(endedAt = System.currentTimeMillis())) }
        scheduleSync()
    }

    suspend fun saveFinding(f: FindingEntity) { db.findings().insert(f); scheduleSync() }

    fun scheduleSync() {
        val req = OneTimeWorkRequestBuilder<SyncWorker>()
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("sync", ExistingWorkPolicy.REPLACE, req)
    }

    /** Push patrols then findings + evidence. Idempotent: remote IDs stored after success. */
    suspend fun syncOnce(api: RviApi = RviApi.create(BuildConfig.API_BASE_URL)) {
        val s = settings.first()
        for (f in db.findings().unsynced()) {
            var patrol = db.patrols().get(f.patrolId) ?: continue
            if (patrol.remoteId == null) {
                val id = api.startPatrol(PatrolIn(patrol.patrolType, patrol.beatFromKm, patrol.beatToKm, patrol.line, patrol.kitCheckOk), s.inspectorId, s.role).id
                patrol = patrol.copy(remoteId = id); db.patrols().update(patrol)
            }
            val iso = { t: Long? -> t?.let { Instant.ofEpochMilli(it).toString() } }
            val rid = api.createFinding(FindingIn(patrol.remoteId!!, f.classId, f.kmReference, f.line, f.railSide, f.lat, f.lon,
                f.gnssAccuracyM, f.note, f.noteLanguage, f.actionTaken, iso(f.lineProtectedAt), iso(f.smInformedAt), iso(f.tpcInformedAt)), s.inspectorId, s.role).id
            f.imagePath?.let { p ->
                val file = File(p)
                if (file.exists()) api.addEvidence(rid, MultipartBody.Part.createFormData("image", file.name, file.asRequestBody("image/jpeg".toMediaType())),
                    "defect".toRequestBody(), s.inspectorId, s.role)
            }
            db.findings().update(f.copy(synced = true, remoteId = rid))
        }
    }
}

class SyncWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result = try {
        (applicationContext as RviApp).container.repository.syncOnce(); Result.success()
    } catch (e: Exception) {
        if (runAttemptCount < 8) Result.retry() else Result.failure()
    }
}
