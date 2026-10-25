/*
 * Parts of this file are adapted from scrcpy (https://github.com/Genymobile/scrcpy), Copyright (C) 2018 Genymobile,
 * Copyright (C) 2018-2026 Romain Vimont, Licensed under the Apache License, Version 2.0
 * (server/.../audio/AudioPlaybackCapture.java, FakeContext.java, Workarounds.java). Modified for Rootnote.
 */
package me.timschneeberger.rootlessjamesdsp.capture

import android.annotation.SuppressLint
import android.app.Application
import android.app.Instrumentation
import android.content.AttributionSource
import android.content.Context
import android.content.ContextWrapper
import android.content.pm.ApplicationInfo
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.os.Build
import android.os.Looper
import android.os.Process
import java.io.FileDescriptor
import java.io.FileOutputStream

/**
 * "가로채기 캡처": runs as the shell user (started through Shizuku with app_process, like scrcpy's server), registers a
 * dynamic audio policy whose loopback mix takes the players of [USAGES] away from the device output, and writes what
 * it captures to stdout as 16-bit stereo PCM at the asked rate. The excluded UIDs (Rootnote itself, the user's
 * excluded apps) keep playing normally. Lines on stderr: "READY" once recording, or "ERROR ...".
 *
 * The policy belongs to this process: when it ends for any reason the system removes it and the audio goes back to
 * the speaker. It ends when stdin closes (the app closed it or died) or the capture fails.
 *
 * Arguments: sample rate, comma-separated excluded UIDs.
 */
object InterceptServer {
    /** The same usages the MediaProjection capture takes. */
    val USAGES = intArrayOf(AudioAttributes.USAGE_MEDIA, AudioAttributes.USAGE_GAME, AudioAttributes.USAGE_UNKNOWN)
    const val READY = "READY"

    @JvmStatic
    fun main(args: Array<String>) {
        val rate = args.getOrNull(0)?.toIntOrNull() ?: 48000
        val excluded = args.getOrNull(1)?.split(',')?.mapNotNull { it.trim().toIntOrNull() }.orEmpty()
        val err = System.err
        try {
            if (Build.VERSION.SDK_INT < 33) throw IllegalStateException("Android 13 or later needed")
            prepareMainLooper()
            ShellRuntime.apply()
            val rec = createRecord(rate, excluded)
            rec.startRecording()
            err.println(READY); err.flush()
            // the app closes stdin to stop us (or dies, which closes it too)
            Thread({
                try { while (System.`in`.read() >= 0) { /* nothing is sent */ } } catch (_: Throwable) {}
                Runtime.getRuntime().halt(0)
            }, "intercept-stdin").apply { isDaemon = true }.start()
            val out = FileOutputStream(FileDescriptor.out)
            val buf = ByteArray(rate / 100 * 4)        // 10 ms of 16-bit stereo
            while (true) {
                val n = rec.read(buf, 0, buf.size, AudioRecord.READ_BLOCKING)
                if (n < 0) { err.println("ERROR read $n"); err.flush(); break }
                if (n > 0) out.write(buf, 0, n)
            }
        } catch (t: Throwable) {
            err.println("ERROR ${t.javaClass.simpleName}: ${t.message ?: t.cause?.message ?: ""}"); err.flush()
        }
        Runtime.getRuntime().halt(1)
    }

