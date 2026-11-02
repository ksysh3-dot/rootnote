import me.timschneeberger.rootlessjamesdsp.pvb.*
import java.io.File
fun main(args:Array<String>) {
 val root=File(args.getOrElse(0){"."})
 val xml=File(root,"app/src/main/res/xml/dsp_pvb_preferences.xml").readText()
 for (key in listOf("pvb_x_smooth","pvb_x_rise","pvb_x_s1m","pvb_x_dense")) check(!xml.contains("android:key=\"$key\""))
 check(xml.contains("android:key=\"pvb_p1ppp\""))
 check(!PvbSettings().p1ppp && PvbEngine.defaultParams()[57]==0f)
 for (g in DevGroup.values()) check(DevParams.group(g).none { DevParams.retired(it) })
 check(listOf("x_rise","x_smooth","x_s1m","x_dense").all { DevParams.byId(it)==null })
 println("Retired X switches absent; P1+++ default OFF and explicit in XML passed")
}
