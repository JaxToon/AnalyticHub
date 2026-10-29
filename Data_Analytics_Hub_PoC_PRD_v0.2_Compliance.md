# Bank Data & Analytics Hub — Product Requirements Document (PRD)

**Document status:** Draft for discovery / PoC — revised for metadata-only AI dashboard generation and Indonesia regulatory review  
**Version:** 0.2  
**Date:** 28 October 2026  
**Product owner:** To be appointed by Bank  
**Executive sponsor:** To be appointed  
**Audience:** Business divisions, Central Data Office, Data Platform, BI/Analytics, Enterprise Architecture, IT, Information Security, Risk, Privacy, Legal & Compliance, Internal Audit as applicable

> **Important assurance note:** This PRD is a product-design proposal, not a legal opinion, regulatory interpretation, security accreditation, or certification of compliance. Production scope must pass Bank's applicable architecture, security, privacy, risk, legal/compliance, procurement, vendor, records-retention, and change-management reviews. The PRD intentionally uses approval gates and leaves bank-specific policies, control owners, locations, retention periods, and approval matrices to be confirmed by Bank.

---

## 1. Executive summary

Bank Data & Analytics Hub is a proposed enterprise front door for finding and using trusted data assets and analytics services across Bank. Version 0.2 adds a bounded **AI Dashboard Generator** capability to the existing governed discovery and request experience. The Hub will provide:

1. Discovery of approved datasets, data products, business terms, KPIs, dashboards, reports, and accountable data owners.
2. An enterprise data dictionary / business glossary with definitions, provenance, freshness, quality information, classification, and permitted-use guidance.
3. A structured request and approval workflow for data access, new datasets, dashboards, reports, analyses, and data-quality issues.
4. A transparent request lifecycle and My Workspace for status, decisions, fulfilment, output references, and audit evidence.
5. A Tableau gallery that catalogs and links to approved existing dashboards; secure embedding remains conditional on the required technical, licensing, and security reviews.
6. An AI Dashboard Generator that accepts a business question and **approved metadata only**, proposes KPI/chart/layout specifications, and renders an interactive preview using clearly labelled synthetic data.

### 1.1 Foundational assumption

This PoC assumes an approved non-production environment, a designated identity and access-management path, an approved source for metadata, and named data owners for the pilot scope. The Hub does **not** replace the bank's lake/lakehouse, Enterprise Data Warehouse (EDW), Tableau, identity provider, IT Service Management (ITSM), data catalog, or approved access-provisioning system.

The first AI Dashboard Generator release is deliberately metadata-only. It will not connect to a production database, read customer/transaction records, execute generated SQL, or publish AI-generated dashboards to a production BI platform. Real Bank metadata may be used only after its classification, visibility, storage, and model-processing path have been explicitly approved. Until then, development and demonstrations use synthetic metadata and synthetic sample data.

If the shared data platform, catalog, ownership, approved model gateway, or identity assumptions are not true, the PoC must record the dependency and use a controlled substitute; it must not simulate a control as if it were implemented.

### 1.2 Product positioning

**Discover → Request → Govern → Generate → Review → (later) Connect**

The Hub is a governed portal and workflow/orchestration layer, not an unrestricted SQL console, raw-data export channel, replacement BI engine, or alternate authorization system. AI-generated dashboards are drafts until reviewed and approved by the responsible business/data owner. Catalog visibility, an approved request, and dashboard generation do not by themselves grant access to underlying data or authorize publication.

### 1.3 Selected PoC direction

- **Scope:** metadata-only in the first release; a database connector is a separately gated future phase.
- **PoC output:** an interactive dashboard preview rendered from a validated dashboard specification and synthetic data. The preview is explicitly marked as non-production and contains no real Bank measures.
- **Metadata baseline:** table names, column names, and data types only. Descriptions, relationships, grain, business definitions, ownership, and classification improve quality but must not be silently invented when absent.
- **LLM policy:** no public/external LLM receives Bank internal metadata by default. Use a Bank-approved model gateway/deployment if available; otherwise use synthetic metadata and a rules-based fallback until the provider and data-processing path are approved.
- **Compliance stance:** this PRD is a control-oriented product proposal, not a legal opinion or compliance certification. Bank Legal/Compliance, Privacy, Information Security, Risk, Data Governance, Architecture, and other assigned control owners determine applicability and approve implementation.

## 2. Problem statement and hypotheses to validate

The product aims to test whether one governed front door can reduce friction across a federated data ecosystem. During discovery, validate the following hypotheses rather than assume they are proven Bank conditions:

- Users may not know whether a data asset or dashboard already exists.
- Business terms and KPI definitions may vary across teams or artifacts.
- Requests may be received via multiple channels, making intake quality, prioritization, and auditability inconsistent.
- Existing Tableau workbooks/views may be difficult to discover outside their creator's team.
- Data and analytics teams may repeat similar work because reusable output is not catalogued.
- Requesters may have limited visibility into ownership, approval, delivery status, or expected completion.

### 2.1 Desired outcomes

- More discoverable and reusable enterprise data/analytics assets.
- Consistent business definitions and clearer data ownership.
- Transparent request lifecycle and service prioritization.
- Reduced duplicate requests and dashboard development.
- Stronger evidence of approval, access provisioning, and control execution.
- No weakening of existing data permissions or Tableau authorization controls.

## 3. Goals and non-goals

### 3.1 Goals

- Provide an authenticated portal to search and navigate approved data/analytics assets.
- Publish approved catalog and business-glossary metadata from the designated system of record where available.
- Provide a structured request lifecycle with assignment, approvals, fulfilment, requester visibility, and audit evidence.
- Catalog existing Tableau content by default using canonical links while preserving Tableau's own authorization.
- Add a bounded AI Dashboard Generator that turns a business question plus approved metadata into a validated dashboard specification, candidate KPI/chart definitions, filter suggestions, and an interactive synthetic-data preview.
- Make assumptions, missing metadata, confidence, unsupported requests, and draft status visible to users.
- Preserve least privilege, data minimization, confidentiality, traceability, and human accountability.
- Measure usefulness and reliability of metadata-to-dashboard generation separately from business-data correctness, which cannot be evaluated without real data and approved KPI definitions.

### 3.2 Non-goals for PoC / MVP

- Replacing the central data platform, EDW/lake/lakehouse, Tableau, enterprise SSO/IAM, ITSM, or authoritative catalog/governance systems.
- Connecting the initial AI Dashboard Generator to production databases or reading real customer, account, transaction, employee, or other production records.
- Executing generated SQL, allowing arbitrary user SQL, enabling unrestricted cross-domain joins, or exporting restricted data.
- Treating metadata as automatically non-sensitive; dataset/column names, descriptions, lineage, and schema relationships must be classified.
- Sending Bank internal metadata, prompts, generated specifications, query text, or outputs to an unapproved external model/provider.
- Allowing an LLM to determine user permissions, make access decisions, approve business definitions, or publish a production dashboard without the prescribed human/control workflow.
- Treating synthetic preview values as actual bank data, evidence of a business trend, or proof that a KPI is correct.
- Allowing generated code or SQL to execute directly. The MVP uses a constrained JSON dashboard specification and a controlled renderer.
- Replacing bank-specific regulatory mapping, legal interpretation, security accreditation, internal audit, or production change approval with this PRD.

## 4. Personas and roles

| Persona / role | Core need | Key permissions (subject to Bank policy) |
|---|---|---|
| Business requester | Find existing assets or request data/analytics outcomes | Search permitted metadata; submit and track requests; access only approved output |
| Data consumer / analyst | Find definitions, understand lineage and reuse curated assets | Browse catalog; request asset access; use data only under approved purpose and entitlement |
| Data owner (domain) | Manage domain meaning, quality, intended uses, and approvals | Maintain/approve domain metadata; make access decisions where assigned; validate definition and quality |
| Data steward | Maintain definitions, glossary, ownership and quality metadata | Edit assigned glossary/catalog fields; raise quality issues; no implicit access to data contents |
| Central Data Platform / Engineering | Operate integrations, pipelines, observability, and platform standards | Manage approved technical integrations and pipeline metadata; privileged activities logged and separated |
| BI / Analytics service owner | Manage dashboard/report/analytics demand and delivery | Triage and deliver assigned services; publish output metadata and service status |
| Governance / Security / Privacy / Risk / Legal & Compliance | Review controls based on policy, asset class, processing purpose, and risk | Perform assigned reviews; no blanket access unless required and authorized for the role |
| Portal administrator | Maintain service catalog, routing, categories, and operational settings | Administer workflow/configuration; does not automatically gain data-content access |
| Auditor / control tester | Obtain evidence within authorized scope | Read relevant immutable/controlled audit evidence under approved procedures |

