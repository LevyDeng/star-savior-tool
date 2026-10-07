package io.github.levydeng.starsavior

import android.app.Activity
import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.SharedPreferences
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Settings
import android.util.DisplayMetrics
import android.util.Log
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.widget.Toast
import java.util.concurrent.Executors

class CaptureService : Service() {
    companion object { @Volatile var running = false; private set }
    private val main = Handler(Looper.getMainLooper())
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var windows: WindowManager
    private var projection: MediaProjection? = null
    private var display: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var scanButton: GlassScanButton? = null
    private var menuPanel: View? = null
    private var resultPanel: View? = null
    private var buttonParams: WindowManager.LayoutParams? = null
    private var busy = false
    private var captureAfter = 0L
    private var waitingForFrame = false
    private var closing = false
    private var lastScan = 0L
    private val readPendingFrame = object : Runnable {
        override fun run() {
            if (!waitingForFrame || closing) return
            reader?.let(::readFrame)
            if (waitingForFrame && !closing) main.postDelayed(this, 50)
        }
    }
    private val appearanceListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        if (key == "floating_size" || key == "floating_transparency") {
            main.post {
                if (!closing && scanButton?.isAttachedToWindow == true) applyButtonAppearance()
            }
        }
    }
    private val timeout = Runnable {
        if (waitingForFrame && !closing) {
            Log.w("CaptureService", "Fresh frame timed out after 5 seconds")
            waitingForFrame = false; busy = false
            main.removeCallbacks(readPendingFrame)
            Toast.makeText(this, Ui.text(this, "capture_timeout"), Toast.LENGTH_LONG).show()
            showButton()
            showFailure("Waiting for screenshot", IllegalStateException(Ui.text(this, "capture_timeout")))
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        Ui.preferences(this).registerOnSharedPreferenceChangeListener(appearanceListener)
    }

    private fun applyButtonAppearance() {
        val button = scanButton ?: return
        val layout = buttonParams ?: return
        val prefs = Ui.preferences(this)
        val size = Ui.dp(this, prefs.getInt("floating_size", 72).coerceIn(40, 160))
        button.alpha = 1f - prefs.getInt("floating_transparency", 0).coerceIn(0, 90) / 100f
        layout.width = size; layout.height = size
        val (width, height) = screenSize()
        layout.x = layout.x.coerceIn(0, (width - size).coerceAtLeast(0))
        layout.y = layout.y.coerceIn(0, (height - size).coerceAtLeast(0))
        if (button.isAttachedToWindow) windows.updateViewLayout(button, layout)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "STOP") { stopSelf(); return START_NOT_STICKY }
        if (running) return START_NOT_STICKY
        if (intent == null || !Settings.canDrawOverlays(this)) { stopSelf(); return START_NOT_STICKY }
        try {
            windows = getSystemService(WindowManager::class.java)
            val notifications = getSystemService(NotificationManager::class.java)
            notifications.createNotificationChannel(NotificationChannel("capture", "Screen capture", NotificationManager.IMPORTANCE_LOW))
            val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
            val stop = PendingIntent.getService(this, 1, Intent(this, CaptureService::class.java).setAction("STOP"), PendingIntent.FLAG_IMMUTABLE)
            val notification = Notification.Builder(this, "capture").setSmallIcon(android.R.drawable.ic_menu_view)
                .setContentTitle("starsaviorhelper").setContentText(Ui.text(this, "capture_hint"))
                .setContentIntent(open).setOngoing(true)
                .addAction(Notification.Action.Builder(null, Ui.text(this, "stop_capture"), stop).build()).build()
            startForeground(1, notification)
            val permission = if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra("captureData", Intent::class.java)
                else @Suppress("DEPRECATION") intent.getParcelableExtra<Intent>("captureData")
            check(permission != null && intent.getIntExtra("resultCode", 0) == Activity.RESULT_OK) { "Missing capture consent" }
            projection = getSystemService(MediaProjectionManager::class.java).getMediaProjection(Activity.RESULT_OK, permission)
            projection!!.registerCallback(object : MediaProjection.Callback() {
                override fun onStop() { stopSelf() }
                override fun onCapturedContentResize(width: Int, height: Int) { resizeCapture(width, height) }
            }, main)
            val (width, height) = screenSize()
            val surface = newReader(width, height)
            // One virtual display per consent token. Rotation resizes the existing display.
            display = projection!!.createVirtualDisplay("StarSavior capture", width, height,
                resources.configuration.densityDpi, DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                surface.surface, null, main)
            running = true
            showButton()
        } catch (error: Exception) {
            Log.e("CaptureService", "Could not start screen capture", error)
            Toast.makeText(this, error.message, Toast.LENGTH_LONG).show()
            stopSelf()
        }
        return START_NOT_STICKY
    }

    private fun screenSize(): Pair<Int, Int> {
        if (Build.VERSION.SDK_INT >= 30) windows.maximumWindowMetrics.bounds.let { return it.width() to it.height() }
        @Suppress("DEPRECATION") val metrics = DisplayMetrics().also { windows.defaultDisplay.getRealMetrics(it) }
        return metrics.widthPixels to metrics.heightPixels
    }

    private fun newReader(width: Int, height: Int): ImageReader {
        return ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2).also { next ->
            reader = next
            next.setOnImageAvailableListener({ source -> readFrame(source) }, main)
        }
    }

    private fun readFrame(source: ImageReader) {
                if (closing || source !== reader) return
                // Keep early post-hide frames queued. Static screens may send only one frame.
                if (waitingForFrame && System.nanoTime() < captureAfter) return
                val image = try {
                    source.acquireLatestImage()
                } catch (error: Exception) {
                    if (waitingForFrame) failCapture("Acquiring screenshot buffer", error)
                    null
                } ?: return
                try {
                    if (!waitingForFrame) return
                    waitingForFrame = false
                    Log.i("CaptureService", "Fresh frame received: ${image.width}x${image.height}")
                    main.removeCallbacks(timeout)
                    main.removeCallbacks(readPendingFrame)
                    val plane = image.planes[0]
                    val paddedWidth = image.width + (plane.rowStride - plane.pixelStride * image.width) / plane.pixelStride
                    val padded = Bitmap.createBitmap(paddedWidth, image.height, Bitmap.Config.ARGB_8888)
                    padded.copyPixelsFromBuffer(plane.buffer)
                    val frame = Bitmap.createBitmap(padded, 0, 0, image.width, image.height)
                    if (frame !== padded) padded.recycle()
                    showButton()
                    executor.execute {
                        val result = runCatching { OcrEngine(this).recognize(frame) }
                        frame.recycle()
                        main.post {
                            if (!closing) {
                                busy = false
                                Log.i("CaptureService", "Recognition completed: success=${result.isSuccess}")
                                showButton()
                                result.fold(::showResults, { error ->
                                    Log.e("CaptureService", "Recognition failed", error)
                                    showFailure("OCR and event lookup", error)
                                })
                            }
                        }
                    }
                } catch (error: Exception) {
                    waitingForFrame = false; busy = false; main.removeCallbacks(timeout)
                    Log.e("CaptureService", "Could not read captured frame", error)
                    showButton()
                    showFailure("Reading captured frame", error)
                } finally { image.close() }
    }

    private fun resizeCapture(width: Int, height: Int) {
        if (width <= 0 || height <= 0 || closing || display == null) return
        if (reader?.width == width && reader?.height == height) return
        val previous = reader
        try {
            val next = newReader(width, height)
            display!!.resize(width, height, resources.configuration.densityDpi)
            display!!.surface = next.surface
            previous?.close()
            if (!busy) showButton()
        } catch (error: Exception) {
            Log.e("CaptureService", "Could not resize screen capture", error)
            stopSelf()
        }
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        if (Build.VERSION.SDK_INT < 34 && ::windows.isInitialized) {
            val (width, height) = screenSize(); resizeCapture(width, height)
        }
        removeResult()
        removeMenu()
        if (!busy && running) showButton()
    }

    // Saved positions are physical coordinates, independent of text direction.
    @SuppressLint("RtlHardcoded")
    private fun params(width: Int, height: Int) = WindowManager.LayoutParams(width, height,
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
        PixelFormat.TRANSLUCENT).apply { gravity = Gravity.TOP or Gravity.LEFT }

    private fun showButton() {
        if (closing || !Settings.canDrawOverlays(this)) return
        val size = Ui.dp(this, Ui.preferences(this).getInt("floating_size", 72).coerceIn(40, 160))
        val button = scanButton ?: GlassScanButton(this).apply {
            scanButton = this
            setOnClickListener { capture() }
            setOnLongClickListener { showMenu(); true }
        }
        val (width, height) = screenSize()
        button.contentDescription = Ui.text(this, "scan")
        button.setBusy(busy)
        val prefs = Ui.preferences(this)
        button.alpha = 1f - prefs.getInt("floating_transparency", 0).coerceIn(0, 90) / 100f
        val layout = buttonParams ?: params(size, size).apply {
            x = prefs.getInt("button_x", 16); y = prefs.getInt("button_y", height / 3)
            buttonParams = this
        }
        layout.width = size; layout.height = size
        layout.x = layout.x.coerceIn(0, (width - size).coerceAtLeast(0))
        layout.y = layout.y.coerceIn(0, (height - size).coerceAtLeast(0))
        var startX = 0f; var startY = 0f; var originX = 0; var originY = 0; var moved = false
        val touchSlop = ViewConfiguration.get(this).scaledTouchSlop.toFloat()
        var held = false
        val hold = Runnable { if (!moved) { held = true; button.performLongClick() } }
        button.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    startX = event.rawX; startY = event.rawY; originX = layout.x; originY = layout.y
                    moved = false; held = false; main.postDelayed(hold, 700)
                }
                MotionEvent.ACTION_MOVE -> {
                    val deltaX = event.rawX - startX
                    val deltaY = event.rawY - startY
                    if (moved || deltaX * deltaX + deltaY * deltaY > touchSlop * touchSlop) {
                        moved = true; main.removeCallbacks(hold)
                        layout.x = (originX + event.rawX - startX).toInt().coerceIn(0, (width - layout.width).coerceAtLeast(0))
                        layout.y = (originY + event.rawY - startY).toInt().coerceIn(0, (height - layout.height).coerceAtLeast(0))
                        if (button.isAttachedToWindow) windows.updateViewLayout(button, layout)
                    }
                }
                MotionEvent.ACTION_UP -> {
                    main.removeCallbacks(hold)
                    prefs.edit().putInt("button_x", layout.x).putInt("button_y", layout.y).apply()
                    if (!moved && !held) button.performClick()
                    else Log.d("CaptureService", "Scan gesture ended without a tap: dragged=$moved held=$held")
                }
                MotionEvent.ACTION_CANCEL -> main.removeCallbacks(hold)
            }
            true
        }
        if (!button.isAttachedToWindow) windows.addView(button, layout) else windows.updateViewLayout(button, layout)
    }

    private fun capture() {
        val now = android.os.SystemClock.elapsedRealtime()
        Log.i("CaptureService", "Scan tap received: busy=$busy waitingForFrame=$waitingForFrame closing=$closing")
        if (busy || now - lastScan < 800 || closing) {
            Log.d("CaptureService", "Scan tap ignored: cooldownMs=${now - lastScan}")
            return
        }
        removeMenu()
        removeResult()
        val (width, height) = screenSize()
        if (width <= height) {
            Toast.makeText(this, Ui.text(this, "landscape_only"), Toast.LENGTH_LONG).show()
            return
        }
        lastScan = now; busy = true; waitingForFrame = true
        Log.i("CaptureService", "Waiting for a fresh capture: ${width}x$height")
        try {
            check(reader != null && display != null && projection != null) { "Screen capture session is unavailable" }
            // Drain old buffers before hiding the button so the hide-triggered frame survives.
            reader?.acquireLatestImage()?.close()
            captureAfter = System.nanoTime() + 180_000_000L
            scanButton?.takeIf { it.isAttachedToWindow }?.let { windows.removeViewImmediate(it) }
            main.postDelayed(timeout, 5000)
            main.postDelayed(readPendingFrame, 180)
            // Only request a surface refresh if no frame has arrived after normal settling.
            main.postDelayed({ if (waitingForFrame && !closing) {
                try {
                    display?.surface = null; display?.surface = reader?.surface
                } catch (error: Exception) {
                    failCapture("Requesting a fresh screenshot", error)
                }
            } }, 1000)
        } catch (error: Exception) {
            failCapture("Starting screenshot capture", error)
        }
    }

    private fun failCapture(stage: String, error: Throwable) {
        waitingForFrame = false; busy = false
        main.removeCallbacks(timeout)
        main.removeCallbacks(readPendingFrame)
        showButton()
        showFailure(stage, error)
    }

    private fun showResults(recognition: Recognition) {
        showResultPanel(ResultsPanel.create(this, recognition, ::removeResult))
    }

    private fun showFailure(stage: String, error: Throwable) {
        if (closing) return
        val prefs = Ui.preferences(this)
        val causes = generateSequence(error) { it.cause }.take(6)
            .joinToString("\n") { "${it.javaClass.simpleName}: ${it.message.orEmpty()}" }
        val version = runCatching { packageManager.getPackageInfo(packageName, 0).versionName }.getOrNull()
        val diagnostics = "Stage: $stage\n$causes\n\n" +
            "App: $version\nDevice: ${Build.MANUFACTURER} ${Build.MODEL}\n" +
            "Android: ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})\n" +
            "Capture: ${reader?.width}x${reader?.height}\n" +
            "Language: ${prefs.getString("language", "zh-CN")}\n" +
            "Difficulty: ${prefs.getString("difficulty", "Normal")}"
        Log.e("CaptureService", diagnostics, error)
        showResultPanel(ResultsPanel.error(this, diagnostics, ::removeResult))
    }

    private fun showResultPanel(panel: View) {
        removeResult()
        val (width, height) = screenSize()
        val layout = params(minOf(Ui.dp(this, 420), width - Ui.dp(this, 24)), (height * .82).toInt())
        layout.x = (width - layout.width - Ui.dp(this, 12)).coerceAtLeast(0)
        layout.y = ((height - layout.height) / 2).coerceAtLeast(0)
        resultPanel = panel
        windows.addView(panel, layout)
    }

    private fun removeResult() {
        resultPanel?.takeIf { it.isAttachedToWindow }?.let { windows.removeViewImmediate(it) }
        resultPanel = null
    }

    private fun showMenu() {
        if (closing) return
        removeMenu()
        val panel = Ui.column(this).apply {
            background = Ui.surface(Ui.background)
            addView(Ui.button(this@CaptureService, Ui.text(this@CaptureService, "settings")) {
                removeMenu()
                startActivity(Intent(this@CaptureService, MainActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP))
            })
            addView(Ui.button(this@CaptureService, Ui.text(this@CaptureService, "quit")) { stopSelf() })
            addView(Ui.button(this@CaptureService, Ui.text(this@CaptureService, "network_cancel")) { removeMenu() })
        }
        val (width, height) = screenSize()
        val layout = params(minOf(Ui.dp(this, 220), width), WindowManager.LayoutParams.WRAP_CONTENT)
        layout.x = (buttonParams?.x ?: 0).coerceIn(0, (width - layout.width).coerceAtLeast(0))
        layout.y = ((buttonParams?.y ?: 0) + (buttonParams?.height ?: Ui.dp(this, 72))).coerceIn(0, (height - Ui.dp(this, 200)).coerceAtLeast(0))
        menuPanel = panel
        windows.addView(panel, layout)
    }

    private fun removeMenu() {
        menuPanel?.takeIf { it.isAttachedToWindow }?.let { windows.removeViewImmediate(it) }
        menuPanel = null
    }

    override fun onDestroy() {
        Ui.preferences(this).unregisterOnSharedPreferenceChangeListener(appearanceListener)
        closing = true; running = false; waitingForFrame = false
        main.removeCallbacksAndMessages(null)
        if (::windows.isInitialized) {
            removeMenu()
            removeResult()
            scanButton?.takeIf { it.isAttachedToWindow }?.let { windows.removeViewImmediate(it) }
        }
        reader?.setOnImageAvailableListener(null, null)
        display?.release(); display = null
        reader?.close(); reader = null
        projection?.stop(); projection = null
        executor.shutdown()
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }
}
