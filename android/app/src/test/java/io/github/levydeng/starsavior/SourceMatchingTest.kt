package io.github.levydeng.starsavior

import org.junit.Assert.*
import org.junit.Test

class SourceMatchingTest {
    private val event = GuideEvent("Beach tournament", "", "", listOf(Choice(1, "Attack", "Focus +20")), "", "")

    @Test fun preservesPriorityAndFallsBackInEitherDirection() {
        for (provider in listOf("espr", "arcana")) {
            val other = if (provider == "espr") "arcana" else "espr"
            val primary = event.copy(title = "Beach tournament!")
            val first = GuideMatcher.matchSources(provider, listOf(primary), listOf(event), listOf(event.title), emptyList())
            assertEquals(provider, first.first)
            assertEquals(primary, first.second.candidates.first().event)
            val fallback = GuideMatcher.matchSources(provider, emptyList(), listOf(event), listOf(event.title), emptyList())
            assertEquals(other, fallback.first)
            assertEquals(event, fallback.second.candidates.first().event)
            val unknown = GuideMatcher.matchSources(provider, listOf(event), listOf(event), listOf("zzzzzzzz"), emptyList())
            assertTrue(unknown.second.candidates.isEmpty())
        }
    }
}
