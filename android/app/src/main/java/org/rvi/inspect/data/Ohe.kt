package org.rvi.inspect.data

import android.content.Context
import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Update
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.rvi.inspect.RviApp
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import java.io.File
import java.security.MessageDigest
import java.time.Instant
import java.util.UUID
import java.util.concurrent.TimeUnit

/* OHE Visual AI Patrol capture flow (HLD v1.0): photos are the only inspection evidence; there is no per-asset
 * confirmation. Everything is stored on the phone first and uploaded in order by a WorkManager job. */

@Entity(tableName = "ohe_session")
data class OheSessionEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val territory: String,
    val inspectorId: String,
    val role: String,
    val startedAt: Long = System.currentTimeMillis(),
    val endedAt: Long? = null,
    val remoteId: String? = null,
    val reportId: String? = null,
    val summaryJson: String? = null,   // RPT-02 summary returned when the cycle closes
)

@Entity(tableName = "ohe_capture")
data class OheCaptureEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val sessionId: String,
    val path: String,
    val sha256: String,
    val capturedAt: Long = System.currentTimeMillis(),
    val lat: Double? = null,
    val lon: Double? = null,
    val accuracyM: Float? = null,
    val localQualityOk: Boolean = true,
    val localReasons: String = "",
    val uploaded: Boolean = false,
    val imageState: String? = null,      // server assessability state for the whole image, if any
    val prompt: String? = null,          // server recapture prompt code (see Prompt)
    val findings: Int = 0,               // assessments with a defect or anomaly on this photo
    val alert: Boolean = false,
)

@Entity(tableName = "ohe_note")
data class OheNoteEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val sessionId: String,
    val text: String,
    val createdAt: Long = System.currentTimeMillis(),
    val uploaded: Boolean = false,
)

@Dao
interface OheDao {
    @Insert suspend fun insertSession(s: OheSessionEntity)
    @Update suspend fun updateSession(s: OheSessionEntity)
    @Query("SELECT * FROM ohe_session WHERE id = :id") suspend fun session(id: String): OheSessionEntity?
    @Query("SELECT * FROM ohe_session WHERE endedAt IS NULL ORDER BY startedAt DESC LIMIT 1") fun active(): Flow<OheSessionEntity?>
    @Query("SELECT * FROM ohe_session ORDER BY startedAt DESC LIMIT 1") fun latest(): Flow<OheSessionEntity?>
    @Query("SELECT * FROM ohe_session WHERE endedAt IS NOT NULL AND reportId IS NULL") suspend fun awaitingReport(): List<OheSessionEntity>

    @Insert suspend fun insertCapture(c: OheCaptureEntity)
    @Update suspend fun updateCapture(c: OheCaptureEntity)
    @Query("SELECT * FROM ohe_capture WHERE sessionId = :sid ORDER BY capturedAt") fun captures(sid: String): Flow<List<OheCaptureEntity>>
    @Query("SELECT * FROM ohe_capture WHERE uploaded = 0 ORDER BY capturedAt") suspend fun pendingCaptures(): List<OheCaptureEntity>
    @Query("SELECT COUNT(*) FROM ohe_capture WHERE uploaded = 0") fun pendingCount(): Flow<Int>
    @Query("SELECT COUNT(*) FROM ohe_capture WHERE uploaded = 0 AND sessionId = :sid") suspend fun pendingFor(sid: String): Int

    @Insert suspend fun insertNote(n: OheNoteEntity)
    @Update suspend fun updateNote(n: OheNoteEntity)
    @Query("SELECT * FROM ohe_note WHERE uploaded = 0 ORDER BY createdAt") suspend fun pendingNotes(): List<OheNoteEntity>
    @Query("SELECT COUNT(*) FROM ohe_note WHERE sessionId = :sid") fun noteCount(sid: String): Flow<Int>
}

/** Recapture prompts as codes, so the phone shows them in the user's language (backend sends English text). */
enum class Prompt { ZOOM, PLATE, WHOLE, SQUARE, BLUR, DARK, BRIGHT;
    companion object {
        fun fromServer(text: String?): Prompt? = when {
            text == null -> null
            text.contains("optical zoom", true) -> ZOOM
            text.contains("number plate", true) -> PLATE
            text.contains("whole assembly", true) -> WHOLE
            text.contains("square-on", true) -> SQUARE
            else -> null
        }
        fun fromLocal(reasons: List<String>): Prompt? = when {
            reasons.any { it.contains("blur") } -> BLUR
            reasons.any { it.contains("dark") } -> DARK
            reasons.any { it.contains("overexposed") || it.contains("bright") || it.contains("clip") } -> BRIGHT
            reasons.any { it.contains("small") || it.contains("resolution") } -> ZOOM
            else -> null
        }
    }
}

