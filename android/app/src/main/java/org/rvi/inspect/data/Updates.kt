package org.rvi.inspect.data

import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import androidx.core.content.ContextCompat
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.GET

/** A published app build, as listed by the server at /ohe/app/latest (written by CI for every Beta build). */
@Serializable
data class AppRelease(
    @SerialName("version_code") val versionCode: Int,
    @SerialName("version_name") val versionName: String,
    val notes: List<String> = emptyList(),
    val sha256: String = "",
    @SerialName("size_bytes") val sizeBytes: Long = 0,
    @SerialName("built_at") val builtAt: String = "",
)

interface UpdateApi {
    @GET("ohe/app/latest")
    suspend fun latest(): AppRelease
}

/** Newer than the installed build? Pure function, unit-tested. */
fun isNewer(installedCode: Int, r: AppRelease?): Boolean = r != null && r.versionCode > installedCode

/** Downloads the APK through DownloadManager (works in the background, survives the screen turning off), then
 *  hands it to the system installer. The first time, Android asks the user to allow installs from this app. */
class Updater(private val context: Context) {
    private var receiver: BroadcastReceiver? = null

    fun download(baseUrl: String, token: String, release: AppRelease, onReady: () -> Unit) {
        val dm = context.getSystemService(DownloadManager::class.java)
        val url = (if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/") + "ohe/app/apk"
        val req = DownloadManager.Request(Uri.parse(url))
            .setTitle("RVI OHE Patrol ${release.versionName}")
            .setMimeType("application/vnd.android.package-archive")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalFilesDir(context, null, "rvi-ohe-${release.versionCode}.apk")
        if (token.isNotBlank()) req.addRequestHeader("Authorization", "Bearer $token")
        val id = dm.enqueue(req)
        receiver?.let { runCatching { context.unregisterReceiver(it) } }
        receiver = object : BroadcastReceiver() {
            override fun onReceive(c: Context, i: Intent) {
                if (i.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1) != id) return
                runCatching { context.unregisterReceiver(this) }
                receiver = null
                val uri = dm.getUriForDownloadedFile(id) ?: return
                onReady()
                context.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK))
            }
        }
        ContextCompat.registerReceiver(context, receiver, IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE),
            ContextCompat.RECEIVER_EXPORTED) // the system DownloadManager sends it
    }
}
