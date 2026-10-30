"""Regenerates the OHE (EL-OH-*) classes of shared/taxonomy.json for the combined Track + OHE foot patrol and adds
domain / danger / route fields to every class.  Run: python shared/ohe_classes.py

Sources (user-supplied, read 31 Oct 2026):
  R1 RDSO Maintenance Instruction TI/MI/0060 (Nov 2022), para 6.1 Foot patrolling of OHE (ACTM Vol II Pt I para 20322),
     items 4(a)-(s); para 6.1(5) major defects reported forthwith to TPC; Proforma 03-2 defect Category A/B.
  R2 CAMTECH Handbook on Inspection of OHE (CAMTECH/E/17-18/OHE-Inspection/1.0, draft), section 7 checklist.
  R3 CAMTECH Review of Maintenance Schedule for OHE (CAMTECH/E/11-12/OHE-Schedule/1.0, Aug 2011), Foot Patrolling Diary.
Severity mapping (proposal): OHE Category A (safety / train operation, R1 Proforma 03-2) -> RF-P2, or RF-P1 where the
defect can foul a pantograph or bring down a live conductor (TPC first); Category B -> RF-P3/RF-P4.
Hindi labels are drafts pending Rajbhasha / TRD terminology review."""
import json
from pathlib import Path

DEPT = "Electrical – Traction Distribution (TRD)"
TPC = ("Treat as live – do not touch or approach. Report forthwith to TPC (emergency socket / mobile) with location and "
       "details so TPC can regulate trains; inform SM; keep watch until relieved (R1 6.1(5)).")
REPORT_TPC = "Report to TPC and OHE depot (Category A, R1 Proforma 03-2); enter in foot patrol diary."
DIARY = "Enter in foot patrol diary; depot attends (Category B)."

