package org.rvi.inspect.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.ListAlt
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.rvi.inspect.ui.theme.GeistMono
import org.rvi.inspect.ui.theme.Ink
import kotlin.math.roundToInt

/** False in screenshot tests: looping animations never let the test settle. */
val LocalMotion = androidx.compose.runtime.staticCompositionLocalOf { true }

val GlassShape = RoundedCornerShape(28.dp)
val SheetShape = RoundedCornerShape(38.dp)

/** A soft colour field behind the glass: blurred-looking radial glows on the mist ground (no blur needed). */
data class Glow(val color: Color, val x: Float, val y: Float, val radius: Float, val alpha: Float = 0.55f)

val GlowsHome = listOf(Glow(Ink.Violet, 0f, 0.05f, 0.9f), Glow(Ink.Aqua, 1f, 0.32f, 0.8f, 0.45f))
val GlowsCool = listOf(Glow(Ink.Electric, 1f, 0f, 0.9f, 0.4f), Glow(Ink.Amber, 0f, 0.45f, 0.8f, 0.32f))
val GlowsMint = listOf(Glow(Color(0xFF3FE0A5), 0.1f, 0f, 0.95f, 0.5f), Glow(Ink.Violet, 1f, 0.45f, 0.8f, 0.4f))
val GlowsWarm = listOf(Glow(Color(0xFFFF8A4C), 0f, 0f, 0.9f, 0.4f), Glow(Ink.Violet, 1f, 0.5f, 0.8f, 0.4f))
val GlowsUrgent = listOf(Glow(Color(0xFFFF5A36), 0.3f, 0f, 1.1f, 0.85f), Glow(Color(0xFF7A2BFF), 1f, 0.3f, 0.8f, 0.5f))

@Composable
fun Aura(modifier: Modifier = Modifier, glows: List<Glow> = GlowsHome, base: Color = Ink.Mist, content: @Composable BoxScope.() -> Unit) {
    BoxWithConstraints(modifier.fillMaxSize().background(base)) {
        val w = constraints.maxWidth.toFloat()
        val h = constraints.maxHeight.toFloat()
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color.Transparent, Color.Transparent))).let { m ->
            glows.fold(m) { acc, g ->
                acc.background(Brush.radialGradient(listOf(g.color.copy(alpha = g.alpha), Color.Transparent),
                    center = Offset(g.x * w, g.y * h), radius = g.radius * minOf(w, h)))
            }
        })
        content()
    }
}

/** Earlier screens' background name. */
@Composable
fun AmbientBackground(modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) = Aura(modifier, GlowsHome, content = content)

/** Frosted panel: translucent white with a brighter top edge and a hairline white border. */
fun Modifier.glass(shape: Shape = GlassShape, strong: Boolean = false, dark: Boolean = false): Modifier {
    val top = if (dark) Color(0x750E1020) else if (strong) Color(0xEBFFFFFF) else Color(0xBFFFFFFF)
    val bottom = if (dark) Color(0x520E1020) else if (strong) Color(0xD1FFFFFF) else Color(0x94FFFFFF)
    return this.clip(shape).background(Brush.verticalGradient(listOf(top, bottom))).border(1.dp, if (dark) Ink.DarkEdge else Ink.GlassEdge, shape)
}

@Composable
fun GlassCard(modifier: Modifier = Modifier, strong: Boolean = false, padding: Dp = 18.dp, dark: Boolean = false,
              shape: Shape = GlassShape, content: @Composable ColumnScope.() -> Unit) {
    Column(modifier.glass(shape, strong, dark).padding(padding), content = content)
}

@Composable
fun Eyebrow(text: String, color: Color = Ink.Electric) = Text(text.uppercase(), style = MaterialTheme.typography.labelSmall, color = color)

enum class PillKind { Primary, Ink, Safety, Glass, Signal, Mint }

