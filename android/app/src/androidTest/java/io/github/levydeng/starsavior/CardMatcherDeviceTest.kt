package io.github.levydeng.starsavior

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CardMatcherDeviceTest {
    private fun image(name: String): Bitmap = InstrumentationRegistry.getInstrumentation().context.assets.open(name)
        .use { BitmapFactory.decodeStream(it)!! }

    @Test fun matchesRealTiltedCardAndRejectsBlankCrop() {
        val crop = image("card-scene.png")
        val references = mapOf(6100201L to image("card-6100201.webp"), 7104601L to image("card-7104601.webp"))
        val blank = Bitmap.createBitmap(crop.width, crop.height, Bitmap.Config.ARGB_8888)
        try {
            val ranked = CardMatcher.rank(crop, references)
            assertTrue(ranked.isNotEmpty())
            assertEquals(6100201L, ranked.first().cardId)
            assertTrue(ranked.first().inliers >= 16)
            val refs = references.keys.map { CardReference(it, "Card $it", "https://ss.esprcdn.dev/images/arcanas/illustration/$it.webp") }
            assertEquals("matched", CardCatalog.decide(ranked, emptyList(), refs).status)
            assertEquals(7104601L, CardMatcher.rank(references.getValue(7104601L), references).first().cardId)
            assertTrue(CardMatcher.rank(blank, references).isEmpty())
            val context = InstrumentationRegistry.getInstrumentation().targetContext
            val regions = Regions.forFrame(context, 2670, 1200)
            assertTrue(regions.containsKey("card"))
            assertTrue(regions.getValue("card").bottom >= 0.4f)
        } finally { crop.recycle(); blank.recycle(); references.values.forEach { it.recycle() } }
    }

    @Test fun downloadsAndReusesValidatedReference() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val directory = java.io.File(context.cacheDir, "card-reference-device-test").apply { mkdirs() }
        val card = CardReference(6100201L, "Reference", "https://ss.esprcdn.dev/images/arcanas/illustration/6100201.webp")
        val first = CardMatcher.reference(card, directory)
        first.recycle()
        val target = directory.listFiles()!!.single { it.name.endsWith(".webp") }
        val modified = target.lastModified()
        val second = CardMatcher.reference(card, directory)
        try { assertTrue(second.width >= 64); assertEquals(modified, target.lastModified()) }
        finally { second.recycle() }
    }
}
