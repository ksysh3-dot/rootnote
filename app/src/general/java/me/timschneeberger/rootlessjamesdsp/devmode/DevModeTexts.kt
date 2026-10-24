package me.timschneeberger.rootlessjamesdsp.devmode

import androidx.annotation.StringRes
import me.timschneeberger.rootlessjamesdsp.R
import me.timschneeberger.rootlessjamesdsp.pvb.DevEvidence
import me.timschneeberger.rootlessjamesdsp.pvb.DevSpec

/**
 * Texts of each developer-mode value (res/values{,-ko}/strings_devmode.xml, from docs/DEVMODE_COPY.md) and the evidence
 * behind it: one sentence per evidence tag and its source.
 */
object DevModeTexts {
    data class Source(@StringRes val label: Int, val url: String?)

    val MOLINER = Source(R.string.dev_src_moliner,
        "https://acris.aalto.fi/ws/portalfiles/portal/51973173/Eloi2020_Virtual_bass_DAFx2020.pdf")
    val GAN = Source(R.string.dev_src_gan, "https://www3.ntu.edu.sg/home/ewsgan/img/projects/VBS.pdf")
    val OO = Source(R.string.dev_src_oo,
        "https://dr.ntu.edu.sg/server/api/core/bitstreams/ac125f2a-2640-47df-b6b1-da7378296748/content")
    val UPC = Source(R.string.dev_src_upc, "https://core.ac.uk/works/108090091")
    val HWANG = Source(R.string.dev_src_hwang, "https://www.mdpi.com/2076-3417/10/24/8902/html")
    val TI = Source(R.string.dev_src_ti, "https://ti.com/lit/gpn/tas2563")
    val CIRRUS = Source(R.string.dev_src_cirrus, "https://androidauthority.com/cirrus-logic-smart-amplifier-1199823")
    /** The owner's listening rounds and REW measurements (not published). */
    val ROOTNOTE = Source(R.string.dev_src_rootnote, null)
    val NONE = Source(R.string.dev_src_none, null)

    data class Item(val tag: DevEvidence, @StringRes val sentence: Int, val sources: List<Source>)

    data class Texts(
        @StringRes val name: Int,
        @StringRes val line: Int,
        @StringRes val up: Int?,
        @StringRes val down: Int?,
        @StringRes val note: Int?,
        val evidence: List<Item>,
    )

    private val R_ = DevEvidence.RESEARCH
    private val M_ = DevEvidence.MAKER
    private val S_ = DevEvidence.MEASURED
    private val E_ = DevEvidence.ESTIMATE

    private val evBoundary = listOf(Item(R_, R.string.dev_ev_boundary_0, listOf(MOLINER)), Item(S_, R.string.dev_ev_boundary_1, listOf(ROOTNOTE)))
    private val evOut = listOf(Item(R_, R.string.dev_ev_out_0, listOf(GAN)), Item(S_, R.string.dev_ev_out_1, listOf(ROOTNOTE)))
    private val evHp = listOf(Item(R_, R.string.dev_ev_hp_0, listOf(MOLINER)), Item(M_, R.string.dev_ev_hp_1, listOf(TI)),
        Item(E_, R.string.dev_ev_hp_2, listOf(NONE)))
    private val evHarm = listOf(Item(R_, R.string.dev_ev_harm_0, listOf(OO, UPC)), Item(S_, R.string.dev_ev_harm_1, listOf(ROOTNOTE)),
        Item(E_, R.string.dev_ev_harm_2, listOf(NONE)))
    private val evRolloff = listOf(Item(R_, R.string.dev_ev_rolloff_0, listOf(MOLINER)), Item(S_, R.string.dev_ev_rolloff_1, listOf(ROOTNOTE)))
    private val evMix = listOf(Item(R_, R.string.dev_ev_mix_0, listOf(MOLINER)), Item(S_, R.string.dev_ev_mix_1, listOf(ROOTNOTE)))
    private val evVol = listOf(Item(M_, R.string.dev_ev_vol_0, listOf(TI)), Item(S_, R.string.dev_ev_vol_1, listOf(ROOTNOTE)))

