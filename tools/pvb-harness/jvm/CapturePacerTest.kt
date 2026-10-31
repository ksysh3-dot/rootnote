import me.timschneeberger.rootlessjamesdsp.capture.CapturePacer

// "가로채기" pacing: while the output rests, reads are held to real time (no sped-up players)
fun main() {
    val p = CapturePacer(48000)
    // reading 10 ms blocks instantly (no blocking write): each block must wait until its real time has passed
    var now = 1_000_000_000L
    var waited = 0L
    repeat(100) {
        val w = p.afterRead(480, now)
        check(w >= 0)
        waited += w
        now += w          // the caller waits, then reads the next block immediately
    }
    // 100 blocks of 10 ms = 1 s of audio took 1 s (the first block's own 10 ms included)
    check(now - 1_000_000_000L == 1_000_000_000L) { "paced span ${now - 1_000_000_000L}" }
    // a read that already took its real time needs no wait
    p.reset()
    check(p.afterRead(480, 5_000_000_000L) == 10_000_000L)
    check(p.afterRead(480, 5_020_000_000L) == 0L)
    // far behind (the thread was held up): no catch-up burst, pacing starts again from now
    p.reset()
    p.afterRead(480, 0L)
    check(p.afterRead(480, 2_000_000_000L) == 0L)
    check(p.afterRead(480, 2_000_000_000L) == 10_000_000L)
    // waits are bounded
    val q = CapturePacer(44100)
    check(q.afterRead(441000, 0L) == CapturePacer.MAX_WAIT_NS)
    println("CapturePacer: real-time pacing, catch-up reset and bounded waits passed")
}
