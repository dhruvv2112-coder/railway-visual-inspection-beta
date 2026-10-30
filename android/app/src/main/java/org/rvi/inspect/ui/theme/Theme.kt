package org.rvi.inspect.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
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

/** Greyscale-only palette. White text on charcoal/black. No hue anywhere: state is shown by
 *  weight, fill, outline and icons (accessible for colour-vision deficiency). */
object Grey {
    val G950 = Color(0xFF0B0B0C) // background
    val G900 = Color(0xFF141416)
    val G850 = Color(0xFF1C1C1F)
    val G800 = Color(0xFF26262A)
    val G700 = Color(0xFF3A3A3F)
    val G500 = Color(0xFF6E6E75)
    val G400 = Color(0xFF8E8E95)
    val G300 = Color(0xFFB4B4BA)
    val G200 = Color(0xFFD6D6DA)
    val White = Color(0xFFFFFFFF)
    val GlassFill = Color(0x1FFFFFFF)      // 12 % white – translucent panels
    val GlassFillStrong = Color(0x33FFFFFF) // 20 %
    val GlassStroke = Color(0x3DFFFFFF)     // 24 % hairline
    val Scrim = Color(0x99000000)
}

val JetBrainsMono = FontFamily(
    Font(R.font.jetbrains_mono_light, FontWeight.Light),
    Font(R.font.jetbrains_mono_regular, FontWeight.Normal),
    Font(R.font.jetbrains_mono_medium, FontWeight.Medium),
    Font(R.font.jetbrains_mono_semibold, FontWeight.SemiBold),
    Font(R.font.jetbrains_mono_bold, FontWeight.Bold),
) // Devanagari glyphs fall back to the system Noto Sans Devanagari automatically.

@Immutable
data class Scale(val factor: Float = 1f)

val LocalScale = staticCompositionLocalOf { Scale() }

private fun type(f: Float) = Typography(
    displaySmall = TextStyle(fontFamily = JetBrainsMono, fontWeight = FontWeight.SemiBold, fontSize = (34 * f).sp, lineHeight = (40 * f).sp, letterSpacing = (-0.5).sp),
    headlineSmall = TextStyle(fontFamily = JetBrainsMono, fontWeight = FontWeight.SemiBold, fontSize = (24 * f).sp, lineHeight = (30 * f).sp),
    titleLarge = TextStyle(fontFamily = JetBrainsMono, fontWeight = FontWeight.Medium, fontSize = (20 * f).sp, lineHeight = (26 * f).sp),
    titleMedium = TextStyle(fontFamily = JetBrainsMono, fontWeight = FontWeight.Medium, fontSize = (16 * f).sp, lineHeight = (22 * f).sp),
    bodyLarge = TextStyle(fontFamily = JetBrainsMono, fontWeight = FontWeight.Normal, fontSize = (16 * f).sp, lineHeight = (24 * f).sp),
    bodyMedium = TextStyle(fontFamily = JetBrainsMono, fontWeight = FontWeight.Normal, fontSize = (14 * f).sp, lineHeight = (21 * f).sp),
    labelLarge = TextStyle(fontFamily = JetBrainsMono, fontWeight = FontWeight.SemiBold, fontSize = (15 * f).sp, letterSpacing = 0.4.sp),
    labelMedium = TextStyle(fontFamily = JetBrainsMono, fontWeight = FontWeight.Medium, fontSize = (12 * f).sp, letterSpacing = 0.8.sp),
    labelSmall = TextStyle(fontFamily = JetBrainsMono, fontWeight = FontWeight.Medium, fontSize = (11 * f).sp, letterSpacing = 1.sp),
)

private val scheme = darkColorScheme(
    primary = Grey.White, onPrimary = Grey.G950,
    secondary = Grey.G300, onSecondary = Grey.G950,
    background = Grey.G950, onBackground = Grey.White,
    surface = Grey.G900, onSurface = Grey.White,
    surfaceVariant = Grey.G850, onSurfaceVariant = Grey.G300,
    outline = Grey.G700, outlineVariant = Grey.G800,
    error = Grey.White, onError = Grey.G950,
)

@Composable
fun RviTheme(largeText: Boolean = false, content: @Composable () -> Unit) {
    val f = if (largeText) 1.2f else 1f
    androidx.compose.runtime.CompositionLocalProvider(LocalScale provides Scale(f)) {
        MaterialTheme(colorScheme = scheme, typography = type(f), content = content)
    }
}
