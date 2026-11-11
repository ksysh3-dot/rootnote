// Host-only contract for the methods used by the real PvbSettings class.
package android.content

interface SharedPreferences {
    val all: Map<String, *>
    fun getString(key: String, defValue: String?): String?
    fun getFloat(key: String, defValue: Float): Float
    fun getBoolean(key: String, defValue: Boolean): Boolean
    fun getInt(key: String, defValue: Int): Int
    fun edit(): Editor
    interface Editor {
        fun putString(key: String, value: String?): Editor
        fun putInt(key: String, value: Int): Editor
        fun putFloat(key: String, value: Float): Editor
        fun putBoolean(key: String, value: Boolean): Editor = error("read-only stub")
        fun remove(key: String): Editor = error("read-only stub")
        fun apply()
    }
}
