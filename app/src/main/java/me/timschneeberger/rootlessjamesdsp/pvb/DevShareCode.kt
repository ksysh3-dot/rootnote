package me.timschneeberger.rootlessjamesdsp.pvb

/**
 * Developer-mode share code ("공유 코드"), format RN1:
 *
 *     RN1-<model>-<app version>-<data group>...-<tail group>
 *
 * - model and app version are readable (they may contain "-"); characters outside [A-Za-z0-9._+] become "_", each is
 *   at most [MAX_META] characters.
 * - data: bytes in Crockford base32 (0-9, A-Z without I L O U), groups of 4 characters. Byte 0 is the value-set
 *   version ([SET_VERSION]); then a bitmap of [DevParams.ALL] (bit i = value i differs from its default; for a switch
 *   the bit is its value); then one byte per moved slider, the step index on its grid ([DevSpec.indexOf]). Values at
 *   their default are not stored: a code from a phone with other defaults (high-pass, strength) keeps the reader's.
 * - tail: 4 characters, 20 bits: the number of data groups (4 bits) and a CRC-16/CCITT-FALSE (16 bits) over the UTF-8
 *   text "RN1-<model>-<version>-<data groups>".
 *
 * Decoding never throws: wrong prefix, unknown format or value-set version, bad characters, length or checksum give a
 * [Result.Error]; an index beyond a value's range is clamped (the slider ranges may shrink in a later version).
 */
object DevShareCode {
    const val PREFIX = "RN1"
    const val SET_VERSION = 1
    const val MAX_META = 24
    private const val ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

    sealed class Result {
        data class Ok(val model: String, val appVersion: String, val values: FloatArray, val moved: Int) : Result() {
            override fun equals(other: Any?): Boolean = other is Ok && model == other.model &&
                appVersion == other.appVersion && values.contentEquals(other.values) && moved == other.moved
            override fun hashCode(): Int = (model.hashCode() * 31 + appVersion.hashCode()) * 31 + values.contentHashCode()
        }
        data class Error(val reason: Reason) : Result()
    }

    enum class Reason { EMPTY, NOT_A_CODE, UNKNOWN_VERSION, BAD_CHARACTERS, BAD_LENGTH, CHECKSUM, TOO_LONG }

    fun cleanMeta(s: String): String {
        val t = s.trim().map { if (it.isLetterOrDigit() && it.code < 128 || it in "._+-") it else '_' }.joinToString("")
        return t.take(MAX_META).ifEmpty { "_" }
    }

    /** The code for [values] ([DevParams.ALL] order) against [defaults] (same order). */
    fun encode(model: String, appVersion: String, values: FloatArray, defaults: FloatArray): String {
        val specs = DevParams.ALL
        require(values.size == specs.size && defaults.size == specs.size) { "expected ${specs.size} values" }
        val bitmapBytes = (specs.size + 7) / 8
        val bytes = ArrayList<Int>()
        bytes += SET_VERSION
        val bitmap = IntArray(bitmapBytes)
        val payload = ArrayList<Int>()
        specs.forEachIndexed { i, spec ->
            val idx = spec.indexOf(values[i])
            if (spec.isSwitch) {
                if (idx == 1) bitmap[i / 8] = bitmap[i / 8] or (1 shl (i % 8))
            } else if (idx != spec.indexOf(defaults[i])) {
                bitmap[i / 8] = bitmap[i / 8] or (1 shl (i % 8))
                payload += idx
            }
        }
        bitmap.forEach { bytes += it }
        bytes += payload
        val groups = base32(bytes).chunked(4)
        val head = "$PREFIX-${cleanMeta(model)}-${cleanMeta(appVersion)}-" + groups.joinToString("-")
        val crc = crc16(head.toByteArray(Charsets.UTF_8))
        val tail = (groups.size.coerceAtMost(15) shl 16) or crc
        return "$head-" + base32Bits(tail.toLong(), 20)
    }