Role membership and approval authority must be sourced from approved enterprise identity / access-management processes. Portal administration must be segregated from authorization to view restricted data.

## 5. Product principles

1. **Search before request.** Check the catalog and Tableau gallery for an existing fit before creating new work.
2. **One front door, multiple systems of record.** Integrate existing approved systems instead of cloning their critical control logic.
3. **Least privilege by default.** Searchable metadata is not equivalent to access to dataset contents.
4. **Business ownership stays explicit.** Each published data product has a named accountable owner and appropriate steward.
5. **Approval is not provisioning.** Distinguish decision, technical provisioning, user confirmation, and closure.
6. **Controls are risk-based, not bypassed for speed.** Use conditional, policy-driven review paths; do not hard-code universal auto-approval.
7. **Sensitive payload minimization.** Requests should contain business context, not customer records, account numbers, credentials, or unnecessary sensitive values.
8. **Traceability by design.** Capture requester, purpose, asset, decision, reviewer, timestamp, provisioner, lifecycle, and output reference.
9. **No silent duplication.** Reuse or link to existing data product, dashboard, or report when fit-for-purpose.
10. **Human accountability.** Automated routing or validation supports, but does not replace, required owner/control decisions.

## 6. Scope and release approach

### 6.1 Phase 1 — Metadata-only PoC (selected scope)

- SSO/role-aware access in an approved non-production environment, or a documented mock identity only for isolated local demonstration before SSO integration.
- Explore Data, data dictionary, selected Tableau gallery, Request Center, My Workspace, and audit-event capture for the agreed pilot scope.
- AI Dashboard Generator accepts a business question and a controlled metadata package (table/column names and data types; optional approved descriptions/relationships).
- Produce a schema-validated dashboard specification: title, candidate KPI definitions, chart types, field mappings, filters, aggregation intent, assumptions, missing-information questions, and confidence/validation status.
- Render an interactive preview using synthetic data generated for the preview only. The UI must display a persistent `SYNTHETIC DATA — NOT Bank ACTUALS` label.
- Provide a rules-based fallback or safe failure path if model access is not approved, unavailable, or fails validation.
- Do not use a database connector, execute generated SQL, ingest production data values, or publish directly to Tableau.
- Run compliance screening, metadata-classification review, threat modelling, and required security/privacy reviews before using any genuine internal Bank metadata or a hosted model service.

### 6.2 Phase 2 — Controlled metadata pilot (conditional)

- Connect to a designated catalog or approved metadata source using read-only, least-privilege API credentials.
- Permit selected Bank metadata only after the data owner and relevant control owners approve metadata fields, classification, purpose, user groups, hosting location, provider/model, retention, and logging behavior.
- Show source and last-sync timestamp, stale/failed sync status, field-level visibility rules, and metadata owner.
- Add controlled business descriptions, table relationships, grain, approved KPI definitions, and permitted-use notes to improve chart selection.
- Enable the approved model gateway/provider only after provider, contract, data-processing, location, subprocessor, security, privacy, exit, and model-retention terms are cleared as applicable.
- No customer/transaction row data and no executable query path in this phase unless separately approved through a new scope and release gate.

### 6.3 Phase 3 — Governed data execution (separate approval and PRD change)

- Add a database/query connector only after architecture, data governance, data-owner, Security, Privacy, Risk, Legal/Compliance, operational, and any applicable OJK approval/notification requirements have been resolved.
- Use server-side allow-listed query templates or a constrained query planner; enforce authenticated user entitlements at query time, not only at dashboard design time.
- Use read-only identities, approved views/data products, row/column-level restrictions where applicable, query timeouts, resource limits, result-size thresholds, small-cell disclosure controls, and audit events.
- Validate business KPI formulas with accountable owners before use. Never infer official business definitions from column names alone.
- Keep query execution, actual data retrieval, and Tableau publication disabled by feature flag until the separate gate is passed.

### 6.4 Conditional / follow-on scope

- Secure Tableau embedding using Tableau Embedding API v3, only after deployment/version, identity model, licensing, configuration, security, and content-owner approval are confirmed.
- Metadata synchronization through approved Tableau or catalog APIs, including stale/error handling and allowed metadata visibility.
- Integration to existing ITSM/workflow and approved access provisioning systems.
- Advanced lineage, data-quality views, certified data-product marketplace, semantic search, and privacy-reviewed usage analytics.
- Controlled database execution and publication, subject to Phase 3 approval and a revised threat model.

### 6.5 Out of scope until separately approved

- Public or internet-facing access; production data export; unrestricted SQL; cross-domain joins; autonomous publication; and AI-generated business conclusions over confidential/restricted data.
- Unapproved external LLM/API use or cross-border transfer/processing that has not passed applicable bank and legal reviews.
- Real customer/transaction data in PoC fixtures, logs, prompts, evaluations, screenshots, or synthetic-data generation.
- Impersonation of privileged users, shared administrator/service-user dashboard access, or any permission bypass.
- Automatic access approvals or automatic certification of datasets, KPI definitions, and dashboards.

## 7. Information architecture and key screens

### 7.1 Homepage

- Global search and guided entry points: Explore Data; Request Center; Analytics Hub; My Workspace.
- Recently viewed / frequently used permitted assets where privacy and telemetry rules permit.
- My requests: items needing requester action, awaiting decision, in progress, delivered, rejected, or closed.
- Service announcements and planned maintenance only from authorized sources.

### 7.2 Explore Data / Catalog

Search scope includes approved metadata for datasets, tables, data products, business terms/KPIs, owners, dashboards/reports, and approved documentation. Results show only fields approved for discovery. Sensitive asset names or metadata may themselves be restricted; visibility must follow classification rules.

Asset detail includes:
- Name, type, description, domain, owner and steward.
- Business definitions and approved synonyms.
- Source system, approved lineage/provenance, grain, primary identifiers where appropriate (not sensitive example values).
- Classification, allowed-use notes, known restrictions, retention class where applicable.
- Refresh/freshness, quality status, SLA, last successful update where safe to disclose.
- Related data products, glossary terms, KPIs, dashboards and reports.
- Request access CTA, which starts the governed workflow rather than opening data by default.

### 7.3 Data Dictionary / Business Glossary

The glossary must distinguish business terms from physical data fields. A term page should include: preferred term, business definition, owner, steward, synonyms, domain, approved formula or methodology where applicable, related physical assets, version/effective date, review status, and dispute/escalation path. Physical field entries should include source, data type, description, nullable/valid values where approved, sensitivity classification, quality rule references, lineage references, and downstream products.

Definitions such as NPL, customer, active account, outstanding balance, revenue, or delinquency must not be invented by the portal team. The designated business owner approves the official Bank definition and methodology.

### 7.4 Analytics Hub — Tableau and existing report gallery

- Browse and search approved existing Tableau workbooks/views.
- Display title, description, owner/contact, business domain, tags, certification/review status, last-updated metadata if available, target audience, and URL.
- Provide a direct link for MVP; only show embedded content if the user is authenticated and authorized using the approved Tableau path.
- Do not proxy dashboard data through the portal unless a separately approved architecture requires it.
- Preserve content-owner and site/project permissions; the portal's catalog listing does not override the underlying Tableau access check.
- Support lifecycle status (published, under review, deprecated, retired) only from an authoritative source or approved workflow.

### 7.5 Request Center

Users select a service type and are shown only the relevant fields. Required information is minimized and purpose-driven. The request must not require the requester to know physical table names or SQL.

### 7.6 My Workspace

Shows requests and outcomes available to the logged-in user based on role. Fields include request ID, service type, short title, requester, assigned team, current status, due/target date where defined, last update, outstanding action, decision evidence/reference, and approved result link. Request history and output links are protected according to their own classification and authorization.

### 7.7 Admin / Service Management

- Service catalog, form schema, routing rules, risk-based review conditions, SLA/priority policy, team queues, escalation rules, and status dictionary.
- No admin control may bypass access policy or approval controls.
- Changes to routing, approvals or entitlements must be versioned and audited; high-risk changes require the bank's change approval process.

### 7.8 AI Dashboard Generator

The generator is a guided draft-creation tool. It must separate business intent, metadata matching, dashboard specification, synthetic preview, and (in a later separately approved phase) data execution.

