package org.rvi.inspect.ui

import android.content.Context
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import java.io.File

/** Holds the ImageCapture use case so the HUD button / voice command can trigger a capture. */
class CameraHandle {
    var capture: ImageCapture? = null

    fun take(context: Context, onSaved: (File) -> Unit, onError: (Exception) -> Unit) {
        val ic = capture ?: return onError(IllegalStateException("camera not ready"))
        val dir = File(context.filesDir, "evidence").apply { mkdirs() }
        val file = File(dir, "${System.currentTimeMillis()}.jpg")
        ic.takePicture(ImageCapture.OutputFileOptions.Builder(file).build(), ContextCompat.getMainExecutor(context),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(output: ImageCapture.OutputFileResults) = onSaved(file)
                override fun onError(exception: ImageCaptureException) = onError(exception)
            })
    }
}

@Composable
fun CameraPreview(handle: CameraHandle, modifier: Modifier = Modifier.fillMaxSize()) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    AndroidView(modifier = modifier, factory = { ctx ->
        val view = PreviewView(ctx).apply { scaleType = PreviewView.ScaleType.FILL_CENTER }
        val providerFuture = ProcessCameraProvider.getInstance(ctx)
        providerFuture.addListener({
            val provider = providerFuture.get()
            val preview = Preview.Builder().build().also { it.setSurfaceProvider(view.surfaceProvider) }
            val capture = ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build()
            provider.unbindAll()
            provider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, preview, capture)
            handle.capture = capture
        }, ContextCompat.getMainExecutor(context))
        view
    })
}
