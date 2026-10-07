package io.github.levydeng.starsavior

import org.json.JSONArray
import org.json.JSONObject
import java.text.Normalizer
import java.util.Locale

data class Choice(val order: Int, val text: String, val effect: String)
data class GuideEvent(val title: String, val phase: String, val source: String,
                      val options: List<Choice>, val displayPhase: String,
                      val displaySource: String, val cardId: Long? = null)
data class Candidate(val event: GuideEvent, var score: Double,
                     val optionScores: List<Double>, val titleScore: Double)
data class MatchResult(val state: String, val candidates: List<Candidate>)

fun JSONArray.objects() = (0 until length()).map { getJSONObject(it) }
fun JSONArray.values() = (0 until length()).map { get(it) }

class Vocabulary(private val root: JSONObject, val language: String) {
    fun text(key: String, vararg values: Pair<String, Any>): String {
        var result = root.getJSONObject(language).optString(key, key)
        for ((name, value) in values) result = result.replace("{$name}", value.toString())
        return result
    }
}

object GuideMatcher {
    fun normalize(value: String): String = Normalizer.normalize(value, Normalizer.Form.NFKC)
        .lowercase(Locale.ROOT).replace(Regex("^\\s*\\d+\\s*[.、:)]\\s*"), "")
        .filter { c -> Character.getType(c) !in setOf(
            Character.CONNECTOR_PUNCTUATION.toInt(), Character.DASH_PUNCTUATION.toInt(),
            Character.START_PUNCTUATION.toInt(), Character.END_PUNCTUATION.toInt(),
            Character.INITIAL_QUOTE_PUNCTUATION.toInt(), Character.FINAL_QUOTE_PUNCTUATION.toInt(),
            Character.OTHER_PUNCTUATION.toInt(), Character.SPACE_SEPARATOR.toInt(),
            Character.LINE_SEPARATOR.toInt(), Character.PARAGRAPH_SEPARATOR.toInt(),
            Character.CONTROL.toInt(), Character.FORMAT.toInt(), Character.SURROGATE.toInt(),
            Character.PRIVATE_USE.toInt(), Character.UNASSIGNED.toInt()) }

    // Match Python SequenceMatcher's longest contiguous block recursion.
    fun ratio(a: String, b: String): Double {
        if (a.isEmpty() && b.isEmpty()) return 1.0
        fun blocks(a0: Int, a1: Int, b0: Int, b1: Int): Int {
            var best = 0; var ai = a0; var bi = b0
            var previous = IntArray(b.length + 1)
            for (i in a0 until a1) {
                val current = IntArray(b.length + 1)
                for (j in b0 until b1) if (a[i] == b[j]) {
                    current[j + 1] = previous[j] + 1
                    if (current[j + 1] > best) {
                        best = current[j + 1]; ai = i - best + 1; bi = j - best + 1
                    }
                }
                previous = current
            }
            if (best == 0) return 0
            return best + blocks(a0, ai, b0, bi) + blocks(ai + best, a1, bi + best, b1)
        }
        return 2.0 * blocks(0, a.length, 0, b.length) / (a.length + b.length)
    }

    fun match(events: List<GuideEvent>, title: List<String>, choices: List<String>): MatchResult {
        val titles = title.map(::normalize).filter { it.isNotEmpty() }
        val lines = choices.map(::normalize).filter { it.isNotEmpty() }
        val segments = titles.indices.flatMap { start ->
            (start + 1..minOf(start + 3, titles.size)).map { titles.subList(start, it).joinToString("") } }
        val scored = events.filter { it.options.isNotEmpty() }.map { event ->
            var cursor = 0
            val scores = event.options.map { option ->
                var best = 0.0; var endpoint = cursor
                for (start in cursor until lines.size) for (end in start + 1..minOf(start + 3, lines.size)) {
                    val score = ratio(normalize(option.text), lines.subList(start, end).joinToString(""))
                    if (score > best) { best = score; endpoint = end }
                }
                cursor = endpoint
                best
            }
            Candidate(event, scores.average(), scores,
                segments.maxOfOrNull { ratio(normalize(event.title), it) } ?: 0.0)
        }
        val titleMode = (scored.maxOfOrNull { it.titleScore } ?: 0.0) >= .88
        val candidates = scored.filter { if (titleMode) it.titleScore >= .75 || it.score >= .90 else it.score >= .55 }
            .onEach { if (titleMode) it.score = if (lines.isEmpty()) it.titleScore else .65 * it.titleScore + .35 * it.score }
            .sortedByDescending { it.score }.take(5)
        val top = candidates.firstOrNull() ?: return MatchResult("unknown", emptyList())
        val margin = if (candidates.size > 1) top.score - candidates[1].score else 1.0
        val full = top.optionScores.min() >= .90 && top.optionScores.average() >= .93
        val matched = if (titleMode) top.titleScore >= .94 && margin >= .10 && (lines.isEmpty() || full)
                      else full && top.event.options.size >= 2 && margin >= .10
        return MatchResult(if (matched) "matched" else "confirm", candidates)
    }
}

