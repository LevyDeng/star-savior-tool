package io.github.levydeng.starsavior

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class SharedContractTest {
    private fun fixture(name: String) = javaClass.classLoader!!.getResource(name)!!.readText()
    private fun event(raw: JSONObject): GuideEvent = GuideEvent(
        raw.getString("title"), raw.getString("phase"), raw.getString("source"),
        raw.getJSONArray("options").objects().map { Choice(it.getInt("order"), it.getString("text"), it.getString("effect")) },
        raw.optString("display_phase", ""), raw.optString("display_source", ""),
        if (raw.isNull("card_id")) null else raw.getLong("card_id"))
    private val vocabulary get() = JSONObject(File("../../shared/assets/vocabulary.json").readText())

    @Test fun matchesDesktopGoldenCases() {
        for (case in JSONArray(fixture("matching.json")).objects()) {
            val actual = GuideMatcher.match(case.getJSONArray("events").objects().map(::event),
                case.getJSONArray("title").values().map { it.toString() },
                case.getJSONArray("choices").values().map { it.toString() })
            val label = case.getString("name")
            assertEquals(label, case.getString("state"), actual.state)
            val expected = case.getJSONArray("candidates").objects()
            assertEquals(label, expected.size, actual.candidates.size)
            expected.zip(actual.candidates).forEach { (reference, candidate) ->
                assertEquals(label, reference.getString("phase"), candidate.event.phase)
                assertEquals(label, reference.getDouble("score"), candidate.score, 0.000001)
            }
        }
    }

    @Test fun convertsAllLanguagesAndDifficultiesLikeDesktop() {
        val fixture = JSONObject(fixture("conversion.json"))
        val converter = GuideConverter(vocabulary)
        for (language in GuideConverter.languages) for (difficulty in GuideConverter.difficulties.keys) {
            val expected = fixture.getJSONObject("expected").getJSONArray("$language/$difficulty").objects().map(::event)
            assertEquals("$language/$difficulty", expected, converter.convert(fixture.getJSONObject("raw"), language, difficulty))
        }
    }

    @Test fun difficultyOnlyScalesPotentialPoints() {
        val converter = GuideConverter(vocabulary)
        val raw = JSONObject(fixture("conversion.json")).getJSONObject("raw")
        val hard = converter.convert(raw, "en-US", "Hard").first().options.first().effect
        assertTrue(hard.contains("Potential Point +50"))
        assertTrue(hard.contains("Focus +20~+30"))
        assertTrue(hard.contains("Stamina -5"))
        assertTrue(hard.contains("Strength >=200"))
    }

    @Test fun invalidSnapshotAndReferencesAreRejected() {
        val converter = GuideConverter(vocabulary)
        val raw = JSONObject(fixture("conversion.json")).getJSONObject("raw")
        raw.put("journey_items", JSONArray())
        assertThrows(IllegalArgumentException::class.java) { converter.convert(raw, "en-US", "Normal") }
        raw.put("journey_items", JSONArray().put(JSONObject().put("id", 999).put("name", "Missing")))
        assertThrows(IllegalStateException::class.java) { converter.convert(raw, "en-US", "Normal") }
    }

    @Test fun liveSnapshotParityWhenAvailable() {
        val path = File("../../build/live-conversion.json")
        if (!path.exists()) return
        val fixture = JSONObject(path.readText())
        val converter = GuideConverter(vocabulary)
        for (language in GuideConverter.languages) for (difficulty in GuideConverter.difficulties.keys) {
            val expected = fixture.getJSONObject("expected").getJSONArray("$language/$difficulty").objects().map(::event)
            val actual = converter.convert(fixture.getJSONObject("raw"), language, difficulty)
            val key: (GuideEvent) -> String = { "${it.source}/${it.phase}/${it.title}" }
            assertEquals("Live event identities $language/$difficulty", expected.map(key).toSet(), actual.map(key).toSet())
            val indexed = actual.associateBy(key)
            for (event in expected) assertEquals("Live $language/$difficulty ${key(event)}", event, indexed[key(event)])
        }
    }
}