@Composable
fun Pill(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, kind: PillKind = PillKind.Primary, icon: ImageVector? = null,
         enabled: Boolean = true, height: Dp = 58.dp) {
    val (bg, fg) = when (kind) {
        PillKind.Primary -> Ink.Electric to Ink.White
        PillKind.Ink -> Ink.Ink to Ink.White
        PillKind.Safety -> Ink.Safety to Ink.White
        PillKind.Glass -> Color(0xC7FFFFFF) to Ink.Ink
        PillKind.Signal -> Ink.Signal to Ink.Ink
        PillKind.Mint -> Ink.Mint to Ink.White
    }
    Surface(onClick = onClick, enabled = enabled, shape = RoundedCornerShape(50), color = if (enabled) bg else Color(0x330E1020),
        contentColor = if (enabled) fg else Ink.Muted, shadowElevation = if (kind == PillKind.Glass || !enabled) 0.dp else 6.dp,
        border = if (kind == PillKind.Glass) BorderStroke(1.dp, Ink.GlassEdge) else null,
        modifier = modifier.heightIn(min = height)) {
        Row(Modifier.padding(horizontal = 22.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center) {
            if (icon != null) { Icon(icon, null, Modifier.size(22.dp)); Spacer(Modifier.width(10.dp)) }
            Text(text, style = MaterialTheme.typography.labelLarge, textAlign = TextAlign.Center)
        }
    }
}

@Composable
fun PrimaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, icon: ImageVector? = null, enabled: Boolean = true) =
    Pill(text, onClick, modifier.fillMaxWidth(), PillKind.Primary, icon, enabled)

@Composable
fun GhostButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, icon: ImageVector? = null) =
    Pill(text, onClick, modifier, PillKind.Glass, icon, height = 52.dp)

@Composable
fun IconCircle(icon: ImageVector, label: String, onClick: () -> Unit, modifier: Modifier = Modifier, size: Dp = 48.dp, dark: Boolean = false,
               bg: Color? = null, tint: Color? = null) {
    Surface(onClick = onClick, shape = CircleShape, color = bg ?: if (dark) Ink.DarkGlass else Color(0x8CFFFFFF),
        contentColor = tint ?: if (dark) Ink.White else Ink.Ink, border = BorderStroke(1.dp, if (dark) Ink.DarkEdge else Ink.GlassEdge),
        modifier = modifier.size(size).semantics { contentDescription = label; role = Role.Button }) {
        Box(contentAlignment = Alignment.Center) { Icon(icon, null, Modifier.size(size * 0.45f)) }
    }
}

@Composable
fun GlassRoundButton(icon: ImageVector, label: String, onClick: () -> Unit, modifier: Modifier = Modifier, size: Dp = 72.dp, filled: Boolean = false) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = modifier) {
        IconCircle(icon, label, onClick, size = size, bg = if (filled) Ink.Electric else null, tint = if (filled) Ink.White else null)
        Spacer(Modifier.height(6.dp))
        Text(label, style = MaterialTheme.typography.labelMedium, color = Ink.Body)
    }
}

@Composable
fun Chip(text: String, selected: Boolean = false, onClick: (() -> Unit)? = null) {
    Surface(onClick = onClick ?: {}, enabled = onClick != null, shape = RoundedCornerShape(50),
        color = if (selected) Ink.Ink else Color(0x99FFFFFF), contentColor = if (selected) Ink.White else Ink.Ink,
        border = BorderStroke(1.dp, if (selected) Ink.Ink else Ink.GlassEdge), modifier = Modifier.heightIn(min = 40.dp)) {
        Box(contentAlignment = Alignment.Center) { Text(text, Modifier.padding(horizontal = 14.dp, vertical = 9.dp), style = MaterialTheme.typography.labelMedium) }
    }
}

enum class Tone { Ok, Urgent, Info, Wait, Now }

@Composable
fun StatusChip(text: String, tone: Tone) {
    val (bg, fg) = when (tone) {
        Tone.Ok -> Ink.MintTint to Ink.MintText
        Tone.Urgent -> Ink.SafetyTint to Ink.SafetyText
        Tone.Info -> Ink.ElectricTint to Ink.ElectricDeep
        Tone.Wait -> Color(0x120E1020) to Ink.Body
        Tone.Now -> Ink.Signal to Ink.Ink
    }
    Text(text, Modifier.clip(RoundedCornerShape(50)).background(bg).padding(horizontal = 10.dp, vertical = 4.dp),
        style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.ExtraBold), color = fg)
}

@Composable
fun Mono(text: String, modifier: Modifier = Modifier, color: Color = Ink.Ink, size: Int = 15) =
    Text(text, modifier, color = color, style = MaterialTheme.typography.bodyLarge.copy(fontFamily = GeistMono, fontWeight = FontWeight.SemiBold,
        fontSize = androidx.compose.ui.unit.TextUnit(size.toFloat(), androidx.compose.ui.unit.TextUnitType.Sp)))

