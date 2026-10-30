package org.rvi.inspect

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.rvi.inspect.domain.Command
import org.rvi.inspect.domain.CommandMatcher
import org.rvi.inspect.domain.QualityGate
import org.rvi.inspect.domain.Taxonomy
import java.io.File
import kotlin.random.Random

class CommandMatcherTest {
    private fun m(s: String) = CommandMatcher.match(s)

    @Test fun englishCommands() {
        assertEquals(Command.Capture, m("capture"))
        assertEquals(Command.Capture, m("please take photo"))
        assertEquals(Command.EndPatrol, m("end patrol"))
        assertEquals(Command.Defect("PW-FS-001"), m("missing clip"))
        assertEquals(Command.Defect("PW-FS-001"), m("clip missing"))
    }

    @Test fun hindiAndHinglishCommands() {
        assertEquals(Command.Capture, m("फोटो लो"))
        assertEquals(Command.EndPatrol, m("गश्त समाप्त"))
        assertEquals(Command.Defect("PW-FS-001"), m("क्लिप गायब"))
        assertEquals(Command.Defect("PW-JT-001"), m("बोल्ट गायब है"))
        assertEquals(Command.Danger, m("खतरा"))
    }

    @Test fun toleratesSmallAsrErrors() {
        assertEquals(Command.Capture, m("captur"))
        assertEquals(Command.EndPatrol, m("end petrol"))
    }

    @Test fun notesAreDictation() {
        assertEquals(Command.Note("sleeper near km 1205/4 hanging"), m("note sleeper near km 1205/4 hanging"))
    }

    @Test fun unrelatedSpeechIsRejected() {
        assertNull(m("what time is the next train to delhi"))
        assertNull(m(""))
    }

    @Test fun noVoicePathToProtectFirstDefects() {
        val tax = Taxonomy.parse(File("../../shared/taxonomy.json").readText())
        val protectFirst = tax.classes.filter { it.protect_first }.map { it.id }.toSet()
        val samples = listOf("rail fracture", "broken rail", "washaway", "weld fracture", "रेल फ्रैक्चर", "टूटी रेल")
        samples.forEach { val c = m(it); assertFalse("$it -> $c", c is Command.Defect && c.classId in protectFirst) }
    }
}

class QualityGateTest {
    private fun texture(w: Int, h: Int, contrast: Int = 255, offset: Int = 0, seed: Int = 1): IntArray {
        val r = Random(seed)
        return IntArray(w * h) { (offset + r.nextInt(contrast)).coerceIn(0, 255) }
    }

    @Test fun sharpTexturePasses() = assertTrue(QualityGate.assess(texture(640, 480, 200, 30), 640, 480).passed)

    @Test fun flatImageIsBlurred() {
        val flat = IntArray(640 * 480) { 128 }
        assertTrue("blurred" in QualityGate.assess(flat, 640, 480).reasons)
    }

    @Test fun darkImageRejected() = assertTrue("too_dark" in QualityGate.assess(texture(640, 480, 30, 0), 640, 480).reasons)

    @Test fun lowResolutionRejected() = assertTrue("resolution_too_low" in QualityGate.assess(texture(320, 240), 320, 240).reasons)
}

class TaxonomyTest {
    private val tax = Taxonomy.parse(File("../../shared/taxonomy.json").readText())

    @Test fun betaExcludesCategoryD() = assertTrue(tax.beta.none { it.category == "D" })

    @Test fun everyBetaClassHasHindiLabel() = assertTrue(tax.beta.all { !it.label.hi.isNullOrBlank() })

    @Test fun bilingualSearch() {
        assertTrue(tax.search("ERC", "en").any { it.id == "PW-FS-001" })
        assertTrue(tax.search("गायब", "hi").any { it.id == "PW-FS-001" })
    }
}
