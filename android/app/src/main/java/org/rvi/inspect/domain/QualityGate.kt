package org.rvi.inspect.domain

/** On-device mirror of backend/app/quality.py (same metrics, same thresholds) so the inspector gets an
 *  immediate "retake" prompt offline. Operates on a downscaled luma array; unit-tested for parity cases.
 *  (OpenCV-Android was rejected for the Beta: ~30 MB APK cost for two simple statistics.) */
object QualityGate {
    const val MIN_SHARPNESS = 60.0
    const val MIN_BRIGHTNESS = 45.0
    const val MAX_BRIGHTNESS = 225.0
    const val MAX_CLIPPED = 0.25

    data class Result(val sharpness: Double, val brightness: Double, val clipped: Double, val reasons: List<String>) {
        val passed get() = reasons.isEmpty()
    }

    /** luma: row-major 0..255 values, width*height. */
    fun assess(luma: IntArray, width: Int, height: Int, originalMinSide: Int = minOf(width, height)): Result {
        var sum = 0.0; var clipped = 0
        for (v in luma) { sum += v; if (v >= 253) clipped++ } // highlights only
        val mean = sum / luma.size
        // 4-neighbour Laplacian variance (as cv2.Laplacian ksize=1)
        var n = 0; var s1 = 0.0; var s2 = 0.0
        for (y in 1 until height - 1) for (x in 1 until width - 1) {
            val i = y * width + x
            val lap = (luma[i - 1] + luma[i + 1] + luma[i - width] + luma[i + width] - 4 * luma[i]).toDouble()
            s1 += lap; s2 += lap * lap; n++
        }
        val varLap = if (n == 0) 0.0 else s2 / n - (s1 / n) * (s1 / n)
        val cf = clipped.toDouble() / luma.size
        val reasons = buildList {
            if (originalMinSide < 480) add("resolution_too_low")
            if (varLap < MIN_SHARPNESS) add("blurred")
            if (mean < MIN_BRIGHTNESS) add("too_dark")
            if (mean > MAX_BRIGHTNESS) add("overexposed")
            if (cf > MAX_CLIPPED) add("clipped_highlights")
        }
        return Result(varLap, mean, cf, reasons)
    }
}