class GuideConverter(private val vocabulary: JSONObject) {
    companion object {
        val files = listOf("journeys", "arcanas", "journey_items", "potentials", "stat_potentials", "journey_buffs")
        val languages = listOf("zh-CN", "zh-TW", "en-US", "ja-JP", "ko-KR")
        val difficulties = linkedMapOf("Easy" to 1.0, "Normal" to 1.5, "Hard" to 2.5)
    }

    fun convert(raw: JSONObject, language: String, difficulty: String): List<GuideEvent> {
        require(language in languages && difficulty in difficulties)
        require(raw.keys().asSequence().toSet() == files.toSet()) { "Incomplete snapshot" }
        require(raw.getJSONObject("journeys").length() > 0) { "Empty journey data" }
        for (file in files.drop(1)) require(raw.getJSONArray(file).length() > 0) { "Empty reference data: $file" }
        val words = Vocabulary(vocabulary, language)
        fun localized(value: Any?, fallback: Boolean = false): String {
            fun clean(s: String) = s.replace(Regex("<[^>]+>"), "").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"")
                .replace("&#39;", "'").replace("&nbsp;", " ").trim()
            if (value is String) return clean(value)
            if (value !is JSONObject) return ""
            for (code in listOf(language, "en-US", "ko-KR").distinct()) {
                val text = clean(value.optString(code, ""))
                if (text.isNotEmpty()) return text + if (fallback && code != language) " [$code]" else ""
            }
            return ""
        }
        fun phase(value: Any): String {
            if (value !is String) return localized(value)
            val found = Regex("\\s*(\\d{1,2})월\\s*(초순|상순|중순|하순)\\s*").matchEntire(value) ?: return value
            val month = found.groupValues[1].toInt()
            if (month !in 1..12) return value
            val segment = when (found.groupValues[2]) { "중순" -> "mid"; "하순" -> "late"; else -> "early" }
            return words.text("phase_$segment", "month" to month)
        }
        val references = files.drop(2).associateWith { file -> raw.getJSONArray(file).objects().associateBy { it.getLong("id") } }
        val linked = mapOf("RT_JOURNEY_ITEM" to "journey_items", "RT_SE_POTEN" to "potentials",
                           "RT_STAT_POTEN" to "stat_potentials", "RT_JOURNEY_BUFF" to "journey_buffs")
        fun number(value: Double) = (if (value >= 0) "+" else "") +
            if (value % 1 == 0.0) value.toLong().toString() else value.toString()
        fun reward(entry: JSONObject): String {
            val type = entry.getString("type")
            var label = if (type in linked) {
                val reference = references.getValue(linked.getValue(type))[entry.getLong("reward_id")]
                    ?: error("Missing reward reference")
                val desc = localized(reference.opt("desc") ?: reference.opt("description"), true)
                localized(reference.get("name"), true) + if (desc.isNotEmpty()) " ($desc)" else ""
            } else if (type == "RT_STAT") words.text(entry.getString("reward_stat").removePrefix("JST_"))
            else words.text(type).also { require(it != type) { "Unsupported reward: $type" } }
            if (entry.has("min") && type != "RT_STAT_POTEN") {
                val multiplier = if (type == "RT_POTEN_POINT") difficulties.getValue(difficulty) else 1.0
                val low = entry.getDouble("min") * multiplier; val high = entry.getDouble("max") * multiplier
                label += " " + number(low) + if (low != high) "~" + number(high) else ""
            }
            return label
        }
        fun rewards(groups: JSONArray): String = groups.values().joinToString("; ") { group ->
            (group as JSONArray).objects().joinToString(words.text("or"), transform = ::reward)
        }.ifEmpty { words.text("none") }
        fun condition(entry: JSONObject): String {
            val type = entry.getString("type")
            val key = mapOf("RR_STAMINA_USE" to "RT_STAMINA", "RR_COIN_USE" to "RT_COIN", "RR_PP_USE" to "RT_POTEN_POINT")[type]
            val label = when {
                key != null -> words.text(key)
                type in listOf("RR_ITEM_USE", "RR_ITEM_CHECK") -> localized(references.getValue("journey_items")
                    .getValue(entry.get("target").toString().toLong()).get("name"))
                type == "RR_STAT" -> words.text(entry.getString("target").removePrefix("JST_"))
                else -> error("Unsupported condition: $type")
            }
            val operator = if (type in listOf("RR_STAT", "RR_ITEM_CHECK")) ">=" else "-"
            return "${words.text("condition")}: $label $operator${entry.opt("value") ?: ""}"
        }
        val result = mutableListOf<GuideEvent>()
        fun add(variants: List<JSONObject>, source: String, displaySource: String, card: Long? = null) {
            val groups = linkedMapOf<Pair<String, List<String>>, MutableList<JSONObject>>()
            for (variant in variants) {
                val tiers = variant.optJSONArray("difficulties")?.values()?.map { value ->
                    if (value is JSONObject) value.optString("en-US").ifEmpty { value.optString("ko-KR") } else value.toString()
                } ?: emptyList()
                require(tiers.all { it in difficulties }) { "Unsupported source difficulty" }
                if (tiers.isNotEmpty() && difficulty !in tiers) continue
                val names = variant.getJSONArray("choices").objects().map { localized(it.get("name")).ifEmpty { words.text("automatic") } }
                require(names.isNotEmpty()) { "Event has no choices" }
                groups.getOrPut(localized(variant.get("name")) to names) { mutableListOf() }.add(variant)
            }
            for ((identity, versions) in groups) {
                val (title, names) = identity
                val options = names.mapIndexed { index, name ->
                    val effects = versions.mapIndexed { versionIndex, version ->
                        val choice = version.getJSONArray("choices").getJSONObject(index)
                        val context = mutableListOf<String>()
                        if (versions.size > 1) context += words.text("variant", "number" to versionIndex + 1)
                        context += version.optJSONArray("times")?.values()?.map(::phase) ?: emptyList()
                        if ((version.optJSONArray("difficulties")?.length() ?: 0) > 0) context += words.text(difficulty)
                        context += version.optJSONArray("battle_names")?.values()?.map { localized(it) } ?: emptyList()
                        val lines = mutableListOf<String>()
                        if (context.isNotEmpty()) lines += "[${context.joinToString(" | ")}]"
                        choice.optJSONObject("condition")?.let { lines += condition(it) }
                        lines += words.text("success") + ": " + rewards(choice.getJSONArray("success_rewards"))
                        choice.optJSONArray("failure_rewards")?.takeIf { it.length() > 0 }?.let {
                            lines += words.text("failure") + ": " + rewards(it)
                        }
                        lines.joinToString("\n")
                    }
                    Choice(index + 1, name, effects.joinToString("\n\n"))
                }
                require(title.isNotBlank() && options.all { it.text.isNotBlank() && it.effect.isNotBlank() }) { "Incomplete event" }
                result += GuideEvent(title, versions.joinToString(" | ") { it.get("id").toString() }, source, options,
                    versions.flatMap { it.optJSONArray("times")?.values()?.map(::phase) ?: emptyList() }
                        .distinct().joinToString(" | "), displaySource, card)
            }
        }
        val journeys = raw.getJSONObject("journeys")
        for (key in journeys.keys()) {
            val variants = journeys.getJSONArray(key).objects()
            add(variants, "Website / Journey / ${variants.first().get("id")}", words.text("journey_source"))
        }
        for (card in raw.getJSONArray("arcanas").objects()) for (event in card.getJSONArray("events").objects()) {
            val name = localized(card.get("name"))
            add(listOf(event), "Website / Arcana / $name / ${card.get("id")}",
                words.text("arcana_source", "card" to name), card.getLong("id"))
        }
        require(result.map { Triple(it.source, it.phase, it.title) }.distinct().size == result.size) { "Duplicate event" }
        return result
    }
}
