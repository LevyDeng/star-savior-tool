package io.github.levydeng.starsavior

import android.annotation.SuppressLint
import android.app.Activity
import android.app.Dialog
import android.os.Handler
import android.os.Looper
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.LinearLayout
import org.json.JSONObject
import org.json.JSONTokener

@SuppressLint("SetJavaScriptEnabled")
class EsprBrowser(private val activity: Activity, language: String,
                  private val loaded: (JSONObject) -> Unit, private val cancelled: () -> Unit) {
    fun close() { dialog.dismiss() }
    private val dialog = Dialog(activity)
    private val handler = Handler(Looper.getMainLooper())
    private val view = WebView(activity)
    private val hint = Ui.label(activity, Ui.text(activity, "browser_sync_hint"), 13f)
    private val expectedPath = JSONObject.quote(android.net.Uri.parse(EsprData.url(language)).path)
    private val extractor = activity.assets.open("espr-extract.js").bufferedReader().use { it.readText() }
    private val script = "(function(){ if(location.pathname.replace(/\\/\u0024/, \"\") !== $expectedPath) return null; return $extractor; })()"
    private var done = false
    private var waiting = false
    private val poll = object : Runnable {
        override fun run() {
            if (!dialog.isShowing || done) return
            if (!waiting) {
                waiting = true
                view.evaluateJavascript(script) { value ->
                    waiting = false
                    if (!done && dialog.isShowing) {
                        val data = runCatching {
                            val text = JSONTokener(value).nextValue() as? String ?: return@runCatching null
                            JSONObject(text)
                        }.getOrNull()
                        if (data?.optJSONArray("events")?.length()?.let { it > 0 } == true) {
                            done = true
                            dialog.dismiss()
                            loaded(data)
                        }
                    }
                }
            }
            if (!done) handler.postDelayed(this, 1500)
        }
    }

    init {
        val body = Ui.column(activity)
        body.addView(hint)
        view.settings.javaScriptEnabled = true
        view.settings.domStorageEnabled = true
        view.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) =
                request.url.scheme != "https" || request.url.host != "ss.espr.gg"
        }
        body.addView(view, LinearLayout.LayoutParams(-1, 0, 1f))
        body.addView(Ui.button(activity, Ui.text(activity, "network_cancel")) { dialog.dismiss() })
        dialog.setTitle(Ui.text(activity, "browser_sync"))
        dialog.setContentView(body)
        dialog.setOnDismissListener {
            handler.removeCallbacksAndMessages(null)
            view.stopLoading(); view.destroy()
            if (!done) { done = true; cancelled() }
        }
        dialog.show()
        dialog.window?.setLayout(-1, -1)
        view.loadUrl(EsprData.url(language))
        handler.postDelayed(poll, 1500)
        handler.postDelayed({ if (!done) {
            handler.removeCallbacks(poll)
            hint.text = Ui.text(activity, "browser_sync_timeout")
        } }, 120000)
    }
}
