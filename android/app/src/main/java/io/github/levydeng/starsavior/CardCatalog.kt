package io.github.levydeng.starsavior

import org.json.JSONArray
import org.json.JSONObject
import java.net.URI
import java.net.URLEncoder

data class CardReference(val id: Long, val name: String, val imageUrl: String,
                         val eventIds: Set<String> = emptySet())
data class CardEvidence(val cardId: Long, val inliers: Int, val coverage: Double)
data class CardResolution(val status: String, val cardId: Long? = null, val name: String = "",
                          val evidence: List<CardEvidence> = emptyList(), val failures: List<Long> = emptyList())

object CardCatalog {
    fun espr(raw: JSONArray): List<CardReference> {
        val seen = mutableSetOf<Long>()
        return raw.objects().map { row ->
            val id = row.getLong("id")
            val name = row.getString("name").trim()
            val url = URI(row.getString("image_url"))
            require(id > 0 && seen.add(id) && name.isNotBlank()) { "Invalid card identity" }
            require(url.scheme == "https" && url.host == "ss.esprcdn.dev" && url.port == -1 &&
                url.userInfo == null && url.query == null && url.fragment == null &&
                url.path == "/images/arcanas/illustration/$id.webp") { "Unexpected card image origin" }
            CardReference(id, name, url.toASCIIString())
        }
    }

    fun legacy(raw: JSONArray?, language: String): List<CardReference> = raw?.objects()?.mapNotNull { card ->
        val names = card.optJSONObject("name") ?: return@mapNotNull null
        val korean = names.optString("ko-KR").trim()
        if (korean.isBlank()) return@mapNotNull null
        val filename = korean.replace(Regex("[\\\\/:*?\"<>|\\s]"), "")
        val name = listOf(language, "en-US", "ko-KR").firstNotNullOfOrNull { code ->
            names.optString(code).trim().takeIf { it.isNotEmpty() }
        } ?: return@mapNotNull null
        CardReference(card.getLong("id"), name,
            "https://star-savior-arcana-db.pages.dev/images/cards/" + URLEncoder.encode(filename, "UTF-8").replace("+", "%20") + ".webp",
            card.optJSONArray("events")?.objects()?.map { it.get("id").toString() }?.toSet() ?: emptySet())
    } ?: emptyList()

    fun attach(events: List<GuideEvent>, raw: JSONObject, catalog: List<CardReference>): List<GuideEvent> {
        val names = catalog.groupBy { GuideMatcher.normalize(it.name) }
        val eventCards = raw.getJSONArray("events").objects().associate { row ->
            val ids = row.getJSONArray("arcanas").values().flatMap { name ->
                names[GuideMatcher.normalize(name.toString())].orEmpty().map { it.id }
            }.distinct()
            val direct = catalog.filter { row.get("id").toString() in it.eventIds }.map { it.id }.distinct()
            row.get("id").toString() to (if (ids.size == 1) ids.single() else direct.singleOrNull())
        }
        return events.map { it.copy(cardId = eventCards[it.phase]) }
    }

    fun contenders(match: MatchResult): List<Candidate> {
        val top = match.candidates.firstOrNull() ?: return emptyList()
        return match.candidates.filter { top.score - it.score <= 0.15 }
    }

    fun select(match: MatchResult, resolution: CardResolution): MatchResult {
        if (resolution.status != "matched") return match
        val selected = match.candidates.filter { it.event.cardId == resolution.cardId }
        if (selected.isEmpty()) return match
        return MatchResult(if (selected.size == 1) "matched" else "confirm",
            selected + match.candidates.filter { it.event.cardId != resolution.cardId })
    }

    fun decide(evidence: List<CardEvidence>, failures: List<Long>, catalog: List<CardReference>): CardResolution {
        val ranked = evidence.sortedByDescending { it.inliers }
        if (failures.isNotEmpty()) return CardResolution("unavailable", evidence = ranked, failures = failures)
        val top = ranked.firstOrNull() ?: return CardResolution("uncertain")
        val second = ranked.getOrNull(1)?.inliers ?: 0
        if (top.inliers < maxOf(16.0, second + 8.0, second * 1.8)) return CardResolution("uncertain", evidence = ranked)
        val card = catalog.singleOrNull { it.id == top.cardId } ?: return CardResolution("unavailable")
        return CardResolution("matched", card.id, card.name, ranked)
    }
}
