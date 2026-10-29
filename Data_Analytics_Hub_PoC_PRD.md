# Bank Data & Analytics Hub — Product Requirements Document (PRD)

**Document status:** Draft for discovery / PoC  
**Version:** 0.1  
**Date:** 23 October 2026  
**Product owner:** To be appointed by Bank  
**Executive sponsor:** To be appointed  
**Audience:** Business divisions, Central Data Office, Data Platform, BI/Analytics, Enterprise Architecture, IT, Information Security, Risk, Privacy, Legal & Compliance, Internal Audit as applicable

> **Important assurance note:** This PRD is a product-design proposal, not a legal opinion, regulatory interpretation, security accreditation, or certification of compliance. Production scope must pass Bank's applicable architecture, security, privacy, risk, legal/compliance, procurement, vendor, records-retention, and change-management reviews. The PRD intentionally uses approval gates and leaves bank-specific policies, control owners, locations, retention periods, and approval matrices to be confirmed by Bank.

---

## 1. Executive summary

Bank Data & Analytics Hub is a proposed enterprise front door for finding and using trusted data assets and analytics services across Bank. It provides a unified experience for:

1. Discovering datasets, data products, business terms, KPIs, dashboards, reports, and data owners.
2. Viewing an enterprise data dictionary / business glossary with definitions, provenance, freshness, data quality, and permitted-use guidance.
3. Requesting access to existing assets or submitting requests for a new dataset, dashboard, report, analysis, or data-quality correction.
4. Tracking requests, approvals, delivery status, service targets, comments, and results in My Workspace.
5. Discovering existing Tableau dashboards and linking to them; embedding selected views only after technical, licensing, and security validation.

### 1.1 Foundational assumption

This PoC assumes the enterprise data centralization initiative has completed or has already established an approved shared data platform, common ingestion patterns, central identity and access management, a baseline metadata/catalog capability (or a planned integration path), and established data ownership. The Hub does **not** replace the bank's lake/lakehouse, Enterprise Data Warehouse (EDW), Tableau, identity provider, IT Service Management (ITSM), or approved data-access provisioning system. It is the shared experience and workflow/orchestration layer over approved systems of record.

If these assumptions are not true, the PoC must explicitly identify the dependency rather than simulate an unapproved control.

### 1.2 Product positioning

**Discover → Request → Consume → Govern**

The Hub is a service portal, not a general-purpose file drop, uncontrolled data export channel, new BI engine, or alternate authorization system. A catalog result does not itself grant access to data. A request status of “approved” does not indicate that technical access has been provisioned.

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

- Provide a single authenticated portal to search and navigate approved data and analytics assets.
- Publish an initial business glossary/data dictionary and data catalog view, sourced from the designated system of record where one exists.
- Provide structured request forms and routing for key service types.
- Provide a transparent request lifecycle, ownership, approval evidence, and requester workspace.
- Integrate existing Tableau content by cataloging and linking to approved dashboards in MVP; evaluate secure embedding as a later or conditional capability.
- Enforce authorization at the point where underlying data, dashboard, or output is accessed.
- Capture operational telemetry sufficient to measure demand, bottlenecks, reuse, service quality, and control exceptions.

### 3.2 Non-goals for PoC / MVP

- Replacing the central data platform, EDW, lake/lakehouse, Tableau, enterprise SSO/IAM, ITSM, or the designated catalog/governance system.
- Building a new dashboard-rendering or charting engine.
- Automatically approving every access request or allowing unrestricted access to raw/bronze data.
- Storing raw bank/customer datasets or exporting sensitive results inside the portal.
- Creating a new enterprise-wide “golden record” without an approved data-product owner and reconciliation process.
- Using generative AI to answer questions over restricted data in MVP.
- Enabling unrestricted self-service SQL, download, or cross-domain joins in MVP.
- Promising regulatory compliance from software features alone.

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

### 6.1 MVP scope

- Enterprise SSO integration in the approved non-production environment.
- Role-aware homepage and global search across an initial asset inventory.
- Data catalog and business glossary/data dictionary pages for selected pilot domains.
- Tableau dashboard catalog / gallery with metadata and deep links.
- Request center for the request types in Section 8.
- Workflow states, assignment, comments, notifications, and My Workspace.
- Admin console for service categories, routing, forms, SLA definitions, and operational monitoring.
- Audit event capture and operational metrics.
- Security/privacy/architecture review evidence and negative authorization tests before pilot acceptance.

### 6.2 Conditional / follow-on scope

