package me.timschneeberger.rootlessjamesdsp.utils.storage

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import timber.log.Timber
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream


object StorageUtils {

    fun importFile(context: Context, targetDir: String, uri: Uri): File? {
        // DISPLAY_NAME comes from another app: keep only a plain file name, and stay inside targetDir
        val dir = File(targetDir).apply { mkdirs() }
        val destinationFile = SafePaths.childFile(dir, queryName(context, uri))
        if(destinationFile == null) {
            Timber.e("importFile: no usable file name")
            return null
        }

        try {
            context.contentResolver.openInputStream(uri)?.use { ins ->
                if(!createFileFromStream(ins, destinationFile))
                    return null
            }
        } catch (ex: Exception) {
            Timber.e(ex.message)
            ex.printStackTrace()
            return null
        }
        return destinationFile
    }

    fun openInputStreamSafe(context: Context, uri: Uri): InputStream? {
        return try {
            context.contentResolver.openInputStream(uri)
        } catch (ex: Exception) {
            Timber.e(ex.message)
            ex.printStackTrace()
            null
        }
    }

    private fun createFileFromStream(ins: InputStream, destination: File?): Boolean {
        try {
            FileOutputStream(destination).use { os ->
                val buffer = ByteArray(4096)
                var length: Int
                while (ins.read(buffer).also { length = it } > 0) {
                    os.write(buffer, 0, length)
                }
                os.flush()
            }
        } catch (ex: Exception) {
            Timber.e(ex.message)
            ex.printStackTrace()
            return false
        }
        return true
    }

    /** The display name offered by the provider, reduced to a plain file name (see [SafePaths.sanitizeFileName]). */
    fun queryName(context: Context, uri: Uri): String? {
        val raw = try {
            context.contentResolver.query(uri, null, null, null, null)?.use { c ->
                val nameIndex = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (nameIndex < 0 || !c.moveToFirst()) null else c.getString(nameIndex)
            }
        } catch (ex: Exception) {
            Timber.e(ex)
            null
        }
        return SafePaths.sanitizeFileName(raw)
    }
}