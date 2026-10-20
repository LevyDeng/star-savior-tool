package io.github.levydeng.starsavior

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.AtomicFile
import org.opencv.android.OpenCVLoader
import org.opencv.android.Utils
import org.opencv.calib3d.Calib3d
import org.opencv.core.*
import org.opencv.features2d.DescriptorMatcher
import org.opencv.features2d.SIFT
import org.opencv.imgproc.Imgproc
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URI
import java.security.MessageDigest
import java.util.concurrent.Executors
import kotlin.math.roundToInt

object CardMatcher {
    private const val maxBytes = 4_000_000
    private const val maxPixels = 8_000_000L

    private fun decode(body: ByteArray): Bitmap {
        require(body.isNotEmpty() && body.size <= maxBytes) { "Invalid card image size" }
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(body, 0, body.size, bounds)
        require(minOf(bounds.outWidth, bounds.outHeight) >= 64 && bounds.outWidth.toLong() * bounds.outHeight <= maxPixels) {
            "Invalid card image dimensions"
        }
        return BitmapFactory.decodeByteArray(body, 0, body.size) ?: error("Could not decode card reference")
    }

    internal fun reference(card: CardReference, directory: File): Bitmap {
        val uri = URI(card.imageUrl)
        require(uri.scheme == "https" && uri.host in setOf("ss.esprcdn.dev", "star-savior-arcana-db.pages.dev") &&
            uri.port == -1 && uri.userInfo == null && uri.fragment == null) { "Unexpected card image origin" }
        directory.mkdirs()
        val hash = MessageDigest.getInstance("SHA-256").digest(card.imageUrl.toByteArray()).take(8).joinToString("") { "%02x".format(it) }
        val target = AtomicFile(File(directory, "${card.id}-$hash.webp"))
        if (target.baseFile.exists()) runCatching {
            require(target.baseFile.length() <= maxBytes)
            return decode(target.openRead().use { it.readBytes() })
        }
        val connection = URL(card.imageUrl).openConnection() as HttpURLConnection
        connection.connectTimeout = 8000; connection.readTimeout = 8000
        connection.instanceFollowRedirects = false
        connection.setRequestProperty("User-Agent", "Mozilla/5.0 (StarSaviorAndroid/0.2)")
        if (uri.host == "ss.esprcdn.dev") connection.setRequestProperty("Referer", "https://ss.espr.gg/")
        val body = try {
            check(connection.responseCode == 200) { "Card image HTTP ${connection.responseCode}" }
            val output = java.io.ByteArrayOutputStream()
            connection.inputStream.use { input ->
                val buffer = ByteArray(8192)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    require(output.size() + count <= maxBytes) { "Card image exceeds its size limit" }
                    output.write(buffer, 0, count)
                }
            }
            output.toByteArray()
        } finally { connection.disconnect() }
        val image = decode(body)
        try {
            val stream = target.startWrite()
            try { stream.write(body); target.finishWrite(stream) }
            catch (error: Exception) { target.failWrite(stream); throw error }
        } catch (error: Exception) { image.recycle(); throw error }
        return image
    }

    private class Features(val shape: Size, val points: MatOfKeyPoint, val descriptors: Mat) : AutoCloseable {
        override fun close() { points.release(); descriptors.release() }
    }

    private fun features(image: Bitmap, isReference: Boolean): Features {
        val rgba = Mat(); val gray = Mat(); val scaled = Mat(); val mask = Mat()
        val points = MatOfKeyPoint(); val descriptors = Mat()
        val sift = SIFT.create(1800, 3, 0.015, 10.0, 1.6)
        try {
            Utils.bitmapToMat(image, rgba)
            Imgproc.cvtColor(rgba, gray, Imgproc.COLOR_RGBA2GRAY)
            val scale = if (isReference) 438.0 / gray.rows() else minOf(3.0, 900.0 / maxOf(gray.rows(), gray.cols()))
            val size = Size(maxOf(1, (gray.cols() * scale).roundToInt()).toDouble(), maxOf(1, (gray.rows() * scale).roundToInt()).toDouble())
            Imgproc.resize(gray, scaled, size)
            sift.detectAndCompute(scaled, mask, points, descriptors)
            return Features(size, points, descriptors)
        } catch (error: Exception) { points.release(); descriptors.release(); throw error }
        finally { rgba.release(); gray.release(); scaled.release(); mask.release(); sift.clear() }
    }

    fun rank(crop: Bitmap, references: Map<Long, Bitmap>): List<CardEvidence> {
        check(OpenCVLoader.initLocal()) { "Could not initialize local card matching" }
        features(crop, false).use { target ->
            if (target.descriptors.empty() || target.descriptors.rows() < 2) return emptyList()
            return references.mapNotNull { (id, bitmap) -> features(bitmap, true).use { source ->
                if (source.descriptors.empty()) return@use null
                val pairs = mutableListOf<MatOfDMatch>()
                val matcher = DescriptorMatcher.create(DescriptorMatcher.BRUTEFORCE)
                try {
                    matcher.knnMatch(source.descriptors, target.descriptors, pairs, 2)
                    val good = pairs.mapNotNull { pair -> pair.toArray().let { if (it.size == 2 && it[0].distance < 0.75 * it[1].distance) it[0] else null } }
                    if (good.size < 8) return@use null
                    val sp = source.points.toArray(); val tp = target.points.toArray()
                    val sourcePoints = MatOfPoint2f(*good.map { sp[it.queryIdx].pt }.toTypedArray())
                    val targetPoints = MatOfPoint2f(*good.map { tp[it.trainIdx].pt }.toTypedArray())
                    val mask = Mat()
                    try {
                        val matrix = Calib3d.findHomography(sourcePoints, targetPoints, Calib3d.RANSAC, 4.0, mask)
                        try {
                            if (matrix.empty() || mask.empty()) return@use null
                            val inliers = good.indices.filter { mask.get(it, 0)[0] != 0.0 }
                            if (inliers.size < 12 || inliers.size.toDouble() / good.size < 0.5) return@use null
                            val original = sourcePoints.toArray()
                            val hullInput = MatOfPoint(*inliers.map { original[it] }.toTypedArray())
                            val hullIndices = MatOfInt(); val hull = MatOfPoint()
                            val corners = MatOfPoint2f(Point(0.0, 0.0), Point(source.shape.width, 0.0),
                                Point(source.shape.width, source.shape.height), Point(0.0, source.shape.height))
                            val projected = MatOfPoint2f(); val polygon = MatOfPoint()
                            try {
                                Imgproc.convexHull(hullInput, hullIndices)
                                val inputPoints = hullInput.toArray()
                                hull.fromArray(*hullIndices.toArray().map { inputPoints[it] }.toTypedArray())
                                val coverage = Imgproc.contourArea(hull) / source.shape.area()
                                if (coverage < 0.06) return@use null
                                Core.perspectiveTransform(corners, projected, matrix)
                                val pp = projected.toArray()
                                if (pp.any { !it.x.isFinite() || !it.y.isFinite() }) return@use null
                                polygon.fromArray(*pp)
                                if (!Imgproc.isContourConvex(polygon)) return@use null
                                val area = kotlin.math.abs(Imgproc.contourArea(polygon))
                                if (area < target.shape.area() * 0.08 || area > target.shape.area() * 1.5) return@use null
                                if (pp.any { it.x < -0.15 * target.shape.width || it.x > 1.15 * target.shape.width ||
                                    it.y < -0.15 * target.shape.height || it.y > 1.15 * target.shape.height }) return@use null
                                CardEvidence(id, inliers.size, coverage)
                            } finally { hullInput.release(); hullIndices.release(); hull.release(); corners.release(); projected.release(); polygon.release() }
                        } finally { matrix.release() }
                    } finally { sourcePoints.release(); targetPoints.release(); mask.release() }
                } finally { pairs.forEach { it.release() }; matcher.clear() }
            } }.sortedByDescending { it.inliers }
        }
    }

    fun resolve(crop: Bitmap, cards: List<CardReference>, context: Context): CardResolution {
        val references = mutableMapOf<Long, Bitmap>(); val failures = mutableListOf<Long>()
        val pool = Executors.newFixedThreadPool(2)
        try {
            val jobs = cards.associateWith { card -> pool.submit<Bitmap> { reference(card, File(context.filesDir, "card_images")) } }
            for ((card, job) in jobs) runCatching { references[card.id] = job.get() }.onFailure { failures.add(card.id) }
            if (failures.isNotEmpty()) return CardResolution("unavailable", failures = failures)
            return CardCatalog.decide(rank(crop, references), failures, cards)
        } finally { pool.shutdownNow(); references.values.forEach { it.recycle() } }
    }
}
