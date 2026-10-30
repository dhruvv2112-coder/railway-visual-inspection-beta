package org.rvi.inspect

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import org.rvi.inspect.ui.AppNav
import org.rvi.inspect.ui.theme.RviTheme

/** AppCompatActivity for per-app language switching (AppCompatDelegate.setApplicationLocales) on API < 33. */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val repo = (application as RviApp).container.repository
        setContent {
            val s by repo.settings.collectAsState(initial = null)
            RviTheme(largeText = s?.largeText == true) { AppNav() }
        }
    }
}
