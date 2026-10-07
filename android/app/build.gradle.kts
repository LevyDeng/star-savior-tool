plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
android {
    val persistentSigningKey = rootProject.file("../.signing/android-debug.keystore")
    check(persistentSigningKey.isFile) {
        "Restore .signing/android-debug.keystore or run build-android.ps1 to preserve the existing project key. See android/README.md."
    }
    signingConfigs {
        getByName("debug") {
            storeFile = persistentSigningKey
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }
    namespace = "io.github.levydeng.starsavior"
    compileSdk = 34
    buildToolsVersion = "34.0.0"
    defaultConfig {
        applicationId = "io.github.levydeng.starsavior"
        minSdk = 26
        targetSdk = 34
        versionCode = 2
        versionName = "0.2.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    sourceSets {
        getByName("main").assets.srcDir("../../shared/assets")
        getByName("test").resources.srcDir("../../shared/fixtures")
    }
    testOptions { unitTests.isReturnDefaultValues = true }
}
dependencies {
    implementation("com.google.mlkit:text-recognition:16.0.1")
    implementation("com.google.mlkit:text-recognition-chinese:16.0.1")
    implementation("com.google.mlkit:text-recognition-japanese:16.0.1")
    implementation("com.google.mlkit:text-recognition-korean:16.0.1")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
