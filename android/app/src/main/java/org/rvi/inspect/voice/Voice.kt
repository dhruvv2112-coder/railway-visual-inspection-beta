package org.rvi.inspect.voice

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.Locale

/** Platform speech: SpeechRecognizer (on-device when available, API 31+) and TextToSpeech.
 *  No bundled ASR model in the Beta – see Solution Design Report §Models (Vosk/Whisper are fall-backs). */
class VoiceController(private val context: Context) : RecognitionListener {
    sealed interface State { data object Idle : State; data object Listening : State; data class Heard(val text: String) : State; data class Error(val code: Int) : State }

    private val _state = MutableStateFlow<State>(State.Idle)
    val state: StateFlow<State> = _state
    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    var onResult: ((String) -> Unit)? = null

    val onDeviceAvailable: Boolean
        get() = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && SpeechRecognizer.isOnDeviceRecognitionAvailable(context)

    private fun ensure(): SpeechRecognizer? {
        if (recognizer == null && SpeechRecognizer.isRecognitionAvailable(context)) {
            recognizer = if (onDeviceAvailable && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S)
                SpeechRecognizer.createOnDeviceSpeechRecognizer(context) else SpeechRecognizer.createSpeechRecognizer(context)
            recognizer?.setRecognitionListener(this)
        }
        return recognizer
    }

    fun listen(languageTag: String) {
        val r = ensure() ?: run { _state.value = State.Error(-1); return }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageTag)            // "hi-IN" or "en-IN"
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
        }
        _state.value = State.Listening
        r.startListening(intent)
    }

    fun speak(text: String, languageTag: String) {
        if (tts == null) tts = TextToSpeech(context) { }
        tts?.language = Locale.forLanguageTag(languageTag)
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "rvi")
    }

    fun release() { recognizer?.destroy(); tts?.shutdown(); recognizer = null; tts = null }

    override fun onResults(results: Bundle?) {
        val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
        _state.value = State.Heard(text); onResult?.invoke(text)
    }
    override fun onError(error: Int) { _state.value = State.Error(error) }
    override fun onReadyForSpeech(params: Bundle?) {}
    override fun onBeginningOfSpeech() {}
    override fun onRmsChanged(rmsdB: Float) {}
    override fun onBufferReceived(buffer: ByteArray?) {}
    override fun onEndOfSpeech() { if (_state.value == State.Listening) _state.value = State.Idle }
    override fun onPartialResults(partialResults: Bundle?) {}
    override fun onEvent(eventType: Int, params: Bundle?) {}
}
