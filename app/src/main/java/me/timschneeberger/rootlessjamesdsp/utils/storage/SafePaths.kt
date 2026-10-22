package me.timschneeberger.rootlessjamesdsp.utils.storage

import java.io.File

/**
 * Path checks for untrusted names (archive entries, file names offered by other apps). Pure Kotlin, so the host JVM
 * test (tools/pvb-harness/jvm/SafePathsTest.kt) runs this exact code.
 */
object SafePaths {
    const val MAX_NAME_LENGTH = 255
    const val MAX_ENTRY_PATH_LENGTH = 512

    /**
     * Resolves archive entry [name] inside [root]. Null when the name is absolute, contains "..", backslashes,
     * control characters or empty segments, or when its canonical path (symbolic links resolved) is not strictly
     * inside the canonical [root].
     */
    fun resolveEntry(root: File, name: String): File? {
        if (name.isEmpty() || name.length > MAX_ENTRY_PATH_LENGTH) return null
        if (name.any { it.code < 0x20 || it.code == 0x7f || it == '\\' }) return null
        if (name.startsWith("/")) return null
        val parts = name.trimEnd('/').split('/')
        if (parts.any { it.isEmpty() || it == "." || it == ".." || it.length > MAX_NAME_LENGTH }) return null
        val rootC = root.canonicalFile
        val f = File(rootC, name.trimEnd('/')).canonicalFile
        return if (isInside(rootC, f)) f else null
    }

    /** [child] is [root] itself or below it? Strictly below: the root itself does not count. */
    fun isInside(root: File, child: File): Boolean {
        val r = root.canonicalFile.path
        val c = child.canonicalFile.path
        return c.startsWith(r + File.separator) && c.length > r.length + 1
    }

    /**
     * A plain file name from an untrusted display name: the last path segment, without control and reserved
     * characters, not "." or "..", at most [MAX_NAME_LENGTH] characters (keeping the extension). Null if nothing usable
     * is left.
     */
    fun sanitizeFileName(raw: String?): String? {
        if (raw == null) return null
        var n = raw.substringAfterLast('/').substringAfterLast('\\')
        n = n.filter { it.code >= 0x20 && it.code != 0x7f && it !in "<>:\"|?*" }.trim()
        n = n.trimStart('.').ifEmpty { return null }   // no hidden files, no "." / ".."
        if (n.length > MAX_NAME_LENGTH) {
            val ext = n.substringAfterLast('.', "").take(16)
            val keep = MAX_NAME_LENGTH - (if (ext.isEmpty()) 0 else ext.length + 1)
            n = n.take(keep) + (if (ext.isEmpty()) "" else ".$ext")
        }
        return n
    }

    /** The file [name] (sanitized) in [dir], or null if it would not stay inside [dir]. */
    fun childFile(dir: File, name: String?): File? {
        val clean = sanitizeFileName(name) ?: return null
        val d = dir.canonicalFile
        val f = File(d, clean).canonicalFile
        return if (f.parentFile?.path == d.path) f else null
    }
}