- **Input:** business question, intended audience/decision, selected domain or approved metadata assets, preferred time granularity where supported, and optional filters. Do not require SQL or physical table names from business users.
- **Metadata discovery:** use only metadata returned by the approved metadata service and visible to the authenticated user's role. Do not let the LLM enumerate hidden tables or bypass catalog permissions.
- **Metadata-only constraints:** when only names and types exist, show candidate mappings and ask the user to confirm ambiguous semantics. Missing facts must remain `unknown`, not be hallucinated.
- **Output specification:** JSON validated against a versioned schema, including allowed asset/field IDs, visual components, metric intent, formula/reference, filters, assumptions, unresolved questions, provenance, generated-at time, model/prompt version where appropriate, and validation result.
- **Renderer:** render only approved component types from trusted templates. Never execute LLM-generated JavaScript, Python, HTML, SQL, or arbitrary code.
- **Preview:** use isolated synthetic fixtures clearly distinguished from actual data. No blending of synthetic and real values.
- **Review controls:** allow user edits and feedback; mark the specification `Draft / AI-generated`; require owner review and required approvals before the dashboard can be certified, published, or connected to data.
- **Safety controls:** treat descriptions, tags, and other metadata values as untrusted input; resist prompt injection; allow-list table/field references; validate output; fail closed on unknown fields or unauthorized assets.
- **No access grant:** generating or saving a draft does not grant rights to the underlying dataset or Tableau view.
- **Audit:** record user, purpose/request ID, visible metadata asset IDs, specification version, model/provider identifier (not secrets), validation result, review decision, and relevant timestamps with minimum necessary payload.

## 8. Request types and workflows

### 8.1 Type A — Access to an existing data asset

1. Search catalog and select an asset.
2. Explain business purpose, task/decision, required scope, requested users/group, duration/expiry if applicable, and intended use.
3. Portal validates required fields and policy attributes; it checks existing entitlement where integration permits.
4. Route to the designated data owner and any conditional control approvers required by the approved policy matrix.
5. Record approval/denial and reason. The portal must distinguish rejected, needs-more-information, approved-awaiting-provisioning, provisioned, provision-failed, expired, and revoked.
6. Provision through the system of record (or create a tracked fulfilment task); do not treat approval as proof of access.
7. Confirm effective access using safe control evidence. Notify requester without including sensitive data in email/chat notifications.
8. Store auditable evidence and expiry/review action as applicable.

### 8.2 Type B — Request a new dataset / integration

1. Capture business question, expected decision/outcome, data domain/source if known, frequency, time horizon, grain, freshness, expected consumers, and sensitivity context.
2. Check if an existing catalog asset/data product meets the need.
3. Triage novelty, value, feasibility, risk, regulatory/reporting criticality, reuse potential, and estimated effort.
4. Obtain source owner authorization and relevant architecture / security / privacy / governance reviews as required.
5. Assign delivery owner; document data contract, quality rules, lineage, SLA, permitted-use rules, and acceptance criteria.
6. Build and validate through approved engineering patterns; publish catalog and data product metadata before general discoverability/consumption.
7. Close request with the published asset reference and operational owner.

### 8.3 Type C — Request a dashboard / report

The workflow supports two paths: (a) conventional dashboard delivery by BI/Analytics and (b) AI-generated draft design from metadata. The AI path does not bypass the existing request, owner, data-access, or publication controls.

1. Capture audience, business question, decision supported, KPI definitions if known, dimensions/filters, granularity, refresh needs, intended use, and confidentiality.
2. Search existing Tableau gallery and certified/approved output first; recommend reuse where fit-for-purpose.
3. User may select `Generate a draft from metadata`. The generator receives only approved metadata visible to that user and produces a validated dashboard specification plus synthetic-data preview.
4. Show unsupported/missing fields, ambiguous metric definitions, assumptions, data lineage references, and a clear synthetic-data disclaimer.
5. A dashboard specification is saved as a draft. It is not marked certified, published, or populated with real data by AI alone.
6. For conventional delivery or any later data-connected dashboard, route to BI/Analytics and the responsible data owner. KPI definitions, data source, purpose, access path, sensitivity, and publication destination must be approved as applicable.
7. Any real-data query execution or direct Tableau publication follows a separate implementation/release gate and the bank-approved BI/access architecture.
8. Register approved output metadata and owner/lifecycle in the Hub. Keep author, approver, version, source, and publication references traceable.

### 8.4 Type D — Analysis / data science / insight

Capture question/hypothesis, business decision, cohort/period/grain, audience, intended action, expected output, and use of personal/confidential data. Triage whether existing products answer the question. Analysis executes in an approved environment with access approved independently. Outputs must be reviewed for disclosure, small-cell re-identification, confidentiality, model/risk policies where applicable, and approved distribution method before publication.

### 8.5 Type E — Data quality issue / definition dispute

Capture affected asset, observed issue, business impact, period, evidence without unnecessary sensitive payload, and desired resolution. Route to data product owner / domain steward. Track severity, investigation, remediation, root cause, closure evidence, and glossary change approval when definitions are involved.

### 8.6 Workflow states

`Draft → Submitted → Validation/Triage → Awaiting Information / Awaiting Approval → Approved (awaiting fulfilment) → In Progress → Review/UAT → Delivered → Closed`

Alternative terminal/exception states: `Rejected`, `Cancelled`, `On Hold`, `Provision Failed`, and `Reopened`. Not every request type must use every state. State changes must be recorded, and permitted transitions are role- and policy-controlled.

## 9. Tableau integration requirements

### 9.1 Discovery checklist (must precede implementation choice)

- Is the current deployment Tableau Server or Tableau Cloud? Record exact supported version/release and topology.
- What authentication and enterprise IdP patterns are in use (SSO, SAML/OIDC, MFA, network zones, session lifetime)?
- What license model applies to current and potential embedded use? Confirm with Tableau/platform owner and procurement as needed.
- Which site(s), projects, workbooks, views, groups, and permissions exist? Who is content owner?
- Is content currently available only through intranet/VPN or other network restrictions?
- Which metadata APIs are approved and available? What API credentials/scopes and rate limits apply?
- Which dashboards may be catalogued or embedded, and what metadata is safe to expose to which roles?
- What are the requirements for domain allowlisting, CSP, browser cookies, TLS, logging, and support?

### 9.2 Integration levels

**Level 1 — Catalog + deep link (MVP default)**
- Create a curated inventory of selected Tableau content.
- Use an approved API or steward-managed import to collect only approved metadata; manual metadata can be used temporarily for a limited pilot if clearly marked and maintained.
- Link to Tableau using its canonical URL and rely on Tableau's own sign-in and content permissions.
- Show access/request guidance when a user cannot open the view; do not grant permission via the portal.

**Level 2 — Secure embedded view (conditional)**
- Use Tableau Embedding API v3 if compatible with the actual deployment, supported by the bank's architecture and licensing, and approved by Security.
- Evaluate Tableau Connected Apps (direct trust / OAuth 2.0 trust) or the supported deployment-specific alternative with Tableau administrators. Tableau Cloud UAT support is version-specific; do not assume it is available for Tableau Server.
- Backend-issued token must be scoped and created for the authenticated user according to the approved model. Never hard-code a privileged user's credential/token or share one user's identity with other users.
- Keep Tableau's view/project permissions and applicable row-level restrictions effective. Validate that embedding cannot disclose content to a user who cannot access that view directly.
- Configure embedding domain allowlist, approved CSP, secret storage/rotation, token expiry, error handling, and auditability as relevant.
- Confirm Tableau license terms for the chosen embedding/usage model before implementation and before production.

**Level 3 — Metadata lifecycle automation (follow-on)**
- Synchronize approved workbook/view metadata, owner, project, tags, certified/deprecated status, last refresh/updated metadata, and approved lineage/usage information where available and permitted.
- Handle API errors, deleted or moved views, changed permission, rate limits, sync failures, and stale metadata.
- Keep a visible metadata-sync timestamp and an exception queue. A failed sync must not silently expose stale access claims or mark a dashboard as certified.

### 9.3 Tableau acceptance tests

- User with permission can open an approved dashboard via portal link or approved embed.
- User without permission cannot see restricted content or data through portal, embed, cached content, search snippets, or export.
- Revoked Tableau access is effective at the source and not bypassed by the portal.
- Token/secret is not exposed in browser storage, client logs, URLs, ticket comments, source code, or portal audit messages.
- Only approved portal domains can embed where that control is configured.
- Content catalog listing does not imply access entitlement.
- License model, user attribution and any required per-user token/entitlement behavior have been confirmed.
- Failed Tableau authentication, network error, deleted view, and expired session have clear safe messages without leaking internal details.

## 10. Functional requirements and acceptance criteria

