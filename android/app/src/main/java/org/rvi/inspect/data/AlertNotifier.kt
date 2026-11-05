package org.rvi.inspect.data

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import kotlinx.coroutines.flow.first
import org.rvi.inspect.MainActivity
import org.rvi.inspect.R
import org.rvi.inspect.RviApp
import java.util.concurrent.TimeUnit

/** Phone notification for each new urgent finding (damaged insulator, nest or object on the wire). Called while the
 *  app is open (every alert refresh) and by a background check every 15 minutes. The first check after install only
 *  records what is already there, so old alerts do not flood the phone. */
object AlertNotifier {
    const val CHANNEL = "urgent_findings"
    const val EXTRA_OPEN = "open"
    private const val PREFS = "alert_notifier"

    fun channel(ctx: Context) {
        if (Build.VERSION.SDK_INT >= 26) {
            val ch = NotificationChannel(CHANNEL, ctx.getString(R.string.g_notif_channel), NotificationManager.IMPORTANCE_HIGH)
            ch.enableVibration(true)
            ctx.getSystemService(NotificationManager::class.java).createNotificationChannel(ch)
        }
    }

    /** Ids that are new since the last call (pure, unit-tested). */
    fun fresh(seen: Set<String>?, rows: List<AlertRow>): List<AlertRow> = if (seen == null) emptyList() else rows.filter { it.findingId !in seen }

    fun notifyNew(ctx: Context, rows: List<AlertRow>) {
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val seen = p.getStringSet("seen", null)
        val news = fresh(seen, rows)
        p.edit().putStringSet("seen", (seen.orEmpty() + rows.map { it.findingId }).toSet()).apply()
        if (news.isEmpty()) return
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        channel(ctx)
        val open = PendingIntent.getActivity(ctx, 7, Intent(ctx, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP).putExtra(EXTRA_OPEN, "alerts"),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        news.forEach { a ->
            val where = listOfNotNull(a.assetId?.let { ctx.getString(R.string.g_notif_mast, it) }, a.territory.ifBlank { null }).joinToString(" · ")
            val n = NotificationCompat.Builder(ctx, CHANNEL).setSmallIcon(R.drawable.ic_stat_alert)
                .setContentTitle(ctx.getString(R.string.g_notif_title, a.what)).setContentText(where)
                .setPriority(NotificationCompat.PRIORITY_HIGH).setCategory(NotificationCompat.CATEGORY_ALARM)
                .setColor(0xFFD93A10.toInt()).setAutoCancel(true).setContentIntent(open).build()
            runCatching { NotificationManagerCompat.from(ctx).notify(a.findingId.hashCode(), n) }
        }
    }

    fun schedule(ctx: Context) {
        val req = PeriodicWorkRequestBuilder<AlertCheckWorker>(15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()).build()
        WorkManager.getInstance(ctx).enqueueUniquePeriodicWork("alert-check", ExistingPeriodicWorkPolicy.KEEP, req)
    }
}

class AlertCheckWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        val c = (applicationContext as RviApp).container
        if (c.repository.settings.first().token.isBlank()) return Result.success()   // not signed in
        runCatching { AlertNotifier.notifyNew(applicationContext, c.ohe.alerts()) }
        return Result.success()
    }
}
