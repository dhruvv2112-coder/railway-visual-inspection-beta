package org.rvi.inspect

import android.app.Application
import android.content.Context
import org.rvi.inspect.data.Repository
import org.rvi.inspect.data.RviDatabase

/** Manual dependency container (Android guide "Manual dependency injection"): enough for a single-module Beta. */
class AppContainer(context: Context) {
    val database by lazy { RviDatabase.build(context) }
    val repository by lazy { Repository(context, database) }
}

class RviApp : Application() {
    lateinit var container: AppContainer
    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