Priority: **P0** = mandatory to pilot; **P1** = desirable for MVP; **P2** = follow-on. Final priorities must be confirmed by product owner and control stakeholders.

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-001 | P0 | Enterprise authentication | Unauthenticated users cannot use portal services; identity comes from approved IdP/SSO; sign-out/session expiry are handled according to enterprise policy. |
| FR-002 | P0 | Role-aware authorization | Search results, metadata fields, request queues, admin pages, comments, and output references are filtered by the authenticated user's role and approved policy. |
| FR-003 | P0 | Global search | Search selected catalog, glossary, data products and Tableau inventory; results show clear asset type and allowed metadata; no sensitive sample data in result snippets. |
| FR-004 | P0 | Data asset detail | Shows owner, description, domain, classification indicator, definition, freshness/quality where available, lineage reference where approved, and governed access path. |
| FR-005 | P0 | Business glossary / dictionary | Definitions have an owner, status, version/effective date and review mechanism; unapproved terms are visibly marked as draft. |
| FR-006 | P0 | Request Center | Requester can submit approved request types with required fields, receives unique request ID, and can view own requests based on authorization. |
| FR-007 | P0 | Workflow and assignment | Requests route to configured queues/owners; every status transition and decision is logged; requester can see next action without seeing restricted internal notes. |
| FR-008 | P0 | Approval evidence | Decisions record approver identity, timestamp, outcome, rationale/reference, and policy path; approval and provisioning are separate states. |
| FR-009 | P0 | My Workspace | Users can view status, assigned/requester action, dates/SLA if defined, comments, and authorized output link. |
| FR-010 | P0 | Tableau gallery | Selected Tableau views are searchable and have canonical links, owner/contact, domain, description and publication/lifecycle status where verified. |
| FR-011 | P0 | No permission bypass | Portal never uses a generic privileged identity to make restricted Tableau content viewable to an unauthorized requester. Negative tests pass. |
| FR-012 | P0 | Audit events | Sign-in outcome, search/request access where policy requires, request changes, approval, assignment, admin change, provisioning and output reference events are logged with controlled access. |
| FR-013 | P0 | Sensitive payload minimization | Forms warn users not to include customer/account identifiers or sensitive records in free text; validation/redaction controls are defined with Security/Privacy. |
| FR-014 | P0 | Security/error handling | No stack traces, credentials, token claims, connection strings or restricted metadata are exposed to users in error messages. |
| FR-015 | P0 | Governance sign-off gates | Production release checklist cannot be completed until required control owners sign off the applicable review items. |
| FR-016 | P1 | Metadata sync | Approved sources can synchronize metadata; sync status and error queue are visible to administrators. |
| FR-017 | P1 | Notifications | Notifications contain minimum necessary details and link to the authenticated portal; sensitive data/results are not embedded in email/chat. |
| FR-018 | P1 | SLA dashboard | Service owners can measure submission-to-triage, approval time, fulfilment time, backlog, reopened/rejected rates and aging. |
| FR-019 | P1 | Dashboard duplicate detection | Request form recommends related existing Tableau views/data products based on metadata and curated synonyms before submission. |
| FR-020 | P1 | Feedback and acceptance | Requester can confirm delivery or record a structured issue/feedback; feedback cannot unilaterally change certified definitions. |
| FR-021 | P2 | Secure embedding | Selected views can be embedded with approved user-specific authentication and no privilege expansion, subject to design review and license confirmation. |
| FR-022 | P2 | Reuse recommendations | Suggest relevant existing assets based on approved metadata/usage telemetry, subject to data privacy and relevance review. |
| FR-023 | P0 | Metadata-only AI dashboard generation | Given an approved metadata package and a business question, produce a schema-valid dashboard specification; no production data rows or database connection are used in Phase 1. |
| FR-024 | P0 | Synthetic preview marking | Every synthetic preview displays a persistent, unambiguous `SYNTHETIC DATA — NOT Bank ACTUALS` label and cannot be confused with a live dashboard. |
| FR-025 | P0 | Structured output validation | Reject or safely repair specifications that reference unknown fields, unapproved assets, unsupported components, or invalid aggregation intents; never execute model-generated code. |
| FR-026 | P0 | Missing metadata / uncertainty handling | Unknown KPI meaning, grain, date semantics, status logic, or aggregation must be shown as an assumption or question and not invented as official business logic. |
| FR-027 | P0 | Model/provider gate | Bank metadata must not be sent to a public/external model by default; provider/model access is disabled until the approved gateway, contract, processing location, logging, retention, and assessment path are cleared. |
| FR-028 | P0 | Metadata-level authorization | Metadata search and generator can use only assets and fields visible under the authenticated user's authorization; unauthorized metadata must not leak via prompts, results, errors, or logs. |
| FR-029 | P0 | Prompt-injection resilience | Metadata text is treated as untrusted input. Embedded instructions cannot alter system policy, expose hidden schema, call tools, or expand permissions. |
| FR-030 | P0 | Draft and human review | AI-generated specifications remain draft; approval/certification/publication requires the assigned owner/reviewer workflow. |
| FR-031 | P0 | Audit and versioning | Record specification version, requester, approved metadata references, model/provider version where applicable, validation status, reviewer/decision, and timestamps with payload minimization. |
| FR-032 | P0 | No Phase 1 query execution | Database connectors, executable SQL, data exports, and direct Tableau publication remain disabled in the Phase 1 configuration; tests confirm they cannot be enabled by ordinary users. |
| FR-033 | P1 | Metadata quality profile | Show availability of descriptions, grain, relationships, ownership, sensitivity classification, lineage, and approved KPI definitions; use missingness to reduce confidence or request clarification. |
| FR-034 | P1 | AI evaluation telemetry | Measure schema validity, field-mapping accuracy against reviewed examples, edit/rejection rate, unsupported-field rate, latency, and safety-test results without storing unnecessary prompt content. |
| FR-035 | P1 | Controlled next-phase query proposal | If added later, proposed query intent must be validated against allow-listed assets and policy; it remains non-executable until Phase 3 is separately approved. |

## 11. Non-functional requirements

### 11.1 Security and privacy

- Authentication, MFA, session lifetime, joiner/mover/leaver processing, and privileged access must follow Bank enterprise IAM policy.
- Enforce least privilege, default deny, segregation of duties, server-side authorization, and separation between portal administration and data-content access.
- Apply data classification to **metadata as well as data values**. Asset/column names, data models, lineage, tags, KPI definitions, and technical error messages can reveal confidential information.
- Use TLS in transit and bank-approved encryption at rest. Use approved secrets management, scoped service identities, key rotation, and network segmentation.
- Never put credentials, access tokens, raw personal data, account identifiers, or confidential customer/transaction records in URLs, ordinary logs, analytics telemetry, or notification payloads.
- In Phase 1, use synthetic data only for chart rendering and evaluation. Do not copy real data into screenshots, test fixtures, logs, prompts, model evaluations, or bug reports.
- Apply secure coding, dependency scanning, SAST/DAST, vulnerability remediation, penetration testing, and change control according to the bank-approved SDLC and risk classification.
- Apply applicable CSRF/XSS/SSRF protections, secure headers/CSP, input validation, output encoding, rate limits, and protections against prompt injection and unsafe model output.
- Establish approved retention, access review, audit-log integrity, legal hold, export control, incident response, backup/recovery, and secure deletion with assigned owners.
- Treat any provider/model, telemetry service, crash-reporting service, or hosted development tool as a potential third party until assessed. Confirm contract, access, location, subprocessors, support access, training-use, retention/deletion, audit rights, incident notification, and exit arrangements where applicable.
- Do not introduce new cross-border processing, hosting, data transfer, or third-party processing without applicable legal, privacy, architecture, security, vendor-risk, and OJK review/approval.
- The applicable legal basis for personal-data processing must be identified and documented under UU PDP; consent is not automatically the only possible basis, nor may the application assume a basis without Legal/Privacy approval.
- A privacy-impact-assessment screening is required before real personal-data processing. Complete a DPIA where the applicable legal/regulatory risk triggers require it, including relevant high-risk or new-technology use cases.
- Maintain a tested incident-escalation process that enables the bank to assess and meet applicable notification deadlines, including the UU PDP Article 46 3 x 24-hour notice requirement where applicable. Legal/Privacy determines recipients, content, and trigger based on the incident.

### 11.2 Availability, performance and resilience

- Business owner, architecture, operations and risk functions must define availability, RTO/RPO, performance and support targets before production.
- Search performance target should be agreed after catalog size, search backend and expected concurrency are profiled; capture p50/p95 latency in PoC.
- The portal must degrade safely if the catalog, Tableau, workflow or IAM integration is unavailable. It must never fail open or grant access because a dependency is down.
- Durable request-state changes should be idempotent where possible; retries must not create duplicate approvals or provisioning requests.
- Backup, disaster recovery, monitoring, on-call, service ownership and recovery runbooks are production prerequisites.

