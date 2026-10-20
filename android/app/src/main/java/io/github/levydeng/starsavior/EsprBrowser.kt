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
    private val journeyUrl = EsprData.url(language)
    private val cardsUrl = journeyUrl.replace("/journey-events", "/arcanas")
    private val extractors = listOf("espr-extract.js", "espr-cards-extract.js").map { name ->
        activity.assets.open(name).bufferedReader().use { it.readText() }
    }
    private var journey: JSONObject? = null
    private var done = false
    private var waiting = false
    private val poll = object : Runnable {
        override fun run() {
            if (!dialog.isShowing || done) return
            if (!waiting) {
                waiting = true
                val phase = if (journey == null) 0 else 1
                val expectedPath = JSONObject.quote(android.net.Uri.parse(if (phase == 0) journeyUrl else cardsUrl).path)
                val script = "(function(){ if(location.pathname.replace(/\\/\u0024/, \"\") !== $expectedPath) return null; return ${extractors[phase]}; })()"
                view.evaluateJavascript(script) { value ->
                    waiting = false
                    if (!done && dialog.isShowing) {
                        val data = runCatching {
                            val text = JSONTokener(value).nextValue() as? String ?: return@runCatching null
                            JSONObject(text)
                        }.getOrNull()
                        if (phase == 0 && data?.optJSONArray("events")?.length()?.let { it > 0 } == true) {
                            journey = data
                            hint.text = Ui.text(activity, "card_index_sync")
                            view.loadUrl(cardsUrl)
                        } else if (phase == 1 && data?.optJSONArray("cards")?.length()?.let { it > 0 } == true) {
                            finish(journey!!.put("card_catalog", data.getJSONArray("cards")))
                        }
                    }
                }
            }
            if (!done) handler.postDelayed(this, 1500)
        }
    }

    private fun finish(raw: JSONObject) {
        done = true
        dialog.dismiss()
        loaded(raw)
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
        view.loadUrl(journeyUrl)
        handler.postDelayed(poll, 1500)
        handler.postDelayed({ if (!done) {
            handler.removeCallbacks(poll)
            if (journey != null) finish(journey!!.put("card_catalog_unavailable", true))
            else hint.text = Ui.text(activity, "browser_sync_timeout")
        } }, 120000)
    }
}
