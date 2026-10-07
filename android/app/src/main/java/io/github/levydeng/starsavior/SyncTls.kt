package io.github.levydeng.starsavior

import java.security.SecureRandom
import java.security.cert.X509Certificate
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.X509TrustManager

object SyncTls {
    // Only mutate this guide-sync connection, never the process-wide TLS defaults.
    @Suppress("CustomX509TrustManager", "TrustAllX509TrustManager", "BadHostnameVerifier")
    fun configure(connection: HttpsURLConnection, verifyTls: Boolean) {
        if (verifyTls) return
        val trust = object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) = Unit
            override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) = Unit
        }
        val context = SSLContext.getInstance("TLS")
        context.init(null, arrayOf(trust), SecureRandom())
        connection.sslSocketFactory = context.socketFactory
        connection.hostnameVerifier = javax.net.ssl.HostnameVerifier { _, _ -> true }
    }
}