### 11.3 Accessibility and usability

- Responsive layout suitable for enterprise desktop and tablet use, with keyboard navigation and readable contrast.
- Plain-language labels; avoid requiring SQL/table names from business users.
- Use progressive disclosure and conditional forms to minimize request completion time without omitting required control information.
- Clearly distinguish asset visibility, approval status, provisioning status and delivery completion.

### 11.4 Maintainability and interoperability

- Prefer existing approved APIs and systems of record to duplicate metadata, identity, approvals or reporting data.
- Version APIs/configuration and maintain integration ownership, retry/error handling, and deprecation policy.
- Keep portal's data model vendor-neutral where practical; vendor/product choices require enterprise architecture approval.

### 11.5 AI / model governance controls

- Maintain a model/provider inventory, intended-use statement, owner, version, risk tier, approval status, and decommissioning path.
- The LLM is a planning assistant, not an authority for data permission, legal interpretation, official KPI definition, risk decision, or publication approval.
- Use a versioned prompt/template and JSON schema; pin model versions where supported and regression-test material model changes.
- Restrict the model to approved metadata and a narrow generation task. Do not expose arbitrary tools, secrets, direct database credentials, filesystem access, or unrestricted network access to the model.
- Validate each output deterministically before rendering. Unsupported fields and components are rejected, not silently substituted with sensitive or plausible-looking alternatives.
- Show provenance: metadata asset/field references, definition source, unresolved assumptions, and whether the preview is synthetic or live.
- Evaluate reliability, bias/accessibility, hallucinations, prompt injection, disclosure risk, and failure modes before each material release. Keep human review proportional to risk.
- If the approved model gateway is unavailable, fail closed or use the pre-approved deterministic fallback. Do not silently route prompts to another provider/model.

## 12. Data entities (conceptual model)

- **User / Group:** enterprise identity ID, unit, roles, entitlements (reference, not duplicate source of truth).
- **Asset:** asset ID, type, name, description, domain, source system, owner, steward, classification, lifecycle, canonical URI.
- **BusinessTerm:** term ID, preferred term, definition, synonyms, domain, owner, status, version/effective date, related assets.
- **DataProduct:** product ID, purpose, schema/grain reference, quality rules, freshness, SLA, owner, permitted usage, dependencies/lineage references.
- **DashboardAsset:** Tableau site/project/workbook/view identifiers, canonical URL, owner, tags, certification/lifecycle status, sync timestamp, allowed metadata visibility.
- **ServiceDefinition:** type, required form fields, routing policy reference, conditional approval rules, SLA/priority definition, fulfilment team.
- **Request:** request ID, requester, request type, business purpose, requested scope, target asset if applicable, sensitivity attributes, status, priority, dates, assigned team, result reference.
- **Decision:** decision ID, request ID, approver, role, outcome, rationale/reference, timestamp, policy version.
- **FulfilmentTask:** task ID, request ID, system of record, assigned team, provisioning/delivery state, evidence reference, timestamps.
- **AuditEvent:** event ID, actor, action, object, timestamp, result, correlation ID, source system, relevant policy version; payload limited to necessary metadata.
- **SLA / ServiceMetric:** request type, start/stop definition, pause conditions, target, exception reason and calculated duration.

Sensitive content should be held in the appropriate source platform, not duplicated into portal entities unless a separately approved need and architecture requires it.

## 13. Integration architecture

### 13.1 Logical components

- **Web UI:** homepage, search, catalog details, request forms, dashboard gallery, My Workspace, admin.
- **Backend/API layer:** identity/session, search façade, metadata façade, request orchestration, notification dispatch, audit event interface.
- **Workflow layer:** routes and approval policies; may be a bank-approved existing workflow/ITSM system.
- **Metadata providers:** designated catalog/glossary source, approved database or data-product registry, Tableau metadata sources.
- **Identity/access systems:** enterprise SSO, group/role mapping, access provisioning system of record.
- **Data and BI platforms:** existing lake/lakehouse, EDW/marts, Tableau Server or Cloud as identified by discovery.
- **Operations:** monitoring, logging, secrets management, SIEM integration if required, backup/DR, support.

### 13.2 Integration principle

The portal stores request/workflow state and limited searchable metadata only as designed. It must reference, not silently replace, authoritative permissions, dataset contents, KPI definitions, and production approvals. Where a source system remains authoritative, synchronize with clear freshness and failure status.

### 13.3 AI Dashboard Generator architecture (Phase 1)

1. **User request UI:** captures the business question, desired audience, and optional filters without requiring SQL.
2. **Authorization-aware metadata service:** returns only approved metadata fields/assets permitted for that user and use case.
3. **Metadata normalizer:** maps data types into candidate roles (dimension, measure, time, identifier, status) but records these as hypotheses, not official business meaning.
4. **AI planner / rules fallback:** generates a versioned dashboard specification from the allowed metadata and prompt. Model access is available only through an approved gateway/provider; otherwise, use synthetic examples and/or deterministic rules.
5. **Specification validator:** checks JSON schema, asset/field IDs, allowed component types, permitted aggregations, missing definitions, and policy constraints.
6. **Synthetic-data provider:** creates isolated test values for preview only; synthetic fixtures cannot be joined with live sources.
7. **Trusted renderer:** converts the validated specification into prebuilt UI components; arbitrary AI-generated code is never executed.
8. **Review and audit service:** saves a draft, metadata references, validation status, approval/rejection, versions, and minimum necessary audit evidence.

**Explicit Phase 1 boundary:** there is no production database connector, query executor, real data cache, automatic Tableau publication, or model tool that can read data. Query generation, if displayed, is explanatory/non-executable and labelled as a proposal. Future database execution must be added behind separate server-side authorization and a new release gate.

## 14. Security, Indonesian regulatory and assurance checklist

This section is a **design-time applicability and evidence checklist**, not a legal opinion, exhaustive legal register, or statement that the Hub is compliant. The relevant Bank functions must validate the current consolidated regulations, internal policies, asset classification, processing purposes, system role, hosting, vendor/model arrangement, and implementation scope before pilot and again before production.

### 14.1 Required review tracks

1. **Legal and regulatory applicability:** Legal/Compliance maps applicable laws, regulations, OJK approvals/notifications/reporting, bank-secrecy requirements, PSE obligations, and internal policies to specific controls, owners, and evidence.
2. **Technology governance and architecture:** Architecture/Data Platform confirms approved target architecture, dependencies, environments, processing location, network paths, resilience, and relationship to Bank's IT strategy and systems of record.
3. **Information security and cyber resilience:** Information Security performs threat modelling and risk assessment, validates IAM, privileged access, secrets, secure development, vulnerability testing, monitoring, incident response, backup/DR, and third-party access.
4. **Privacy and data protection:** Privacy/Legal establishes controller/processor roles as applicable, purpose, lawful basis, minimization, transparency, rights handling, retention, DPIA screening, vendor/subprocessor processing, data-subject request handling where relevant, breach process, and cross-border-transfer analysis.
5. **Bank secrecy and confidentiality:** The bank's designated functions determine whether requested data/metadata or generated outputs reveal protected customer information or bank secrets, and establish authorized purposes, roles, disclosure boundaries, and procedures under applicable banking law and POJK Rahasia Bank.
6. **Data governance:** Data owners/stewards approve data classification including metadata, official KPI definitions, grain, lineage, asset ownership, permitted use, quality rules, publication lifecycle, and the scope of discoverability.
7. **Third-party / model provider:** Vendor Risk, Procurement, Legal, Privacy, Security, and Architecture assess model/API/cloud providers and tools, including processing location, subcontractors, model training use, retention, deletion, access by support staff, audit rights, incident reporting, service continuity, portability, and exit.
8. **Operational control and audit:** Validate approval, fulfilment, revocation, retention/deletion, incident, model rollback, failed dependency, audit retrieval, and change-control runbooks.
9. **PSE and system administration:** Legal/Compliance determines whether registration, reporting, or other obligations for PSE Lingkup Privat apply to the actual deployment and operating model; do not assume an internal portal is automatically exempt.
10. **Independent assurance:** Arrange control testing or independent review at the tier required by Bank policy and applicable regulation.

### 14.2 Regulatory baseline to validate with Bank Legal/Compliance

