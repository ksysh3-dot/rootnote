import java.security.KeyStore
import java.util.Base64

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("kotlin-kapt")
    id("com.google.devtools.ksp") version AndroidConfig.kspVersion
    id("dev.rikka.tools.refine") version AndroidConfig.rikkaRefineVersion
    id("org.jetbrains.kotlin.plugin.serialization") version "2.1.0"
    // Compose compiler (Kotlin 2.x ships it as a Kotlin plugin, same version as Kotlin). Only the general build's
    // home screen uses Compose (src/general); see the dependencies below.
    id("org.jetbrains.kotlin.plugin.compose") version "2.1.0"
}

// General flavor signing: GENERAL_KEYSTORE_PATH (CI decodes the GENERAL_KEYSTORE_B64 secret into it) or, for a
// local build, GENERAL_KEYSTORE_B64 itself; plus GENERAL_KEYSTORE_PASSWORD, GENERAL_KEY_ALIAS, GENERAL_KEY_PASSWORD.
// Missing anything -> the general APK is signed with the debug key and is a test build only.
val generalKeystore: File? = run {
    val pass = System.getenv("GENERAL_KEYSTORE_PASSWORD")
    val alias = System.getenv("GENERAL_KEY_ALIAS")
    val keyPass = System.getenv("GENERAL_KEY_PASSWORD")
    if (pass.isNullOrEmpty() || alias.isNullOrEmpty() || keyPass.isNullOrEmpty()) return@run null
    val path = System.getenv("GENERAL_KEYSTORE_PATH")
    if (!path.isNullOrEmpty()) return@run file(path).takeIf { it.isFile }
    val b64 = System.getenv("GENERAL_KEYSTORE_B64")
    if (b64.isNullOrEmpty()) return@run null
    val out = layout.buildDirectory.file("general-signing/general.jks").get().asFile
    out.parentFile.mkdirs()
    out.writeBytes(Base64.getMimeDecoder().decode(b64))
    out
}
if (generalKeystore == null) logger.warn("PVB: no general signing key in the environment; general release = debug-signed test build")

// The passwords that actually open the general key. A PKCS12 store (as made by RELEASE_GENERAL.md) has a single
// password, so the keystore password is also tried for the key, and surrounding whitespace (for example a newline
// pasted into a secret) is ignored. Nothing that opens the key -> the build stops with a clear message.
val generalPasswords: Pair<String, String>? = generalKeystore?.let { store ->
    val alias = System.getenv("GENERAL_KEY_ALIAS").trim()
    val storeCandidates = listOf(System.getenv("GENERAL_KEYSTORE_PASSWORD")).flatMap { listOf(it, it.trim()) }.distinct()
    val keyCandidates = listOf(System.getenv("GENERAL_KEY_PASSWORD"), System.getenv("GENERAL_KEYSTORE_PASSWORD"))
        .flatMap { listOf(it, it.trim()) }.distinct()
    for (sp in storeCandidates) {
        val ks = try { KeyStore.getInstance(store, sp.toCharArray()) } catch (e: Exception) { continue }
        for (kp in keyCandidates) {
            val ok = try { ks.getKey(alias, kp.toCharArray()) != null } catch (e: Exception) { false }
            if (ok) {
                if (kp != System.getenv("GENERAL_KEY_PASSWORD")) {
                    logger.warn("PVB: GENERAL_KEY_PASSWORD does not open the key as given; using the password that does")
                    if (System.getenv("GITHUB_ACTIONS") == "true")
                        println("::warning title=General signing::GENERAL_KEY_PASSWORD does not open the key as given; a fallback password was used")
                } else if (System.getenv("GITHUB_ACTIONS") == "true") {
                    println("::notice title=General signing::GENERAL_KEY_PASSWORD opens the release key as given")
                }
                return@let sp to kp
            }
        }
    }
    throw GradleException("General signing key: no GENERAL_KEYSTORE_PASSWORD/GENERAL_KEY_PASSWORD combination opens " +
        "alias '$alias' in the keystore from GENERAL_KEYSTORE_*; check the four GENERAL_* secrets (RELEASE_GENERAL.md)")
}

