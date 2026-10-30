package org.rvi.inspect

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.rvi.inspect.domain.Taxonomy
import org.rvi.inspect.ui.SUGGESTED
import org.rvi.inspect.ui.screens.BookRow
import org.rvi.inspect.ui.screens.ClassifyScreen
import org.rvi.inspect.ui.screens.ClassifyState
import org.rvi.inspect.ui.screens.DangerSheet
import org.rvi.inspect.ui.screens.HomeScreen
import org.rvi.inspect.ui.screens.HomeState
import org.rvi.inspect.ui.screens.KitCheckScreen
import org.rvi.inspect.ui.screens.PatrolHud
import org.rvi.inspect.ui.screens.ReviewItem
import org.rvi.inspect.ui.screens.ReviewScreen
import org.rvi.inspect.ui.screens.SettingsScreen
import org.rvi.inspect.ui.screens.SettingsState
import org.rvi.inspect.ui.screens.SummaryScreen
import org.rvi.inspect.ui.theme.RviTheme
import java.io.File

/** Renders real Compose screens on the JVM (Robolectric native graphics) – used for design review
 *  and as visual-regression baselines. Output: app/build/outputs/roborazzi (PNG files) */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w393dp-h852dp-night-xxhdpi")
abstract class Shots(private val lang: String) {
    private val tax = Taxonomy.parse(File("../../shared/taxonomy.json").readText())

    private fun shot(name: String, content: @Composable () -> Unit) =
        captureRoboImage("build/outputs/roborazzi/${lang}_$name.png") { RviTheme { content() } }

    /** Stand-in for the live camera feed: a dim track-like gradient so translucency is visible. */
    @Composable
    private fun FakeFeed() = Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFF5A5A5A), Color(0xFF2B2B2B), Color(0xFF8A8A8A)))))

    @Test fun s01_home() = shot("01_home") {
        HomeScreen(HomeState("CP-0412", "1204/0", "1207/4", "UP", if (lang == "hi") "संयुक्त पैदल गश्त · ट्रैक + OHE · CP-01" else "Combined foot patrol · Track + OHE · CP-01", false, 3, true), {}, {}, {}, {})
    }

    @Test fun s02_kit() = shot("02_kit_check") { KitCheckScreen(listOf(true, true, true, true, false, false, false, false), {}, {}) }

    @Test fun s03_patrol() = shot("03_patrol_hud") {
        PatrolHud("1205/6", 2, false, if (lang == "hi") "क्लिप गायब" else "missing clip", {}, {}, {}, {}) { FakeFeed() }
    }

    @Test fun s04_danger() = shot("04_protect_first") {
        Box { PatrolHud("1205/8", 2, false, null, {}, {}, {}, {}) { FakeFeed() }
            DangerSheet("track", true, false, false, false, {}, {}, {}, {}, {}, {}, {}) }
    }

    @Test fun s04b_ohe_danger() = shot("04b_ohe_danger") {
        Box { PatrolHud("1205/14", 3, false, null, {}, {}, {}, {}) { FakeFeed() }
            DangerSheet("ohe", false, false, true, true, {}, {}, {}, {}, {}, {}, {}) }
    }

    @Test fun s04c_danger_choice() = shot("04c_danger_choice") {
        Box { PatrolHud("1205/14", 3, false, null, {}, {}, {}, {}) { FakeFeed() }
            DangerSheet(null, false, false, false, false, {}, {}, {}, {}, {}, {}, {}) }
    }

    @Test fun s05_classify() = shot("05_classify") {
        val sel = tax.beta.first { it.id == "EL-OH-004" }
        ClassifyScreen(ClassifyState(lang, "", SUGGESTED.mapNotNull { id -> tax.beta.firstOrNull { it.id == id } }, tax.search("", lang, "ohe"), sel, true,
            "1205/12", "UP", "B", if (lang == "hi") "OHE डिपो को सूचित" else "OHE depot informed", "", "GNSS 26.91234, 75.78781 ±4 m", "ohe"),
            {}, {}, {}, {}, {}, {}, {}, {}, {})
    }

    @Test fun s06_summary() = shot("06_summary") {
        val l = { id: String -> tax.classes.first { it.id == id }.label.forLang(lang) }
        SummaryScreen(listOf(BookRow("1205/6", l("PW-FS-001"), "Recouped ERC", false), BookRow("1206/2", l("PW-RL-008"), "Watched; JE informed", false),
            BookRow("1205/12", l("EL-OH-004"), "OHE depot informed", false, "ohe"), BookRow("1206/4", l("EL-OH-014"), "Bond tightened on the spot", false, "ohe"),
            BookRow("1206/9", l("EL-OH-008"), "TPC and depot informed", false, "ohe"))) {}
    }

    @Test fun s07_review() = shot("07_review") {
        val l = { id: String -> tax.classes.first { it.id == id }.label.forLang(lang) }
        ReviewScreen(listOf(ReviewItem("a", "1205/12", l("EL-OH-004"), "B", "CP-0412", "", "SSE/TRD (OHE depot)"),
            ReviewItem("b", "1206/2", l("PW-RL-008"), "A", "CP-0412", "Mark faded; joggled plate absent", "SSE/P.Way")), mapOf("a" to "RF-P2"), { _, _ -> }, {}, {})
    }

    @Test fun s08_settings() = shot("08_settings") { SettingsScreen(SettingsState(lang, true, true, false, true), {}, { _, _ -> }) }
}

@Config(qualifiers = "en-rIN-w393dp-h852dp-night-xxhdpi")
class EnglishShots : Shots("en")

@Config(qualifiers = "hi-rIN-w393dp-h852dp-night-xxhdpi")
class HindiShots : Shots("hi")
