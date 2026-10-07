package io.github.levydeng.starsavior

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.media.projection.MediaProjectionConfig
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.Spinner
import android.widget.TextView
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var status: TextView
    private lateinit var summary: TextView
    private lateinit var syncButton: Button
    private lateinit var startButton: Button
    private lateinit var sslButton: Button
    private var busy = false

    override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); render() }

    private fun render() {
        val body = Ui.column(this)
        val prefs = Ui.preferences(this)
        val header = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        header.addView(Ui.label(this, "starsaviorhelper", 21f).apply { setTextColor(Ui.blue) }, LinearLayout.LayoutParams(0, -2, 1f))
        val languages = linkedMapOf("zh-CN" to "简体中文", "zh-TW" to "繁體中文", "en-US" to "English", "ja-JP" to "日本語", "ko-KR" to "한국어")
        header.addView(selector(languages.keys.toList(), languages.values.toList(), prefs.getString("language", "zh-CN")!!) { value ->
            prefs.edit().putString("language", value).apply(); render()
        }.apply { contentDescription = Ui.text(this@MainActivity, "language") }, LinearLayout.LayoutParams(Ui.dp(this, 130), -2))
        body.addView(header)
        summary = Ui.label(this, "", 14f); body.addView(summary)
        val syncRow = LinearLayout(this)
        syncButton = Ui.button(this, Ui.text(this, "sync"), true) { synchronize() }
        syncRow.addView(syncButton, LinearLayout.LayoutParams(0, Ui.dp(this, 48), 1f))
        syncRow.addView(Ui.button(this, Ui.text(this, "website")) {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://star-savior-arcana-db.pages.dev/journey")))
        }, LinearLayout.LayoutParams(0, Ui.dp(this, 48), 1f).apply { marginStart = Ui.dp(this@MainActivity, 8) })
        body.addView(syncRow)
        val optionsRow = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL; setPadding(0, Ui.dp(this@MainActivity, 12), 0, 0) }
        sslButton = Ui.button(this, Ui.text(this, "ssl_settings")) { configureSsl() }
        optionsRow.addView(sslButton, LinearLayout.LayoutParams(0, Ui.dp(this, 48), 1f))
        val difficulty = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        difficulty.addView(Ui.label(this, Ui.text(this, "difficulty"), 13f))
        val keys = GuideConverter.difficulties.keys.toList()
        difficulty.addView(selector(keys, keys.map { Ui.text(this, it) }, prefs.getString("difficulty", "Normal")!!) { value ->
            prefs.edit().putString("difficulty", value).apply(); updateSummary()
        })
        optionsRow.addView(difficulty, LinearLayout.LayoutParams(0, -2, 1f).apply { marginStart = Ui.dp(this@MainActivity, 12) })
        body.addView(optionsRow)
        addButtonAppearance(body)
        status = Ui.label(this, Ui.text(this, "share_hint"), 14f); body.addView(status)
        body.addView(View(this), LinearLayout.LayoutParams(1, 0, 1f))
        val bottom = LinearLayout(this).apply { gravity = Gravity.END }
        startButton = Ui.button(this, Ui.text(this, "start"), true) { startCapture() }
        startButton.background = Ui.surface(Ui.blue, Ui.dp(this, 42).toFloat())
        bottom.addView(startButton, LinearLayout.LayoutParams(Ui.dp(this, 84), Ui.dp(this, 84)))
        body.addView(bottom)
        setContentView(ScrollView(this).apply { isFillViewport = true; addView(body) })
        setBusy(busy); updateSummary()
    }

    private fun addButtonAppearance(body: LinearLayout) {
        val prefs = Ui.preferences(this)
        val preview = GlassScanButton(this).apply {
            isClickable = false; isLongClickable = false
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }
        val stage = FrameLayout(this).apply {
            background = Ui.surface(android.graphics.Color.rgb(220, 230, 240))
            addView(preview, FrameLayout.LayoutParams(1, 1, Gravity.CENTER))
        }
        fun updatePreview() {
            val size = Ui.dp(this, prefs.getInt("floating_size", 72).coerceIn(40, 160))
            preview.layoutParams = FrameLayout.LayoutParams(size, size, Gravity.CENTER)
            preview.alpha = 1f - prefs.getInt("floating_transparency", 0).coerceIn(0, 90) / 100f
        }
        fun slider(key: String, label: String, minimum: Int, maximum: Int, initial: Int, unit: String) {
            val value = prefs.getInt(key, initial).coerceIn(minimum, maximum)
            val caption = Ui.label(this, "${Ui.text(this, label)}: $value $unit", 14f)
            body.addView(caption)
            body.addView(SeekBar(this).apply {
                max = maximum - minimum; progress = value - minimum
                contentDescription = Ui.text(this@MainActivity, label)
                progressTintList = android.content.res.ColorStateList.valueOf(Ui.blue)
                thumbTintList = android.content.res.ColorStateList.valueOf(Ui.blue)
                setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                    override fun onStartTrackingTouch(seekBar: SeekBar) = Unit
                    override fun onStopTrackingTouch(seekBar: SeekBar) = Unit
                    override fun onProgressChanged(seekBar: SeekBar, progress: Int, fromUser: Boolean) {
                        val selected = progress + minimum
                        prefs.edit().putInt(key, selected).apply()
                        caption.text = "${Ui.text(this@MainActivity, label)}: $selected $unit"
                        updatePreview()
                    }
                })
            }, LinearLayout.LayoutParams(-1, Ui.dp(this, 40)))
        }
        slider("floating_size", "floating_size", 40, 160, 72, "dp")
        slider("floating_transparency", "floating_transparency", 0, 90, 0, "%")
        body.addView(Ui.label(this, Ui.text(this, "floating_preview"), 14f).apply { gravity = Gravity.CENTER })
        body.addView(stage, LinearLayout.LayoutParams(Ui.dp(this, 176), Ui.dp(this, 176)).apply { gravity = Gravity.CENTER_HORIZONTAL })
        updatePreview()
    }

    private fun configureSsl() {
        val prefs = Ui.preferences(this)
        val body = Ui.column(this)
        val skip = CheckBox(this).apply {
            text = Ui.text(this@MainActivity, "skip_tls")
            isChecked = prefs.getBoolean("sync_skip_tls", false)
        }
        body.addView(skip)
        body.addView(Ui.label(this, Ui.text(this, "ssl_warning"), 14f))
        AlertDialog.Builder(this).setTitle(Ui.text(this, "ssl_settings")).setView(body)
            .setPositiveButton(Ui.text(this, "network_save")) { _, _ -> prefs.edit().putBoolean("sync_skip_tls", skip.isChecked).apply() }
            .setNegativeButton(Ui.text(this, "network_cancel"), null).show()
    }

    private fun selector(keys: List<String>, labels: List<String>, current: String, changed: (String) -> Unit): Spinner {
        var previous = current
        return Spinner(this).apply {
            adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, labels)
            setSelection(keys.indexOf(current).coerceAtLeast(0))
            onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
                override fun onNothingSelected(parent: AdapterView<*>?) = Unit
                override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                    if (keys[position] != previous && !busy) { previous = keys[position]; changed(keys[position]) }
                }
            }
        }
    }

    private fun updateSummary() {
        val repo = AppState.repository(this); val prefs = Ui.preferences(this)
        val language = prefs.getString("language", "zh-CN")!!; val difficulty = prefs.getString("difficulty", "Normal")!!
        val words = Vocabulary(repo.vocabulary, language)
        val updated = if (repo.updated.isBlank()) words.text("never") else runCatching {
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss").withZone(ZoneId.systemDefault()).format(Instant.parse(repo.updated))
        }.getOrDefault(repo.updated)
        summary.text = words.text("summary", "count" to repo.events(language, difficulty).size, "updated" to updated)
    }

    private fun setBusy(value: Boolean) {
        busy = value; syncButton.isEnabled = !value; startButton.isEnabled = !value; sslButton.isEnabled = !value
    }

    private fun synchronize() {
        if (busy) return
        val verifyTls = !Ui.preferences(this).getBoolean("sync_skip_tls", false)
        setBusy(true)
        status.text = Ui.text(this, "syncing") + if (!verifyTls) "\n" + Ui.text(this, "tls_disabled") else ""
        executor.execute {
            val result = runCatching { AppState.repository(this).sync(verifyTls) }
            result.exceptionOrNull()?.let { Log.e("MainActivity", "Guide synchronization failed", it) }
            runOnUiThread {
                if (!isDestroyed) {
                    setBusy(false); updateSummary()
                    status.text = result.fold({ Ui.text(this, "synced") }, {
                        Ui.text(this, "sync_failed").replace("{error}", it.message ?: it.javaClass.simpleName)
                    }) + if (!verifyTls) "\n" + Ui.text(this, "tls_disabled") else ""
                }
            }
        }
    }

    private fun startCapture() {
        if (busy) return
        if (CaptureService.running) { status.text = Ui.text(this, "capture_active"); moveTaskToBack(true); return }
        if (!Settings.canDrawOverlays(this)) {
            status.text = Ui.text(this, "overlay_permission")
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
            return
        }
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED
                && !Ui.preferences(this).getBoolean("notification_requested", false)) {
            Ui.preferences(this).edit().putBoolean("notification_requested", true).apply()
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 3)
            return
        }
        val manager = getSystemService(MediaProjectionManager::class.java)
        val consent = if (Build.VERSION.SDK_INT >= 34)
            manager.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay())
            else manager.createScreenCaptureIntent()
        startActivityForResult(consent, 1)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 3) startCapture()
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == 1) {
            if (resultCode == RESULT_OK && data != null) {
                startForegroundService(Intent(this, CaptureService::class.java).putExtra("resultCode", resultCode).putExtra("captureData", data))
                status.text = Ui.text(this, "capture_hint"); moveTaskToBack(true)
            } else status.text = Ui.text(this, "capture_denied")
        }
    }

    override fun onDestroy() { executor.shutdown(); super.onDestroy() }
}