    /** Decodes [text] (spaces and line breaks are ignored, case-insensitive), with [defaults] for values not stored. */
    fun decode(text: String, defaults: FloatArray): Result {
        val specs = DevParams.ALL
        if (defaults.size != specs.size) return Result.Error(Reason.BAD_LENGTH)
        val code = text.filterNot { it.isWhitespace() }
        if (code.isEmpty()) return Result.Error(Reason.EMPTY)
        if (code.length > 200) return Result.Error(Reason.TOO_LONG)
        val parts = code.split('-')
        if (parts.size < 5 || !parts[0].startsWith("RN", ignoreCase = true)) return Result.Error(Reason.NOT_A_CODE)
        if (!parts[0].equals(PREFIX, ignoreCase = true)) return Result.Error(Reason.UNKNOWN_VERSION)
        val tailBits = decodeBits(parts.last(), 20) ?: return Result.Error(Reason.BAD_CHARACTERS)
        val nGroups = (tailBits shr 16).toInt()
        val crc = (tailBits and 0xFFFF).toInt()
        // RN1, model (>= 1 part), version (>= 1 part), data groups, tail
        if (nGroups < 1 || parts.size < 1 + 2 + nGroups + 1) return Result.Error(Reason.BAD_LENGTH)
        // data as canonical characters (lower case, O -> 0, I/L -> 1); a character outside the alphabet stays and fails
        val dataParts = parts.subList(parts.size - 1 - nGroups, parts.size - 1)
            .map { g -> g.map { c -> digit(c)?.let { ALPHABET[it] } ?: c }.joinToString("") }
        val meta = parts.subList(1, parts.size - 1 - nGroups)
        val head = (listOf(PREFIX) + meta + dataParts).joinToString("-")
        // the checksum covers the text as written (model and version keep their case)
        if (crc16(head.toByteArray(Charsets.UTF_8)) != crc) return Result.Error(Reason.CHECKSUM)
        if (dataParts.any { it.length != 4 }) return Result.Error(Reason.BAD_LENGTH)
        val bytes = unbase32(dataParts.joinToString("")) ?: return Result.Error(Reason.BAD_CHARACTERS)
        val bitmapBytes = (specs.size + 7) / 8
        if (bytes.size < 1 + bitmapBytes) return Result.Error(Reason.BAD_LENGTH)
        if (bytes[0] != SET_VERSION) return Result.Error(Reason.UNKNOWN_VERSION)
        val values = defaults.copyOf()
        var p = 1 + bitmapBytes
        var moved = 0
        specs.forEachIndexed { i, spec ->
            val bit = (bytes[1 + i / 8] shr (i % 8)) and 1 == 1
            if (spec.isSwitch) {
                values[i] = if (bit) 1f else 0f
                if (spec.indexOf(values[i]) != spec.indexOf(defaults[i])) moved++
            } else if (bit) {
                if (p >= bytes.size) return Result.Error(Reason.BAD_LENGTH)
                values[i] = spec.valueAt(bytes[p++])   // clamped to the range
                moved++
            }
        }
        // only zero padding may follow (base32 rounds up to whole characters and groups)
        if ((p until bytes.size).any { bytes[it] != 0 }) return Result.Error(Reason.BAD_LENGTH)
        // a model / version split for display: the version is the first part that starts with "digit." (else last)
        val split = meta.indexOfFirst { Regex("^[0-9]+\\.").containsMatchIn(it) }.let { if (it <= 0) meta.size - 1 else it }
        val model = meta.subList(0, split).joinToString("-").ifEmpty { meta.first() }
        val version = meta.subList(split, meta.size).joinToString("-")
        return Result.Ok(model, version, values, moved)
    }

    // ------------------------------------------------------------------------------------------------ helpers
    private fun base32(bytes: List<Int>): String {
        val sb = StringBuilder()
        var buffer = 0
        var bits = 0
        for (b in bytes) {
            buffer = (buffer shl 8) or (b and 0xFF)
            bits += 8
            while (bits >= 5) {
                sb.append(ALPHABET[(buffer shr (bits - 5)) and 31])
                bits -= 5
            }
            buffer = buffer and ((1 shl bits) - 1)
        }
        if (bits > 0) sb.append(ALPHABET[(buffer shl (5 - bits)) and 31])
        while (sb.length % 4 != 0) sb.append('0')
        return sb.toString()
    }

    private fun unbase32(s: String): List<Int>? {
        val out = ArrayList<Int>()
        var buffer = 0
        var bits = 0
        for (c in s) {
            val v = digit(c) ?: return null
            buffer = (buffer shl 5) or v
            bits += 5
            if (bits >= 8) {
                out += (buffer shr (bits - 8)) and 0xFF
                bits -= 8
                buffer = buffer and ((1 shl bits) - 1)
            }
        }
        return out
    }

    private fun digit(c: Char): Int? = when (val u = c.uppercaseChar()) {
        'O' -> 0
        'I', 'L' -> 1
        else -> ALPHABET.indexOf(u).takeIf { it >= 0 }
    }

    private fun base32Bits(v: Long, bits: Int): String {
        val n = (bits + 4) / 5
        return (n - 1 downTo 0).map { ALPHABET[((v shr (5 * it)) and 31).toInt()] }.joinToString("")
    }

    private fun decodeBits(s: String, bits: Int): Long? {
        if (s.length != (bits + 4) / 5) return null
        var v = 0L
        for (c in s) v = (v shl 5) or (digit(c) ?: return null).toLong()
        return v
    }

    /** CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF). */
    fun crc16(data: ByteArray): Int {
        var crc = 0xFFFF
        for (b in data) {
            crc = crc xor ((b.toInt() and 0xFF) shl 8)
            repeat(8) { crc = if (crc and 0x8000 != 0) ((crc shl 1) xor 0x1021) and 0xFFFF else (crc shl 1) and 0xFFFF }
        }
        return crc
    }
}
