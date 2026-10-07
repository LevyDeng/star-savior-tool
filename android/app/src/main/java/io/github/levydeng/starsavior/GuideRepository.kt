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
    private val cache = AtomicFile(File(context.filesDir, "guide.json"))
    val vocabulary = JSONObject(context.assets.open("vocabulary.json").bufferedReader().use { it.readText() })
    private val converter = GuideConverter(vocabulary)
    private var snapshot: JSONObject? = null
    private val converted = mutableMapOf<Pair<String, String>, List<GuideEvent>>()
    var updated: String = ""
        private set

    init {
        if (cache.baseFile.exists()) runCatching {
            val payload = cache.openRead().bufferedReader().use { JSONObject(it.readText()) }
            snapshot = payload.getJSONObject("data")
            updated = payload.getString("updated")
        }.onFailure { Log.e("GuideRepository", "Could not load cached snapshot", it) }
    }

    @Synchronized
    fun events(language: String, difficulty: String): List<GuideEvent> {
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
            updated = timestamp
        }
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
