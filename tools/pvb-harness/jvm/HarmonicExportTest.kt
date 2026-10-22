import me.timschneeberger.rootlessjamesdsp.pvb.*
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.ByteArrayInputStream
import java.security.MessageDigest
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

fun main() {
    val r=BuzzRing(48000,detailed=true).apply { armed=true }
    val pcm=FloatArray(512);val data=FloatArray(HarmonicHistory.FIELDS)
    data[23]=1f;data[9]=-6200f;data[10]=424f
    data[HarmonicHistory.HEADER+1]=2f
    data[HarmonicHistory.HEADER+13]=1f // id65536: low16=0 is still a valid track
    repeat(1125) { r.recordFloat(pcm,pcm,512,null,7140,5,1f,true,harmonic=data,harmonicRows=1) }
    check(r.trigger())
    while(!r.frozen) r.recordFloat(pcm,pcm,512,null,7140,5,1f,true,harmonic=data,harmonicRows=1)
    val bytes=ByteArrayOutputStream();val hashes=JSONObject();val report=JSONObject().put("sha256",hashes)
    ZipOutputStream(bytes).use { HarmonicTraceWriter.write(it,r,report,hashes) }
    val payload=ZipInputStream(ByteArrayInputStream(bytes.toByteArray())).use { z ->
        check(z.nextEntry.name=="harmonics.jsonl");z.readBytes()
    }
    val expected=MessageDigest.getInstance("SHA-256").digest(payload).joinToString("") { "%02x".format(it.toInt() and 255) }
    check(hashes.getString("harmonics.jsonl")==expected)
    val lines=payload.toString(Charsets.UTF_8).trim().lines().map { JSONObject(it) }
    check(lines[0].getJSONArray("header_fields").length()==HarmonicHistory.HEADER)
    check(lines[0].getJSONArray("track_fields").length()==14)
    check(lines.size in 1501..1505)
    for(line in lines.drop(1)) {
        check(line.getJSONArray("header").length()==HarmonicHistory.HEADER)
        val track=line.getJSONArray("tracks").getJSONArray(0)
        check(track.length()==HarmonicHistory.TRACK && track.getInt(0)==0 && track.getInt(13)==1)
        check(line.getDouble("source_center_in_clip_s") < line.getDouble("nominal_output_grain_center_in_clip_s"))
    }
    check(report.getJSONObject("harmonic_processing").getInt("recorded_hops")==lines.size-1)
    println("Harmonic JSONL: schema widths, high16 track identity,8s+context, timing and ZIP checksum passed")
}
