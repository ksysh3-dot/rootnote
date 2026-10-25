package me.timschneeberger.rootlessjamesdsp.devmode

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.media.MicrophoneInfo

/**
 * What the phone declares about its built-in microphone (AudioManager.getMicrophones, no permission needed; the
 * vendor's microphone_characteristics data): the bottom microphone where the phone names one, else the first of
 * its group. [sensDbfs]: dB re full scale for 94 dB SPL at 1 kHz, null when undeclared. [responseHz]/[responseDb]:
 * its frequency response re 1 kHz, empty when undeclared.
 */
data class DeclaredMic(
    val address: String,
    val sensDbfs: Double?,
    val responseHz: DoubleArray,
    val responseDb: DoubleArray,
) {
    /** The declared response at [hz] (nearest point), or null. */
    fun responseAt(hz: Double): Double? =
        responseHz.indices.minByOrNull { kotlin.math.abs(responseHz[it] - hz) }?.let { responseDb[it] }

    companion object {
        fun read(context: Context): DeclaredMic? = try {
            val mics = context.getSystemService(AudioManager::class.java)?.microphones.orEmpty()
                .filter { it.type == AudioDeviceInfo.TYPE_BUILTIN_MIC }
            val m = mics.firstOrNull { it.address.contains("bottom", ignoreCase = true) } ?: mics.minByOrNull { it.indexInTheGroup }
            m?.let { mic ->
                val sens = mic.sensitivity.takeIf { it != MicrophoneInfo.SENSITIVITY_UNKNOWN }?.toDouble()
                val fr = mic.frequencyResponse
                DeclaredMic(mic.address ?: "", sens,
                    DoubleArray(fr.size) { fr[it].first.toDouble() }, DoubleArray(fr.size) { fr[it].second.toDouble() })
            }
        } catch (_: Exception) { null }
    }
}
