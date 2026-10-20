package io.github.levydeng.starsavior

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class EsprDataTest {
    @Test fun preservesAlternativesAndOnlyScalesPotentialPoints() {
        val raw = JSONObject(javaClass.classLoader!!.getResource("espr.json")!!.readText())
        val vocabulary = JSONObject(java.io.File("../../shared/assets/vocabulary.json").readText())
        val event = EsprData.convert(raw, "en-US", "Hard", vocabulary).single()
        assertTrue(event.options[0].effect.contains("Strength >=500"))
        assertTrue(event.options[0].effect.contains("Focus +20"))
        assertTrue(event.options[0].effect.contains("Potential Point +50"))
        assertTrue(event.options[0].effect.contains("Stamina -5"))
        assertTrue(event.options[1].effect.contains("Vitality +20 / +30"))
        assertTrue(event.options[1].effect.contains("Protection +10 (A temporary bonus)"))
        assertTrue(event.options[1].effect.contains("Possible outcome 2"))
    }
}
