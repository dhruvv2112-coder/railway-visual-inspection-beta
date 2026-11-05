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
import org.rvi.inspect.data.AppRelease
import org.rvi.inspect.data.isNewer
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

    @Test fun updateOnlyWhenNewer() {
        assertTrue(isNewer(1005, AppRelease(1006, "0.2.1006")))
        assertFalse(isNewer(1006, AppRelease(1006, "0.2.1006")))
        assertFalse(isNewer(1006, null))
    }

    @Test fun releaseManifestParses() {
        val r = kotlinx.serialization.json.Json { ignoreUnknownKeys = true }.decodeFromString(AppRelease.serializer(),
            """{"version_code":1012,"version_name":"0.2.1012","notes":["Sign-in on home"],"sha256":"ab","size_bytes":123,"built_at":"x","extra":1}""")
        assertEquals(1012, r.versionCode); assertEquals("Sign-in on home", r.notes[0])
    }
}

class DiscoveryTest {
    @Test fun normalisesTypedAddresses() {
        assertEquals("http://192.168.1.20:8000/", org.rvi.inspect.data.Discovery.normalise("192.168.1.20"))
        assertEquals("http://192.168.1.20:9000/", org.rvi.inspect.data.Discovery.normalise("http://192.168.1.20:9000"))
        assertEquals("https://ohe.example.in/", org.rvi.inspect.data.Discovery.normalise("https://ohe.example.in"))
        assertEquals("", org.rvi.inspect.data.Discovery.normalise("  "))
    }

    @Test fun reportTrackerFollowsSignatureAndAmendments() {
        fun rep(json: String) = org.rvi.inspect.data.parseReport(Json.parseToJsonElement(json) as kotlinx.serialization.json.JsonObject)
        val waiting = rep("""{"id":"r1","status":"READY_FOR_REVIEW","content":{},"latest":{"id":"r1","revision":1,"status":"READY_FOR_REVIEW"}}""")
        assertFalse(org.rvi.inspect.data.isSigned(waiting.status)); assertEquals("READY_FOR_REVIEW", waiting.status)
        val signed = rep("""{"id":"r1","status":"AUTHORISED_SIGNED","signed_by":"SSE-1","content":{},"latest":{"id":"r1","revision":1,"status":"AUTHORISED_SIGNED","signed_by":"SSE-1"}}""")
        assertTrue(org.rvi.inspect.data.isSigned(signed.status)); assertEquals("SSE-1", signed.signedBy)
        val amended = rep("""{"id":"r1","status":"SUPERSEDED","content":{},"latest":{"id":"r2","revision":2,"status":"READY_FOR_REVIEW"}}""")
        assertEquals("REVIEWED", amended.status)
        val amendedSigned = rep("""{"id":"r1","status":"SUPERSEDED","content":{},"latest":{"id":"r2","revision":2,"status":"AUTHORISED_SIGNED","signed_by":"SSE-2"}}""")
        assertTrue(org.rvi.inspect.data.isSigned(amendedSigned.status)); assertEquals("SSE-2", amendedSigned.signedBy)
    }

    @Test fun relaySignatureMatchesServer() {
        // same HMAC-SHA256("url|ts") the server computes in remote.sign
        val key = "k3y"; val url = "https://brave-words.trycloudflare.com/"; val ts = 1762300000L
        val mac = javax.crypto.Mac.getInstance("HmacSHA256").apply { init(javax.crypto.spec.SecretKeySpec(key.toByteArray(), "HmacSHA256")) }
        val sig = mac.doFinal("$url|$ts".toByteArray()).joinToString("") { "%02x".format(it) }
        assertTrue(org.rvi.inspect.data.Discovery.verify(url, ts, sig, key))
        // value produced by the Python server for the same inputs
        assertTrue(org.rvi.inspect.data.Discovery.verify(url, ts, "f374d0400c25aa84ab2fbe7180e2dcd432b16bc5e265571a8938f9caef79e439", key))
        assertFalse(org.rvi.inspect.data.Discovery.verify("https://evil.example/", ts, sig, key))
        assertTrue(org.rvi.inspect.data.Discovery.isLocal("http://192.168.1.20:8000/"))
        assertFalse(org.rvi.inspect.data.Discovery.isLocal(url))
    }

    @Test fun parsesReportsAndAlertsFromServer() {
        val reports = Json.parseToJsonElement("""[{"id":"r1","territory":"SEC-1","status":"SIGNED","signed_by":"SSE-1","ended_at":"2026-11-05T04:30:00",
            "summary":{"expected_assets":6,"with_findings":1,"alerts":1,"not_assessable":0}}]""") as kotlinx.serialization.json.JsonArray
        val r = org.rvi.inspect.data.parseReports(reports).single()
        assertEquals(6, r.masts); assertEquals("SSE-1", r.signedBy)
        val alerts = Json.parseToJsonElement("""[{"finding":"f1","session":"s1","territory":"SEC-1","asset_id":"1205/12",
            "assessment":{"component":"insulator","condition":"shed_damage","observed_feature":"Insulator shed damage"}}]""") as kotlinx.serialization.json.JsonArray
        assertEquals("Insulator shed damage", org.rvi.inspect.data.parseAlerts(alerts).single().what)
    }
}
