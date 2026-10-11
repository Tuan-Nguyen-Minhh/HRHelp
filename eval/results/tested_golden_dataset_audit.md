# Assessment evaluation dataset audit

Reviewed on 11 October 2026. Scope: all five DOCX files in `tested_golden_dataset`, current assessment and clarification code, and read-only inspection of the configured policy database. Each DOCX was extracted in full and rendered; all five are readable single-page documents. No source DOCX was modified. No model generation or retrieval run was performed. This review checks compatibility with the implementation and its corpus, not independent legal validity.

## Verdict

All five files are useful sources of employee case facts. None is ready to serve unchanged as a complete golden reference for case assessment. They are disciplinary meeting minutes with narrative findings and management proposals, whereas the assessment model produces an evidence-based case assessment with condition analysis, citations, risk, procedure status, and a structured handoff.

Employee facts are supplied by HR; they are not expected to already exist in the policy corpus. Their compatibility depends on whether the exact facts reach the model and whether the reference uses the applicable corpus rules.

## Verified policy context

The live HR citation corpus contains 18 NQCT chunks, not all the expanded internal-policy text present in repository Markdown and chunk artifacts. Its policy name is `Nội quy lao động HRCorp`, code `NQCT`, effective from 1 January 2026. All five DOCX files name Công ty TNHH An Phát and cite unnamed sections of that company's rules. Explicitly establish An Phát as a fictional alias for this policy in evaluation fixtures, or supply the actual applicable An Phát policy. Do not silently treat the two as interchangeable.

Relevant live NQCT provisions:

- Article 3: morning shift begins at 08:30; normal workweek is Monday through Friday.
- Article 7: workers must use and maintain provided personal protective equipment.
- Article 11: written reprimand for first offenses meeting specified conditions. These include lateness or early departure of at least 15 minutes more than three times in one working month without justified reason; unauthorized departure from the workstation for more than 60 minutes in a shift; failure to complete assigned duties through subjective fault with no material damage or damage below VND 5 million; and one day's unauthorized absence.
- Article 13: unauthorized absence of five cumulative days in 30 days or 20 days in 365 days, without justified reason. The text identifies examples of justified reasons.
- Articles 14 and 15: recording violations and disciplinary meeting procedure.

The live version metadata marks ND145_2020 as ending on 9 September 2026 and ND283_2026 as beginning on 10 September 2026. The code places ND283 passages in the administrative-penalty layer, not the employee-sanction layer. Pin this corpus state when building expected answers. These are implementation observations, not a verification of whether the version metadata accurately reflects law.

## File reviews

### 01 Unauthorized absence

Source: `tested_golden_dataset/01_Bien_ban_nghi_khong_phep.docx`.

- Family: `UNAUTHORIZED_ABSENCE`.
- Facts: Nguyễn Văn An, EMP-005, software engineer, engineering department; absent on 5–9 October 2026, five working days; no leave request or prior notification; attendance records and manager correspondence; employee says family matters caused the absence and promises supporting documents.
- The five dated absences fall within 30 days. Preserve the dates and explicitly validate any normalized count/window in confirmed facts.
- The reason's justification is unresolved. Do not turn 'family matters' into either a proven justified reason or a proven absence of justified reason.
- Contract type is absent. Whether a formal explanation request has already been sent is not explicit; requesting further explanation in the minutes is not proof of an earlier completed send action.
- Relevant evidence targets: NQCT Articles 4 and 13, corresponding legal conditions, and procedure evidence as applicable.
- Candidate expected behavior: recognize the count/window, identify the unresolved justification condition, request relevant evidence, and avoid an unconditional dismissal recommendation. The document's cautious finding is directionally useful but lacks traced rule analysis.

### 02 Lateness

Source: `tested_golden_dataset/02_Bien_ban_di_muon.docx`.

