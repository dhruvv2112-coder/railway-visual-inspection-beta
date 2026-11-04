package org.rvi.inspect.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import org.rvi.inspect.R

/** OnTrack.AI glass palette (canvas "Glass kit"): ink text, electric blue for action, signal yellow for "now",
 *  safety orange only for danger, mint for checked/signed. Colours that must be told apart also differ in lightness. */
object Ink {
    val Ink = Color(0xFF0E1020)
    val Body = Color(0xFF3B4058)
    val Muted = Color(0xFF464B63)
    val Mist = Color(0xFFE6EAF5)
    val Mist2 = Color(0xFFEEF0F7)
    val Electric = Color(0xFF3346FF)
    val ElectricDeep = Color(0xFF2433D6)
    val ElectricTint = Color(0xFFDDE2FF)
    val Signal = Color(0xFFFFD84D)
    val Safety = Color(0xFFD93A10)
    val SafetyTint = Color(0xFFFFE0D3)
    val SafetyText = Color(0xFFA1300A)
    val Mint = Color(0xFF10A36E)
    val MintTint = Color(0xFFD3F5E6)
    val MintText = Color(0xFF046C4E)
    val Aqua = Color(0xFF14C8B4)
    val Amber = Color(0xFFFFB020)
    val Violet = Color(0xFF7C8CFF)
    val White = Color(0xFFFFFFFF)
    val Glass = Color(0x9EFFFFFF)        // 62 % white panel
    val GlassStrong = Color(0xD1FFFFFF)  // 82 %
    val GlassEdge = Color(0xE6FFFFFF)
    val DarkGlass = Color(0x610E1020)    // 38 % ink, on the camera
    val DarkEdge = Color(0x38FFFFFF)
    val Hair = Color(0x140E1020)
}

/** Kept for the earlier track-patrol screens (they still compile against these names). */
object Grey {
    val G950 = Ink.Ink
    val G900 = Color(0xFF1A1D33)
    val G850 = Color(0xFF23274A)
    val G800 = Color(0xFF2E3360)
    val G700 = Color(0xFF8C93B0)
    val G500 = Ink.Muted
    val G400 = Ink.Muted
    val G300 = Ink.Body
    val G200 = Ink.Body
    val White = Ink.Ink
    val GlassFill = Ink.Glass
    val GlassFillStrong = Ink.GlassStrong
    val GlassStroke = Ink.GlassEdge
    val Scrim = Color(0x990E1020)
}

/** Stand-in for FK Grotesk Neue (the Even Realities app face, commercial): Inter Tight with tight tracking.
 *  Devanagari falls back to the system Noto Sans Devanagari. */
val InterTight = FontFamily(
    Font(R.font.inter_tight_400, FontWeight.Normal),
    Font(R.font.inter_tight_500, FontWeight.Medium),
    Font(R.font.inter_tight_600, FontWeight.SemiBold),
    Font(R.font.inter_tight_700, FontWeight.Bold),
    Font(R.font.inter_tight_800, FontWeight.ExtraBold),
)
val GeistMono = FontFamily(Font(R.font.geist_mono_500, FontWeight.Medium), Font(R.font.geist_mono_600, FontWeight.SemiBold))
val JetBrainsMono = GeistMono

@Immutable
data class Scale(val factor: Float = 1f)

val LocalScale = staticCompositionLocalOf { Scale() }

private fun type(f: Float): Typography {
    fun t(size: Int, w: FontWeight, ls: Double = -0.01, lh: Double = 1.25) =
        TextStyle(fontFamily = InterTight, fontWeight = w, fontSize = (size * f).sp, lineHeight = (size * f * lh).sp, letterSpacing = (size * f * ls).sp)
    return Typography(
        displaySmall = t(34, FontWeight.Bold, -0.03, 1.1),
        headlineMedium = t(30, FontWeight.Bold, -0.03, 1.1),
        headlineSmall = t(24, FontWeight.Bold, -0.03, 1.15),
        titleLarge = t(20, FontWeight.Bold, -0.02),
        titleMedium = t(16, FontWeight.Bold, -0.02),
        bodyLarge = t(16, FontWeight.Normal, -0.01, 1.45),
        bodyMedium = t(14, FontWeight.Normal, -0.01, 1.45),
        bodySmall = t(12, FontWeight.Normal, 0.0, 1.4),
        titleSmall = t(14, FontWeight.Bold, -0.01),
        headlineLarge = t(32, FontWeight.Bold, -0.03, 1.1),
        displayMedium = t(40, FontWeight.Bold, -0.03, 1.1),
        displayLarge = t(48, FontWeight.Bold, -0.03, 1.1),
        labelLarge = t(16, FontWeight.Bold, -0.01),
        labelMedium = t(13, FontWeight.SemiBold, 0.0),
        labelSmall = t(12, FontWeight.ExtraBold, 0.08),
    )
}

private val scheme = lightColorScheme(
    primary = Ink.Electric, onPrimary = Ink.White,
    secondary = Ink.Ink, onSecondary = Ink.White,
    tertiary = Ink.Signal, onTertiary = Ink.Ink,
    background = Ink.Mist, onBackground = Ink.Ink,
    surface = Ink.White, onSurface = Ink.Ink,
    surfaceVariant = Ink.Mist2, onSurfaceVariant = Ink.Body,
    outline = Color(0x1F0E1020), outlineVariant = Ink.Hair,
    error = Ink.Safety, onError = Ink.White,
)

@Composable
fun RviTheme(largeText: Boolean = false, content: @Composable () -> Unit) {
    val f = if (largeText) 1.2f else 1f
    androidx.compose.runtime.CompositionLocalProvider(LocalScale provides Scale(f)) {
        MaterialTheme(colorScheme = scheme, typography = type(f), content = content)
    }
}
