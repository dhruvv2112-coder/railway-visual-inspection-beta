package org.rvi.inspect.data

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/** A server found on the Wi-Fi (the laptop advertises _ontrack._tcp). */
data class FoundServer(val name: String, val url: String)

/** Finds OnTrack.AI laptop servers on the same network with Android's built-in network service discovery. */
class Discovery(context: Context) {
    private val nsd = context.getSystemService(Context.NSD_SERVICE) as NsdManager

    fun find(): Flow<FoundServer> = callbackFlow {
        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(type: String) {}
            override fun onDiscoveryStopped(type: String) {}
            override fun onStartDiscoveryFailed(type: String, code: Int) { close() }
            override fun onStopDiscoveryFailed(type: String, code: Int) {}
            override fun onServiceLost(info: NsdServiceInfo) {}
            override fun onServiceFound(info: NsdServiceInfo) {
                @Suppress("DEPRECATION")
                nsd.resolveService(info, object : NsdManager.ResolveListener {
                    override fun onResolveFailed(i: NsdServiceInfo, code: Int) {}
                    override fun onServiceResolved(i: NsdServiceInfo) {
                        val host = if (Build.VERSION.SDK_INT >= 34) i.hostAddresses.firstOrNull { it is java.net.Inet4Address }?.hostAddress
                        else @Suppress("DEPRECATION") i.host?.hostAddress
                        if (host != null) trySend(FoundServer(i.serviceName.substringBefore(" (").ifBlank { "OnTrack.AI server" }, "http://$host:${i.port}/"))
                    }
                })
            }
        }
        nsd.discoverServices(TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
        awaitClose { runCatching { nsd.stopServiceDiscovery(listener) } }
    }

    companion object {
        const val TYPE = "_ontrack._tcp."
        private val http = OkHttpClient.Builder().connectTimeout(3, TimeUnit.SECONDS).readTimeout(4, TimeUnit.SECONDS).build()

        /** True when the address answers /health (used for the "Connected" chip). */
        suspend fun reachable(url: String): Boolean = withContext(Dispatchers.IO) {
            runCatching {
                http.newCall(Request.Builder().url(url.trimEnd('/') + "/health").build()).execute().use { it.isSuccessful }
            }.getOrDefault(false)
        }

        /** Normalise what a person types: "192.168.1.20" -> "http://192.168.1.20:8000/". */
        fun normalise(raw: String): String {
            var s = raw.trim()
            if (s.isEmpty()) return s
            if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://$s"
            val hostPart = s.substringAfter("://").substringBefore("/")
            if (!hostPart.contains(":") && s.startsWith("http://")) s = s.replaceFirst(hostPart, "$hostPart:8000")
            return if (s.endsWith("/")) s else "$s/"
        }
    }
}
