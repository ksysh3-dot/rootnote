import android.content.SharedPreferences
import me.timschneeberger.rootlessjamesdsp.pvb.PvbBuild
import me.timschneeberger.rootlessjamesdsp.pvb.PvbModels
import me.timschneeberger.rootlessjamesdsp.pvb.PvbSettings

// Same semantics as Android's SharedPreferencesImpl for what PvbSettings uses: a getter of the wrong type throws.
private class Prefs(initial: Map<String, Any?> = emptyMap()) : SharedPreferences {
    val values = initial.toMutableMap()
    var writes = 0
    override val all: Map<String, *> get() = values.toMap()
    override fun getString(key: String, defValue: String?): String? =
        if (values.containsKey(key)) values[key] as String? else defValue
    override fun getFloat(key: String, defValue: Float): Float =
        if (values.containsKey(key)) values[key] as Float else defValue
    override fun getBoolean(key: String, defValue: Boolean): Boolean =
        if (values.containsKey(key)) values[key] as Boolean else defValue
    override fun getInt(key: String, defValue: Int): Int =
        if (values.containsKey(key)) values[key] as Int else defValue
    override fun edit(): SharedPreferences.Editor = object : SharedPreferences.Editor {
        private val next = mutableMapOf<String, Any?>()
        override fun putString(key: String, value: String?) = apply { next[key] = value }
        override fun putInt(key: String, value: Int) = apply { next[key] = value }
        override fun putFloat(key: String, value: Float) = apply { next[key] = value }
        override fun putBoolean(key: String, value: Boolean) = apply { next[key] = value }
        override fun remove(key: String) = apply { next[key] = null }
        override fun apply() { next.forEach { (k,v) -> if(v==null) values.remove(k) else values[k]=v }; writes++ }
    }
}

fun main() {
    check(PvbModels.models.map { it.id } == listOf(6))
    check((0..18).filter { PvbModels.inUse(it) } == listOf(6))
    check(PvbModels.presets.map { it.key } == listOf("fullness"))
    val removed = listOf("hpv","bankstown","hpv52m","alpha3_gentle12","alpha2_reference","alpha2_d2",
        "alpha2_j2","alpha2_osc","alpha2_osc_correct","alpha2_p1plus","alpha2_p1pp","alpha2_p1pp_v03",
        "alpha2_p1_c1","resultant_core_v15","resultant_core_v16","resultant_core_v16d","unknown") + (0..18).map { it.toString() }
    val xs = listOf(PvbSettings.KEY_X_SMOOTH,PvbSettings.KEY_X_RISE,PvbSettings.KEY_X_S1M,PvbSettings.KEY_X_DENSE)
    var cases=0
    for (general in listOf(false,true)) for (schema in listOf<Any>(0,1,2,3,4,"corrupt")) for (model in removed + PvbModels.P1_KEY) {
        PvbBuild.general=general;PvbBuild.firstRunConfirmed=true
        val initial=mutableMapOf<String,Any?>(PvbSettings.KEY_VB_ALGO to model, PvbSettings.KEY_VB_MODEL_SCHEMA to schema,
            PvbSettings.KEY_VB_MODE to "deep",PvbSettings.KEY_VB_LEVEL_DB to "-3",PvbSettings.KEY_LOW_DB to 2f,
            PvbSettings.KEY_OUT_DB to -7f,PvbSettings.KEY_VB_ON to true,"historical_ab" to "id16")
        xs.forEach { initial[it]=true }
        val p=Prefs(initial);PvbSettings.migrateVirtualBassModel(p);val writes=p.writes
        PvbSettings.migrateVirtualBassModel(p);check(p.writes==writes)
        val s=PvbSettings.load(p)
        check(s.vbAlgo==6 && !s.p1ppp && s.vbLevelDb == -3f && s.lowDb==2f && s.outDb == -7f && s.vbOn)
        check(xs.all { p.all[it]==false } && PvbSettings.KEY_VB_MODE !in p.all && p.all["historical_ab"]=="id16")
        check(p.all[PvbSettings.KEY_VB_ALGO]==PvbModels.P1_KEY);cases++
    }
    for (raw in listOf<Any>(0,3,16,17,99,true,Float.NaN)) {
        val p=Prefs(mapOf(PvbSettings.KEY_VB_ALGO to raw,PvbSettings.KEY_VB_STRENGTH_DB to 9f))
        PvbSettings.migrateVirtualBassModel(p);check(PvbSettings.load(p).vbAlgo==6 && !PvbSettings.load(p).p1ppp)
    }
    // An existing explicit opt-in survives migration; deletion never manufactures one.
    val p=Prefs(mapOf(PvbSettings.KEY_P1PPP to true));PvbSettings.migrateVirtualBassModel(p);check(PvbSettings.load(p).p1ppp)
    PvbBuild.reset();println("Pruned model/migration contracts: $cases plus corrupt numeric IDs passed")
}