# id, visual category, asset, focus unit, en, hi, severity, danger, measurement, action, reference, beta
OHE = [
    ("EL-OH-001", "B", "Insulator", "Bracket / stay / 9-tonne / post insulator", "Chipped, cracked or shed-damaged insulator",
     "इंसुलेटर टूटा / चटका / शेड क्षतिग्रस्त", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R1 6.1(4)(a); R2 7(b); R3 diary 4", True),
    ("EL-OH-002", "B", "Insulator", "Insulator / section-insulator runner", "Flashover mark on insulator or runner",
     "इंसुलेटर पर फ्लैशओवर का निशान", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R2 7(b),(k); R3 diary 5", True),
    ("EL-OH-003", "B", "Insulator", "Insulator surface", "Heavy dust or dirt on insulators (polluted area)",
     "इंसुलेटर पर अधिक धूल / गंदगी", "RF-P3 (OHE Cat B)", None, False, DIARY, "R2 7(b); R1 weekly check 6", True),
    ("EL-OH-004", "B", "OHE span", "Dropper", "Dropper broken, missing, displaced or out of plumb",
     "ड्रॉपर टूटा / गायब / खिसका", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R1 6.1(4)(b); R2 7(g); R3 diary 7", True),
    ("EL-OH-005", "A", "OHE conductors", "Contact wire / catenary", "Contact wire or catenary broken, hanging or fallen",
     "कॉन्टैक्ट वायर / कैटेनरी टूटा या लटका", "RF-P1 (OHE Cat A)", "ohe", False, TPC, "R1 6.1(5); R2 1, 7(e)", True),
    ("EL-OH-006", "B", "OHE conductors", "Catenary / stranded conductor", "Damaged strands of catenary or other stranded wire",
     "कैटेनरी के तार (स्ट्रैंड) क्षतिग्रस्त", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R2 7(e); R3 diary 7(iv)", True),
    ("EL-OH-007", "B", "OHE conductors", "Contact wire", "Excessive sag or hog, kink or twist in contact wire",
     "कॉन्टैक्ट वायर में अधिक झोल / उभार / ऐंठन", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R1 6.1(4)(c); R2 7(e),(g)", True),
    ("EL-OH-008", "A", "Foreign object", "OHE / feeder", "Bird nest, stray wire or other foreign object on OHE",
     "OHE पर चिड़िया का घोंसला / तार / बाहरी वस्तु", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R1 6.1(4)(h); R2 7(p); R3 diary 9(viii)", True),
    ("EL-OH-009", "A", "Vegetation", "Tree branches near OHE", "Tree branches likely to infringe OHE",
     "OHE के पास पेड़ की शाखाएँ", "RF-P3 (OHE Cat B)", None, False, "Clear small creepers on the spot with chopper if safe without power block; otherwise diary.",
     "R1 6.1(3),(4)(h); R3 diary 9(vii)", True),
    ("EL-OH-010", "A", "Obstruction", "Pantograph / train path", "Branch or obstruction touching OHE or fouling the pantograph path",
     "शाखा / अवरोध OHE को छू रहा या पेंटोग्राफ पथ में", "RF-P1 (OHE Cat A)", "ohe", False, TPC, "R1 6.1(4)(k),(5); R2 7(p)", True),
    ("EL-OH-011", "A", "Mast / portal", "Mast", "Mast or portal tilted, deflected or hit-damaged",
     "मस्त / पोर्टल झुका या टक्कर से क्षतिग्रस्त", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R1 6.1(4)(o); R2 7(a); R3 diary 2", True),
    ("EL-OH-012", "A", "Foundation", "Mast foundation", "Foundation cracked or sinking, water around it or earth filling needed",
     "मस्त नींव में दरार / धँसाव / पानी भराव", "RF-P3 (OHE Cat B)", None, False, DIARY, "R2 7(a); R3 diary 1", True),
    ("EL-OH-013", "A", "Mast / portal", "Location number plate", "Mast number plate missing or damaged",
     "मस्त नंबर प्लेट गायब / क्षतिग्रस्त", "RF-P4 (OHE Cat B)", None, False, DIARY, "R1 6.1(4)(p); R3 diary 2(iv),(v)", True),
    ("EL-OH-014", "A", "Bonding & earthing", "Structure / longitudinal / cross bond, AEC / BEC", "Bond or earth connection missing, open or loose",
     "बॉन्ड / अर्थ कनेक्शन गायब या ढीला", "RF-P2 (OHE Cat A)", None, False,
     "Tighten / refix on the spot if possible (R1 6.1(6)); else report to depot.", "R1 6.1(4)(i),(r),(6); R2 7(d)", True),
    ("EL-OH-015", "A", "Regulating equipment", "ATD counterweight", "Counterweight outside marked limits or not moving freely",
     "काउंटरवेट सीमा चिह्न से बाहर / अटका", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R1 6.1(4)(e); R2 7(c); R3 diary 10", True),
    ("EL-OH-016", "A", "Regulating equipment", "Equalizing plate / guide tube", "Equalizing plate tilted or guide tube bent",
     "इक्वलाइज़िंग प्लेट झुकी / गाइड ट्यूब मुड़ी", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R1 6.1(4)(d); R3 diary 10(i),(vii)", True),
    ("EL-OH-017", "B", "Regulating equipment", "SS wire rope", "ATD wire rope strands broken, bird-caged or over-riding the drum",
     "ATD वायर रोप के तार टूटे / बर्ड-केजिंग", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R2 7(c); R3 diary 10(iv)-(vi)", True),
    ("EL-OH-018", "B", "Cantilever", "Bracket tubes / fittings", "Cantilever fittings rusted or damaged, or cantilever out of plumb",
     "कैंटिलीवर फिटिंग जंग लगी / क्षतिग्रस्त / टेढ़ी", "RF-P3 (OHE Cat B)", None, False, DIARY, "R2 7(f)", True),
    ("EL-OH-019", "B", "Jumpers", "Jumper / PG clamp", "Jumper or PG clamp loose, damaged or poorly looped",
     "जंपर / PG क्लैंप ढीला या क्षतिग्रस्त", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R2 7(e),(g); R3 diary 7(iii)", True),
    ("EL-OH-020", "B", "Section insulator", "Runners / assembly", "Section insulator runner worn, flash-marked or greasy",
     "सेक्शन इंसुलेटर रनर घिसा / फ्लैश चिह्न", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R2 7(i); R3 diary 5", True),
    ("EL-OH-021", "A", "Isolator", "Isolator switch", "Isolator blades not fully in, sparking or overheating marks, lock missing",
     "आइसोलेटर ब्लेड पूरा अंदर नहीं / स्पार्किंग / ताला गायब", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R1 6.1(4)(m); R2 7(h); R3 diary 8", True),
    ("EL-OH-022", "A", "Safety fittings", "Boards / screens / anti-climbing", "Danger or caution board, protective screen or anti-climbing device missing",
     "खतरा / सावधानी बोर्ड, सुरक्षा स्क्रीन या एंटी-क्लाइम्बिंग गायब", "RF-P3 (OHE Cat B)", None, False, DIARY, "R1 6.1(4)(f),(8); R3 diary 9(i),(vi)", True),
    ("EL-OH-023", "A", "Level crossing", "Height gauge", "Height gauge at level crossing damaged or unsound",
     "समपार पर हाइट गेज क्षतिग्रस्त", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R1 6.1(4)(g); R2 7 (level crossing)", True),
    ("EL-OH-024", "A", "Current collection", "Pantograph – OHE interface", "Heavy sparking seen when a train passes",
     "ट्रेन गुजरते समय अधिक स्पार्किंग", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC + " Record video if safe.", "R1 6.1(4)(l); R3 diary 9(xii)", True),
    ("EL-OH-025", "A", "Auxiliary transformer", "AT / drop-out fuse", "Auxiliary transformer oil leak or drop-out fuse fallen",
     "सहायक ट्रांसफॉर्मर से तेल रिसाव / ड्रॉप-आउट फ्यूज गिरा", "RF-P2 (OHE Cat A)", None, False, REPORT_TPC, "R1 6.1(4)(j); R3 diary 6", True),
    ("EL-OH-026", "A", "Communication", "Emergency telephone socket", "Emergency telephone socket damaged or not working",
     "आपातकालीन टेलीफोन सॉकेट खराब", "RF-P3 (OHE Cat B)", None, False,
     "Test by calling TPC from each socket; report defective sockets to S&T (R1 6.1(7)).", "R1 6.1(7); R3 diary 9(iii)", True),
    ("EL-OH-027", "C", "OHE conductors", "Contact wire", "Contact wire height or stagger out of limits",
     "कॉन्टैक्ट वायर ऊँचाई / स्टैगर सीमा से बाहर", "RF-P2 (OHE Cat A)", None, True, "Needs measurement (trolley / OHE inspection car); not decidable from a photo.",
     "R2 7(f),(n)", False),
    ("EL-OH-028", "D", "Insulator", "Insulator", "Insulation degradation without visible sign",
     "बिना दृश्य संकेत के इन्सुलेशन क्षरण", "Per TRD", None, True, "Not visual – thermo-vision / testing.", "R3 schedule 9 (thermo vision)", False),
]


def main():
    p = Path(__file__).with_name("taxonomy.json")
    t = json.loads(p.read_text(encoding="utf-8"))
    rest = [c for c in t["classes"] if not c["id"].startswith("EL-OH-")]
    ohe = []
    for (i, cat, asset, unit, en, hi, sev, danger, meas, act, ref, beta) in OHE:
        ohe.append({"id": i, "category": cat, "department": DEPT, "asset": "OHE – " + asset, "focus_unit": unit,
                    "label": {"en": en, "hi": hi}, "severity": sev, "protect_first": False, "needs_measurement": meas,
                    "immediate_action": act, "reference": ref, "beta_enabled": beta})
    for c in rest + ohe:
        c["domain"] = "ohe" if c["id"].startswith("EL-OH-") else ("track" if "Engineering (Civil)" in c["department"] else "other")
        c["danger"] = "track" if c.get("protect_first") else next((o[7] for o in OHE if o[0] == c["id"]), None)
        c["route"] = ("SSE/Bridges" if "Bridges" in c["department"] else {"track": "SSE/P.Way", "ohe": "SSE/TRD (OHE depot)"}.get(c["domain"], c["department"]))
    t["classes"] = rest + ohe
    t["version"] = "2.0-combined-patrol"
    t["scope"] = "Combined foot patrol: track (P.Way) + OHE (TRD). Danger: 'track' = protect line + inform SM; 'ohe' = treat as live, report TPC."
    t["ohe_sources"] = ["RDSO TI/MI/0060 (2022) para 6.1", "CAMTECH/E/17-18/OHE-Inspection/1.0 (draft) section 7",
                        "CAMTECH/E/11-12/OHE-Schedule/1.0 (2011) Foot Patrolling Diary"]
    p.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    b = [c for c in t["classes"] if c["beta_enabled"]]
    print(len(t["classes"]), "classes;", len(b), "beta:", sum(c["domain"] == "track" for c in b), "track,", sum(c["domain"] == "ohe" for c in b), "OHE;",
          sum(c["danger"] == "track" for c in b), "track-danger,", sum(c["danger"] == "ohe" for c in b), "OHE-danger")


if __name__ == "__main__":
    main()
