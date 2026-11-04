package me.timschneeberger.rootlessjamesdsp.utils.storage

import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.InputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest

/** Transactional import. The old destination is never opened for writing or deleted.
 * Requires an atomic rename in the destination directory; unsupported filesystems fail closed.
 * A hash verifies the bytes read from the provider against the staged file, not content authenticity.
 */
internal object AtomicFileImport {
    internal open class Io {
        open fun output(file: File): FileOutputStream = FileOutputStream(file)
        open fun sync(output: FileOutputStream) = output.fd.sync()
        open fun replace(temp: File, destination: File) {
            Files.move(temp.toPath(), destination.toPath(),
                StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
        }
    }

    fun copy(destination: File, expectedSize: Long? = null,
             io: Io = Io(), openInput: () -> InputStream?): File {
        val dir = destination.absoluteFile.parentFile ?: throw IOException("No destination directory")
        if (!dir.isDirectory && !dir.mkdirs()) throw IOException("Cannot create destination directory")
        var temp: File? = null
        try {
            // Close the provider before committing too: a failed read/close must preserve the old file.
            (openInput() ?: throw IOException("Provider returned no input stream")).use { input ->
                val staged = File.createTempFile(".import-", ".tmp", dir)
                temp = staged
                val sourceHash = MessageDigest.getInstance("SHA-256")
                var copied = 0L
                io.output(staged).use { output ->
                    val buffer = ByteArray(8192)
                    while (true) {
                        var count = input.read(buffer)
                        if (count < 0) break
                        if (count == 0) {
                            // Some providers return zero temporarily; zero is not EOF.
                            val one = input.read()
                            if (one < 0) break
                            buffer[0] = one.toByte()
                            count = 1
                        }
                        output.write(buffer, 0, count)
                        sourceHash.update(buffer, 0, count)
                        copied += count
                    }
                    output.flush()
                    if (staged.length() != copied ||
                        (expectedSize != null && expectedSize >= 0 && expectedSize != copied))
                        throw IOException("Imported size does not match")
                    val storedHash = MessageDigest.getInstance("SHA-256")
                    staged.inputStream().use { check ->
                        while (true) {
                            val count = check.read(buffer)
                            if (count < 0) break
                            storedHash.update(buffer, 0, count)
                        }
                    }
                    if (!MessageDigest.isEqual(sourceHash.digest(), storedHash.digest()))
                        throw IOException("Imported hash does not match")
                    io.sync(output)
                }
            }
            io.replace(checkNotNull(temp), destination)
            return destination
        } finally {
            // After a successful rename this path is already absent. Never delete the destination.
            temp?.delete()
        }
    }
}