object Hashing {
    fun sha256(file: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buf = ByteArray(64 * 1024)
            while (true) { val n = input.read(buf); if (n < 0) break; md.update(buf, 0, n) }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }
}

@Serializable data class OheSessionIn(val territory: String, @SerialName("expected_assets") val expectedAssets: List<String>? = null)
@Serializable data class OheIdOut(val id: String)
@Serializable data class OheNoteIn(val text: String)
@Serializable data class OheLoginIn(val id: String, val pin: String)
@Serializable data class OheLoginOut(val token: String, val id: String, val role: String, val name: String = "")
@Serializable data class OheEndOut(@SerialName("report_id") val reportId: String, val revision: Int, val sha256: String, val summary: JsonObject)

interface OheApi {
    @POST("ohe/auth/login")
    suspend fun login(@Body body: OheLoginIn): OheLoginOut

    @POST("ohe/sessions")
    suspend fun start(@Body body: OheSessionIn, @Header("X-Actor") actor: String, @Header("X-Role") role: String): OheIdOut

    @Multipart
    @POST("ohe/sessions/{sid}/media")
    suspend fun media(
        @Path("sid") sid: String,
        @Part image: MultipartBody.Part,
        @Part("sha256") sha256: RequestBody,
        @Part("captured_at") capturedAt: RequestBody,
        @Part("lat") lat: RequestBody?,
        @Part("lon") lon: RequestBody?,
        @Part("accuracy_m") accuracy: RequestBody?,
        @Part("device") device: RequestBody,
        @Header("X-Actor") actor: String,
        @Header("X-Role") role: String,
    ): JsonObject

    @POST("ohe/sessions/{sid}/notes")
    suspend fun note(@Path("sid") sid: String, @Body body: OheNoteIn, @Header("X-Actor") actor: String, @Header("X-Role") role: String): OheIdOut

    @POST("ohe/sessions/{sid}/end")
    suspend fun end(@Path("sid") sid: String, @Header("X-Actor") actor: String, @Header("X-Role") role: String): OheEndOut

