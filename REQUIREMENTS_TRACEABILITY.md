# Job-description alignment & implementation plan

The source PDF contains three pages describing an AI Engineer Intern role at Edxso. It contains no assigned product, API contract, dataset, deadlines or acceptance criteria. This document separates actual role statements from the approved project scope; it does not claim the PDF specified this app.

## Confirmed decisions

1. User approved the recommended education assistant + conversational analytics project.
2. User chose a hosted LLM.
3. User selected Google Gemini.
4. A Gemini credential was supplied in the revision and configured server-side. Live generation is now verified with `gemini-3.1-flash-lite`; real school data and cloud credentials were not supplied. The app retains labelled sample data and an explicit non-LLM fallback.

## Relevant statements, mapped line by line

| Source | Statement / intent | Project evidence / limit |
|---|---|---|
| Page 1, About the organisation | Education consulting, improved academic outcomes, leadership and institutional growth | Education-focused FAQs and enquiry insights. The app does **not** claim to improve academic outcomes or provide institutional diagnostics on its own. |
| Page 1, Role summary | Build and deploy intelligent systems | Runnable Python app, Dockerfile and staging instructions. No external cloud deployment claimed. |
| Page 1, Role summary | Conversational automation | Gemini-assisted FAQ answers with retrieved school context, transparent fallback, suggested questions and feedback. Single-turn processing is disclosed. |
| Page 1, Role summary | Data analytics capabilities | Stored conversation analytics, predicted-intent distribution, session counts, response time, feedback and CSV export. |
| Page 1, Role summary | Integrate models into live business systems | Model-serving API and working browser integration. No pre-existing school system was supplied; no ERP/CRM integration is claimed. |
| Page 1, Role summary | Scalable solutions and production workflows | Modular boundaries, API validation, timeouts, concurrency cap, Docker health check and readiness checklist. SQLite/single-worker architecture is explicitly a demo/staging constraint. |
| Page 2, responsibility 1 | Design, train and evaluate classification/NLP models | TF–IDF + Logistic Regression; 135 synthetic samples (60 original + 75 added); held-out split; accuracy, macro F1, per-class report and confusion matrix. |
| Page 2, responsibility 2 | Integrate AI into backend and user-facing platforms | FastAPI endpoints, server-only Gemini adapter and responsive browser UI. |
| Page 2, responsibility 3 | Feature engineering, model testing, iterative refinement | Word n-grams, stop-word removal, sublinear TF–IDF; classifier tests; word-vs-character experiments. A failing fee-intent regression was corrected by improving preprocessing. |
| Page 2, responsibility 4 | Modular code and documentation | Separate `ml`, `provider`, `store` and API modules; frontend assets; README; API docs; this traceability file. |
| Page 2, responsibility 5 | Staging deployment and performance monitoring | Container recipe and staging checklist; health endpoint; stored latency, answer mode and helpfulness. No live cloud staging or external monitoring system claimed. |
| Page 2, responsibility 6 | Research and experiment with new ML techniques | Reproducible 3-fold comparison of word TF–IDF and character n-grams. Larger validation set required before adopting a more complex model. |
| Page 2, responsibility 7 | Troubleshoot/debug development and test issues | 151 automated tests, browser smoke script, explicit provider-error fallback, captured test report and known limitations. |
| Page 2, required skills | Python and scikit-learn / TensorFlow / PyTorch | Uses Python and scikit-learn. The PDF lists alternatives; TensorFlow/PyTorch are unnecessary for this small classifier and are not added gratuitously. |
| Page 2, required skills | Preprocessing and evaluation metrics | Input validation, contact-detail redaction, TF–IDF pipeline, stratified split and no feature leakage in evaluation. |
| Page 2, required skills | NLP and conversational AI interest | Intent classification, lexical retrieval and hosted Gemini generation. |
| Page 2, required skills | Clear written/verbal communication | Written architecture, setup, limitations and an understandable UI. No verbal assessment is claimed. |
| Page 2, preferred skills | NLP libraries, e.g. NLTK / spaCy / Hugging Face | Uses scikit-learn NLP primitives. Listed optional libraries are not falsely claimed as used. |
| Page 2, preferred skills | AWS / GCP / Azure familiarity | Generic container-host deployment guidance. No cloud resources created; hosting choice and credentials are still needed for actual deployment. |
| Page 2, preferred skills | APIs or microservices for model serving | FastAPI model-serving and feedback API, OpenAPI schema and self-contained API reference. |
| Page 2, preferred skills | Data pipelines and experimentation frameworks | Versioned JSON training data, leakage-safe sklearn Pipeline, deterministic evaluation and cross-validation experiment script. No heavyweight external experiment tracker is claimed. |