| Instrument / source | Why it is relevant to this product | Implementation implication (subject to official interpretation) |
|---|---|---|
| **UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi (UU PDP)** | Applies where the system processes personal data. Metadata can still be personal data if it identifies or can reasonably be linked to an individual; output and telemetry may also contain personal data. | Identify and document the lawful processing basis, purpose, minimization, transparency and rights processes as applicable; implement security, retention/deletion, processor governance, DPIA where required, breach response, and cross-border transfer safeguards. Do not assume consent is the only legal basis or is automatically sufficient. |
| **POJK No. 11/POJK.03/2022 tentang Penyelenggaraan Teknologi Informasi oleh Bank Umum** | Core OJK regulation on bank IT governance, architecture, IT risk, security, IT providers, data/system placement and related obligations. | Treat the Hub as a bank IT change/service requiring risk-based architecture, security, supplier and operational review under Bank's approved governance. |
| **PADK OJK No. 1 Tahun 2026 tentang Penyelenggaraan Teknologi Informasi oleh Bank Umum** (effective 1 March 2026) | OJK implementation guideline to POJK 11/2022. It includes IT governance, risk and security, IT service providers, system/data-processing location matters, data governance and PDP, and internal control/audit. It discusses DPIA for certain elevated-risk processing, including use of new technology. | Map relevant provisions and evidence before use of real internal metadata, model services, connectors or production. Screen the AI use case for DPIA; complete the assessment where required by applicable risk triggers/policy. Assess overseas service/system placement and approvals separately; do not assume all providers are prohibited or that all deployments are permitted. |
| **SEOJK No. 29/SEOJK.03/2022 tentang Ketahanan dan Keamanan Siber bagi Bank Umum** | Cybersecurity and resilience expectations for commercial banks. | Incorporate into threat modelling, incident management, access controls, security testing, third-party risk, resilience and monitoring, as confirmed by Bank control owners. |
| **SEOJK No. 24/SEOJK.03/2023 tentang Penilaian Tingkat Maturitas Digital Bank Umum** | Bank digital maturity assessment includes governance, architecture, risk, cyber, technology, data, collaboration and consumer protection. | Use as a governance alignment/reference where applicable; do not claim that passing this PoC proves bank maturity or satisfies the assessment. |
| **POJK No. 44 Tahun 2024 tentang Rahasia Bank** and applicable banking-law provisions, including UU No. 7 Tahun 1992 as amended, most recently by UU No. 4 Tahun 2023 | Bank secrecy and the handling/disclosure of protected customer information. | Classify protected content; restrict purpose and access; do not expose it to models, logs, previews or downstream users without a valid authorized basis and applicable bank procedure. Review generated aggregate outputs for disclosure risk. |
| **PP No. 71 Tahun 2019 tentang Penyelenggaraan Sistem dan Transaksi Elektronik** and **UU No. 11 Tahun 2008 tentang ITE as amended, including UU No. 1 Tahun 2024** | Electronic-system reliability, security, responsibility and relevant obligations. | Apply secure/reliable system operation, recordkeeping, access control and incident practices; determine requirements for the actual system and operating role. |
| **Permenkominfo No. 5 Tahun 2020 tentang PSE Lingkup Privat as amended by Permenkominfo No. 10 Tahun 2021** | Potential registration/operational obligations for private-scope electronic systems, depending on the service and operator classification. | Legal/Compliance must determine registration/reporting applicability from the actual service model and confirm status in the current Komdigi JDIH/PSE process. |
| **POJK No. 22 Tahun 2023 tentang Pelindungan Konsumen dan Masyarakat di Sektor Jasa Keuangan** | Relevant where the Hub or generated analytics support consumer-facing services, affect consumer treatment, or use consumer information. | Ensure downstream use is not misleading or unauthorized; review consumer impact, transparency and complaint/evidence considerations where the use case falls in scope. |
| **Surat Edaran Menkominfo No. 9 Tahun 2023 tentang Etika Kecerdasan Artifisial** | Indonesian AI-ethics guidance includes security, transparency, accountability, privacy, inclusivity and human oversight themes. | Apply these as design principles: disclose AI-generated drafts, keep humans accountable, assess error/discrimination risks, protect data, and provide traceability. This is guidance and does not replace binding sector rules. |
| **AI-related draft rules / roadmap** | Official Komdigi communications in 2026 described RPerpres instruments on AI ethics and the national AI roadmap as being developed/finalized. | Do not treat a draft as an in-force regulation. Recheck JDIH/official publications before each release and update this regulatory baseline if a new instrument is promulgated. |

### 14.3 Specific controls for metadata-only AI dashboard generation

- **Classify metadata:** include asset name, column name, descriptions, lineage, relations, KPI definitions, tags, and schema in metadata-classification and field-visibility decisions.
- **Purpose and access:** record approved purposes and eligible user groups. The generator inherits the user's metadata entitlements and cannot discover or use hidden assets.
- **No unapproved model disclosure:** no Bank metadata, prompts, generated spec, query proposals, or outputs go to a public model/API, external development assistant, telemetry system or third party unless the relevant processing path is approved.
- **Model provider review:** if external processing is proposed, assess contractual confidentiality, controller/processor role, data location, subprocessors, retention, no-training commitments where required, deletion, support access, audit rights, incident handling, exit and any transfer/approval requirements.
- **No actual data in preview:** synthetic data is isolated, tagged and technically separated. It must not be generated by sampling or perturbing real personal/customer records unless separately approved and reviewed for re-identification risk.
- **No executable model output:** AI cannot run arbitrary code or SQL, connect to data sources, grant access, or publish a dashboard. Validate all specification references server-side.
- **Human approval:** official KPI meaning, formula, intended use, audience, and publication are approved by accountable owners. AI-generated content must remain marked as a draft until approval.
- **Audit and retention:** log event metadata and version references with minimum necessary content; define access, tamper-evidence, retention and deletion. Do not retain full prompts/responses by default if a reduced audit record meets the need.
- **DPIA screen:** complete a documented privacy-impact-assessment screening before real personal-data processing; perform a DPIA where required by UU PDP, PADK/POJK requirements and Bank policy.
- **Cross-border / location:** approve hosting and processing location. If personal data transfer outside Indonesia is involved, assess UU PDP Article 56 conditions; if OJK rules require permission/notification for system placement or IT processing outside Indonesia, meet them before implementation. The detailed application must be confirmed by Legal/Compliance and Architecture.
- **Incident response:** link model/provider and Hub incidents to Bank incident management; assess confidentiality breach, disclosure, integrity, availability, and applicable OJK/PDP/vendor notification obligations.

### 14.4 Required approval evidence

Before Phase 1 uses genuine internal metadata or any hosted model, retain as applicable:

- Approved scope, business purpose, metadata inventory/classification, data owner and allowed-user matrix.
- Architecture diagram, data-flow diagram, trust boundaries, threat model, model/provider inventory, and environment/location record.
- Legal/regulatory applicability matrix with assigned control owners and evidence references.
- DPIA screening and completed DPIA if required; documented lawful basis and processing purpose where personal data is in scope.
- Vendor/provider assessment and contractual terms if third-party services are used.
- Security test results covering authorization, prompt injection, output validation, audit, secrets, error handling and fail-closed behavior.
- Retention/deletion, incident-response, rollback and change-control runbooks.
- Required signatures/approvals from Bank's designated functions. The exact approver matrix is an internal decision, not defined by this PRD.

### 14.5 Explicit go-live blockers

Do not release to a broader pilot or production if any applicable blocker remains unresolved:

- No designated product/service owner or accountable data owner for in-scope metadata/assets.
- Unclear purpose, authorization, classification, lawful basis where personal data is processed, or permitted use.
- Real Bank metadata or prompts would be sent to an unapproved external model/provider.
- Unresolved system/data location, vendor, subprocessor, cross-border, OJK approval/notification, or PSE-registration question where applicable.
- Missing required DPIA, privacy/security/architecture/vendor-risk/legal/compliance/risk sign-off.
- Metadata or dashboards can leak unauthorized schema, sensitive descriptions, query fragments, protected customer information, or restricted outputs via prompts, search, logs, errors, screenshots, exports or synthetic fixtures.
- AI-generated fields/SQL/code can execute, access data, grant permission or publish without the required controls.
- Audit evidence for critical actions is unavailable or can be altered by the actor it is meant to monitor.
- Missing incident response, retention/deletion, model/provider rollback, operational support, or recovery plan for the intended release.

## 15. PoC plan and evaluation

### 15.1 Suggested pilot

Select 2–3 low-to-moderate-risk use cases, subject to Bank approval, and add a bounded metadata-to-dashboard demonstration:

- **Pilot A — Discover existing Tableau dashboards:** inventory approved views from a small set of domains; catalog, search, filter, owner, canonical link and lifecycle metadata.
- **Pilot B — Data dictionary for one domain:** publish approved business terms and a small dataset/table inventory with owner, definition, classification, freshness and access route.
- **Pilot C — Request lifecycle:** enable one existing-data access request and one dashboard/report request from submission through decision, fulfilment/delivery evidence and closure.
- **Pilot D — AI Dashboard Generator (metadata-only):** use synthetic metadata to generate a validated JSON specification and interactive preview using synthetic fixture data. The user can edit/reject the draft. No production connector or executable query is enabled.

