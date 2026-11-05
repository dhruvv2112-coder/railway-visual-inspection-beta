package org.rvi.inspect.data

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import kotlin.math.atan2
import kotlin.math.sqrt

/** Latest gravity reading, turned into the phone's roll in portrait: 0 = upright, + = top of the phone turned
 *  clockwise. The server subtracts it from the mast angle it measures in the photo. */
class Tilt(context: Context) : SensorEventListener {
    private val sm = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val sensor = sm.getDefaultSensor(Sensor.TYPE_GRAVITY) ?: sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    @Volatile private var g: FloatArray? = null

    fun start() { sensor?.let { sm.registerListener(this, it, SensorManager.SENSOR_DELAY_UI) } }
    fun stop() = sm.unregisterListener(this)

    /** Null when there is no sensor, no reading yet, or the phone is lying flat (roll is then meaningless). */
    fun rollDeg(): Float? = g?.let { rollFrom(it[0], it[1], it[2]) }

    override fun onSensorChanged(e: SensorEvent) { g = e.values.copyOf() }
    override fun onAccuracyChanged(s: Sensor?, a: Int) {}

    companion object {
        fun rollFrom(ax: Float, ay: Float, az: Float): Float? {
            val inPlane = sqrt(ax * ax + ay * ay)
            if (inPlane < 0.5f * sqrt(ax * ax + ay * ay + az * az)) return null  // pointing up/down too steeply
            return Math.toDegrees(atan2(-ax.toDouble(), ay.toDouble())).toFloat()
        }
    }
}
