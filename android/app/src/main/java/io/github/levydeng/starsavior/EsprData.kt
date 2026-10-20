package io.github.levydeng.starsavior

import org.json.JSONArray
import org.json.JSONObject

object EsprData {
    val locales = mapOf("zh-CN" to "zh-CN", "zh-TW" to "zh-TW", "en-US" to "en", "ja-JP" to "ja", "ko-KR" to "ko")
    fun url(language: String) = "https://ss.espr.gg/${locales.getValue(language)}/database/journey-events"
    private fun text(value: Any?): String {
        if (value == null || value == JSONObject.NULL || value == "\$undefined") return ""
        require(value is String && !value.startsWith("$")) { "Unsupported ESPR text reference" }
        return value.trim()
    }

    fun convert(raw: JSONObject, language: String, difficulty: String, vocabulary: JSONObject): List<GuideEvent> {
        val words = Vocabulary(vocabulary, language)
        val multiplier = GuideConverter.difficulties.getValue(difficulty)
        val tier = GuideConverter.difficulties.keys.indexOf(difficulty)
        val entries = raw.getJSONArray("events").objects()
        require(entries.isNotEmpty() && raw.getJSONArray("tiers").length() == 3) { "Incomplete ESPR data" }
        val ids = mutableSetOf<String>()
        fun rewards(groups: JSONArray): String {
            val result = groups.objects().map { group ->
                val chips = group.getJSONArray("chips").objects()
                require(chips.isNotEmpty()) { "Empty ESPR reward group" }
                chips.joinToString(if (group.optBoolean("oneOf")) words.text("or") else "; ") { chip ->
                    val label = text(chip.get("label"))
                    require(label.isNotBlank()) { "Empty ESPR reward label" }
                    var amount = text(chip.opt("amount"))
                    if (Regex("potential\\s*points?|[\u6f5c\u6f5b][\u8d28\u8cea]|\u6f5c\u5728.*\u30dd\u30a4\u30f3\u30c8|\uc7a0\uc7ac\ub825", RegexOption.IGNORE_CASE).containsMatchIn(label)) {
                        amount = Regex("[+-]\\d+(?:\\.\\d+)?").replace(amount) { match ->
                            val value = match.value.toDouble() * multiplier
                            (if (value >= 0) "+" else "") + if (value == value.toLong().toDouble()) value.toLong().toString() else value.toString()
                        }
                    }
                    val note = text(chip.opt("note"))
                    label + (if (amount.isBlank()) "" else " $amount") + (if (note.isBlank()) "" else " ($note)")
                }
            }
            return result.joinToString("; ").ifEmpty { words.text("none") }
        }
        return entries.map { entry ->
            val id = entry.getString("id")
            require(ids.add(id) && id.isNotBlank()) { "Duplicate ESPR identity" }
            val title = text(entry.get("title"))
            val choices = entry.getJSONArray("choices").objects()
            require(title.isNotBlank() && choices.isNotEmpty()) { "Empty ESPR event" }
            val cards = entry.getJSONArray("arcanas").values().map(::text)
            val options = choices.mapIndexed { index, choice ->
                val effects = mutableListOf<String>()
                choice.optJSONObject("gate")?.let { gate ->
                    val counts = gate.optJSONArray("counts")
                    require(counts == null || counts.length() == 3) { "Unexpected ESPR difficulty gates" }
                    val count = counts?.get(tier) ?: gate.get("count")
                    val consumed = gate.getString("kind") != "stat" && gate.opt("consumed") != false
                    effects.add(words.text("condition") + ": " + text(gate.get("name")) + (if (consumed) " -" else " >=") + count)
                    if (gate.opt("convertPP") is Number) effects.add(words.text("item_pp_value") + ": ${gate.get("convertPP")}")
                }
                val alternatives = choice.optJSONArray("variants")?.objects()?.takeIf { it.isNotEmpty() } ?: listOf(choice)
                alternatives.forEachIndexed { variantIndex, variant ->
                    val lines = mutableListOf<String>()
                    if (alternatives.size > 1) lines.add("[" + words.text("possible_result", "number" to variantIndex + 1) + "]")
                    lines.add(words.text("success") + ": " + rewards(variant.getJSONArray("success")))
                    variant.optJSONArray("failure")?.takeIf { it.length() > 0 }?.let { lines.add(words.text("failure") + ": " + rewards(it)) }
                    effects.add(lines.joinToString("\n"))
                }
                Choice(index + 1, text(choice.opt("label")).ifBlank { words.text("automatic") }, effects.joinToString("\n\n"))
            }
            val source = if (cards.isEmpty()) words.text("journey_source") else words.text("arcana_source", "card" to cards.joinToString(" / "))
            GuideEvent(title, id, "ESPR.gg / Journey / $id", options, "", "ESPR.gg / $source")
        }
    }
}