## Non-software statements

- Position, Delhi hybrid attendance, six-month duration, ₹7,000 stipend and academic eligibility describe employment conditions, not app features.
- Selection/technical evaluation and personal commitment are applicant obligations, not requirements that software can satisfy.
- Collaboration, mentorship, full-time transition, certificate and professional reference are organisational outcomes; this project cannot deliver or guarantee them.
- PDF text contains apparent typography/OCR issues. These were not treated as technical specifications.

## Delivery phases and completion

1. **Read and clarify** — completed: full PDF extracted; project and provider approved.
2. **Design data and ML** — completed: synthetic FAQs, intent data, retrieval and classifier.
3. **Build backend** — completed: Gemini adapter, storage, API, protected analytics and privacy controls.
4. **Build UI** — completed: overview, assistant, knowledge, model lab and settings; desktop/mobile layouts.
5. **Validate** — completed for local demo: API/ML/provider tests and browser smoke checks. Live Gemini is verified: all 8 canonical FAQ source/mode/intent checks passed; unknown query remains no-match.
6. **Package and document** — completed: source package, environment template, Dockerfile, README and testing report.
7. **Deploy to cloud / connect real data** — not performed; requires hosting selection, credentials, approved school data and production-readiness work.


## Revision 1.1 — added engineering evidence

- **Classification/NLP refinement:** 75 additional labelled synthetic examples, preserved original 15-example test partition, dataset fingerprint, malformed/duplicate-data tests and all-FAQ intent regressions. No real-world model-performance guarantee.
- **Backend integration:** explicit Pydantic contracts, Bearer security schema, request-size protection, typed provider failures, pooled HTTP client, bounded generation/queue and threadpool storage offload.
- **Deployment/monitoring:** separate readiness check, process-local provider health and timestamped live-generation diagnostics. Actual container/cloud deployment is still not claimed.
- **Testing/debugging:** 132 offline automated tests, measured backend coverage, desktop/mobile live/offline workflows and 11 browser resilience check groups.
- **Scalability within demo scope:** SQL aggregation, bounded recent results, paginated history and streaming export instead of full Python-side loads. Production load testing and external monitoring still required.
- **Documentation/communication:** updated README, self-contained 13-endpoint reference, sanitized evidence artifacts and CI configuration.
- **Code quality:** Ruff/ESLint/Prettier gates, pinned runtime/development dependencies, advisory scans and no secrets in exported source.

Employment eligibility, internship conditions and benefits remain non-software statements; optional technologies not used are not falsely claimed as implemented.


## Final v1.2 review

All 3 original PDF pages were re-read. The 7 page-2 engineering responsibilities are individually mapped in `PDF_COMPLETION_AUDIT.md`. This pass added protected runtime/model/database monitoring, safe backup/restore tooling, an operations runbook and a real knowledge-base diagnostic regression fix. Final checks: 151 automated tests, 12 browser resilience groups, actual backup/restore verification and all 8 live Gemini canonical FAQ checks passed. Preview deployment is verified; external cloud deployment, Docker execution, official school data and institutional production/security policies are still not fabricated or claimed as complete.
