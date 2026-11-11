package me.timschneeberger.rootlessjamesdsp.utils.storage

import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayInputStream
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.InputStream
import java.nio.file.AtomicMoveNotSupportedException

class AtomicFileImportTest {
    @get:Rule val folder = TemporaryFolder()
    private val old = ByteArray(16384) { (it * 7).toByte() }
    private val fresh = ByteArray(27001) { (it * 11 + 3).toByte() }
    private fun target() = File(folder.root, "same-name.irs").apply { writeBytes(old) }
    private fun clean() = assertFalse(folder.root.listFiles()!!.any { it.name.startsWith(".import-") })
    private fun fails(io: AtomicFileImport.Io = AtomicFileImport.Io(), size: Long? = null,
                      input: () -> InputStream?) {
        val f = target()
        assertThrows(IOException::class.java) { AtomicFileImport.copy(f, size, io, input) }
        assertArrayEquals(old, f.readBytes())
        clean()
    }

    @Test fun nullStreamKeepsOldFile() = fails { null }
    @Test fun providerOpenFailureKeepsOldFile() = fails { throw IOException("open") }
    @Test fun readFailureKeepsOldFile() = fails {
        object : ByteArrayInputStream(fresh) {
            override fun read(b: ByteArray, off: Int, len: Int): Int {
                if (pos >= 8192) throw IOException("read")
                return super.read(b, off, len)
            }
        }
    }
    @Test fun inputCloseFailureKeepsOldFile() = fails {
        object : ByteArrayInputStream(fresh) { override fun close() { throw IOException("close") } }
    }
    @Test fun outputOpenFailureKeepsOldFile() = fails(object : AtomicFileImport.Io() {
        override fun output(file: File): FileOutputStream = throw IOException("write open")
    }) { fresh.inputStream() }
    @Test fun partialWriteFailureKeepsOldFile() = fails(object : AtomicFileImport.Io() {
        override fun output(file: File) = object : FileOutputStream(file) {
            override fun write(b: ByteArray, off: Int, len: Int) {
                super.write(b, off, minOf(4096, len)); throw IOException("disk full")
            }
        }
    }) { fresh.inputStream() }
    @Test fun outputCloseFailureKeepsOldFile() = fails(object : AtomicFileImport.Io() {
        override fun output(file: File) = object : FileOutputStream(file) {
            override fun close() { super.close(); throw IOException("close") }
        }
    }) { fresh.inputStream() }
    @Test fun fsyncFailureKeepsOldFile() = fails(object : AtomicFileImport.Io() {
        override fun sync(output: FileOutputStream) { throw IOException("fsync") }
    }) { fresh.inputStream() }
    @Test fun atomicMoveFailureKeepsOldFile() = fails(object : AtomicFileImport.Io() {
        override fun replace(temp: File, destination: File) { throw IOException("rename") }
    }) { fresh.inputStream() }
    @Test fun unsupportedAtomicMoveHasNoDestructiveFallback() = fails(object : AtomicFileImport.Io() {
        override fun replace(temp: File, destination: File) {
            throw AtomicMoveNotSupportedException(temp.path, destination.path, "unsupported")
        }
    }) { fresh.inputStream() }
    @Test fun shortProviderStreamFailsAdvertisedSize() = fails(size = fresh.size.toLong() + 1) { fresh.inputStream() }
    @Test fun extraProviderBytesFailAdvertisedSize() = fails(size = fresh.size.toLong() - 1) { fresh.inputStream() }
    @Test fun silentShortWriteFailsSizeCheck() = fails(object : AtomicFileImport.Io() {
        override fun output(file: File) = object : FileOutputStream(file) {
            override fun write(b: ByteArray, off: Int, len: Int) { super.write(b, off, len - 1) }
        }
    }) { fresh.inputStream() }
    @Test fun sameSizeCorruptionFailsHashCheck() = fails(object : AtomicFileImport.Io() {
        override fun output(file: File) = object : FileOutputStream(file) {
            override fun write(b: ByteArray, off: Int, len: Int) {
                val damaged = b.copyOfRange(off, off + len)
                damaged[0] = (damaged[0].toInt() xor 1).toByte()
                super.write(damaged, 0, damaged.size)
            }
        }
    }) { fresh.inputStream() }
    @Test fun sameNameSuccessReplacesOnlyAfterSyncAndClose() {
        val f = target(); var synced = false; var closed = false
        val io = object : AtomicFileImport.Io() {
            override fun sync(output: FileOutputStream) {
                assertArrayEquals(old, f.readBytes()); super.sync(output); synced = true
            }
            override fun replace(temp: File, destination: File) {
                assertTrue(synced); assertTrue(closed)
                assertArrayEquals(old, destination.readBytes()); assertArrayEquals(fresh, temp.readBytes())
                super.replace(temp, destination)
            }
        }
        assertEquals(f, AtomicFileImport.copy(f, fresh.size.toLong(), io) {
            object : ByteArrayInputStream(fresh) { override fun close() { closed = true; super.close() } }
        })
        assertArrayEquals(fresh, f.readBytes()); clean()
    }
    @Test fun importingDestinationItselfPreservesBytes() {
        val f = target()
        AtomicFileImport.copy(f, old.size.toLong()) { f.inputStream() }
        assertArrayEquals(old, f.readBytes()); clean()
    }
    @Test fun zeroLengthReadIsNotEof() {
        val f = target()
        AtomicFileImport.copy(f, fresh.size.toLong()) {
            object : ByteArrayInputStream(fresh) {
                var zero = true
                override fun read(b: ByteArray, off: Int, len: Int): Int {
                    if (zero) { zero = false; return 0 }
                    return super.read(b, off, len)
                }
            }
        }
        assertArrayEquals(fresh, f.readBytes()); clean()
    }
    @Test fun failureWithoutOldFileLeavesNoDestination() {
        val f = File(folder.root, "new.irs")
        assertThrows(IOException::class.java) { AtomicFileImport.copy(f) { null } }
        assertFalse(f.exists()); clean()
    }
    @Test fun emptyFileAndUnknownSizeAreValid() {
        val f = target()
        AtomicFileImport.copy(f) { byteArrayOf().inputStream() }
        assertEquals(0L, f.length()); clean()
    }
}