- Embedded Tableau views using Tableau Embedding API v3, only if Tableau deployment/version, identity model, licensing, site configuration, and Security approval support the selected design.
- Metadata synchronization through approved Tableau REST API / Metadata API use, limited to approved metadata and API scopes.
- Automated provisioning through an existing approved access-management workflow.
- Integration to enterprise ITSM or workflow tooling if it is designated the system of record for tickets/approvals.
- Data quality dashboards, lineage visualization, certified data-product marketplace, advanced search/synonyms, usage analytics, and semantic search.

### 6.3 Out of scope until separately approved

- Direct data export from the portal for restricted data.
- Public or internet-facing access.
- Any new cross-border storage/processing or new third-party data processor without the applicable assessment and approval.
- Any mechanism that impersonates a privileged user or grants access broader than the signed-in user's authorization.
- Automatic AI-generated conclusions from confidential or restricted datasets.

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

1. Capture audience, business question, decision supported, KPI definitions, dimensions/filters, granularity, refresh needs, expected delivery/use date, and confidentiality.
2. Search existing Tableau gallery and certified/approved output.
3. If an existing view is fit for purpose, request access or change request instead of creating a duplicate.
4. Otherwise route through BI/Analytics triage and backlog rules.
5. KPI and business definitions are approved by the responsible owner; data sources and access path are approved.
6. Develop in the approved BI environment, validate with requester, owner, and control stakeholders as applicable.
7. Publish in Tableau or approved BI system, register metadata in the Hub, and set owner/review lifecycle.

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

## 11. Non-functional requirements

### 11.1 Security and privacy

- Authentication and MFA/session policy must follow Bank enterprise identity policy.
- Enforce least privilege; default deny; segregate roles for requester, owner, fulfilment, admin, and audit.
- Use TLS in transit and approved encryption at rest for stored portal data/logs.
- Keep secrets in approved secrets management, with rotation and tightly scoped service identities.
- Never put tokens, passwords, full customer records, account numbers or secrets in URLs or ordinary logs.
- Apply secure coding, dependency scanning, SAST/DAST, penetration testing and vulnerability remediation per bank SDLC.
- Apply anti-CSRF/XSS/session protections, content-security policy, secure headers and upload controls if attachments are later introduced.
- Define audit retention, access review, legal hold, export control, log integrity and incident response with the relevant owners.
- Do not introduce new third-party processing, cross-border transfer or hosting location without the relevant bank review/approval.

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

## 14. Security, regulatory and assurance checklist

This list is a **review checklist**, not a complete legal/control mapping. Final applicability must be determined by Bank's designated functions for this specific system, data types, architecture, vendors, deployment location, and use cases.

### 14.1 Required review tracks before production

1. **Regulatory/legal applicability:** Map applicable OJK/BI regulations, Indonesian personal data protection law, banking secrecy/confidentiality obligations, recordkeeping requirements, and internal policies to design and operating evidence. Identify obligations, controls, owners and evidence per item.
2. **Architecture and technology risk:** Confirm approved hosting/processing locations, connectivity, environment segregation, resilience, capacity, operational ownership, and change control.
3. **Information security:** Threat model portal and integrations; validate IAM, privileged access, secrets, secure coding, vulnerability management, logging, monitoring, incident response and security testing.
4. **Privacy/data protection:** Confirm processing purpose, minimization, legal basis/authority where applicable, role allocation, retention, data subject rights handling where applicable, disclosure, analytics output risks and vendor/transfer implications.
5. **Data governance:** Confirm asset classification, owners/stewards, metadata visibility rules, quality thresholds, lineage coverage, data contract, lifecycle and approved uses.
6. **Third-party/vendor and licensing:** Review contracts, subprocessor, operational support, audit rights, data location and Tableau licensing/embedded-use terms where relevant.
7. **Operational control:** Test access request, approval, provisioning, access revocation, failed provisioning, expiry, data correction, incident, retention/deletion, audit retrieval and continuity runbooks.
8. **Independent assurance:** Arrange control testing or independent review according to Bank's policies and risk tier.

### 14.2 Regulatory references to validate

- **PADK OJK No. 1 Tahun 2026 tentang Penyelenggaraan Teknologi Informasi oleh Bank Umum**, effective 1 March 2026. OJK's regulation page describes scope including IT governance, IT risk/security, use of IT service providers, system/data-processing location issues, data management, personal data protection, internal control/audit and reporting. The applicability and required evidence for this specific Hub must be mapped by Bank's control functions.
- **UU Republik Indonesia No. 27 Tahun 2022 tentang Pelindungan Data Pribadi.** Applicable obligations and the bank's role(s) for each processing activity must be assessed by Bank's Legal/Privacy function.
- Other OJK/BI regulations, banking confidentiality obligations, recordkeeping, outsourcing, cloud/third-party, cybersecurity, incident, and internal bank requirements may apply depending on scope and implementation. Confirm current applicability and transition status with Bank Legal/Compliance; do not rely on this PRD as an exhaustive list.

