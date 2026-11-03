package nl.mjop.photowalk

/**
 * Vertaalfuncties voor ARCore-gegevens. Bewust zonder ARCore-afhankelijkheid (parameters zijn primitieve waarden) zodat ze JVM-testbaar zijn.
 * Zie docs/android.md voor de tabel ARKit <-> ARCore.
 */
object ArCoreMapping {
    /**
     * ARCore `Camera.getPose()` geeft camera->wereld met OpenGL-camera (x rechts, y OMHOOG, -z vooruit), zoals ARKit.
     * OpenCV-camera: R_cv = R_gl * diag(1, -1, -1). [qx,qy,qz,qw] en translatie t komen uit Pose.
     */
    fun poseToContract(frameId: String, intrinsicsId: String, q: DoubleArray, t: DoubleArray, valid: Boolean = true): CameraPose {
        val (x, y, z, w) = q.toList()
        val r = arrayOf(
            doubleArrayOf(1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            doubleArrayOf(2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            doubleArrayOf(2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
        )
        val flip = doubleArrayOf(1.0, -1.0, -1.0)
        val m = DoubleArray(16)
        for (i in 0..2) { for (j in 0..2) m[i * 4 + j] = r[i][j] * flip[j]; m[i * 4 + 3] = t[i] }
        m[15] = 1.0
        return CameraPose(frameId, intrinsicsId, m, valid)
    }

    /** `Camera.getImageIntrinsics()`: focalLength [fx, fy], principalPoint [cx, cy], imageDimensions [w, h] (CPU-beeld). */
    fun intrinsics(id: String, focal: FloatArray, principal: FloatArray, dims: IntArray) =
        CameraIntrinsics(id, focal[0].toDouble(), focal[1].toDouble(), principal[0].toDouble(), principal[1].toDouble(), dims[0], dims[1])

    /** ARCore TrackingState + TrackingFailureReason (als tekst) -> contractstatus. */
    fun tracking(state: String, failureReason: String): TrackingStateContract = when (state) {
        "TRACKING" -> TrackingStateContract.NORMAL
        "PAUSED" -> when (failureReason) {
            "EXCESSIVE_MOTION" -> TrackingStateContract.LIMITED_EXCESSIVE_MOTION
            "INSUFFICIENT_FEATURES", "INSUFFICIENT_LIGHT" -> TrackingStateContract.LIMITED_INSUFFICIENT_FEATURES
            "BAD_STATE" -> TrackingStateContract.LIMITED_RELOCALIZING
            else -> TrackingStateContract.NOT_AVAILABLE
        }
        else -> TrackingStateContract.NOT_AVAILABLE
    }

    /** `Frame.acquireDepthImage16Bits()`: uint16 in MILLIMETER -> meter; 0 = ongeldig. Lage confidence (RAW: <~0.3) behandelt de aanroeper als NaN. */
    fun depthFromMillimeters(frameId: String, width: Int, height: Int, mm: ShortArray, confidenceOk: BooleanArray? = null): DepthFrame {
        val out = FloatArray(width * height) { i ->
            val v = mm[i].toInt() and 0xFFFF
            if (v == 0 || (confidenceOk != null && !confidenceOk[i])) Float.NaN else v / 1000f
        }
        return DepthFrame(frameId, width, height, out)
    }
}