    @SuppressLint("PrivateApi", "DiscouragedPrivateApi", "BlockedPrivateApi")
    private fun createRecord(rate: Int, excluded: List<Int>): AudioRecord {
        val ruleClass = Class.forName("android.media.audiopolicy.AudioMixingRule")
        val ruleBuilderClass = Class.forName("android.media.audiopolicy.AudioMixingRule\$Builder")
        val ruleBuilder = ruleBuilderClass.getConstructor().newInstance()
        ruleBuilderClass.getMethod("setTargetMixRole", Int::class.javaPrimitiveType)
            .invoke(ruleBuilder, ruleClass.getField("MIX_ROLE_PLAYERS").getInt(null))
        val addRule = ruleBuilderClass.getMethod("addMixRule", Int::class.javaPrimitiveType, Any::class.java)
        val matchUsage = ruleClass.getField("RULE_MATCH_ATTRIBUTE_USAGE").getInt(null)
        for (u in USAGES) addRule.invoke(ruleBuilder, matchUsage, AudioAttributes.Builder().setUsage(u).build())
        // as AudioPlaybackCaptureConfiguration.excludeUid does: excludeMixRule(RULE_MATCH_UID, uid). addMixRule refuses
        // the combined RULE_EXCLUDE_UID value ("Illegal rule value 32772", seen on a Galaxy S26 Ultra).
        val matchUid = ruleClass.getField("RULE_MATCH_UID").getInt(null)
        val excludeMixRule = ruleBuilderClass.getMethod("excludeMixRule", Int::class.javaPrimitiveType, Any::class.java)
        for (uid in excluded) excludeMixRule.invoke(ruleBuilder, matchUid, Integer.valueOf(uid))
        val rule = ruleBuilderClass.getMethod("build").invoke(ruleBuilder)

        val format = AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(rate)
            .setChannelMask(AudioFormat.CHANNEL_IN_STEREO).build()
        val mixClass = Class.forName("android.media.audiopolicy.AudioMix")
        val mixBuilderClass = Class.forName("android.media.audiopolicy.AudioMix\$Builder")
        val mixBuilder = mixBuilderClass.getConstructor(ruleClass).newInstance(rule)
        mixBuilderClass.getMethod("setFormat", AudioFormat::class.java).invoke(mixBuilder, format)
        // LOOP_BACK (not LOOP_BACK_RENDER): the players stop playing on the device; Rootnote plays them processed
        mixBuilderClass.getMethod("setRouteFlags", Int::class.javaPrimitiveType)
            .invoke(mixBuilder, mixClass.getField("ROUTE_FLAG_LOOP_BACK").getInt(null))
        val mix = mixBuilderClass.getMethod("build").invoke(mixBuilder)

        val policyClass = Class.forName("android.media.audiopolicy.AudioPolicy")
        val policyBuilderClass = Class.forName("android.media.audiopolicy.AudioPolicy\$Builder")
        val policyBuilder = policyBuilderClass.getConstructor(Context::class.java).newInstance(ShellContext.get())
        policyBuilderClass.getMethod("addMix", mixClass).invoke(policyBuilder, mix)
        val policy = policyBuilderClass.getMethod("build").invoke(policyBuilder)
        val register = AudioManager::class.java.getDeclaredMethod("registerAudioPolicyStatic", policyClass)
        register.isAccessible = true
        val result = register.invoke(null, policy) as Int
        if (result != 0) throw IllegalStateException("registerAudioPolicy returned $result")
        return policyClass.getMethod("createAudioRecordSink", mixClass).invoke(policy, mix) as AudioRecord
    }

    /** Looper.prepareMainLooper(), but allowed to quit (as scrcpy does). */
    private fun prepareMainLooper() {
        Looper.prepare()
        synchronized(Looper::class.java) {
            val f = Looper::class.java.getDeclaredField("sMainLooper")
            f.isAccessible = true
            f.set(null, Looper.myLooper())
        }
    }
}

/** An ActivityThread for this bare process, so system services and a system context exist (scrcpy's Workarounds). */
@SuppressLint("PrivateApi", "DiscouragedPrivateApi", "SoonBlockedPrivateApi")
internal object ShellRuntime {
    private val atClass: Class<*> = Class.forName("android.app.ActivityThread")
    val activityThread: Any = atClass.getDeclaredConstructor().apply { isAccessible = true }.newInstance().also { at ->
        atClass.getDeclaredField("sCurrentActivityThread").apply { isAccessible = true }.set(null, at)
        atClass.getDeclaredField("mSystemThread").apply { isAccessible = true }.setBoolean(at, true)
    }

    fun apply() {
        if (Build.VERSION.SDK_INT >= 31) try {
            val ccClass = Class.forName("android.app.ConfigurationController")
            val atiClass = Class.forName("android.app.ActivityThreadInternal")
            val cc = ccClass.getDeclaredConstructor(atiClass).apply { isAccessible = true }.newInstance(activityThread)
            atClass.getDeclaredField("mConfigurationController").apply { isAccessible = true }.set(activityThread, cc)
        } catch (_: Throwable) {}
        try {
            val bindClass = Class.forName("android.app.ActivityThread\$AppBindData")
            val bind = bindClass.getDeclaredConstructor().apply { isAccessible = true }.newInstance()
            bindClass.getDeclaredField("appInfo").apply { isAccessible = true }
                .set(bind, ApplicationInfo().apply { packageName = ShellContext.PACKAGE })
            atClass.getDeclaredField("mBoundApplication").apply { isAccessible = true }.set(activityThread, bind)
        } catch (_: Throwable) {}
        try {
            val app = Instrumentation.newApplication(Application::class.java, ShellContext.get())
            atClass.getDeclaredField("mInitialApplication").apply { isAccessible = true }.set(activityThread, app)
        } catch (_: Throwable) {}
    }

    fun systemContext(): Context? = try {
        atClass.getDeclaredMethod("getSystemContext").invoke(activityThread) as Context
    } catch (_: Throwable) { null }
}

/** A context that says it is the shell package (scrcpy's FakeContext, reduced to what the audio policy needs). */
internal class ShellContext private constructor(base: Context?) : ContextWrapper(base) {
    override fun getPackageName(): String = PACKAGE
    override fun getOpPackageName(): String = PACKAGE
    override fun getApplicationContext(): Context = this
    override fun createPackageContext(packageName: String, flags: Int): Context = this

    @SuppressLint("NewApi")
    override fun getAttributionSource(): AttributionSource =
        AttributionSource.Builder(Process.SHELL_UID).setPackageName(PACKAGE).build()

    companion object {
        const val PACKAGE = "com.android.shell"
        private val instance by lazy { ShellContext(ShellRuntime.systemContext()) }
        fun get(): ShellContext = instance
    }
}
