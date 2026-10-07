package io.github.levydeng.starsavior

import android.graphics.Bitmap
import android.graphics.RectF
import android.content.Context
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import org.json.JSONObject
import java.util.concurrent.TimeUnit

data class Recognition(val title: List<String>, val choices: List<String>, val match: MatchResult, val elapsed: Double)

object Regions {
    fun load(context: Context): Map<String, RectF> {
        val defaults = JSONObject(context.assets.open("contract.json").bufferedReader().use { it.readText() }).getJSONObject("regions")
        return listOf("title", "options").associateWith { key ->
            val points = defaults.getJSONArray(key)
            RectF(points.getDouble(0).toFloat(), points.getDouble(1).toFloat(),
                  points.getDouble(2).toFloat(), points.getDouble(3).toFloat())
        }
    }
}

class OcrEngine(private val context: Context) {
    fun recognize(bitmap: Bitmap): Recognition {
        require(bitmap.width > bitmap.height) { Ui.text(context, "landscape_only") }
        val started = System.nanoTime()
        val settings = Ui.preferences(context)
        val language = settings.getString("language", "zh-CN") ?: "zh-CN"
        val difficulty = settings.getString("difficulty", "Normal") ?: "Normal"
        val events = AppState.repository(context).events(language, difficulty)
        check(events.isNotEmpty()) { Ui.text(context, "no_data") }
        val recognizer = when (language) {
            "zh-CN", "zh-TW" -> TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())
            "ja-JP" -> TextRecognition.getClient(JapaneseTextRecognizerOptions.Builder().build())
            "ko-KR" -> TextRecognition.getClient(KoreanTextRecognizerOptions.Builder().build())
            else -> TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        }
        fun read(rect: RectF): List<String> {
            val left = (rect.left * bitmap.width).toInt().coerceIn(0, bitmap.width - 1)
            val top = (rect.top * bitmap.height).toInt().coerceIn(0, bitmap.height - 1)
            val width = ((rect.right * bitmap.width).toInt() - left).coerceIn(1, bitmap.width - left)
            val height = ((rect.bottom * bitmap.height).toInt() - top).coerceIn(1, bitmap.height - top)
            val crop = Bitmap.createBitmap(bitmap, left, top, width, height)
            try {
                val text = Tasks.await(recognizer.process(InputImage.fromBitmap(crop, 0)), 30, TimeUnit.SECONDS)
                return text.textBlocks.flatMap { it.lines }.sortedWith(compareBy({ it.boundingBox?.top ?: 0 }, { it.boundingBox?.left ?: 0 })).map { it.text }
            } finally { if (crop !== bitmap) crop.recycle() }
        }
        try {
            val regions = Regions.load(context)
            val title = read(regions.getValue("title")); val choices = read(regions.getValue("options"))
            return Recognition(title, choices, GuideMatcher.match(events, title, choices), (System.nanoTime() - started) / 1e9)
        } finally { recognizer.close() }
    }
}
