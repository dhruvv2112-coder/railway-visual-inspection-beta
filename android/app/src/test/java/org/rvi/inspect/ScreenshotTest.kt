package org.rvi.inspect

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.rvi.inspect.data.FoundServer
import org.rvi.inspect.data.Prompt
import org.rvi.inspect.ui.OheSummary
import org.rvi.inspect.ui.components.FloatingTabBar
import org.rvi.inspect.ui.components.Tab
import org.rvi.inspect.ui.components.Tone
import org.rvi.inspect.ui.screens.*
import org.rvi.inspect.ui.theme.RviTheme

/** Renders the real Compose screens on the JVM (Robolectric native graphics) for design review and as
 *  visual-regression baselines. Output: app/build/outputs/roborazzi (PNG files). */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-xxhdpi")
abstract class Shots(private val lang: String) {
    private val hi = lang == "hi"
    private fun shot(name: String, content: @Composable () -> Unit) =
        captureRoboImage("build/outputs/roborazzi/${lang}_$name.png") {
            androidx.compose.runtime.CompositionLocalProvider(org.rvi.inspect.ui.components.LocalMotion provides false) { RviTheme { content() } }
        }

    /** Stand-in for the live camera: a dusk sky so the dark glass is visible. */
    @Composable
    private fun FakeFeed() = Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFF24306B), Color(0xFF5A5FA8), Color(0xFFE9967A), Color(0xFFF4C27A)))))

    @Composable
    private fun WithTabs(tab: Tab, content: @Composable () -> Unit) = Box(Modifier.fillMaxSize()) {
        content()
        FloatingTabBar(tab, {}, mapOf(Tab.Home to if (hi) "होम" else "Home", Tab.Patrols to if (hi) "गश्तें" else "Patrols",
            Tab.Alerts to if (hi) "अलर्ट" else "Alerts", Tab.Profile to if (hi) "प्रोफ़ाइल" else "Profile"), 2,
            Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(bottom = 14.dp))
    }

    private val found = listOf(FoundServer("OnTrack.AI server", "http://192.168.1.20:8000/"))

    @Test fun s01_signin() = shot("01_signin") {
        SignInScreen(SignInState("PT-0412", 2, false, null, "http://192.168.1.20:8000/", true, false, emptyList(), hi, false), {}, {}, {}, {}, {}, {}, {}, {})
    }
    @Test fun s01b_signin_server() = shot("01b_signin_find_server") {
        SignInScreen(SignInState("PT-0412", 0, false, null, "", false, false, found, hi, true), {}, {}, {}, {}, {}, {}, {}, {})
    }
    @Test fun s02_home() = shot("02_home") {
        WithTabs(Tab.Home) {
            OheHomeScreen(OheHomeState("Ravi", "SEC-1205", false, 0, "SEC-1204 · Wed 4 Nov · 10:02", true, "0.3.3002-draft", false, true, "192.168.1.20:8000"), {}, {}, {}, {}, {}, {})
        }
    }
    @Test fun s03_start() = shot("03_start") { StartSheet(StartState("SEC-1205"), {}, {}, {}) }
    @Test fun s04_hud() = shot("04_camera") {
        OheHud(OheHudState(14, 12, 2, 1, 1, null, false, null, "SEC-1205", 3f, 5f, ToastKind.Checked), {}, {}, {}, {}) { FakeFeed() }
    }
    @Test fun s05_retake() = shot("05_retake") {
        OheHud(OheHudState(14, 12, 2, 1, 1, Prompt.ZOOM, false, null, "SEC-1205", 1f, 5f), {}, {}, {}, {}) { FakeFeed() }
    }
    @Test fun s06_urgent() = shot("06_urgent") { UrgentSheet("1205/12", 2, {}, {}) }
    @Test fun s07_note() = shot("07_note") {
        Box { OheHud(OheHudState(14, 12, 2, 1, 1, null, false, null, "SEC-1205"), {}, {}, {}, {}) { FakeFeed() }
            OheNoteSheet(if (hi) "मस्त 1205/12 के पास पेड़ की शाखा" else "Tree branch near mast 1205/12", {}, {}, {}, {}) }
    }
    @Test fun s08_end() = shot("08_end") { OheEndScreen(OheSummary(19, 17, 1, "a1b2c3d4", 6, 6, 1, 1, 1), {}, {}, {}) }
    @Test fun s09_patrols() = shot("09_patrols") {
        WithTabs(Tab.Patrols) {
            PatrolsScreen(listOf(
                PatrolRow("1", "SEC-1205 · Thu 5 Nov · 10:02", "6 masts · 1 urgent", if (hi) "जाँच में" else "Under review", Tone.Urgent, true, "r1"),
                PatrolRow("2", "SEC-1204 · Wed 4 Nov · 09:40", "6 masts · signed by SSE-0001", if (hi) "हस्ताक्षरित" else "Signed", Tone.Ok, false, "r2"),
                PatrolRow("3", "SEC-1203 · Tue 3 Nov · 09:12", if (hi) "इस फ़ोन पर" else "On this phone", if (hi) "अपलोड" else "Uploading", Tone.Info, true, null)), false, {}, {})
        }
    }
    @Test fun s10_report() = shot("10_report") {
        ReportScreen(ReportUi("RPT-01 · a1b2c3d4", "6 masts · 1 urgent", 3, null, listOf("Shed chipped, not broken · now: replace at next block"),
            listOf("Insulator shed damage · 1205/12" to true), null), {}, {})
    }
    @Test fun s11_alerts() = shot("11_alerts") {
        WithTabs(Tab.Alerts) {
            AlertsScreen(listOf(AlertUi("a", "Insulator shed damage", "SEC-1205 · 1205/12 · Thu 5 Nov · 09:31", true, true, "s"),
                AlertUi("b", "Bird nest on cantilever", "SEC-1204 · 1204/07 · Wed 4 Nov · 09:55", false, true, "s2")), false, {}, {})
        }
    }
    @Test fun s12_profile() = shot("12_profile") {
        WithTabs(Tab.Profile) {
            ProfileScreen(ProfileState("Ravi Sharma", "PT-0412", "Patrol", hi, true, true, false, "0141 2xx xxxx", "http://192.168.1.20:8000/", true,
                "0.3.3001-draft (3001)", "0.3.3002-draft", false, false, found), {}, { _, _ -> }, {}, {}, {}, {}, {})
        }
    }
}

@Config(qualifiers = "en-rIN-w393dp-h852dp-xxhdpi")
class EnglishShots : Shots("en")

@Config(qualifiers = "hi-rIN-w393dp-h852dp-xxhdpi")
class HindiShots : Shots("hi")
