package io.github.levydeng.starsavior

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.SweepGradient
import android.view.View
import android.view.animation.LinearInterpolator

class GlassScanButton(context: Context) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val icon = BitmapFactory.decodeResource(resources, R.drawable.floating_icon)
    private val iconBounds = RectF(0f, 0f, 72f, 72f)
    private val sheen = SweepGradient(36f, 36f,
        intArrayOf(Color.TRANSPARENT, Color.rgb(115, 213, 160), Color.rgb(217, 255, 233),
            Color.rgb(163, 237, 192), Color.TRANSPARENT, Color.TRANSPARENT),
        floatArrayOf(0f, .3f, .48f, .55f, .75f, 1f))
    private val rotation = Matrix()
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
        paint.color = Color.WHITE
        paint.shader = null
        paint.isFilterBitmap = true
        canvas.drawBitmap(icon, null, iconBounds, paint)
        if (busy) {
            paint.style = Paint.Style.STROKE
            paint.strokeWidth = 3f
            rotation.setRotate(phase, 36f, 36f)
            sheen.setLocalMatrix(rotation)
            paint.shader = sheen
            canvas.drawCircle(36f, 36f, 31f, paint)
        }
        paint.shader = null; canvas.restore()
    }
}
