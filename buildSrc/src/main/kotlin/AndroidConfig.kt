object AndroidConfig {
    var minSdk = 29

    const val compileSdk = 35
    const val targetSdk = 34

    // s26u build (personal S26 Ultra channel)
    const val versionName = "1.6.23-alpha3.3"
    const val versionCode = 61

    // General distribution build (flavor "general"). The brand name and package name are set only here:
    // renaming the app is a change to GENERAL_BRAND_NAME (and, for a new package, GENERAL_APPLICATION_ID).
    const val GENERAL_BRAND_NAME = "Rootnote"
    const val GENERAL_APPLICATION_ID = "kr.ksysh3.rootnote"
    // Own version scheme, independent of upstream 1.6.x and of the s26u alphas.
    const val generalVersionName = "0.9.0-beta.2"
    const val generalVersionCode = 1001
    // Upstream version this fork is based on (shown in the About screen).
    const val upstreamVersion = "1.6.14"

    const val kotlinVersion = "2.1.0"
    const val kspVersion = "2.1.0-1.0.29"
    const val shizukuVersion = "12.2.0"
    const val rikkaRefineVersion = "4.3.0"
}