    companion object {
        /** With a token (from sign-in) every call carries it; the server then ignores the X-Actor/X-Role headers. */
        fun create(baseUrl: String, token: String? = null): OheApi = retrofit(baseUrl, token).create(OheApi::class.java)

        fun retrofit(baseUrl: String, token: String? = null): Retrofit = Retrofit.Builder()
            .baseUrl(if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/")
            .client(OkHttpClient.Builder().connectTimeout(20, TimeUnit.SECONDS).readTimeout(120, TimeUnit.SECONDS)
                .addInterceptor { chain ->
                    val req = chain.request()
                    chain.proceed(if (token.isNullOrBlank()) req else req.newBuilder().header("Authorization", "Bearer $token").build())
                }.build())
            .addConverterFactory(RviApi.json.asConverterFactory("application/json".toMediaType()))
            .build()
    }
}

/** What the phone keeps from the server's analysis of one photo (pure function: unit-tested). */
data class UploadResult(val imageState: String?, val prompt: Prompt?, val findings: Int, val alert: Boolean)

fun parseUpload(body: JsonObject): UploadResult {
    val a = body["analysis"]?.let { it as? JsonObject } ?: return UploadResult(null, null, 0, false)
    fun str(e: JsonElement?) = (e as? kotlinx.serialization.json.JsonPrimitive)?.takeIf { it.isString }?.content
    val asm = a["assessments"]?.let { runCatching { it.jsonArray }.getOrNull() }.orEmpty()
    val flagged = asm.map { it.jsonObject }.filter { str(it["state"]) in setOf("assessable_defect", "anomalous_unclassified") }
    val alert = flagged.any { runCatching { it["alert"]?.jsonPrimitive?.content == "true" }.getOrDefault(false) }
    return UploadResult(str(a["image_state"]), Prompt.fromServer(str(a["recapture_prompt"])), flagged.size, alert)
}

class OheRepository(private val context: Context, private val db: RviDatabase, private val settings: suspend () -> UserSettings,
                    private val baseUrl: suspend () -> String, private val save: suspend (String, String) -> Unit = { _, _ -> }) {
    private val dao get() = db.ohe()
    val active = dao.active()
    val latest = dao.latest()
    val pending = dao.pendingCount()
    fun captures(sid: String) = dao.captures(sid)
    fun notes(sid: String) = dao.noteCount(sid)

    suspend fun start(territory: String): OheSessionEntity {
        val s = settings()
        val e = OheSessionEntity(territory = territory, inspectorId = s.inspectorId, role = s.role)
        dao.insertSession(e); schedule(); return e
    }

    /** ID + PIN sign-in. Stores the token and the role the server assigned. Throws with a readable message. */
    suspend fun signIn(id: String, pin: String): OheLoginOut {
        val out = try {
            OheApi.create(baseUrl()).login(OheLoginIn(id.trim(), pin.trim()))
        } catch (e: HttpException) {
            throw IllegalStateException(if (e.code() == 401) "Wrong ID or PIN" else "Server error ${e.code()}")
        }
        save("token", out.token); save("inspector", out.id); save("role", out.role)
        schedule()
        return out
    }

    suspend fun signOut() { save("token", "") }

    /** Latest published app build on this server, or null when none is published or the server is unreachable. */
    suspend fun latestRelease(): AppRelease? = runCatching {
        val s = settings()
        OheApi.retrofit(baseUrl(), s.token).create(UpdateApi::class.java).latest()
    }.getOrNull()

    suspend fun serverAndToken(): Pair<String, String> = baseUrl() to settings().token

    suspend fun addCapture(c: OheCaptureEntity) { dao.insertCapture(c); schedule() }
    suspend fun addNote(sid: String, text: String) { dao.insertNote(OheNoteEntity(sessionId = sid, text = text)); schedule() }

    suspend fun end(sid: String) {
        dao.session(sid)?.let { dao.updateSession(it.copy(endedAt = System.currentTimeMillis())) }
        schedule()
    }

    fun schedule() {
        val req = OneTimeWorkRequestBuilder<OheSyncWorker>()
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 20, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("ohe-sync", ExistingWorkPolicy.APPEND_OR_REPLACE, req)
    }

    private suspend fun remoteSession(api: OheApi, local: OheSessionEntity): String {
        local.remoteId?.let { return it }
        val s = settings()
        val id = api.start(OheSessionIn(local.territory), s.inspectorId, s.role).id
        dao.updateSession(local.copy(remoteId = id))
        return id
    }

    /** Upload photos and notes in capture order, then close any ended session. Safe to repeat: the server accepts the
     *  same photo bytes once (same SHA-256) and returns the earlier result. */
    suspend fun syncOnce() {
        val s = settings()
        val api = OheApi.create(baseUrl(), s.token)
        val text = { v: String -> v.toRequestBody("text/plain".toMediaType()) }
        for (c in dao.pendingCaptures()) {
            val sess = dao.session(c.sessionId) ?: continue
            val sid = remoteSession(api, sess)
            val file = File(c.path)
            if (!file.exists()) { dao.updateCapture(c.copy(uploaded = true, imageState = "missing_file")); continue }
            val body = try {
                api.media(sid, MultipartBody.Part.createFormData("image", file.name, file.asRequestBody("image/jpeg".toMediaType())),
                    text(c.sha256), text(Instant.ofEpochMilli(c.capturedAt).toString()), c.lat?.let { text(it.toString()) },
                    c.lon?.let { text(it.toString()) }, c.accuracyM?.let { text(it.toString()) }, text(android.os.Build.MODEL ?: ""),
                    s.inspectorId, s.role)
            } catch (e: HttpException) {
                if (e.code() == 422) { dao.updateCapture(c.copy(uploaded = true, imageState = "checksum_rejected")); continue }
                throw e
            }
            val r = parseUpload(body)
            dao.updateCapture(c.copy(uploaded = true, imageState = r.imageState, prompt = r.prompt?.name ?: c.prompt,
                findings = r.findings, alert = r.alert))
        }
        for (n in dao.pendingNotes()) {
            val sess = dao.session(n.sessionId) ?: continue
            api.note(remoteSession(api, sess), OheNoteIn(n.text), s.inspectorId, s.role)
            dao.updateNote(n.copy(uploaded = true))
        }
        for (sess in dao.awaitingReport()) {
            if (dao.pendingFor(sess.id) > 0) continue
            val out = api.end(remoteSession(api, sess), s.inspectorId, s.role)
            dao.updateSession((dao.session(sess.id) ?: sess).copy(reportId = out.reportId, summaryJson = out.summary.toString()))
        }
    }
}

class OheSyncWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result = try {
        (applicationContext as RviApp).container.ohe.syncOnce(); Result.success()
    } catch (e: Exception) {
        if (runAttemptCount < 10) Result.retry() else Result.failure()
    }
}
