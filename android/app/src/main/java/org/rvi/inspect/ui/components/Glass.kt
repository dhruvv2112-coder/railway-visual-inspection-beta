package org.rvi.inspect.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import org.rvi.inspect.ui.theme.Grey

val GlassShape = RoundedCornerShape(24.dp)

/** Ambient background: soft greyscale light blobs, blurred (Compose Modifier.blur, API 31+;
 *  on older devices the blobs render unblurred at lower alpha – still greyscale and legible). */
@Composable
fun AmbientBackground(modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) {
    Box(modifier.fillMaxSize().background(Grey.G950)) {
        Box(Modifier.fillMaxSize().blur(90.dp)) {
            Box(Modifier.size(320.dp).offset((-80).dp, (-40).dp).clip(CircleShape)
                .background(Brush.radialGradient(listOf(Color(0x40FFFFFF), Color.Transparent))))
            Box(Modifier.size(380.dp).align(Alignment.CenterEnd).offset(120.dp, 60.dp).clip(CircleShape)
                .background(Brush.radialGradient(listOf(Color(0x2EFFFFFF), Color.Transparent))))
            Box(Modifier.size(260.dp).align(Alignment.BottomStart).offset((-40).dp, 40.dp).clip(CircleShape)
                .background(Brush.radialGradient(listOf(Color(0x24FFFFFF), Color.Transparent))))
        }
        content()
    }
}

/** iOS-style translucent panel: low-alpha white fill, vertical sheen, hairline stroke. */
@Composable
fun GlassCard(modifier: Modifier = Modifier, strong: Boolean = false, padding: Dp = 20.dp, content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier
            .clip(GlassShape)
            .background(Brush.verticalGradient(listOf(if (strong) Grey.GlassFillStrong else Grey.GlassFill, Color(0x0DFFFFFF))))
            .border(BorderStroke(1.dp, Grey.GlassStroke), GlassShape)
            .padding(padding),
        content = content,
    )
}

@Composable
fun Eyebrow(text: String) = Text(text.uppercase(), style = MaterialTheme.typography.labelSmall, color = Grey.G400)

/** Primary action: solid white pill, black text – the single highest-contrast element on screen. */
@Composable
fun PrimaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, icon: ImageVector? = null, enabled: Boolean = true) {
    Surface(
        onClick = onClick, enabled = enabled, shape = RoundedCornerShape(50),
        color = if (enabled) Grey.White else Grey.G700, contentColor = Grey.G950,
        modifier = modifier.heightIn(min = 60.dp).fillMaxWidth(),
    ) {
        Row(Modifier.padding(horizontal = 24.dp, vertical = 18.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = androidx.compose.foundation.layout.Arrangement.Center) {
            if (icon != null) { Icon(icon, null); Spacer(Modifier.width(10.dp)) }
            Text(text, style = MaterialTheme.typography.labelLarge)
        }
    }
}

@Composable
fun GhostButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, icon: ImageVector? = null) {
    Surface(
        onClick = onClick, shape = RoundedCornerShape(50), color = Grey.GlassFill, contentColor = Grey.White,
        border = BorderStroke(1.dp, Grey.GlassStroke), modifier = modifier.heightIn(min = 52.dp),
    ) {
        Row(Modifier.padding(horizontal = 20.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
            if (icon != null) { Icon(icon, null, Modifier.size(20.dp)); Spacer(Modifier.width(8.dp)) }
            Text(text, style = MaterialTheme.typography.labelLarge)
        }
    }
}

/** Round glass control used on the camera/patrol HUD (min 72dp touch target for gloved use). */
@Composable
fun GlassRoundButton(icon: ImageVector, label: String, onClick: () -> Unit, modifier: Modifier = Modifier, size: Dp = 72.dp, filled: Boolean = false) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = modifier) {
        Surface(
            onClick = onClick, shape = CircleShape,
            color = if (filled) Grey.White else Grey.GlassFillStrong, contentColor = if (filled) Grey.G950 else Grey.White,
            border = BorderStroke(1.dp, Grey.GlassStroke),
            modifier = Modifier.size(size).semantics { role = Role.Button },
        ) { Box(contentAlignment = Alignment.Center) { Icon(icon, label, Modifier.size(size * 0.42f)) } }
        Spacer(Modifier.padding(top = 6.dp))
        Text(label, style = MaterialTheme.typography.labelMedium, color = Grey.G200)
    }
}

@Composable
fun Chip(text: String, selected: Boolean = false, onClick: (() -> Unit)? = null) {
    val m = Modifier
    Surface(
        onClick = onClick ?: {}, enabled = onClick != null, shape = RoundedCornerShape(50),
        color = if (selected) Grey.White else Grey.GlassFill, contentColor = if (selected) Grey.G950 else Grey.G200,
        border = BorderStroke(1.dp, if (selected) Grey.White else Grey.GlassStroke), modifier = m,
    ) { Text(text, Modifier.padding(horizontal = 14.dp, vertical = 8.dp), style = MaterialTheme.typography.labelMedium) }
}
