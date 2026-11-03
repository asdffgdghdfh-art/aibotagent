package me.rerere.rikkahub.robot

import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.painter.BitmapPainter
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.imageResource
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import me.rerere.rikkahub.R
import kotlin.math.PI
import kotlin.math.sin

/** Six pre-authored Xiaoliu poses on a single compact image atlas, with subtle breathing.
 * This is a cutout animation, not a full facial bone rig or a frame-accurate lip sync.
 */
private enum class MascotPose(val x: Int, val y: Int) {
    IDLE(0, 0), WAVE(1, 0), LISTEN(2, 0),
    TALK(0, 1), THINK(1, 1), SLEEP(2, 1)
}

@Composable
fun XiaoLiuAnimatedMascot(
    mood: RobotMood,
    speaking: Boolean,
    modifier: Modifier = Modifier
) {
    val pose = when {
        speaking -> MascotPose.TALK
        mood == RobotMood.LISTENING -> MascotPose.LISTEN
        mood == RobotMood.THINKING -> MascotPose.THINK
        mood == RobotMood.HAPPY -> MascotPose.WAVE
        mood == RobotMood.SLEEPY -> MascotPose.SLEEP
        else -> MascotPose.IDLE
    }
    val timeline = rememberInfiniteTransition(label = "xiaoliu-animation")
    val progress by timeline.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(2800, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ), label = "xiaoliu-breath"
    )
    val atlas = ImageBitmap.imageResource(id = R.drawable.xiaoliu_pose_atlas)
    val cellWidth = atlas.width / 3
    val cellHeight = atlas.height / 2
    Crossfade(targetState = pose, modifier = modifier,
        animationSpec = tween(250), label = "xiaoliu-pose") { current ->
        val painter = BitmapPainter(
            atlas,
            srcOffset = IntOffset(current.x * cellWidth, current.y * cellHeight),
            srcSize = IntSize(cellWidth, cellHeight)
        )
        val phase = (2.0 * PI * progress).toFloat()
        val slow = sin(phase)
        val quick = sin(phase * 2.5f)
        val angle = when(current) {
            MascotPose.IDLE -> 0.7f * slow
            MascotPose.WAVE -> 2.8f * slow
            MascotPose.LISTEN -> 1.0f * slow
            MascotPose.THINK -> 2.0f * slow
            MascotPose.TALK -> 1.3f * quick
            MascotPose.SLEEP -> 0.25f * slow
        }
        val shift = when(current) {
            MascotPose.WAVE -> 5.5f * slow
            MascotPose.TALK -> 3.5f * quick
            MascotPose.SLEEP -> 0.8f * slow
            else -> 2.2f * slow
        }
        Image(painter = painter, contentDescription = "小六动态形象",
            contentScale = ContentScale.Fit,
            modifier = Modifier.fillMaxSize().graphicsLayer {
                rotationZ = angle
                translationY = shift * density
                scaleY = 1f + (if(current == MascotPose.TALK) 0.012f * quick else 0.008f * slow)
            }
        )
    }
}
