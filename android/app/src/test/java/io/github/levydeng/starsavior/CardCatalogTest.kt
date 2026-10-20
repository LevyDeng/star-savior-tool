package io.github.levydeng.starsavior

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class CardCatalogTest {
    private fun reference(id: Long, name: String) = CardReference(id, name,
        "https://ss.esprcdn.dev/images/arcanas/illustration/$id.webp")

    @Test fun currentSourceLinksCardsWithoutLegacyData() {
        val raw = JSONObject(File("../../shared/fixtures/espr.json").readText())
        val original = raw.getJSONArray("events").getJSONObject(0)
        original.put("arcanas", JSONArray().put("Alpha"))
        val other = JSONObject(original.toString()).put("id", "999").put("arcanas", JSONArray().put("Beta"))
        raw.getJSONArray("events").put(other)
        val vocabulary = JSONObject(File("../../shared/assets/vocabulary.json").readText())
        val events = EsprData.convert(raw, "en-US", "Hard", vocabulary)
        val linked = CardCatalog.attach(events, raw, listOf(reference(1, "Alpha"), reference(2, "Beta")))
        assertEquals(listOf(1L, 2L), linked.map { it.cardId })
        assertTrue(linked.all { it.cardEvent })
        assertEquals(events.map { it.options }, linked.map { it.options })
        assertTrue(CardCatalog.attach(events, raw, emptyList()).all { it.cardId == null })
    }

    @Test fun rejectsUnexpectedImageOriginsAndDuplicateIds() {
        fun row(url: String) = JSONObject().put("id", 1).put("name", "Alpha").put("image_url", url)
        val valid = row(reference(1, "Alpha").imageUrl)
        assertEquals(1L, CardCatalog.espr(JSONArray().put(valid)).single().id)
        for (url in listOf("http://ss.esprcdn.dev/images/arcanas/illustration/1.webp",
            "https://example.com/1.webp", "https://ss.esprcdn.dev/images/arcanas/illustration/2.webp",
            reference(1, "Alpha").imageUrl + "?redirect=1")) {
            assertThrows(IllegalArgumentException::class.java) { CardCatalog.espr(JSONArray().put(row(url))) }
        }
        assertThrows(IllegalArgumentException::class.java) { CardCatalog.espr(JSONArray().put(valid).put(valid)) }
    }

    @Test fun imageWinnerMovesFirstAndRetainsManualAlternatives() {
        fun candidate(id: Long) = Candidate(GuideEvent("Shared event", "$id", "test",
            listOf(Choice(1, "Same choice", "Reward $id")), "", "Card $id", id), 1.0, listOf(1.0), 1.0)
        val refs = listOf(reference(1, "Alpha"), reference(2, "Beta"))
        val evidence = listOf(CardEvidence(2, 40, 0.4), CardEvidence(1, 15, 0.2))
        val decision = CardCatalog.decide(evidence, emptyList(), refs)
        assertEquals("matched", decision.status)
        assertEquals("Beta", decision.name)
        val original = MatchResult("confirm", listOf(candidate(1), candidate(2)))
        val selected = CardCatalog.select(original, decision)
        assertEquals(listOf(2L, 1L), selected.candidates.map { it.event.cardId })
        assertEquals("matched", selected.state)
        val unavailable = CardCatalog.decide(evidence, listOf(1), refs)
        assertEquals("unavailable", unavailable.status)
        assertEquals(original, CardCatalog.select(original, unavailable))
        assertEquals("uncertain", CardCatalog.decide(listOf(CardEvidence(1, 24, 0.3), CardEvidence(2, 20, 0.3)), emptyList(), refs).status)
        assertEquals("uncertain", CardCatalog.decide(emptyList(), emptyList(), refs).status)
    }
}