Use synthetic assets and values for initial UI/model tests. Before using actual Bank metadata, complete classification, owner authorization, the appropriate privacy/security/legal screening, and model/provider review. Do not ingest customer/transaction values just to make the PoC look realistic.

### 15.2 PoC success criteria

- A user can discover an already catalogued asset and understand its owner, definition, classification guidance and access path.
- A user can submit a request without knowing table names or SQL and track all relevant status transitions.
- A reviewer can see a queue, decision context, and role-appropriate audit trail.
- Existing Tableau content can be found/opened through its canonical link while source permissions remain effective.
- Given supported synthetic metadata and a business question, the generator emits a schema-valid dashboard specification and renders a useful interactive preview.
- The generated specification references only fields present in the approved metadata package; unsupported fields and metrics are explicitly identified instead of hallucinated.
- Synthetic values are visibly and persistently labelled and cannot be mistaken for actual Bank values.
- All Phase 1 tests confirm there is no database connection, SQL execution, production data access, model-based permission decision, or direct publication path.
- Control stakeholders can inspect the relevant evidence pack, review comments, test results, exceptions and remediation.
- Baseline metrics are collected for catalog discoverability, request completion, specification validity, reviewed field-mapping accuracy, user edit/rejection rate and generation latency. Targets are set after the baseline, not fabricated in advance.

Compliance/security gates are pass/fail prerequisites and cannot be traded against feature delivery or model accuracy.

### 15.3 Test scenarios

**Positive tests**

- User can search permitted metadata and open an authorized Tableau view.
- Requester submits a complete data-access/dashboard request and receives a request ID.
- Data owner approves/rejects with rationale; workflow and history reflect the decision.
- Fulfilment is recorded separately from approval.
- Steward updates a definition through the controlled draft/review/publish workflow.
- Generator creates a valid specification from a known schema, renders the synthetic preview, and exposes the assumptions and source-field references.
- User edits a draft; each saved version and review decision is traceable.

**Negative tests**

- Unauthorized user cannot view restricted metadata, another user's request, an output reference, or a Tableau view.
- Workflow, identity, catalog or model outage never causes access to be granted; model failure uses the approved fallback or safe error.
- A prompt or metadata description instructs the model to reveal hidden tables, ignore policy, or execute code; the attempt is ignored/blocked and recorded at the approved level.
- Generated output references a nonexistent field, hidden field, unapproved aggregation, unsupported chart, or arbitrary code; the validator rejects it.
- A synthetic preview is never labelled or presented as actual Bank data; test fixtures contain no real customer/transaction rows.
- Requester includes customer/account identifiers in free text; handling follows the approved warning/redaction policy and the content is not silently copied into notifications or model prompts.
- External model routing, telemetry, or fallback provider is blocked unless approved; no silent provider switching occurs.
- Database connector, query execution, CSV export and direct Tableau publication remain disabled for Phase 1, including attempts by ordinary administrators.
- Metadata sync failure is flagged and cannot incorrectly mark an asset current/certified.
- A revoked entitlement cannot be retained by cached portal permissions or stale embedded sessions beyond the approved policy.
- Admin attempts prohibited approval/entitlement changes and is denied/logged according to segregation-of-duties rules.

### 15.4 Evidence pack

- Scope, use cases, data classification, threat model, data-flow diagram, trust boundaries and approved architecture.
- Approved RACI, processing purpose, metadata owner/allowed-field matrix, and decision/approval matrix.
- Legal/regulatory applicability matrix, PSE applicability decision where relevant, DPIA screening and DPIA if required.
- Model/provider inventory, configuration, contract/security/privacy assessment and data-processing/location terms if a third party is used.
- Synthetic test dataset provenance and confirmation that no production values are included.
- Tableau inventory, deployment/version, identity model, licensing decision and chosen integration mode.
- Functional, AI-quality, prompt-injection and negative security test results; defects, owners and disposition.
- Privacy/security/risk/legal/compliance review comments and required sign-offs.
- Retention/deletion, incident/rollback, model change, support and monitoring runbooks; change record.

## 16. Metrics and service management

Measure the product's outcomes; do not use stored terabytes or request counts alone as success.

| Metric | Definition (proposed) | Notes |
|---|---|---|
| Catalog coverage | In-scope priority assets with complete mandatory metadata / total priority assets | Scope and required fields agreed before baseline |
| Search-to-success | Searches that lead to asset view, authorized click-through, or reuse within defined window | Avoid collecting more user telemetry than necessary |
| Duplicate prevention | Requests identified as satisfied by an existing asset | Track verified reuse, not just recommendations |
| Request lead time | Median/percentile time from complete submission to triage, decision, and fulfilment | Separate requester-wait, approval, and delivery time |
| SLA attainment | Requests completed within approved target / requests eligible for target | Define pause/exclusion rules |
| Data-product trust | Products with owner, approved definition, lineage, quality checks and current status | Threshold depends on product criticality |
| Tableau discoverability | Selected existing Tableau views with owner, description, domain and canonical link | Do not count stale or retired views as active inventory |
| Control effectiveness | Access exceptions, failed negative tests, unresolved review findings, audit gaps | Zero unresolved critical blocker at production gate |
| User experience | Search usefulness, form completion, user feedback, self-service resolution | Use approved survey/telemetry approach |

Targets are set after baseline, capacity analysis and service-owner agreement. Security and compliance gates are pass/fail prerequisites, not KPIs to trade off for speed.

## 17. Dependencies, risks and mitigations

| Dependency / risk | Impact | Mitigation / decision needed |
|---|---|---|
| No single authoritative catalog/glossary | Duplicate metadata and conflicting definitions | Designate source of truth per metadata type; use a read model/facade with visible sync freshness. |
| Tableau deployment/version unknown | Embedding/auth approach may be incompatible | Complete technical discovery; use catalog + deep link as safe MVP default. |
| Tableau licensing unclear | Unplanned cost or disallowed usage model | Confirm license/embedding terms before embedding. |
| Owner/steward gaps | Assets cannot be trusted or requests stall | Make ownership a publication prerequisite; define escalation path. |
| Over-centralized delivery backlog | Longer lead time and user workarounds | Standardize intake, delegate appropriate domain decisions and measure queue capacity. |
| Overly open search | Sensitive metadata disclosure | Classify metadata itself; apply field-/asset-level authorization to results, snippets, prompts, errors and logs. |
| Portal duplicates ITSM | Conflicting status and audit trail | Decide request/workflow system of record; portal should orchestrate or link as agreed. |
| Approval mistaken for permission | Unauthorized use if provisioning fails | Separate states; verify fulfilment and test revoke paths. |
| Metadata schema is too sparse | Wrong chart or incorrect semantic interpretation | Mark candidates as hypotheses; ask clarifying questions; add approved descriptions/grain/relationships/KPI definitions over time. |
| LLM hallucinates fields or KPI meaning | Misleading dashboard design and reduced trust | Versioned JSON schema, allow-listed field IDs, deterministic validator, clear assumptions and owner review. |
| Prompt injection through metadata descriptions | Policy bypass or disclosure | Treat metadata as untrusted; remove/escape instructions; restrict model context/tools; test adversarial cases. |
| Internal metadata exposed to public model | Confidentiality, privacy, vendor and cross-border risk | Default deny external model routing; use synthetic metadata until provider/location/contract/security/privacy approvals complete. |
| Metadata mistaken for non-sensitive by default | Schema or internal architecture disclosure | Apply classification to names, descriptions, lineage, relationships and KPI terms; restrict search and model context by role. |
| Synthetic preview mistaken for real results | Users may make business decisions from fabricated values | Persistent synthetic label, seeded synthetic fixtures, no mixing with real data, no production export/publish. |
| Future query execution too permissive | Unauthorized records, cost, or disclosure | Separate Phase 3 gate; allow-listed read-only views/templates, server-side authorization, query guardrails and output controls. |
| Cross-border/provider location unclear | OJK, PDP, confidentiality and contract questions | Determine precise processing/data locations, applicable transfer rules and required approvals before provider connection. |
| PSE registration applicability unclear | Missing system-level obligation | Legal/Compliance records a formal applicability decision against actual deployment/operator scope. |
| Regulatory requirements change | Stale control matrix | Regulatory owner rechecks official JDIH/OJK/Komdigi sources at each release gate and updates the matrix. |
| Too much scope in MVP | Delayed proof of value | Limit Phase 1 to metadata-to-specification and synthetic preview; disable connectors and publication. |
| Compliance assumed from architecture alone | Unresolved bank obligations | Require evidence-based mapping/sign-off; keep PoC acceptance distinct from production approval. |