android {

    // PVB: the Galaxy S26 Ultra is arm64 only; one ABI keeps CI builds short
    val SUPPORTED_ABIS = setOf("arm64-v8a")
    compileSdk = AndroidConfig.compileSdk
    project.setProperty("archivesBaseName", "PVB-S26U-v${AndroidConfig.versionName}")

    defaultConfig {
        targetSdk = AndroidConfig.targetSdk
        versionCode = AndroidConfig.versionCode
        versionName = AndroidConfig.versionName

        manifestPlaceholders["label"] = "RootlessJamesDSP"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        buildConfigField("String", "COMMIT_COUNT", "\"${getCommitCount()}\"")
        buildConfigField("String", "COMMIT_SHA", "\"${getGitSha()}\"")
        buildConfigField("String", "BUILD_TIME", "\"${getBuildTime()}\"")
        buildConfigField("boolean", "PREVIEW", "false")
        buildConfigField("boolean", "PLUGIN", "false")

        externalNativeBuild {
            cmake {
                arguments.addAll(listOf("-DANDROID_ARM_NEON=ON"))
                cFlags.add("-std=gnu11 -Wno-incompatible-pointer-types -Wno-implicit-int -Wno-implicit-function-declaration")
            }
        }

        ndk {
            abiFilters += SUPPORTED_ABIS
        }
    }

    // PVB: one fixed signing key for the personal s26u channel, so every CI build installs over the previous one.
    // It protects nothing; it only keeps the signature stable. Do not use it for anything distributed.
    // Only the s26u flavor uses it. The key file is not part of the public source: without app/pvb-signing.jks
    // the s26u flavor is signed with the debug key (a test build).
    val pvbKeystore = file("pvb-signing.jks")
    signingConfigs {
        if (pvbKeystore.isFile) {
            create("pvb") {
                storeFile = pvbKeystore
                storePassword = "pvb-s26u"
                keyAlias = "pvb"
                keyPassword = "pvb-s26u"
            }
        }
        // General flavor: the distribution key comes only from the environment (GitHub secrets decoded by CI,
        // see RELEASE_GENERAL.md). It is never stored in the repository.
        if (generalKeystore != null) {
            create("general") {
                storeFile = generalKeystore
                storePassword = generalPasswords!!.first
                keyAlias = System.getenv("GENERAL_KEY_ALIAS").trim()
                keyPassword = generalPasswords!!.second
            }
        }
    }

    buildTypes {
        getByName("debug") {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-${getCommitCount()}"
            manifestPlaceholders["crashlyticsCollectionEnabled"] = "false"
        }
        getByName("release") {
            manifestPlaceholders += mapOf("crashlyticsCollectionEnabled" to "false")

            //proguardFiles("proguard-android-optimize.txt", "proguard-rules.pro")
            isMinifyEnabled = false
            isShrinkResources = false
            // The signing key is chosen by the device flavor (s26u: repository key; general: environment key).
        }
        create("preview") {
            initWith(getByName("release"))
            buildConfigField("boolean", "PREVIEW", "true")

            val debugType = getByName("debug")
            versionNameSuffix = debugType.versionNameSuffix
            matchingFallbacks.add("release")
        }
    }

    flavorDimensions += "version"
    flavorDimensions += "dependencies"
    flavorDimensions += "device"
    productFlavors {
        // PVB: which phone/channel the build is for.
        create("s26u") {
            dimension = "device"
            // The personal Galaxy S26 Ultra channel: unchanged package, label, key, version and behaviour.
            applicationId = "kr.ksysh3.pvb.s26u"
            manifestPlaceholders["label"] = "PVB"
            resValue("string", "app_brand_name", "PVB")
            buildConfigField("boolean", "GENERAL_BUILD", "false")
            buildConfigField("boolean", "RESEARCH_UI", "true")
            buildConfigField("boolean", "RECORD_FEATURES", "true")
            buildConfigField("String", "UPSTREAM_VERSION", "\"${AndroidConfig.upstreamVersion}\"")
            signingConfig = if (pvbKeystore.isFile) signingConfigs.getByName("pvb")
                else signingConfigs.getByName("debug")  // public source without the personal key: test build only
        }
        create("general") {
            dimension = "device"
            // The general distribution build. Name and package come from AndroidConfig (one place each).
            applicationId = AndroidConfig.GENERAL_APPLICATION_ID
            versionName = AndroidConfig.generalVersionName
            versionCode = AndroidConfig.generalVersionCode
            manifestPlaceholders["label"] = "@string/app_brand_name"
            resValue("string", "app_brand_name", AndroidConfig.GENERAL_BRAND_NAME)
            buildConfigField("boolean", "GENERAL_BUILD", "true")
            buildConfigField("boolean", "RESEARCH_UI", "false")
            buildConfigField("boolean", "RECORD_FEATURES", "false")
            buildConfigField("String", "UPSTREAM_VERSION", "\"${AndroidConfig.upstreamVersion}\"")
            // English by default plus Korean; upstream translations of other languages are left out so the
            // UI does not mix languages.
            resourceConfigurations += listOf("en", "ko", "ko-rKR")
            signingConfig = if (generalKeystore != null) signingConfigs.getByName("general")
                else signingConfigs.getByName("debug")  // test builds only: CI names them -UNSIGNED-TEST
        }

        create("fdroid") {
            dimension = "dependencies"
            buildConfigField("boolean", "FOSS_ONLY", "true")
            android.defaultConfig.externalNativeBuild.cmake.arguments += "-DNO_CRASHLYTICS=1"
        }
        create("full") {
            dimension = "dependencies"
            buildConfigField("boolean", "FOSS_ONLY", "false")
        }

        create("rootless") {
            dimension = "version"

            // PVB: package name and label come from the device flavor (s26u / general), so the original
            // RootlessJamesDSP can stay installed
            AndroidConfig.minSdk = 29
            minSdk = AndroidConfig.minSdk
            buildConfigField("boolean", "ROOTLESS", "true")
            buildConfigField("boolean", "PLUGIN", "false")
        }
        create("root") {
            dimension = "version"

            manifestPlaceholders["label"] = "JamesDSP"
            applicationId = "james.dsp"
            AndroidConfig.minSdk = 26
            minSdk = AndroidConfig.minSdk
            buildConfigField("boolean", "ROOTLESS", "false")
            buildConfigField("boolean", "PLUGIN", "false")
        }
        create("plugin") {
            dimension = "version"

            AndroidConfig.minSdk = 26
            minSdk = AndroidConfig.minSdk
            buildConfigField("boolean", "ROOTLESS", "false")
            buildConfigField("boolean", "PLUGIN", "true")
        }
    }

    sourceSets {
        // Use different app icon for non-release builds
        getByName("debug").res.srcDirs("src/debug/res")
    }

    // Export multiple CPU architecture split apks
    splits {
        abi {
            isEnable = true
            reset()
            include(*SUPPORTED_ABIS.toTypedArray())
            isUniversalApk = true
        }
    }

    lint {
        abortOnError = false
        checkReleaseBuilds = false
        disable += "ObsoleteSdkInt"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
        compose = true
        // Disable unused features
        aidl = false
        renderScript = false
        shaders = false
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }
    namespace = "me.timschneeberger.rootlessjamesdsp"
}

