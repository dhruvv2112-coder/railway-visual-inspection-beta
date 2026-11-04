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

        /** Newest signed address on the relay topic, or null. The signature (HMAC-SHA256 of "url|ts" with the pairing
         *  key) must match and the message must be under 3 days old, so nobody else can redirect the phone. */
        suspend fun relayAddress(server: String, topic: String, key: String): String? = withContext(Dispatchers.IO) {
            if (server.isBlank() || topic.isBlank() || key.isBlank()) return@withContext null
            runCatching {
                val body = http.newCall(Request.Builder().url("${server.trimEnd('/')}/$topic/json?poll=1&since=72h").build()).execute()
                    .use { if (it.isSuccessful) it.body?.string() else null } ?: return@runCatching null
                body.lineSequence().filter { it.isNotBlank() }.mapNotNull { line ->
                    val o = kotlinx.serialization.json.Json.parseToJsonElement(line) as? kotlinx.serialization.json.JsonObject ?: return@mapNotNull null
                    val msg = (o["message"] as? kotlinx.serialization.json.JsonPrimitive)?.content ?: return@mapNotNull null
                    val m = runCatching { kotlinx.serialization.json.Json.parseToJsonElement(msg) as kotlinx.serialization.json.JsonObject }.getOrNull() ?: return@mapNotNull null
                    val url = (m["url"] as? kotlinx.serialization.json.JsonPrimitive)?.content ?: return@mapNotNull null
                    val ts = (m["ts"] as? kotlinx.serialization.json.JsonPrimitive)?.content?.toLongOrNull() ?: return@mapNotNull null
                    val sig = (m["sig"] as? kotlinx.serialization.json.JsonPrimitive)?.content ?: return@mapNotNull null
                    val fresh = System.currentTimeMillis() / 1000 - ts < 72 * 3600
                    if (fresh && verify(url, ts, sig, key) && url.startsWith("https://")) ts to url else null
                }.maxByOrNull { it.first }?.second
            }.getOrNull()
        }

        fun verify(url: String, ts: Long, sig: String, key: String): Boolean {
            val mac = javax.crypto.Mac.getInstance("HmacSHA256")
            mac.init(javax.crypto.spec.SecretKeySpec(key.toByteArray(), "HmacSHA256"))
            val want = mac.doFinal("$url|$ts".toByteArray()).joinToString("") { "%02x".format(it) }
            return java.security.MessageDigest.isEqual(want.toByteArray(), sig.toByteArray())
        }

        /** True when the address is on a home/office network (192.168.x, 10.x, 172.16-31.x), false for internet. */
        fun isLocal(url: String): Boolean {
            val h = url.substringAfter("://").substringBefore("/").substringBefore(":")
            return h.startsWith("192.168.") || h.startsWith("10.") || Regex("^172\\.(1[6-9]|2\\d|3[01])\\.").containsMatchIn(h) || h.endsWith(".local")
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