## 18. Open decisions required from Bank

1. Who is the executive sponsor, product owner, operating service owner, regulatory mapping owner and AI/model risk owner?
2. Which divisions/domains are in the pilot, and what official data classifications and permitted-use categories apply?
3. Which system is authoritative for catalog, glossary, lineage, ownership, classification, quality and approval state?
4. Which identity provider, metadata APIs, Tableau deployment and workflow/ITSM systems are approved for non-production integration?
5. What is the minimum metadata schema: table, column, type, descriptions, owner, grain, relation, classification, lineage, KPI formula and allowed aggregation?
6. Can any actual internal metadata be used in Phase 1? Which specific fields are cleared, by whom, for which purpose and user group?
7. What approved model gateway or local model deployment can be used? If none, is a deterministic/rule-based fallback acceptable for the initial demonstration?
8. If a third-party model or hosting provider is considered, who approves the provider, contract, subprocessor, model training-use, prompt/response retention, location, support access and exit terms?
9. What is the current Bank DPIA screening process and who decides whether a DPIA is required for this AI use case?
10. What retention period and access rules apply to metadata snapshots, specifications, prompts/responses, telemetry and audit records?
11. Who approves official KPI formulas, semantic mappings, draft review, certification, publication and any future real-data connection?
12. What network zones, hosting/processing locations, recovery objectives, security controls and incident notification processes are required?
13. Does the actual deployment trigger PSE registration or other reporting/notification obligations? Obtain a written Legal/Compliance decision.
14. What Tableau Server/Cloud version, authentication, licensing, site/project structure, API scope and content permissions apply?
15. What are the agreed SLA definitions, support hours, escalation paths and operating responsibilities?
16. Which telemetry is permitted to evaluate user experience and AI output quality, and how is it minimized, retained and reviewed?
17. What change in scope, risk tier or data use triggers re-assessment (for example, adding customer data, query execution, an external model provider, cross-border processing or automated publication)?

## 19. Proposed MVP acceptance gate

The PoC is accepted for demonstration only when the core user journeys work in a controlled non-production environment using approved/synthetic metadata and synthetic data. PoC acceptance is not production approval or a declaration of regulatory compliance.

**Required Phase 1 product acceptance:**
- [ ] SSO / role-aware access passes tests, or the demo-only mock identity is isolated and documented as non-production scaffolding.
- [ ] Search, catalog, glossary, Tableau directory, request center and My Workspace work for the agreed pilot scope.
- [ ] Request state, decision, fulfilment and closure can be distinguished and audited.
- [ ] AI generator outputs schema-valid JSON using allowed metadata references; invalid fields/components are rejected.
- [ ] Interactive preview uses synthetic data only and displays a persistent disclaimer.
- [ ] Missing/ambiguous metadata and KPI semantics are visible; no official business definitions are invented.
- [ ] No production database connector, SQL executor, data export, privileged model tools or direct Tableau publication is enabled.
- [ ] No unapproved Bank metadata/prompts are transmitted to an external model/provider.
- [ ] Prompt-injection, authorization, fail-closed, audit, secret-handling and negative access tests pass; critical defects are closed.
- [ ] Support, retention/deletion, incident and rollback procedures are documented for the test environment.

**Required gate before using actual Bank metadata or a hosted model:**
- [ ] Metadata classification, purpose, owner and allowed-user matrix are approved.
- [ ] Applicable legal/regulatory mapping and provider/location assessments are completed.
- [ ] DPIA screening is complete and a DPIA is approved where required.
- [ ] Architecture, Information Security, Privacy, Data Governance, Risk, Legal/Compliance, Vendor Risk and other assigned stakeholders have given required approval.
- [ ] Provider contracts, model training-use, retention/deletion, support-access, subprocessor, incident and exit terms are reviewed where applicable.

**Separate gate before real-data query execution or production dashboard publication:**
- [ ] A new/revised PRD and threat model are approved; applicable OJK requirements, including permission/notification if required, are resolved.
- [ ] Database/query access is read-only, allow-listed, identity-aware, resource-constrained and server-side authorized.
- [ ] Official KPI formulas, grain, data quality and output disclosure controls are approved.
- [ ] Row/column restrictions, small-cell disclosure, export controls, query logs, revocation, incident response and operational support are tested.
- [ ] Tableau authentication, authorization, licensing and publication model are approved.
- [ ] Required control functions sign off before production change implementation.

## 20. Public reference links and regulatory change control

The following official sources are a starting point for applicability review. They do not replace Bank internal policies, consolidated legal research, legal advice, or a formal clause-by-clause mapping. **Regulatory sources were checked for this PRD revision on 28 October 2026; re-validate their status and applicability at each release gate.**

1. OJK — [PADK OJK No. 1 Tahun 2026: Penyelenggaraan Teknologi Informasi oleh Bank Umum](https://ojk.go.id/id/regulasi/Pages/PADK-1-Tahun-2026-Penyelenggaraan-Teknologi-Informasi-oleh-Bank-Umum.aspx) (effective 1 March 2026; implementation guideline for POJK 11/2022).
2. OJK — [POJK No. 11/POJK.03/2022: Penyelenggaraan Teknologi Informasi oleh Bank Umum](https://ojk.go.id/en/regulasi/Pages/Implementation-of-Information-Technology-by-Commercial-Banks.aspx).
3. BPK — [UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi](https://peraturan.bpk.go.id/Details/229798/uu-no-27-tahun-2022).
4. OJK — [SEOJK No. 29/SEOJK.03/2022 tentang Ketahanan dan Keamanan Siber bagi Bank Umum](https://ojk.go.id/id/regulasi/Pages/Ketahanan-dan-Keamanan-Siber-Bagi-Bank-Umum.aspx).
5. OJK — [SEOJK No. 24/SEOJK.03/2023 tentang Penilaian Tingkat Maturitas Digital Bank Umum](https://ojk.go.id/id/regulasi/Pages/Penilaian-Tingkat-Maturitas-Digital-Bank-Umum.aspx).
6. OJK — [POJK No. 44 Tahun 2024 tentang Rahasia Bank](https://ojk.go.id/id/regulasi/Pages/POJK-44-Tahun-2024-Rahasia-Bank-.aspx) (effective 27 December 2024).
7. BPK — [PP No. 71 Tahun 2019 tentang Penyelenggaraan Sistem dan Transaksi Elektronik](https://peraturan.bpk.go.id/Details/122030/pp-no-71-).
8. BPK — [UU No. 1 Tahun 2024, Perubahan Kedua atas UU ITE](https://peraturan.bpk.go.id/details/274494/uu-no-1-tahun-2024).
9. Komdigi — [Pendaftaran PSE Lingkup Privat: FAQ and legal basis](https://pse.komdigi.go.id/pertanyaan-umum) (registration applicability must be determined for the actual operating model).
10. OJK — [POJK No. 22 Tahun 2023 tentang Pelindungan Konsumen dan Masyarakat di Sektor Jasa Keuangan](https://peraturan.bpk.go.id/Details/302699/peraturan-ojk-no-22-tahun-2023).
11. Komdigi JDIH — [Surat Edaran Menkominfo No. 9 Tahun 2023 tentang Etika Kecerdasan Artifisial](https://jdih.komdigi.go.id/produk_hukum/view/id/883/t/surat%2Bedaran%2Bmenteri%2Bkomunikasi%2Bdan%2Binformatika%2Bnomor%2B9%2Btahun%2B2023).
12. Komdigi — [Official 2026 update on proposed AI-specific regulation](https://www.komdigi.go.id/berita/siaran-pers/detail/wamen-nezar-aturan-ai-akan-dibuat-spesifik-untuk-kesehatan-pendidikan-hingga-keuangan) (re-check whether the proposed national AI instruments have since been promulgated; do not treat draft instruments as binding law).
13. Tableau — [Embedding API v3: Authentication and Embedding](https://help.tableau.com/current/api/embedding_api/en-us/docs/embedding_api_auth.html).
14. Tableau — [Embedding API v3 overview](https://help.tableau.com/current/api/embedding_api/en-us/).
15. Tableau — [Connected Apps for Application Integration (Tableau Server)](https://help.tableau.com/current/server/en-us/connected_apps.htm).

**Regulatory change control:** the designated Legal/Compliance owner should recheck the official OJK, BPK/JDIH, and Komdigi sources before each new release, after a material scope change, and when a new provider, model, personal-data category, cross-border path, query connector, or publication workflow is introduced.

