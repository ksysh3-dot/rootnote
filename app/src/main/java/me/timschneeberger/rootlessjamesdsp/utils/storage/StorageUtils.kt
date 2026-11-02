package me.timschneeberger.rootlessjamesdsp.utils.storage

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import timber.log.Timber
import java.io.File
import java.io.InputStream


object StorageUtils {

    fun importFile(context: Context, targetDir: String, uri: Uri): File? {
        return try {
            // DISPLAY_NAME comes from another app: keep a plain file name inside targetDir.
            val dir = File(targetDir)
            val destination = SafePaths.childFile(dir, queryName(context, uri))
                ?: return null.also { Timber.e("importFile: no usable file name") }
            AtomicFileImport.copy(destination, querySize(context, uri)) {
                context.contentResolver.openInputStream(uri)
            }
        } catch (ex: Exception) {
            Timber.e(ex, "importFile failed; destination preserved")
            null
        }
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

    /** Providers may omit SIZE. If supplied, reject premature EOF as well as extra bytes. */
    private fun querySize(context: Context, uri: Uri): Long? = try {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { c ->
            val index = c.getColumnIndex(OpenableColumns.SIZE)
            if (index < 0 || !c.moveToFirst() || c.isNull(index)) null
            else c.getLong(index).takeIf { it >= 0 }
        }
    } catch (ex: Exception) {
        Timber.w(ex, "Provider size unavailable; verifying copied size and hash")
        null
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