// The general flavor is only built as rootless + F-Droid (no Firebase, no root/plugin packages).
androidComponents {
    beforeVariants { variant ->
        val flavors = variant.productFlavors.toMap()
        if (flavors["device"] == "general" && (flavors["version"] != "rootless" || flavors["dependencies"] != "fdroid"))
            variant.enable = false
    }
}

dependencies {
    // Kotlin extensions
    implementation("org.jetbrains.kotlin:kotlin-reflect:2.0.20")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.1")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.5.0")

    // AndroidX
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.lifecycle:lifecycle-livedata-ktx:2.8.7")
    implementation("androidx.constraintlayout:constraintlayout:2.2.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.navigation:navigation-fragment-ktx:2.8.4")
    implementation("androidx.navigation:navigation-ui-ktx:2.8.4")
    implementation("androidx.preference:preference-ktx:1.2.1")
    implementation("androidx.databinding:databinding-runtime:8.7.3")
    implementation("androidx.work:work-runtime-ktx:2.10.0")
    implementation("androidx.mediarouter:mediarouter:1.7.0")

    // Material
    implementation("com.google.android.material:material:1.9.0")

    // Jetpack Compose: the general build's home screen only (src/general/java/.../home). The s26u build gets just
    // the runtime, which the Compose compiler plugin requires on every variant's classpath; it has no Compose UI.
    val composeBom = platform("androidx.compose:compose-bom:2025.04.01")
    implementation(composeBom)
    implementation("androidx.compose.runtime:runtime")
    "generalImplementation"(composeBom)
    "generalImplementation"("androidx.compose.ui:ui")
    "generalImplementation"("androidx.compose.foundation:foundation")
    "generalImplementation"("androidx.compose.material3:material3")
    "generalImplementation"("androidx.compose.ui:ui-tooling-preview")
    "generalImplementation"("androidx.activity:activity-compose:1.9.3")

    // Dependency injection
    implementation("io.insert-koin:koin-android:3.3.3")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.7")

    // Firebase
    "fullImplementation"(platform("com.google.firebase:firebase-bom:33.7.0"))
    "fullImplementation"("com.google.firebase:firebase-analytics-ktx")
    "fullImplementation"("com.google.firebase:firebase-crashlytics-ktx")
    "fullImplementation"("com.google.firebase:firebase-crashlytics-ndk")

    // Web API client
    implementation("com.google.code.gson:gson:2.11.0")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.retrofit2:converter-scalars:2.9.0")

    // Logging
    implementation("com.jakewharton.timber:timber:5.0.1")
    implementation("com.github.bastienpaulfr:Treessence:1.0.0")

    // IO
    implementation("org.kamranzafar:jtar:2.3")
    implementation("com.squareup.okio:okio:3.6.0")

    // Room databases
    val roomVersion = "2.6.1"
    implementation("androidx.room:room-runtime:$roomVersion")
    ksp("androidx.room:room-compiler:$roomVersion")
    implementation("androidx.room:room-ktx:$roomVersion")

    // Script editor
    implementation(project(":codeview"))

    // Shizuku
    implementation("dev.rikka.shizuku:api:${AndroidConfig.shizukuVersion}")
    implementation("dev.rikka.shizuku:provider:${AndroidConfig.shizukuVersion}")

    // Used for backup file access
    implementation("com.github.tachiyomiorg:unifile:17bec43")

    // Root APIs
    "rootImplementation"("com.github.topjohnwu.libsu:core:5.0.4")

    // Hidden APIs
    implementation("dev.rikka.tools.refine:runtime:${AndroidConfig.rikkaRefineVersion}")
    implementation("org.lsposed.hiddenapibypass:hiddenapibypass:4.3")
    compileOnly(project(":hidden-api-refined"))
    implementation(project(":hidden-api-impl"))

    // Debug utilities
    debugImplementation("com.squareup.leakcanary:leakcanary-android:2.10")
    debugImplementation("com.plutolib:pluto:2.0.9")
    "previewImplementation"("com.plutolib:pluto-no-op:2.0.9")
    releaseImplementation("com.plutolib:pluto-no-op:2.0.9")
    debugImplementation("com.plutolib.plugins:bundle-core:2.0.9")
    "previewImplementation"("com.plutolib.plugins:bundle-core-no-op:2.0.9")
    releaseImplementation("com.plutolib.plugins:bundle-core-no-op:2.0.9")

    // Unit tests
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
}