    private val byId: Map<String, Texts> = mapOf(
        "boundary" to Texts(R.string.dev_p_boundary_name, R.string.dev_p_boundary_line, R.string.dev_p_boundary_up,
            R.string.dev_p_boundary_down, R.string.dev_p_boundary_note, evBoundary),
        "out_lo" to Texts(R.string.dev_p_out_lo_name, R.string.dev_p_out_lo_line, R.string.dev_p_out_lo_up, null, null, evOut),
        "out_hi" to Texts(R.string.dev_p_out_hi_name, R.string.dev_p_out_hi_line, R.string.dev_p_out_hi_up, null, null, evOut),
        "hp" to Texts(R.string.dev_p_hp_name, R.string.dev_p_hp_line, R.string.dev_p_hp_up, R.string.dev_p_hp_down, null, evHp),
        "h2" to Texts(R.string.dev_p_h2_name, R.string.dev_p_h2_line, null, null, R.string.dev_p_h2_note, evHarm),
        "h3" to Texts(R.string.dev_p_h3_name, R.string.dev_p_h3_line, null, null, R.string.dev_p_h3_note, evHarm),
        "h4" to Texts(R.string.dev_p_h4_name, R.string.dev_p_h4_line, null, null, R.string.dev_p_h4_note, evHarm),
        "h5" to Texts(R.string.dev_p_h5_name, R.string.dev_p_h5_line, null, null, R.string.dev_p_h5_note, evHarm),
        "rolloff" to Texts(R.string.dev_p_rolloff_name, R.string.dev_p_rolloff_line, R.string.dev_p_rolloff_up,
            R.string.dev_p_rolloff_down, R.string.dev_p_rolloff_note, evRolloff),
        "sust" to Texts(R.string.dev_p_sust_name, R.string.dev_p_sust_line, R.string.dev_p_sust_up, null, R.string.dev_p_sust_note, evMix),
        "perc" to Texts(R.string.dev_p_perc_name, R.string.dev_p_perc_line, R.string.dev_p_perc_up, null, null, evMix),
        "attack" to Texts(R.string.dev_p_attack_name, R.string.dev_p_attack_line, R.string.dev_p_attack_up,
            R.string.dev_p_attack_down, null, listOf(Item(E_, R.string.dev_ev_attack_0, listOf(NONE)))),
        "release" to Texts(R.string.dev_p_release_name, R.string.dev_p_release_line, R.string.dev_p_release_up,
            R.string.dev_p_release_down, null, listOf(Item(S_, R.string.dev_ev_release_0, listOf(ROOTNOTE)),
                Item(E_, R.string.dev_ev_release_1, listOf(NONE)))),
        "x_rise" to Texts(R.string.dev_p_x_rise_name, R.string.dev_p_x_rise_line, R.string.dev_p_x_rise_up, null, null,
            listOf(Item(S_, R.string.dev_ev_x_rise_0, listOf(ROOTNOTE)))),
        "x_smooth" to Texts(R.string.dev_p_x_smooth_name, R.string.dev_p_x_smooth_line, R.string.dev_p_x_smooth_up, null, null,
            listOf(Item(S_, R.string.dev_ev_x_smooth_0, listOf(ROOTNOTE)))),
        "x_s1m" to Texts(R.string.dev_p_x_s1m_name, R.string.dev_p_x_s1m_line, R.string.dev_p_x_s1m_up, null,
            R.string.dev_p_x_s1m_note, listOf(Item(E_, R.string.dev_ev_x_s1m_0, listOf(NONE)))),
        "strength" to Texts(R.string.dev_p_strength_name, R.string.dev_p_strength_line, R.string.dev_p_strength_up, null,
            R.string.dev_p_strength_note, listOf(Item(R_, R.string.dev_ev_strength_0, listOf(MOLINER)),
                Item(M_, R.string.dev_ev_strength_1, listOf(TI, CIRRUS)), Item(S_, R.string.dev_ev_strength_2, listOf(ROOTNOTE)))),
        "vol_start" to Texts(R.string.dev_p_vol_start_name, R.string.dev_p_vol_start_line, null, R.string.dev_p_vol_start_down,
            R.string.dev_p_vol_start_note, evVol),
        "vol_slope" to Texts(R.string.dev_p_vol_slope_name, R.string.dev_p_vol_slope_line, R.string.dev_p_vol_slope_up, null, null, evVol),
        "vol_max" to Texts(R.string.dev_p_vol_max_name, R.string.dev_p_vol_max_line, R.string.dev_p_vol_max_up, null, null, evVol),
        "x_dense" to Texts(R.string.dev_p_x_dense_name, R.string.dev_p_x_dense_line, R.string.dev_p_x_dense_up, null, null,
            listOf(Item(E_, R.string.dev_ev_x_dense_0, listOf(NONE)), Item(S_, R.string.dev_ev_x_dense_1, listOf(ROOTNOTE)))),
        "table_floor" to Texts(R.string.dev_p_table_floor_name, R.string.dev_p_table_floor_line, R.string.dev_p_table_floor_up,
            R.string.dev_p_table_floor_down, null, listOf(Item(S_, R.string.dev_ev_table_floor_0, listOf(ROOTNOTE)),
                Item(E_, R.string.dev_ev_table_floor_1, listOf(NONE)))),
    )

    fun of(spec: DevSpec): Texts = byId.getValue(spec.id)
}