/** Swipe the yellow knob to the end to start (a pocket tap cannot start a patrol). Tapping the knob also works,
 *  for accessibility services and gloves. */
@Composable
fun SwipeToStart(label: String, onDone: () -> Unit, modifier: Modifier = Modifier) {
    val scope = rememberCoroutineScope()
    val x = remember { Animatable(0f) }
    val density = LocalDensity.current
    BoxWithConstraints(modifier.fillMaxWidth().height(66.dp).clip(RoundedCornerShape(50)).background(Ink.Ink)) {
        val knob = with(density) { 54.dp.toPx() }
        val pad = with(density) { 6.dp.toPx() }
        val max = constraints.maxWidth - knob - pad * 2
        Box(Modifier.fillMaxHeight().width(with(density) { (x.value + knob + pad * 2).toDp() }).clip(RoundedCornerShape(50)).background(Ink.Electric))
        Text(label, Modifier.align(Alignment.Center).padding(start = 48.dp), style = MaterialTheme.typography.labelLarge, color = Color(0xE6FFFFFF))
        Surface(onClick = { scope.launch { x.animateTo(max, spring()); onDone(); x.snapTo(0f) } }, shape = CircleShape, color = Ink.Signal,
            contentColor = Ink.Ink, shadowElevation = 4.dp,
            modifier = Modifier.offset { IntOffset((pad + x.value).roundToInt(), pad.roundToInt()) }.size(54.dp)
                .semantics { contentDescription = label }
                .pointerInput(max) {
                    detectHorizontalDragGestures(
                        onDragEnd = { scope.launch { if (x.value > max * 0.8f) { x.animateTo(max); onDone(); x.snapTo(0f) } else x.animateTo(0f, spring()) } },
                        onDragCancel = { scope.launch { x.animateTo(0f) } },
                    ) { _, d -> scope.launch { x.snapTo((x.value + d).coerceIn(0f, max)) } }
                }) {
            Box(contentAlignment = Alignment.Center) { Icon(Icons.AutoMirrored.Outlined.ArrowForward, null) }
        }
    }
}

enum class Tab { Home, Patrols, Alerts, Profile }

/** Floating glass tab bar: four tabs, labels always shown, the active one in a white lens. */
@Composable
fun FloatingTabBar(selected: Tab, onSelect: (Tab) -> Unit, labels: Map<Tab, String>, alerts: Int, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth().padding(horizontal = 16.dp).height(66.dp).glass(RoundedCornerShape(50)).padding(6.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        for (t in Tab.entries) {
            val on = t == selected
            val icon = when (t) { Tab.Home -> Icons.Outlined.Home; Tab.Patrols -> Icons.Outlined.ListAlt; Tab.Alerts -> Icons.Outlined.Notifications; Tab.Profile -> Icons.Outlined.Person }
            Surface(onClick = { onSelect(t) }, shape = RoundedCornerShape(50), color = if (on) Ink.White else Color.Transparent,
                shadowElevation = if (on) 3.dp else 0.dp, contentColor = if (on) Ink.Electric else Ink.Body,
                modifier = Modifier.weight(1f).fillMaxHeight().semantics { role = Role.Tab }) {
                Box(contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(icon, null, Modifier.size(22.dp))
                        Text(labels[t] ?: t.name, style = MaterialTheme.typography.labelMedium.copy(fontWeight = if (on) FontWeight.Bold else FontWeight.SemiBold))
                    }
                    if (t == Tab.Alerts && alerts > 0) {
                        val dx by animateDpAsState(14.dp, label = "badge")
                        Text("$alerts", Modifier.align(Alignment.TopCenter).offset(x = dx, y = 2.dp).clip(CircleShape).background(Color(0xFFE2470F))
                            .border(2.dp, Ink.White, CircleShape).padding(horizontal = 6.dp, vertical = 1.dp),
                            color = Ink.White, style = MaterialTheme.typography.labelSmall.copy(letterSpacing = androidx.compose.ui.unit.TextUnit.Unspecified))
                    }
                }
            }
        }
    }
}

/** Tick legend used under photo thumbnails: saved, uploaded, checked by the system. */
fun ticks(uploaded: Boolean, checked: Boolean) = if (!uploaded) "✓" else "✓✓"

val ScreenPad = PaddingValues(horizontal = 16.dp)
