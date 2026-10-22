// Host JVM test of the archive/import path checks (review F06).
import me.timschneeberger.rootlessjamesdsp.utils.storage.SafePaths
import java.io.File
import java.nio.file.Files
import kotlin.system.exitProcess

private var failed = 0
private fun check(name: String, ok: Boolean, info: String = "") {
    println("[${if (ok) "PASS" else "FAIL"}] $name $info")
    if (!ok) failed++
}

fun main() {
    val base = Files.createTempDirectory("pvbsafe").toFile()
    val root = File(base, "restore").apply { mkdirs() }
    check("plain entries resolve inside", SafePaths.resolveEntry(root, "shared_prefs/dsp_eq.xml")?.path ==
        File(root.canonicalFile, "shared_prefs/dsp_eq.xml").path && SafePaths.resolveEntry(root, "profiles/a/b.json") != null)
    val bad = listOf("../dsp_review_probe.xml", "shared_prefs/../../dsp_x.xml", "/etc/dsp_x.xml", "a//b", "./dsp_x.xml",
        "dsp_\u0000.xml", "a\\..\\b.xml", "..", "", "x/..")
    check("traversal, absolute, empty and odd names rejected", bad.all { SafePaths.resolveEntry(root, it) == null },
        bad.filter { SafePaths.resolveEntry(root, it) != null }.joinToString())
    // a symbolic link inside the folder that points outside is not followed
    val outside = File(base, "outside").apply { mkdirs() }
    val link = File(root, "link")
    var linkOk = true
    try {
        Files.createSymbolicLink(link.toPath(), outside.toPath())
        linkOk = SafePaths.resolveEntry(root, "link/dsp_x.xml") == null
    } catch (e: Exception) {
        println("  (symbolic links not available: ${e.message})")
    }
    check("entry through a symbolic link leaving the folder rejected", linkOk)

    check("display names: last segment, no control/reserved chars, no dot files",
        SafePaths.sanitizeFileName("../../x/evil.wav") == "evil.wav" && SafePaths.sanitizeFileName("a\\b\\c.irs") == "c.irs" &&
            SafePaths.sanitizeFileName("..") == null && SafePaths.sanitizeFileName(".hidden") == "hidden" &&
            SafePaths.sanitizeFileName("we<i>rd\u0001.eel") == "weird.eel" && SafePaths.sanitizeFileName(null) == null &&
            SafePaths.sanitizeFileName("x".repeat(400) + ".vdc")!!.let { it.length == 255 && it.endsWith(".vdc") })
    val dir = File(base, "Convolver").apply { mkdirs() }
    check("import target stays in its folder", SafePaths.childFile(dir, "../../evil.wav")?.parentFile?.path == dir.canonicalFile.path &&
        SafePaths.childFile(dir, "/") == null)
    base.deleteRecursively()
    if (failed > 0) exitProcess(1)
    println("all safe path checks passed")
}