### 14.3 Explicit go-live blockers

Do not release to production if any relevant blocker remains unresolved:
- No designated product/service owner or data owner for in-scope assets.
- Unclear authorization/purpose for processing a dataset, or unresolved classification/retention/location question.
- Access control can be bypassed through portal, embedded Tableau, exports, search snippets, logs or notifications.
- Required security/privacy/legal/compliance/risk sign-off is absent.
- Tableau licensing or authentication pattern for embedding is unconfirmed.
- Audit trail for critical access/request/admin changes is unavailable or modifiable by the actor it is meant to monitor.
- No operational support, incident response, rollback, backup/recovery or change control for production service.

## 15. PoC plan and evaluation

### 15.1 Suggested pilot

Select 2–3 low-to-moderate-risk, well-understood use cases with different characteristics. Suggested illustrative pilots (subject to Bank approval):

- **Pilot A — Discover existing Tableau dashboards:** inventory approved views from a small set of domains; catalog, search, filter, owner, canonical link, and lifecycle metadata.
- **Pilot B — Data dictionary for one domain:** publish approved business terms and a small dataset/table inventory with owner, definition, classification, freshness, and access route.
- **Pilot C — Request lifecycle:** enable one existing-data access request type and one dashboard/report request type from submission through decision, fulfilment/delivery evidence, and closure.

Use synthetic or approved non-production metadata/data for early UI testing. Do not ingest real customer/transaction data solely to make the PoC look realistic.

### 15.2 PoC success criteria

- A user can discover an already catalogued asset from one search and understand its owner, definition, classification guidance and access path.
- A user can submit a request without knowing source-table names and can track every relevant status transition.
- A reviewer can see a queue, decision context and audit trail appropriate to their role.
- Existing Tableau content can be found and opened through its canonical link, with the source Tableau permission still enforced.
- An unauthorized user fails negative access tests for restricted catalog fields, dashboard views, request records and output references.
- Data definitions are visibly marked draft vs approved and linked to an accountable owner.
- Control stakeholders can inspect a traceable evidence pack for review decisions, test outcomes, exceptions and remediation.
- Baseline metrics are collected for discoverability, request completion, triage time, duplication, and user feedback; numerical targets are approved after baseline measurement.

### 15.3 Test scenarios

**Positive tests**
- User from an entitled division searches permitted metadata and opens an authorized Tableau view.
- Requester submits a complete data access request and receives a request ID.
- Data owner approves or rejects with rationale; workflow status and history reflect the decision.
- Fulfilment records actual provisioning/delivery separately from approval.
- Steward updates a definition through the controlled draft/review/publish workflow.

**Negative tests**
- Unauthorized user cannot open a restricted Tableau view by pasting or guessing the URL, opening embedded content, or navigating from the Hub.
- User cannot view another user's restricted request or result link.
- User cannot edit an approved glossary term without assigned privilege.
- A workflow outage, IAM outage, or Tableau API failure does not fall back to allow access.
- A revoked entitlement cannot be retained by a cached portal permission or stale embedded session beyond the approved session/propagation policy.
- Requester enters customer/account identifiers into free text: warning/redaction/handling follows the designed policy and does not silently copy them into notifications.
- A failed metadata sync is flagged and does not incorrectly mark an asset as current/certified.
- Admin attempts a prohibited approval or entitlement change and is denied / logged according to segregation-of-duties rules.

### 15.4 Evidence pack

- Scope, use cases, data classification, threat model and approved architecture.
- Approved RACI and decision/approval matrix.
- Asset inventory, metadata fields, ownership and glossary sign-off.
- Tableau inventory, deployment/version, identity model, licensing decision, and chosen integration mode.
- Functional and negative security test results; defects, owners and disposition.
- Privacy/security/risk/legal/compliance review comments and sign-offs required by bank policy.
- Operational runbooks, monitoring dashboards, incident/rollback plan, support contacts, and change record.

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
| No single authoritative catalog/glossary | Duplicate metadata and conflicting definitions | Designate source of truth per metadata type; portal may be a facade/read model with sync freshness shown. |
| Tableau deployment/version unknown | Embedding/auth approach may be incompatible | Complete technical discovery early; use catalog + deep link as safe MVP fallback. |
| Tableau licensing unclear | Unplanned cost or disallowed usage model | Confirm license/embedding terms with administrator/procurement/vendor before embed. |
| Owner/steward gaps | Assets cannot be trusted or requests stall | Make ownership a publication prerequisite for curated assets; define escalation path. |
| Over-centralized delivery backlog | Long wait times and user workarounds | Standardize intake and delegate domain decisions; monitor queue/capacity and reuse. |
| Overly open search | Sensitive metadata disclosure | Apply classification to catalog metadata itself and test result/snippet authorization. |
| Portal becomes duplicate ITSM | Conflicting status and audit trail | Decide the request/workflow system of record; portal can orchestrate or link to it. |
| Approval is mistaken for permission | Unauthorized use if provisioning fails | Separate status states; verify fulfilment in system of record and test revoke paths. |
| Too much scope in MVP | Delayed proof of value | Pilot a few use cases and a small approved Tableau inventory. |
| Compliance assumed from architecture alone | Unresolved bank obligations | Formal mapping/sign-off and go-live blockers as in Section 14. |