- Family: `LATE`.
- Facts: Trần Thị Bình, EMP-012; four late arrivals on 5, 6, 8, and 12 October 2026; scheduled start 08:30; arrivals 08:50, 08:45, 09:00, and 08:55.
- Arithmetic is correct: 20 + 15 + 30 + 25 = 90 minutes. Every occurrence meets the live policy's at-least-15-minute condition, and four is more than three in a month.
- The 08:30 start matches the live database. Older repository Markdown uses different hours and thresholds; do not use that older text to label this case.
- Contract type, first-offense history, and completed explanation-request status are absent. Personal scheduling difficulties should be evaluated rather than silently converted into a legally conclusive reason classification.
- Relevant evidence targets: NQCT Articles 3 and 11, applicable legal and procedural passages.
- Candidate expected behavior: explicitly analyze Article 11's conditions. If first-offense and remaining conditions are confirmed, assess the written-reprimand provision; otherwise identify the missing condition. 'No decision issued yet' does not mean no disciplinary recommendation is supportable.

### 03 Late report submission

Source: `tested_golden_dataset/03_Bien_ban_cham_nop_bao_cao.docx`.

- Family: `GENERAL`, not a separate dedicated late-report family.
- Facts: Lê Văn Cường, EMP-021; report assigned on 1 October, due at 17:00 on 9 October, submitted at 10:00 on 13 October; no extension requested before the deadline; source emails exist; no monetary loss recorded; timing of supporting documents and responsibility remain to be verified.
- Preserve the assignment, deadline, submission times, employee explanation, and unresolved responsibility in the initial case description. A short `violation_summary` alone may lose decisive details.
- Contract type and first-offense history are absent. The minutes recommend additional explanation but do not clearly establish a previously sent formal request.
- Relevant evidence target: NQCT Article 11's subjective-fault/non-completion condition, plus applicable legal and procedural passages. Do not assume a standalone report-deadline policy absent from the live corpus.
- Candidate expected behavior: distinguish a proven delay from proven subjective fault. Identify the need to verify when supporting documents became available and who was responsible before applying that sanction condition.

### 04 Leaving workstation

Source: `tested_golden_dataset/04_Bien_ban_roi_vi_tri_lam_viec.docx`.

- Family: `GENERAL`.
- Facts: Phạm Thị Dung, EMP-034; away from the support desk from 14:00 to 15:10 on 14 October 2026; no prior permission/notification or handover; shift logs and employee statement; three support requests delayed; break schedule remains to be checked.
- Duration is 70 minutes, exceeding the live Article 11 threshold of 60 minutes. The document's generic handover-section citation is not an exact citation to the live rule.
- Contract type, first-offense history, and explanation-request status are absent. Preserve the unresolved break-schedule question.
- Relevant evidence target: NQCT Article 11's unauthorized-departure provision, plus applicable procedure evidence.
- Candidate expected behavior: analyze permission, in-shift duration, first-offense status, and the unresolved break question. Do not assert that the only possible response is recording a commitment and sending the file to HR. A report may discuss a conditional supported sanction even while finalization remains blocked.

### 05 Protective equipment

Source: `tested_golden_dataset/05_Bien_ban_khong_tuan_thu_an_toan.docx`.

- Family: `GENERAL`.
- Facts: Hoàng Văn Em, EMP-047; entered goods-receiving area at 09:15 on 15 October 2026 without wearing issued safety shoes; supervisor stopped work; employee put on the equipment before continuing; issue record and supervisor confirmation; no accident or property damage recorded.
- The duty to use supplied PPE matches live NQCT Article 7. The inspected 18-article internal corpus does not give a PPE-specific sanction mapping.
- Contract type and explanation-request status are absent. Training details are unresolved. The report should distinguish confirmed provision of shoes from unresolved training or equipment-condition questions.
- Relevant evidence targets: NQCT Article 7 and any actually retrieved relevant legal provisions. A duty provision by itself does not establish a particular employee sanction.
- Candidate expected behavior: explain the duty and incident, avoid inventing a PPE-specific disciplinary level, and identify the evidence needed for further action. Retraining may be a management recommendation; do not call it a mandatory retrieved procedure unless a passage supports that claim.

## Input compatibility gaps shared by the files

