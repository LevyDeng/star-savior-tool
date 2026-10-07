package io.github.levydeng.starsavior

import android.content.Context
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView

object ResultsPanel {
    fun create(context: Context, recognition: Recognition, close: () -> Unit): View {
        val scroll = ScrollView(context)
        val body = Ui.column(context)
        scroll.addView(body)
        val elapsed = Ui.text(context, "elapsed").replace("{seconds}", "%.2f".format(recognition.elapsed))
        body.addView(Ui.label(context, elapsed + "\n" + Ui.text(context, "verify_result"), 13f))
        val effects = Ui.column(context).apply { background = Ui.surface() }
        body.addView(effects)
        fun show(event: GuideEvent) {
            effects.removeAllViews()
            effects.addView(Ui.label(context, event.title, 21f))
            effects.addView(Ui.label(context, listOf(event.displayPhase, event.displaySource).filter { it.isNotBlank() }.joinToString(" | "), 13f))
            for (option in event.options) {
                effects.addView(Ui.label(context, "${option.order}. ${option.text}", 17f))
                effects.addView(Ui.label(context, option.effect, 15f))
            }
        }
        recognition.match.candidates.firstOrNull()?.let { show(it.event) }
            ?: effects.addView(Ui.label(context, Ui.text(context, "unknown")))
        if (recognition.match.candidates.size > 1) {
            val list = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL; visibility = View.GONE }
            body.addView(Ui.button(context, Ui.text(context, "candidates") + " (${recognition.match.candidates.size})") {
                list.visibility = if (list.visibility == View.GONE) View.VISIBLE else View.GONE
            })
            for (candidate in recognition.match.candidates) list.addView(Ui.button(context,
                "${candidate.event.title} | ${candidate.event.displaySource} | ${"%.2f".format(candidate.score)}") { show(candidate.event) })
            body.addView(list)
        }
        val raw = Ui.label(context, (recognition.title + recognition.choices).joinToString("\n"), 14f).apply { visibility = View.GONE }
        body.addView(Ui.button(context, Ui.text(context, "text")) {
            raw.visibility = if (raw.visibility == View.GONE) View.VISIBLE else View.GONE
        })
        body.addView(raw)
        body.addView(Ui.button(context, Ui.text(context, "network_cancel"), action = close))
        return scroll
    }
}