## 18. Open decisions required from Bank

1. Who is the executive sponsor, product owner and operating service owner?
2. What is the official name/branding and which divisions/domains are in the pilot?
3. Which system is the source of truth for catalog, glossary, data quality, lineage, ownership and approvals?
4. Is the central platform a lake, lakehouse, EDW-centric architecture, or a hybrid? Which APIs are approved for use?
5. Which Tableau deployment is in use (Server or Cloud), what version, identity model, licensing, site/project structure and API capabilities are present?
6. Does MVP use deep links only, or is secure embedding necessary for the first pilot? Default recommendation: deep links first.
7. What is the system of record for request/ticket/approval state: existing ITSM/workflow or new Hub backend?
8. What data classifications exist, and which metadata fields may be visible to which user groups?
9. Who approves each type of data access / data product / dashboard request? Which approvals are risk-based and which are mandatory?
10. Which hosting/processing locations, vendor constraints, retention rules, recovery objectives and logging controls apply?
11. What are the agreed SLA definitions, support hours, escalation paths and operational responsibilities?
12. What user metrics and search telemetry are permitted, and how are they retained and reviewed?

## 19. Proposed MVP acceptance gate

The PoC is accepted for demonstration when the core user journeys work against approved sample/metadata in a controlled non-production environment and the evidence pack is available. A production decision requires separate approval.

**Required product acceptance:**
- [ ] SSO / role-aware access passes functional tests.
- [ ] Search, catalog, glossary, Tableau directory, request center, and My Workspace work for the agreed pilot scope.
- [ ] Request state, decision, fulfilment, and closure can be distinguished and audited.
- [ ] Tableau access cannot be bypassed; chosen integration mode and license are documented.
- [ ] Mandatory negative tests pass; critical security defects are closed.
- [ ] Data owners approve published definitions and asset metadata.
- [ ] Support/runbooks/monitoring and change path are documented for the intended test environment.

**Required production gate (separate from PoC acceptance):**
- [ ] Applicable regulatory and policy mapping is approved by designated Bank functions.
- [ ] Architecture, Security, Privacy, Risk, Legal/Compliance, Data Governance, and other required stakeholders have signed off.
- [ ] Hosting, vendor, location and processing assessments are complete where relevant.
- [ ] Operational readiness, resilience, access review, incident response, retention/disposal, rollback and audit evidence are approved.
- [ ] Tableau embedding/authentication/licensing checks are complete if embedding is in scope.

## 20. Public reference links

The following are reference starting points. They do not replace Bank's internal policies, control standards, legal review, or a formal clause-by-clause applicability assessment.

1. OJK — [PADK OJK No. 1 Tahun 2026: Penyelenggaraan Teknologi Informasi oleh Bank Umum](https://ojk.go.id/id/regulasi/Pages/PADK-1-Tahun-2026-Penyelenggaraan-Teknologi-Informasi-oleh-Bank-Umum.aspx) (effective 1 March 2026; verify current status and applicability with Bank Legal/Compliance).
2. BPK — [UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi](https://peraturan.bpk.go.id/Details/229798/uu-no-27-tahun-2022).
3. Tableau — [Embedding API v3: Authentication and Embedding](https://help.tableau.com/current/api/embedding_api/en-us/docs/embedding_api_auth.html).
4. Tableau — [Embedding API v3 overview](https://help.tableau.com/current/api/embedding_api/en-us/).
5. Tableau — [Connected Apps for Application Integration (Tableau Server)](https://help.tableau.com/current/server/en-us/connected_apps.htm).

---

**End of PRD — all proposed workflows, controls and approvals must be aligned to Bank's approved operating model and confirmed by relevant control owners before implementation.**