The catalog requires `contract_type`, `minutes_made`, and `explanation_requested` for every family. Absence additionally requires `absence_days` and `notice_form`; lateness requires `late_days`; general cases require `violation_summary`. Facts must be confirmed.

None of the five files states contract type. Through the normal chat workflow, the system must ask for that fact before entering case-assessment retrieval. The files can therefore support clarification tests now, but need supplemented confirmed inputs for an end-to-end assessment evaluation. Do not invent contract type to make a fixture pass.

These DOCX files can establish that minutes exist only if the test snapshot is after these minutes were created. If the scenario is asking the model to create the first minutes, using these completed minutes as input leaks later workflow facts. Similarly, employee explanations and recommended requests do not automatically prove that the formal explanation request was already sent.

Use incident dates from the event narrative, not the meeting dates. For multi-day events, choose and document the fixture's incident-date convention and preserve the full date range. The documents include dates after the review date; they should be treated as simulated future scenarios or assigned an explicit later assessment time.

The assessment synthesis payload is constructed in `src/features/answer/model/synthesis.py::_payload`. It includes question, initial description, family, event date, employee name, confirmed facts, fact lines, and categorized passages. It does not include the entire conversation transcript. Non-catalog details such as exact arrival times, employee explanations, witness statements, harm, and break schedules must survive in the description or supported fact text. Information existing somewhere in chat is not sufficient evidence that the assessment model saw it.

Employee code, department, job title, company address, participant names, meeting time, and signatures are not dedicated fields in that synthesis payload. They are available only if retained in the supplied narrative; do not require the model to reproduce unseen metadata.

## Converting the files into golden assessment samples

For each source document, create separate records for:

1. Input: neutral incident narrative, event date, confirmed catalog facts, unknown facts, and relevant employee explanations/evidence. Exclude the document's assessment and management proposal from model input when those are the target being evaluated.
2. Expected reference: independently reviewed condition analysis, applicable rule evidence, justified conclusion, risk, and next steps. Include supported alternatives where a unique answer is not warranted.
3. Structured expectations: assessment status, proposed sanction or null, missing conditions, required evidence, and finalization restrictions. Distinguish model assessment status from API case status and from the application sanction lock.
4. Runtime output: actual retrieved passages and `answer.message` from that execution, plus relevant API fields. Do not fill retrieved contexts with passages the model did not receive.

If testing generation alone, freeze the full input payload and evidence. If testing retrieval plus generation, freeze the corpus/version snapshot and expected evidence, then capture actual retrieved contexts at runtime. Missing retrieved support and missing true case facts are different failure types.

The assessment prompt requests `BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC`, sections I–XI, whereas these documents use `BIÊN BẢN XỬ LÝ VI PHẠM KỶ LUẬT`, two sections, meeting participants, and signature blocks. Evaluate substantive assessment content, not matching the existing meeting-minutes template. Do not use management proposals as authoritative evidence for the recommendation.

All five source documents avoid a finalized disciplinary decision. Add supported-sanction cases and boundary pairs to avoid rewarding an evaluator/model that always abstains. Examples grounded in the live corpus include three versus four qualifying late arrivals, 60 versus 70 minutes away, first offense versus an established recurrence, and unresolved versus verified absence justification. Five cases are a useful pilot, not sufficient coverage for a broad quality claim.

## Code evidence

- `src/features/clarify/model/catalog.py`: required fields and the three supported case families.
- `src/features/clarify/model/graph.py::route_after_extract`: confirmation gate before assessment retrieval.
- `src/agents/handoff.py::CaseHandoff`: confirmed-fact and passage contract.
- `src/features/answer/model/synthesis.py::_payload`: exact assessment-model context.
- `src/features/answer/model/synthesis.py::SYSTEM_PROMPT`: condition analysis and eleven-section report expectations.
- `src/features/answer/model/assessment.py`: structured assessment schema.
- `src/features/answer/model/draft.py::draft_answer`: report used as the final message when present.
- `src/features/answer/model/decide.py::_blocked`: conditions that keep the application sanction unset.
- `src/features/answer/model/layers.py`: distinction between employee-sanction evidence and administrative penalties.
