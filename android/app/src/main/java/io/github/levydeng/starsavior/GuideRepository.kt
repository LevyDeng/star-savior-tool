package io.github.levydeng.starsavior

import android.content.Context
import android.util.AtomicFile
import android.util.Log
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import javax.net.ssl.HttpsURLConnection

class GuideRepository(context: Context) {
    private val preferences = Ui.preferences(context)
    private val esprCache = AtomicFile(File(context.filesDir, "guide-espr.json"))
    private var esprSnapshot = JSONObject()
    private val cache = AtomicFile(File(context.filesDir, "guide.json"))
    val vocabulary = JSONObject(context.assets.open("vocabulary.json").bufferedReader().use { it.readText() })
    private val converter = GuideConverter(vocabulary)
    private var snapshot: JSONObject? = null
    private val converted = mutableMapOf<Pair<String, String>, List<GuideEvent>>()
    private var legacyUpdated: String = ""
    val source: String get() = preferences.getString("guide_source", "espr")?.takeIf { it in setOf("espr", "arcana") } ?: "espr"
    val updated: String get() = if (source == "arcana") legacyUpdated else
        esprSnapshot.optJSONObject(preferences.getString("language", "zh-CN")!!)?.optString("updated", "") ?: ""
    fun sourceUrl(language: String) = if (source == "espr") EsprData.url(language) else "https://star-savior-arcana-db.pages.dev/journey"

    init {
        if (cache.baseFile.exists()) runCatching {
            val payload = cache.openRead().bufferedReader().use { JSONObject(it.readText()) }
            snapshot = payload.getJSONObject("data")
            legacyUpdated = payload.getString("updated")
        }.onFailure { Log.e("GuideRepository", "Could not load cached snapshot", it) }
        if (esprCache.baseFile.exists()) runCatching {
            esprSnapshot = esprCache.openRead().bufferedReader().use { JSONObject(it.readText()) }
        }.onFailure { Log.e("GuideRepository", "Could not load ESPR snapshot", it) }
    }

    @Synchronized
    fun events(language: String, difficulty: String, provider: String = source): List<GuideEvent> {
        if (provider == "espr") {
            val raw = esprSnapshot.optJSONObject(language)?.optJSONObject("data") ?: return emptyList()
            return converted.getOrPut(("espr:$language") to difficulty) { EsprData.convert(raw, language, difficulty, vocabulary) }
        }
        val raw = snapshot ?: return emptyList()
        return converted.getOrPut(language to difficulty) { converter.convert(raw, language, difficulty) }
    }

    fun sync(verifyTls: Boolean = true) {
        val raw = JSONObject()
        for (file in GuideConverter.files) {
            var last: Exception? = null
            for (attempt in 1..2) {
                try {
                    raw.put(file, fetch(file, verifyTls))
                    last = null
                    break
                } catch (error: Exception) {
                    last = error
                    if (attempt < 2) Thread.sleep(2000)
                }
            }
            if (last != null) throw IllegalStateException("$file.json: ${last.message}", last)
        }
        // Validate the entire snapshot before atomically replacing the last good copy.
        val next = mutableMapOf<Pair<String, String>, List<GuideEvent>>()
        for (language in GuideConverter.languages) for (difficulty in GuideConverter.difficulties.keys)
            next[language to difficulty] = converter.convert(raw, language, difficulty)
        val timestamp = Instant.now().toString()
        val payload = JSONObject().put("schema_version", 1).put("updated", timestamp).put("data", raw)
        synchronized(this) {
            val stream = cache.startWrite()
            try {
                stream.write(payload.toString().toByteArray(Charsets.UTF_8))
                cache.finishWrite(stream)
            } catch (error: Exception) {
                cache.failWrite(stream)
                throw error
            }
            snapshot = raw
            converted.clear(); converted.putAll(next)
            legacyUpdated = timestamp
        }
    }

    @Synchronized
    fun replaceEspr(language: String, raw: JSONObject) {
        require(language in EsprData.locales) { "Unsupported ESPR locale" }
        for (difficulty in GuideConverter.difficulties.keys) EsprData.convert(raw, language, difficulty, vocabulary)
        val next = JSONObject(esprSnapshot.toString()).put(language,
            JSONObject().put("updated", Instant.now().toString()).put("data", raw))
        val stream = esprCache.startWrite()
        try {
            stream.write(next.toString().toByteArray(Charsets.UTF_8))
            esprCache.finishWrite(stream)
        } catch (error: Exception) {
            esprCache.failWrite(stream); throw error
        }
        esprSnapshot = next
        converted.clear()
    }

    private fun fetch(file: String, verifyTls: Boolean): Any {
        val url = URL("https://star-savior-arcana-db.pages.dev/data/$file.json")
        val connection = url.openConnection() as HttpURLConnection
        SyncTls.configure(connection as HttpsURLConnection, verifyTls)
        connection.connectTimeout = 30000; connection.readTimeout = 60000
        connection.instanceFollowRedirects = false
        connection.setRequestProperty("User-Agent", "StarSaviorAndroid/0.1")
        try {
            check(connection.responseCode == 200) { "HTTP ${connection.responseCode}" }
            val output = java.io.ByteArrayOutputStream()
            connection.inputStream.use { input ->
                val buffer = ByteArray(8192)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    require(output.size() + count <= 16_000_000) { "Resource exceeds 16 MB" }
                    output.write(buffer, 0, count)
                }
            }
            val text = output.toString("UTF-8")
            return if (file == "journeys") JSONObject(text) else org.json.JSONArray(text)
        } finally { connection.disconnect() }
    }
}

object AppState {
    @Volatile private var instance: GuideRepository? = null
    fun repository(context: Context): GuideRepository = instance ?: synchronized(this) {
        instance ?: GuideRepository(context.applicationContext).also { instance = it }
    }
}
