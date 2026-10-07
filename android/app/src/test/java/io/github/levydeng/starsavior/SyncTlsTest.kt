package io.github.levydeng.starsavior

import java.net.URL
import javax.net.ssl.HttpsURLConnection
import org.junit.Assert.*
import org.junit.Test

class SyncTlsTest {
    @Test fun verificationOverrideIsExplicitAndConnectionScoped() {
        val factory = HttpsURLConnection.getDefaultSSLSocketFactory()
        val verifier = HttpsURLConnection.getDefaultHostnameVerifier()
        val normal = URL("https://example.com").openConnection() as HttpsURLConnection
        SyncTls.configure(normal, true)
        assertSame(factory, normal.sslSocketFactory)
        assertSame(verifier, normal.hostnameVerifier)
        val bypass = URL("https://example.com").openConnection() as HttpsURLConnection
        SyncTls.configure(bypass, false)
        assertNotSame(factory, bypass.sslSocketFactory)
        assertTrue(bypass.hostnameVerifier.verify("example.com", null))
        assertSame(factory, HttpsURLConnection.getDefaultSSLSocketFactory())
        assertSame(verifier, HttpsURLConnection.getDefaultHostnameVerifier())
        val later = URL("https://example.com").openConnection() as HttpsURLConnection
        assertSame(factory, later.sslSocketFactory)
        assertSame(verifier, later.hostnameVerifier)
    }
}
