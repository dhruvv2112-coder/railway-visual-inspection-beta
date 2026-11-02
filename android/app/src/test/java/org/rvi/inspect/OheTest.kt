package org.rvi.inspect

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.rvi.inspect.data.Hashing
import org.rvi.inspect.data.OheCaptureEntity
import org.rvi.inspect.data.OheSessionEntity
import org.rvi.inspect.data.Prompt
import org.rvi.inspect.data.parseUpload
import org.rvi.inspect.domain.Command
import org.rvi.inspect.domain.CommandMatcher
import org.rvi.inspect.ui.summaryFrom
import java.io.File

class OheTest {
    private fun obj(s: String) = Json.parseToJsonElement(s) as JsonObject

    @Test fun uploadWithUrgentFinding() {
        val r = parseUpload(obj("""{"media":{},"idempotent":false,"analysis":{"image_state":null,
            "recapture_prompt":"Capture the mast number plate from where you stand",
            "assessments":[{"state":"assessable_defect","alert":true},{"state":"assessable_no_visible_defect"}]}}"""))
        assertEquals(1, r.findings); assertTrue(r.alert); assertEquals(Prompt.PLATE, r.prompt); assertNull(r.imageState)
    }

    @Test fun uploadNotAssessableAsksForZoom() {
        val r = parseUpload(obj("""{"analysis":{"image_state":"insufficient_resolution",
            "recapture_prompt":"Hold still and use optical zoom on the component; do not move closer to the OHE","assessments":[]}}"""))
        assertEquals("insufficient_resolution", r.imageState); assertEquals(Prompt.ZOOM, r.prompt); assertEquals(0, r.findings); assertFalse(r.alert)
    }

    @Test fun duplicateUploadWithoutAnalysisIsHarmless() {
        val r = parseUpload(obj("""{"media":{"id":"m1"},"idempotent":true}"""))
        assertEquals(0, r.findings); assertNull(r.prompt)
    }

    @Test fun localQualityPrompts() {
        assertEquals(Prompt.BLUR, Prompt.fromLocal(listOf("blurred")))
        assertEquals(Prompt.DARK, Prompt.fromLocal(listOf("too_dark")))
        assertEquals(Prompt.BRIGHT, Prompt.fromLocal(listOf("overexposed")))
        assertNull(Prompt.fromLocal(emptyList()))
    }

    @Test fun promptsNeverAskToApproachLiveOhe() {
        // every server prompt maps to a code whose wording is reviewed in strings.xml; unknown text maps to nothing
        assertNull(Prompt.fromServer("Walk up to the mast and look closely"))
        assertEquals(Prompt.SQUARE, Prompt.fromServer("Take the photo square-on to the mast"))
    }

    @Test fun sha256MatchesKnownVector() {
        val f = File.createTempFile("abc", ".bin").apply { writeText("abc") }
        assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", Hashing.sha256(f))
    }

    @Test fun summaryUsesServerCountsWhenReportExists() {
        val sess = OheSessionEntity(territory = "SEC", inspectorId = "a", role = "Patrol", reportId = "r1",
            summaryJson = """{"expected_assets":6,"evidenced_assets":4,"with_findings":1,"not_assessable":1,"alerts":1}""")
        val caps = listOf(OheCaptureEntity(sessionId = sess.id, path = "x", sha256 = "h", uploaded = true),
            OheCaptureEntity(sessionId = sess.id, path = "y", sha256 = "i"))
        val s = summaryFrom(sess, caps, 2)
        assertEquals(2, s.photos); assertEquals(1, s.uploaded); assertEquals(6, s.expected); assertEquals(1, s.alerts); assertEquals("r1", s.reportId)
    }

    @Test fun oheVoiceSetIsPhotoNoteEnd() {
        assertEquals(Command.Capture, CommandMatcher.match("फोटो"))
        assertEquals(Command.EndPatrol, CommandMatcher.match("end patrol"))
        assertTrue(CommandMatcher.match("note insulator looks dirty") is Command.Note)
    }
}
