package nl.mjop.photowalk

/**
 * Android-kant van `photo_walk_capture_v1` (schemas/photo_walk_capture_v1.schema.json).
 * Conventies zijn identiek aan iOS: pixel = u rechts / v omlaag, camera = OpenCV (x rechts, y omlaag, z vooruit), wereld = Y omhoog, meter,
 * pose = camera_to_world rij-hoofdvolgorde (16 getallen), diepte = depth_z in meter (0/NaN = ongeldig).
 * De meetkern zelf (vlakfit, niveau A/B/C, kwaliteitspoorten) is nog NIET naar Kotlin geport; dit module legt alleen vast wat een adapter moet aanleveren.
 */
enum class TrackingStateContract { NORMAL, LIMITED_INITIALIZING, LIMITED_EXCESSIVE_MOTION, LIMITED_INSUFFICIENT_FEATURES, LIMITED_RELOCALIZING, NOT_AVAILABLE }

data class SensorCapabilities(
    val lidar: Boolean = false,            // Android: altijd false (geen LiDAR); ToF-sensoren vallen onder depthApi
    val sceneDepth: Boolean = false,       // iOS-term; op Android gelijk aan depthApi
    val depthApi: Boolean,                 // Session.isDepthModeSupported(Config.DepthMode.AUTOMATIC / RAW_DEPTH_ONLY)
    val arWorldTracking: Boolean,
    val metricTracking: Boolean,           // ARCore volgt metrisch (VIO); NIET onafhankelijk geverifieerd
    val cameraIntrinsicsAvailable: Boolean,
)

data class CameraIntrinsics(val intrinsicsId: String, val fx: Double, val fy: Double, val cx: Double, val cy: Double, val width: Int, val height: Int)

/** camera_to_world, rij-hoofdvolgorde, OpenCV-cameraconventie. */
data class CameraPose(val frameId: String, val intrinsicsId: String, val cameraToWorld: DoubleArray, val poseValid: Boolean = true) {
    init { require(cameraToWorld.size == 16) { "pose moet 16 getallen hebben" } }
}

/** depth_z in meter, rij-hoofdvolgorde; ongeldige pixels = Float.NaN. */
class DepthFrame(val frameId: String, val width: Int, val height: Int, val metersZ: FloatArray) {
    init { require(metersZ.size == width * height) }
}

enum class DepthSource { LIDAR, TOF, DEPTH_FROM_MOTION, NONE }

/** Wat een platformadapter per keyframe moet leveren. */
interface KeyframeSource {
    fun capabilities(): SensorCapabilities
    fun nextKeyframe(): Keyframe?
}

data class Keyframe(
    val frameId: String,
    val timestampIso: String,
    val intrinsics: CameraIntrinsics,
    val pose: CameraPose,
    val tracking: TrackingStateContract,
    val depth: DepthFrame?,
    val depthSource: DepthSource,
    val imageRef: String,                  // opake lokale verwijzing "local://..."; nooit een upload
)
