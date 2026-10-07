package io.github.levydeng.starsavior

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.Shader
import android.graphics.SweepGradient
import android.view.View
import android.view.animation.LinearInterpolator

class GlassScanButton(context: Context) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val shadow = RadialGradient(36f, 42f, 35f, intArrayOf(Color.argb(100, 12, 40, 74), Color.argb(35, 12, 40, 74), Color.TRANSPARENT), floatArrayOf(0f, .7f, 1f), Shader.TileMode.CLAMP)
    private val glass = LinearGradient(14f, 4f, 51f, 62f, intArrayOf(Color.rgb(193, 232, 255), Color.rgb(101, 175, 230), Color.rgb(51, 127, 186), Color.rgb(23, 72, 121)), floatArrayOf(0f, .32f, .68f, 1f), Shader.TileMode.CLAMP)
    private val highlight = LinearGradient(0f, 7f, 0f, 35f, Color.argb(150, 255, 255, 255), Color.TRANSPARENT, Shader.TileMode.CLAMP)
    private val sheen = SweepGradient(36f, 33f, intArrayOf(Color.TRANSPARENT, Color.rgb(130, 216, 255), Color.rgb(239, 252, 255), Color.rgb(162, 230, 255), Color.TRANSPARENT, Color.TRANSPARENT), floatArrayOf(0f, .3f, .48f, .55f, .75f, 1f))
    private val rotation = Matrix()
    private val star = Path().apply {
        moveTo(36f, 17f); lineTo(40f, 29f); lineTo(52f, 33f); lineTo(40f, 37f)
        lineTo(36f, 49f); lineTo(32f, 37f); lineTo(20f, 33f); lineTo(32f, 29f); close()
    }
    private var spinner: ValueAnimator? = null
    private var phase = 0f
    var busy = false
        private set

    init {
        isClickable = true; isLongClickable = true
        contentDescription = Ui.text(context, "scan")
    }

    fun setBusy(value: Boolean) {
        busy = value
        updateAnimation()
        invalidate()
    }

    private fun updateAnimation() {
        if (busy && isAttachedToWindow && visibility == VISIBLE) {
            if (spinner == null) spinner = ValueAnimator.ofFloat(0f, 360f).apply {
                duration = 1800; repeatCount = ValueAnimator.INFINITE; interpolator = LinearInterpolator()
                addUpdateListener { phase = it.animatedValue as Float; invalidate() }
            }
            if (spinner?.isStarted != true) spinner?.start()
        } else spinner?.cancel()
    }

    override fun onAttachedToWindow() { super.onAttachedToWindow(); updateAnimation() }
    override fun onDetachedFromWindow() { spinner?.cancel(); super.onDetachedFromWindow() }
    override fun onVisibilityChanged(changedView: View, visibility: Int) {
        super.onVisibilityChanged(changedView, visibility); updateAnimation()
    }
    override fun performClick(): Boolean { super.performClick(); return true }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        canvas.save(); canvas.scale(width / 72f, height / 72f)
        paint.style = Paint.Style.FILL
        paint.shader = shadow
        canvas.drawOval(1f, 9f, 71f, 71f, paint)
        paint.shader = glass
        canvas.drawCircle(36f, 33f, 29f, paint)
        paint.shader = null; paint.style = Paint.Style.STROKE; paint.strokeWidth = 1.5f; paint.color = Color.argb(220, 226, 247, 255)
        canvas.drawCircle(36f, 33f, 29f, paint)
        paint.style = Paint.Style.FILL
        paint.shader = highlight
        canvas.drawOval(14f, 8f, 58f, 32f, paint)
        paint.shader = null; paint.color = Color.argb(90, 13, 57, 93)
        canvas.save(); canvas.translate(0f, 1.5f); canvas.drawPath(star, paint); canvas.restore()
        paint.color = Color.rgb(243, 251, 255); canvas.drawPath(star, paint)
        if (busy) {
            rotation.setRotate(phase, 36f, 33f)
            sheen.setLocalMatrix(rotation)
            paint.shader = sheen; paint.style = Paint.Style.STROKE; paint.strokeWidth = 3f
            canvas.drawCircle(36f, 33f, 33f, paint)
        }
        paint.shader = null; canvas.restore()
    }
}
