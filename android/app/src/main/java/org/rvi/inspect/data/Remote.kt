package org.rvi.inspect.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path

@Serializable
data class PatrolIn(
    @SerialName("patrol_type") val patrolType: String,
    @SerialName("beat_from_km") val beatFromKm: String,
    @SerialName("beat_to_km") val beatToKm: String,
    val line: String,
    @SerialName("kit_check_ok") val kitCheckOk: Boolean,
)

@Serializable
data class IdOut(val id: String)

@Serializable
data class FindingIn(
    @SerialName("patrol_id") val patrolId: String,
    @SerialName("class_id") val classId: String,
    @SerialName("km_reference") val kmReference: String,
    val line: String,
    @SerialName("rail_side") val railSide: String,
    val lat: Double? = null,
    val lon: Double? = null,
    @SerialName("gnss_accuracy_m") val gnssAccuracyM: Float? = null,
    val note: String = "",
    @SerialName("note_language") val noteLanguage: String = "en",
    @SerialName("action_taken") val actionTaken: String = "",
    @SerialName("line_protected_at") val lineProtectedAt: String? = null,
    @SerialName("sm_informed_at") val smInformedAt: String? = null,
    @SerialName("tpc_informed_at") val tpcInformedAt: String? = null,
)

interface RviApi {
    @POST("patrols")
    suspend fun startPatrol(@Body body: PatrolIn, @Header("X-Actor") actor: String, @Header("X-Role") role: String): IdOut

    @POST("findings")
    suspend fun createFinding(@Body body: FindingIn, @Header("X-Actor") actor: String, @Header("X-Role") role: String): IdOut

    @Multipart
    @POST("findings/{id}/evidence")
    suspend fun addEvidence(
        @Path("id") id: String,
        @Part image: MultipartBody.Part,
        @Part("kind") kind: RequestBody,
        @Header("X-Actor") actor: String,
        @Header("X-Role") role: String,
    ): okhttp3.ResponseBody

    companion object {
        val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
        fun create(baseUrl: String): RviApi = Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(OkHttpClient.Builder().build())
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(RviApi::class.java)
    }
}
