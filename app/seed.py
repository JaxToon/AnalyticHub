"""Synthetic seed data for the PoC.

All people, metadata and request history are fictitious. No real Bank or customer data is used.
Glossary definitions are illustrative industry samples, not official Bank definitions.
"""
import json
import random
from datetime import timedelta

from . import audit
from .db import iso, utcnow
from .policy import load_user
from .workflow import create_request, perform

USERS = [
    # id, name, title, unit, roles, clearance, groups, note
    ("rina", "Rina Wulandari", "Funding Product Manager", "Retail Banking – Funding", "requester",
     "Internal", "all-staff,retail-business", "Business requester. Finds dashboards, requests access & new reports."),
    ("budi", "Budi Santoso", "Senior Risk Analyst", "Credit Risk Analytics", "requester,analyst",
     "Confidential", "all-staff,risk-analytics", "Data consumer. Uses curated data products for analysis."),
    ("dewi", "Dewi Lestari", "Head of Retail Data Domain", "Retail Banking", "data_owner,requester",
     "Restricted", "all-staff,retail-business,retail-owners", "Data owner: Retail, Operations & Channels, CX, SME."),
    ("agus", "Agus Pratama", "Head of Risk & Finance Data Domain", "Risk Management", "data_owner,requester",
     "Restricted", "all-staff,risk-analytics,finance-team", "Data owner: Credit Risk, Finance, Treasury, Human Capital."),
    ("sari", "Sari Rahmawati", "Data Steward", "Central Data Office", "steward,requester",
     "Confidential", "all-staff", "Maintains glossary & metadata; handles data-quality issues."),
    ("hendra", "Hendra Wijaya", "Data Platform Engineer", "Data Platform", "platform",
     "Confidential", "all-staff", "Fulfils dataset access & new data integrations."),
    ("maya", "Maya Putri", "BI & Analytics Service Owner", "BI & Analytics", "bi,analytics",
     "Confidential", "all-staff,bi-team", "Triage dashboard / analysis requests; manages Tableau groups."),
    ("yusuf", "Yusuf Hakim", "Security & Privacy Reviewer", "Information Security", "governance",
     "Restricted", "all-staff", "Conditional reviewer for Confidential / Restricted access."),
    ("tono", "Tono Saputra", "Portal Administrator", "IT Application Support", "admin",
     "Internal", "all-staff", "Manages service catalog & settings. Has NO data or approval rights."),
    ("lina", "Lina Marlina", "IT Auditor", "Internal Audit", "auditor",
     "Internal", "all-staff", "Read-only access to audit trail and evidence pack."),
]

DOMAINS = [
    # id, name, owner, steward, description, delegate approver (used when the owner is the requester)
    ("RET", "Retail Banking", "dewi", "sari", "Funding, consumer lending, cards and retail customer data.", "agus"),
    ("SME", "SME & Business Banking", "dewi", "sari", "SME lending portfolio and business customers.", "agus"),
    ("OPS", "Operations & Channels", "dewi", "sari", "Branch network, ATM, digital channels and operations.", "agus"),
    ("CXP", "Customer Experience", "dewi", "sari", "Complaints, service quality and customer feedback.", "agus"),
    ("RSK", "Credit Risk", "agus", "sari", "Portfolio quality, collectibility, NPL and provisioning.", "dewi"),
    ("FIN", "Finance", "agus", "sari", "General ledger, profitability and management reporting.", "dewi"),
    ("TRE", "Treasury", "agus", "sari", "Liquidity, FX and market positions.", "dewi"),
    ("HCM", "Human Capital", "agus", "sari", "Organisation and workforce data.", "dewi"),
]


def _f(name, typ, desc, sens="Internal", nullable=False):
    return {"name": name, "type": typ, "description": desc, "sensitivity": sens, "nullable": nullable}


def _q(rule, status="Pass"):
    return {"rule": rule, "status": status}


ASSETS = [
    dict(id="AS-001", type="Data product", name="dp_retail_funding_daily",
         title="Retail Funding Daily (CASA & Time Deposit)", domain_id="RET",
         description="Certified daily funding positions for CASA and time deposits, aggregated by product, branch and segment. Primary source for funding performance reporting.",
         source_system="Core Banking → Lakehouse (gold)", classification="Confidential", lifecycle="Certified",
         grain="Product × branch × customer segment × day (no customer identifiers)", refresh="Daily, 06:00 WIB",
         quality_status="Passing", quality_score=98.7, sla="Available 07:00 WIB on business days",
         allowed_use="Management reporting and funding analysis. Not for direct marketing without consent review.",
         retention_class="RC-5 (5 years)", tags="casa,dpk,funding,giro,tabungan,deposito,time deposit",
         fields=[_f("business_date", "DATE", "Position date"), _f("branch_code", "STRING", "Branch code (see Branch Master)"),
                 _f("product_code", "STRING", "Funding product code"), _f("segment", "STRING", "Customer segment"),
                 _f("casa_balance_idr", "DECIMAL(20,2)", "End-of-day CASA balance", "Confidential"),
                 _f("td_balance_idr", "DECIMAL(20,2)", "End-of-day time deposit balance", "Confidential"),
                 _f("account_count", "INTEGER", "Number of active accounts", "Confidential")],
         up=["Core Banking System", "AS-002"], down=["DB-001", "DB-013"],
         rules=[_q("Balance reconciles to GL within 0.01%"), _q("No missing branch_code"), _q("Loaded before 07:00 WIB")]),
    dict(id="AS-002", type="Table", name="gold.retail.casa_balance_daily", title="CASA Balance Daily (account level)",
         domain_id="RET", description="Account-level daily CASA balances. Feeds the Retail Funding data product.",
         source_system="Core Banking → Lakehouse (gold)", classification="Confidential", lifecycle="Published",
         grain="Account × day", refresh="Daily, 05:00 WIB", quality_status="Passing", quality_score=99.2,
         sla="Available 06:00 WIB", allowed_use="Engineering and approved analytical use only; prefer AS-001 for reporting.",
         retention_class="RC-10 (10 years)", tags="casa,giro,tabungan,account,balance",
         fields=[_f("business_date", "DATE", "Position date"), _f("account_key", "STRING", "Surrogate account key (tokenised)", "Confidential"),
                 _f("product_code", "STRING", "Product code"), _f("branch_code", "STRING", "Home branch"),
                 _f("eod_balance_idr", "DECIMAL(20,2)", "End-of-day balance", "Confidential")],
         up=["Core Banking System"], down=["AS-001"], rules=[_q("Unique account_key per day"), _q("Balance not null")]),
    dict(id="AS-003", type="Data product", name="dp_loan_portfolio_monthly", title="Loan Portfolio Monthly Snapshot",
         domain_id="RSK", description="Month-end loan portfolio with outstanding, collectibility and restructuring flags, aggregated to facility level.",
         source_system="Loan Origination + Core Banking → Lakehouse", classification="Confidential", lifecycle="Certified",
         grain="Facility × month-end", refresh="Monthly, BD+3", quality_status="Passing", quality_score=97.9,
         sla="Available by business day 3", allowed_use="Risk analysis, portfolio monitoring, regulatory reporting preparation.",
         retention_class="RC-10 (10 years)", tags="loan,kredit,portfolio,outstanding,kolektibilitas,npl",
         fields=[_f("month_end", "DATE", "Snapshot date"), _f("facility_key", "STRING", "Tokenised facility key", "Confidential"),
                 _f("segment", "STRING", "Business segment"), _f("outstanding_idr", "DECIMAL(20,2)", "Outstanding balance", "Confidential"),
                 _f("collectibility", "TINYINT", "Collectibility 1–5"), _f("dpd", "INTEGER", "Days past due"),
                 _f("restructured_flag", "BOOLEAN", "Restructured facility")],
         up=["Loan Origination System", "Core Banking System"], down=["AS-004", "DB-002", "DB-003"],
         rules=[_q("Collectibility within 1–5"), _q("Outstanding reconciles to GL"), _q("DPD ≥ 0")]),
    dict(id="AS-004", type="Data product", name="dp_npl_monitoring", title="NPL Monitoring Mart", domain_id="RSK",
         description="Aggregated NPL amounts and ratios by region, segment and product. Safe for broad internal use.",
         source_system="Lakehouse (derived from AS-003)", classification="Internal", lifecycle="Certified",
         grain="Region × segment × product × month", refresh="Monthly, BD+4", quality_status="Warning", quality_score=94.1,
         sla="Available by business day 4", allowed_use="Internal management reporting.", retention_class="RC-5 (5 years)",
         tags="npl,non performing loan,kredit bermasalah,ratio,region",
         fields=[_f("month_end", "DATE", "Period"), _f("region", "STRING", "Regional office"), _f("segment", "STRING", "Segment"),
                 _f("npl_amount_idr", "DECIMAL(20,2)", "NPL outstanding (collectibility 3–5)"),
                 _f("gross_npl_ratio", "DECIMAL(7,4)", "NPL / total loans")],
         up=["AS-003"], down=["DB-002", "DB-011"],
         rules=[_q("All regions present", "Warning"), _q("Ratio between 0 and 1")]),
    dict(id="AS-005", type="Table", name="gold.ref.branch_master", title="Branch Master (Reference)", domain_id="OPS",
         description="Reference list of branches, sub-branches and regional offices with hierarchy and status.",
         source_system="Branch Management System", classification="Internal", lifecycle="Certified", grain="Branch",
         refresh="Daily", quality_status="Passing", quality_score=99.8, sla="Daily 05:00 WIB",
         allowed_use="Any internal use.", retention_class="RC-5 (5 years)", tags="branch,cabang,outlet,region,reference",
         fields=[_f("branch_code", "STRING", "Branch code"), _f("branch_name", "STRING", "Branch name"),
                 _f("region", "STRING", "Regional office"), _f("type", "STRING", "KC / KCP / KK"), _f("status", "STRING", "Active / closed")],
         up=["Branch Management System"], down=["AS-001", "DB-004"], rules=[_q("Unique branch_code")]),
    dict(id="AS-006", type="Table", name="gold.channel.atm_txn_hourly_agg", title="ATM Transactions Hourly (Aggregated)",
         domain_id="OPS", description="Hourly ATM transaction counts and amounts by terminal, aggregated — no card or customer data.",
         source_system="ATM Switch → Lakehouse", classification="Internal", lifecycle="Published", grain="Terminal × hour",
         refresh="Hourly", quality_status="Passing", quality_score=96.5, sla="T+1 hour", allowed_use="Operational monitoring and analysis.",
         retention_class="RC-3 (3 years)", tags="atm,e-channel,transactions,cash",
         fields=[_f("hour_ts", "TIMESTAMP", "Hour bucket"), _f("terminal_id", "STRING", "ATM terminal"),
                 _f("txn_count", "INTEGER", "Transactions"), _f("cash_out_idr", "DECIMAL(18,2)", "Cash withdrawn")],
         up=["ATM Switch"], down=["DB-010"], rules=[_q("No future timestamps")]),
    dict(id="AS-007", type="Dataset", name="silver.channel.digital_sessions", title="Digital Channel Usage Events",
         domain_id="OPS", description="Session-level usage events from mobile and internet banking (pseudonymised).",
         source_system="Digital Banking Platform → Lakehouse (silver)", classification="Confidential", lifecycle="Published",
         grain="Session", refresh="Every 4 hours", quality_status="Passing", quality_score=95.0, sla="T+4 hours",
         allowed_use="Product analytics. Aggregated outputs only.", retention_class="RC-2 (2 years)",
         tags="digital,mobile banking,internet banking,sessions,adoption",
         fields=[_f("session_id", "STRING", "Session id"), _f("user_key", "STRING", "Pseudonymised user key", "Confidential"),
                 _f("channel", "STRING", "Mobile / Internet"), _f("feature", "STRING", "Feature used"), _f("ts", "TIMESTAMP", "Event time")],
         up=["Digital Banking Platform"], down=["DB-005"], rules=[_q("user_key tokenised")]),
    dict(id="AS-008", type="Dataset", name="gold.treasury.fx_positions_intraday", title="Treasury FX Positions Intraday",
         domain_id="TRE", description="Intraday FX net open positions by currency and desk.",
         source_system="Treasury System → Lakehouse", classification="Restricted", lifecycle="Published", grain="Desk × currency × 15 min",
         refresh="Every 15 minutes", quality_status="Passing", quality_score=99.0, sla="T+15 min", allowed_use="Treasury & market risk only.",
         retention_class="RC-10 (10 years)", tags="fx,valas,treasury,position,nop",
         fields=[_f("ts", "TIMESTAMP", "Snapshot time"), _f("desk", "STRING", "Desk"), _f("ccy", "STRING", "Currency"),
                 _f("net_open_position", "DECIMAL(20,2)", "Net open position", "Restricted")],
         up=["Treasury System"], down=["DB-006"], rules=[_q("NOP reconciles to treasury system")]),
    dict(id="AS-009", type="Table", name="silver.cif.customer_master", title="Customer Master (CIF) — Personal Data",
         domain_id="RET", description="Customer identity and contact attributes. Personal data under UU PDP.",
         source_system="CIF System", classification="Restricted", lifecycle="Published", grain="Customer",
         refresh="Daily", quality_status="Warning", quality_score=92.3, sla="Daily 05:00 WIB",
         allowed_use="Restricted to approved operational purposes with privacy review.", retention_class="Per PDP retention policy",
         tags="customer,nasabah,cif,personal data",
         fields=[_f("cif_key", "STRING", "Tokenised CIF", "Restricted"), _f("full_name", "STRING", "Name", "Restricted"),
                 _f("birth_date", "DATE", "Date of birth", "Restricted"), _f("segment", "STRING", "Segment")],
         up=["CIF System"], down=["AS-001"], rules=[_q("Completeness of mandatory KYC fields", "Warning")]),
    dict(id="AS-010", type="Data product", name="dp_sme_credit_features", title="SME Credit Scoring Features",
         domain_id="SME", description="Feature store for SME credit scoring models.", source_system="Lakehouse (gold)",
         classification="Restricted", lifecycle="Certified", grain="Borrower × month", refresh="Monthly",
         quality_status="Passing", quality_score=97.1, sla="BD+5", allowed_use="Approved model development & validation only.",
         retention_class="RC-10 (10 years)", tags="sme,umkm,scoring,features,model",
         fields=[_f("borrower_key", "STRING", "Tokenised borrower", "Restricted"), _f("feature_set", "MAP", "Model features", "Restricted")],
         up=["AS-003"], down=[], rules=[_q("Feature drift within threshold")]),
    dict(id="AS-011", type="Table", name="gold.finance.gl_daily_balance", title="General Ledger Daily Balance", domain_id="FIN",
         description="Daily GL balances by account, cost centre and branch.", source_system="General Ledger → Lakehouse",
         classification="Confidential", lifecycle="Certified", grain="GL account × cost centre × day", refresh="Daily, 08:00 WIB",
         quality_status="Passing", quality_score=99.5, sla="08:00 WIB", allowed_use="Finance and management reporting.",
         retention_class="RC-10 (10 years)", tags="gl,general ledger,finance,p&l,balance sheet",
         fields=[_f("business_date", "DATE", "Date"), _f("gl_account", "STRING", "GL account"), _f("cost_centre", "STRING", "Cost centre"),
                 _f("balance_idr", "DECIMAL(22,2)", "Balance", "Confidential")],
         up=["General Ledger"], down=["DB-008", "DB-013"], rules=[_q("Trial balance = 0")]),
    dict(id="AS-012", type="Dataset", name="gold.cx.complaint_cases", title="Customer Complaint Cases", domain_id="CXP",
         description="Complaint cases with category, channel, SLA and resolution status (free-text removed).",
         source_system="Complaint Management System", classification="Confidential", lifecycle="Published", grain="Case",
         refresh="Daily", quality_status="Passing", quality_score=96.0, sla="Daily 07:00 WIB",
         allowed_use="Service quality analysis and regulatory complaint reporting preparation.", retention_class="RC-5 (5 years)",
         tags="complaint,keluhan,pengaduan,sla,cx",
         fields=[_f("case_id", "STRING", "Case id"), _f("category", "STRING", "Complaint category"), _f("channel", "STRING", "Channel"),
                 _f("opened_at", "TIMESTAMP", "Opened"), _f("resolved_at", "TIMESTAMP", "Resolved", nullable=True)],
         up=["Complaint Management System"], down=["DB-007"], rules=[_q("resolved_at ≥ opened_at")]),
    dict(id="AS-013", type="Dataset", name="gold.hc.headcount_monthly", title="Headcount & Organisation Monthly", domain_id="HCM",
         description="Workforce headcount by unit and grade.", source_system="HRIS", classification="Restricted", lifecycle="Published",
         grain="Unit × grade × month", refresh="Monthly", quality_status="Passing", quality_score=98.0, sla="BD+5",
         allowed_use="Human Capital only.", retention_class="Per HC policy", tags="headcount,pegawai,karyawan,organisation",
         fields=[_f("month_end", "DATE", "Period"), _f("unit", "STRING", "Unit"), _f("grade", "STRING", "Grade", "Restricted"),
                 _f("headcount", "INTEGER", "Headcount", "Restricted")],
         up=["HRIS"], down=[], rules=[_q("Headcount ≥ 0")]),
    dict(id="AS-014", type="Table", name="gold.ref.fx_rate_daily", title="FX Reference Rates Daily", domain_id="TRE",
         description="Daily reference exchange rates used for reporting conversion.", source_system="Treasury System",
         classification="Public", lifecycle="Certified", grain="Currency × day", refresh="Daily 09:00 WIB",
         quality_status="Passing", quality_score=100.0, sla="09:00 WIB", allowed_use="Any use.", retention_class="RC-10 (10 years)",
         tags="fx,kurs,valas,exchange rate,reference",
         fields=[_f("rate_date", "DATE", "Date"), _f("ccy", "STRING", "Currency"), _f("mid_rate", "DECIMAL(18,6)", "Mid rate")],
         up=["Treasury System"], down=["AS-011"], rules=[_q("All major currencies present")]),
    dict(id="AS-015", type="Data product", name="dp_sme_portfolio", title="SME Portfolio Overview", domain_id="SME",
         description="Aggregated SME loan portfolio by region, sector and collectibility.", source_system="Lakehouse (derived from AS-003)",
         classification="Internal", lifecycle="Published", grain="Region × sector × month", refresh="Monthly",
         quality_status="Passing", quality_score=97.4, sla="BD+4", allowed_use="Internal management reporting.",
         retention_class="RC-5 (5 years)", tags="sme,umkm,portfolio,loan,kredit",
         fields=[_f("month_end", "DATE", "Period"), _f("region", "STRING", "Region"), _f("sector", "STRING", "Economic sector"),
                 _f("outstanding_idr", "DECIMAL(20,2)", "Outstanding")],
         up=["AS-003"], down=["DB-009"], rules=[_q("Reconciles to AS-003")]),
    dict(id="AS-016", type="Table", name="legacy.risk.npl_report_2023", title="NPL Report Extract 2023 (Legacy)", domain_id="RSK",
         description="Legacy NPL extract. Deprecated — use NPL Monitoring Mart (AS-004).", source_system="Legacy EDW",
         classification="Internal", lifecycle="Deprecated", grain="Region × month", refresh="Not refreshed",
         quality_status="Failing", quality_score=71.0, sla="None", allowed_use="Historical reference only.",
         retention_class="RC-5 (5 years)", tags="npl,legacy,deprecated",
         fields=[_f("period", "STRING", "Period"), _f("region", "STRING", "Region"), _f("npl", "DECIMAL(20,2)", "NPL")],
         up=["Legacy EDW"], down=["DB-011"], rules=[_q("Freshness", "Fail")]),
]

TERMS = [
    ("TM-001", "Non-Performing Loan", "NPL", "Loans classified in collectibility 3 (substandard), 4 (doubtful) or 5 (loss) based on the applicable OJK asset-quality criteria.",
     "", "kredit bermasalah,kredit macet,non performing loan", "RSK", "Approved", 3, "AS-003,AS-004", "DB-002"),
    ("TM-002", "Gross NPL Ratio", "NPL Gross", "Ratio of non-performing loans to total gross loans at period end.",
     "NPL (coll. 3–5) ÷ total gross loans", "rasio npl,npl ratio", "RSK", "Approved", 2, "AS-004", "DB-002,DB-013"),
    ("TM-003", "Current Account & Savings Account", "CASA", "Sum of current account (giro) and savings account (tabungan) balances, excluding time deposits.",
     "Giro + Tabungan", "dana murah,giro tabungan", "RET", "Approved", 2, "AS-001,AS-002", "DB-001"),
    ("TM-004", "CASA Ratio", "CASA Ratio", "Share of CASA in total third-party funds.", "CASA ÷ DPK", "rasio casa",
     "RET", "Approved", 1, "AS-001", "DB-001,DB-013"),
    ("TM-005", "Third-Party Funds", "DPK", "Customer funds placed with the bank as current accounts, savings accounts and time deposits.",
     "Giro + Tabungan + Deposito", "dana pihak ketiga,deposits,simpanan", "RET", "Approved", 1, "AS-001", "DB-001"),
    ("TM-006", "Active Account", "", "An account with at least one customer-initiated financial transaction in the last 6 months.",
     "", "rekening aktif", "RET", "Under Review", 1, "AS-001", "DB-001"),
    ("TM-007", "Outstanding Balance", "OS", "Principal amount owed by the borrower at period end, excluding accrued interest.",
     "", "baki debet,outstanding", "RSK", "Approved", 1, "AS-003", "DB-003"),
    ("TM-008", "Loan-to-Deposit Ratio", "LDR", "Ratio of total loans to total third-party funds.", "Total loans ÷ DPK",
     "loan to deposit ratio", "FIN", "Approved", 1, "AS-003,AS-001", "DB-013"),
    ("TM-009", "Net Interest Margin", "NIM", "Net interest income relative to average earning assets, annualised.",
     "(Interest income − interest expense) ÷ avg. earning assets", "nim", "FIN", "Draft", 1, "AS-011", "DB-008"),
    ("TM-010", "Days Past Due", "DPD", "Number of days a scheduled payment is overdue.", "", "tunggakan,delinquency",
     "RSK", "Approved", 1, "AS-003", "DB-003"),
    ("TM-011", "Collectibility", "Kol", "Asset-quality classification 1 (current) to 5 (loss) per OJK criteria.", "",
     "kolektibilitas,asset quality", "RSK", "Approved", 1, "AS-003", "DB-002"),
    ("TM-012", "Customer", "CIF", "A party with at least one active product relationship identified by a unique CIF.",
     "", "nasabah,client", "RET", "Under Review", 1, "AS-009", ""),
    ("TM-013", "Digital Active User", "DAU", "Customer who logged in to a digital channel at least once in the last 30 days.",
     "", "pengguna aktif digital,mobile banking active", "OPS", "Draft", 1, "AS-007", "DB-005"),
    ("TM-014", "Cost of Fund", "CoF", "Weighted average interest expense on third-party funds.", "Interest expense on DPK ÷ avg. DPK",
     "biaya dana", "FIN", "Approved", 1, "AS-001,AS-011", "DB-008"),
    ("TM-015", "Complaint Resolution Time", "", "Elapsed working days from complaint registration to resolution notice.",
     "", "sla pengaduan", "CXP", "Approved", 1, "AS-012", "DB-007"),
]

TABLEAU = "https://tableau.bank.example/#/site/analytics/views"
DASHBOARDS = [
    ("DB-001", "Retail Funding Performance", "CASA, time deposit and DPK growth by region and branch, with CASA ratio trend.",
     "Retail", "RetailFunding", "Overview", "maya", "RET", "casa,dpk,funding,giro,tabungan,branch", 1, "published",
     "Retail leadership, regional heads", "Internal", "retail-business,retail-owners,bi-team,exec", 1840, "TM-003,TM-004,TM-005", "AS-001"),
    ("DB-002", "NPL Monitoring by Region", "Gross NPL amount and ratio by region and segment, collectibility migration.",
     "Risk", "NPLMonitoring", "ByRegion", "maya", "RSK", "npl,kolektibilitas,region,risk", 1, "published",
     "Risk committee, regional heads", "Internal", "risk-analytics,bi-team,exec", 960, "TM-001,TM-002,TM-011", "AS-004"),
    ("DB-003", "Loan Disbursement Tracker", "Daily loan disbursement against target by product and region.",
     "Risk", "LoanDisbursement", "Tracker", "maya", "RSK", "loan,kredit,disbursement,pencairan", 1, "published",
     "Lending business units", "Confidential", "risk-analytics,bi-team", 702, "TM-007,TM-010", "AS-003"),
    ("DB-004", "Branch Productivity Scorecard", "Branch-level productivity KPIs and ranking.",
     "Operations", "BranchScorecard", "Scorecard", "maya", "OPS", "branch,cabang,productivity,scorecard", 1, "published",
     "Branch managers", "Internal", "all-staff", 2310, "", "AS-005"),
    ("DB-005", "Digital Channel Adoption", "Digital active users, feature adoption and session trends.",
     "Digital", "DigitalAdoption", "Overview", "maya", "OPS", "digital,mobile banking,adoption,dau", 0, "published",
     "Digital banking team", "Internal", "bi-team,digital", 530, "TM-013", "AS-007"),
    ("DB-006", "Treasury Liquidity Monitor", "Intraday liquidity and FX net open position monitor.",
     "Treasury", "LiquidityMonitor", "Intraday", "maya", "TRE", "treasury,liquidity,fx,nop", 1, "published",
     "Treasury desk, ALCO", "Restricted", "treasury-desk", 120, "", "AS-008"),
    ("DB-007", "Complaint Handling SLA", "Complaint volumes, categories and SLA attainment by channel.",
     "CX", "ComplaintSLA", "Overview", "maya", "CXP", "complaint,keluhan,pengaduan,sla", 0, "published",
     "Customer experience team", "Confidential", "cx-team,bi-team", 410, "TM-015", "AS-012"),
    ("DB-008", "Finance Daily P&L Flash", "Daily P&L flash with NIM and cost of fund.",
     "Finance", "PLFlash", "Daily", "maya", "FIN", "p&l,laba rugi,nim,finance,cost of fund", 1, "published",
     "Finance leadership", "Confidential", "finance-team", 300, "TM-009,TM-014", "AS-011"),
    ("DB-009", "SME Portfolio Overview", "SME outstanding by sector and region with collectibility mix.",
     "SME", "SMEPortfolio", "Overview", "maya", "SME", "sme,umkm,portfolio,sector", 0, "under review",
     "SME business unit", "Internal", "bi-team,sme-business", 95, "TM-011", "AS-015"),
    ("DB-010", "ATM Network Availability", "ATM uptime, cash-out volume and incident counts.",
     "Operations", "ATMNetwork", "Availability", "maya", "OPS", "atm,e-channel,uptime,cash", 1, "published",
     "Channel operations", "Internal", "all-staff", 1205, "", "AS-006"),
    ("DB-011", "NPL Report 2023 (Legacy)", "Legacy NPL report. Deprecated — use NPL Monitoring by Region.",
     "Risk", "Legacy_NPL", "Report", "maya", "RSK", "npl,legacy", 0, "deprecated",
     "—", "Internal", "risk-analytics", 12, "TM-001", "AS-016"),
    ("DB-012", "Credit Card Spend Analytics", "Card spend by merchant category and segment.",
     "Retail", "CardSpend", "Overview", "maya", "RET", "card,kartu kredit,spend,merchant", 0, "under review",
     "Cards business", "Confidential", "bi-team", 64, "", ""),
    ("DB-013", "Executive KPI Summary", "Bank-wide headline KPIs: DPK, CASA ratio, LDR, NPL.",
     "Executive", "ExecKPI", "Summary", "maya", "FIN", "executive,kpi,ldr,casa,npl", 1, "published",
     "Board of Directors, executives", "Confidential", "exec", 880, "TM-002,TM-004,TM-008", "AS-001,AS-011"),
    ("DB-014", "Regional Potential Map (H3)", "For regional heads (kepala wilayah): untapped funding potential, "
     "Bank share of local funds and outlet coverage per H3 hexagon, with the top hexagons to prioritise in each region.",
     "Retail", "RegionalPotentialH3", "PotentialMap", "maya", "RET",
     "h3,hexagon,map,peta,peta potensi,potensi,kepala wilayah,wilayah,region,geospatial,dpk,casa,branch,cabang", 1,
     "published", "Regional heads (kepala wilayah), retail leadership, network planning", "Internal",
     "retail-business,retail-owners,bi-team,exec", 640, "TM-003,TM-004,TM-005", "AS-001,AS-005"),
]

SERVICES = [
    ("A", "Data / dashboard access", "Access to an existing catalogued dataset, data product or Tableau dashboard.",
     "platform / bi", 5, "Data owner approval; + Security & Privacy review when Confidential/Restricted. Provisioning in system of record.",
     "ACCESS-POL v0.3 (PoC)"),
    ("B", "New dataset / integration", "Onboard a new source or build a new curated dataset.", "platform", 30,
     "Triage by Data Platform; domain owner authorises source use.", "DATA-INTAKE v0.2 (PoC)"),
    ("C", "New dashboard / report", "Build a new Tableau dashboard or report when no existing view fits.", "bi", 15,
     "Triage by BI incl. duplicate check; domain owner approves KPI definitions.", "BI-INTAKE v0.2 (PoC)"),
    ("D", "Analysis / data science", "Ad-hoc analysis, insight or model.", "analytics", 10,
     "Triage by Analytics; domain owner approves data use; output disclosure review.", "ANALYTICS-INTAKE v0.1 (PoC)"),
    ("E", "Data quality / definition issue", "Report a data-quality problem or dispute a definition.", "steward", 7,
     "Routed to domain steward; definition changes follow glossary approval.", "DQ-ISSUE v0.1 (PoC)"),
]

GATES = [
    ("G01", 1, "Regulatory", "Regulatory & policy mapping approved (PADK OJK 1/2026, UU PDP 27/2022, internal policy)", "legal"),
    ("G02", 2, "Architecture", "Hosting location, environment segregation and integration architecture approved", "architecture"),
    ("G03", 3, "Security", "Threat model, SAST/DAST and penetration test — critical findings closed", "governance"),
    ("G04", 4, "Privacy", "Privacy impact assessment and data minimisation confirmed", "governance"),
    ("G05", 5, "Data governance", "Data owners approved published definitions and asset metadata", "data_owner"),
    ("G06", 6, "Tableau", "Tableau deployment, identity model and licence for chosen integration mode confirmed", "bi"),
    ("G07", 7, "Operations", "Runbooks, monitoring, backup/DR and support model in place", "platform"),
    ("G08", 8, "Assurance", "Mandatory negative access tests pass (evidence reviewed)", "auditor"),
    ("G09", 9, "Change", "Change record, rollback plan and release approval", "admin"),
    ("G10", 10, "AI / metadata", "Metadata classification, purpose and allowed-user matrix approved before real Bank metadata is used by the generator", "data_owner"),
    ("G11", 11, "AI / model", "Model/provider assessment (location, retention, no-training, subprocessors, exit) and DPIA screening before any hosted model", "governance"),
]


def _rows(conn):
    for u in USERS:
        conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?)", (u[0], u[1], u[2], u[3], u[4], u[5], u[6],
                                                                       f"{u[0]}@bank.example", u[7]))
    for d in DOMAINS:
        conn.execute("INSERT INTO domains VALUES (?,?,?,?,?,?)", d)
    now = utcnow()
    domain_owner = {d[0]: (d[2], d[3]) for d in DOMAINS}
    for i, a in enumerate(ASSETS):
        owner, steward = domain_owner[a["domain_id"]]
        updated = now - timedelta(hours=(3 if a["refresh"].startswith(("Daily", "Hourly", "Every")) else 24 * 9) + i)
        if a["lifecycle"] == "Deprecated":
            updated = now - timedelta(days=290)
        conn.execute(
            "INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (a["id"], a["type"], a["name"], a["title"], a["description"], a["domain_id"], a["source_system"], owner,
             steward, a["classification"], a["lifecycle"], a["grain"], a["refresh"], iso(updated), a["quality_status"],
             a["quality_score"], a["sla"], a["allowed_use"], a["retention_class"], a["tags"], json.dumps(a["fields"]),
             json.dumps(a["up"]), json.dumps(a["down"]), json.dumps(a["rules"]),
             f"lakehouse://bank-dp/{a['name']}"))
    for t in TERMS:
        owner, steward = domain_owner[t[6]]
        eff = (now - timedelta(days=120 + 10 * int(t[0][-2:]))).date().isoformat()
        conn.execute("INSERT INTO terms VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (t[0], t[1], t[2], t[3], t[4], t[5], t[6], owner, steward, t[7], t[8], eff, t[9], t[10], iso(now)))
        conn.execute("INSERT INTO term_revisions(term_id, version, definition, formula, change_note, status, author_id,"
                     " created_at, decided_by, decided_at, rationale) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (t[0], t[8], t[3], t[4], "Initial publication" if t[7] == "Approved" else "Initial draft",
                      "approved" if t[7] == "Approved" else "draft", steward, iso(now - timedelta(days=150)),
                      owner if t[7] == "Approved" else None, eff if t[7] == "Approved" else None, None))
    for i, d in enumerate(DASHBOARDS):
        conn.execute("INSERT INTO dashboards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (d[0], d[1], d[2], "analytics", d[3], d[4], d[5], d[6], d[7], d[8], d[9], d[10], d[11], d[12],
                      d[13], iso(now - timedelta(days=1 + i)), iso(now - timedelta(hours=2)), "ok", d[15], d[16], d[14]))
    for s in SERVICES:
        conn.execute("INSERT INTO service_definitions VALUES (?,?,?,?,?,?,?,1,?,?)", (*s, iso(now), "seed"))
    for g in GATES:
        conn.execute("INSERT INTO release_gates VALUES (?,?,?,?,?,'open',NULL,NULL,NULL)", g)
    for key in ("iam_outage", "tableau_outage"):
        conn.execute("INSERT INTO system_flags VALUES (?,?,?,?)", (key, "off", iso(now), "seed"))
    conn.execute("INSERT INTO sync_runs(at, source, status, items, detail, actor_id) VALUES (?,?,?,?,?,?)",
                 (iso(now - timedelta(hours=2)), "Tableau metadata (simulated)", "success", len(DASHBOARDS),
                  "Synchronised title, owner, project, tags, certification, lifecycle", "system"))


# Request history replayed through the real workflow engine so states, events, decisions and
# audit chain are internally consistent. (days_ago, requester, type, data, [(hours_after, actor, action, note, result)])
HISTORY = [
    (48, "budi", "A", {"target": "asset:AS-003", "purpose": "Quarterly portfolio quality review for the risk committee.",
                       "task": "Collectibility migration analysis", "scope": "Last 24 month-ends, all segments",
                       "duration_days": "90", "intended_use": "Ad-hoc analysis"},
     [(20, "agus", "approve", "Purpose fits permitted use for risk analysis.", ""),
      (30, "yusuf", "approve", "Tokenised keys only; no personal data exposed. OK.", ""),
      (40, "hendra", "provision", "", ""), (44, "budi", "confirm", "", "")]),
    (45, "rina", "C", {"title": "Branch funding league table", "purpose": "Rank branches by CASA growth for monthly review.",
                       "decision": "Branch incentive allocation", "audience": "Regional funding heads", "kpis": "CASA, CASA ratio",
                       "refresh": "Monthly", "domain_id": "RET", "confidentiality": "Internal", "priority": "Medium"},
     [(6, "maya", "reuse", "Retail Funding Performance already has a branch ranking tab.", "dashboard:DB-001")]),
    (42, "budi", "E", {"target": "asset:AS-004", "title": "Region missing in NPL mart", "purpose": "One regional office has no rows for the latest month-end.",
                       "impact": "NPL by region understated in committee pack", "period": "Latest month-end", "severity": "High"},
     [(10, "sari", "accept", "", ""), (72, "sari", "resolve", "Root cause: region code remap in source; reloaded and rule added.", ""),
      (96, "budi", "confirm", "", "")]),
    (40, "budi", "D", {"title": "SME early-warning signals", "purpose": "Which behavioural signals precede SME downgrades to collectibility 2?",
                       "decision": "Early-warning watchlist design", "cohort": "SME facilities, 36 months, monthly",
                       "output": "Recommendation memo", "personal_data": "Aggregated only", "domain_id": "SME", "priority": "High"},
     [(24, "maya", "accept", "", ""), (48, "dewi", "approve", "Use of SME portfolio data approved; aggregated output only.", ""),
      (60, "maya", "start", "", ""), (190, "maya", "submit_uat", "Draft memo ready for review.", "Analysis memo AN-2026-014"),
      (214, "budi", "accept_delivery", "", ""), (226, "maya", "close", "Memo published to analytics library.", "Analysis memo AN-2026-014")]),
    (38, "rina", "A", {"target": "dashboard:DB-008", "purpose": "Monitor cost of fund impact on funding products.",
                       "task": "Pricing review", "scope": "Daily, bank-wide", "duration_days": "90", "intended_use": "Management reporting"},
     [(24, "agus", "reject", "P&L flash is limited to finance leadership. Executive KPI Summary covers cost of fund.", "")]),
    (35, "rina", "C", {"title": "Funding campaign tracker", "purpose": "Track daily new CASA from the Q3 campaign by branch.",
                       "decision": "Campaign budget reallocation", "audience": "Funding product team", "kpis": "CASA, Active Account",
                       "dimensions": "Region, branch, product", "refresh": "Daily", "domain_id": "RET",
                       "confidentiality": "Internal", "priority": "High"},
     [(20, "maya", "accept", "", ""), (48, "dewi", "approve", "Use approved CASA definition v2; Active Account still under review — label as provisional.", ""),
      (72, "maya", "start", "", ""), (288, "maya", "submit_uat", "", "Tableau UAT: RetailCampaign/Tracker"),
      (312, "rina", "raise_issue", "CASA ratio filter does not match the glossary definition.", ""),
      (360, "maya", "submit_uat", "Fixed CASA ratio to use DPK denominator.", "Tableau UAT: RetailCampaign/Tracker v2"),
      (384, "rina", "accept_delivery", "", ""), (396, "maya", "close", "Published and registered.", "Tableau: RetailCampaign/Tracker")]),
    (30, "budi", "B", {"title": "Collections call outcomes into lakehouse", "purpose": "Need collections call outcomes to measure cure rates.",
                       "expected_outcome": "Cure-rate model input", "domain_id": "RSK", "source_hint": "Collections system",
                       "frequency": "Daily", "grain": "Facility × call", "consumers": "Credit risk analytics",
                       "sensitivity": "May contain personal data", "priority": "High"},
     [(24, "hendra", "accept", "", ""), (96, "agus", "approve", "Source use approved; personal data must be tokenised.", ""),
      (120, "hendra", "start", "", "")]),
    (28, "budi", "A", {"target": "dashboard:DB-003", "purpose": "Compare disbursement pace with early delinquency.",
                       "task": "Vintage monitoring", "scope": "All products", "duration_days": "180", "intended_use": "Operational monitoring"},
     [(24, "agus", "approve", "Approved for vintage monitoring.", ""), (48, "yusuf", "approve", "No record-level data in view.", ""),
      (52, "maya", "provision", "", ""), (56, "budi", "confirm", "", "")]),
    (25, "rina", "A", {"target": "asset:AS-005", "purpose": "Map funding numbers to branch hierarchy.", "task": "Monthly funding pack",
                       "scope": "All branches", "duration_days": "180", "intended_use": "Management reporting"},
     [(5, "dewi", "approve", "Reference data, approved.", ""), (24, "hendra", "provision", "", ""), (29, "rina", "confirm", "", "")]),
    (21, "rina", "E", {"target": "term:TM-006", "title": "Active Account definition dispute",
                       "purpose": "Funding uses 3-month window, glossary says 6 months. Which one is official?",
                       "impact": "Two dashboards report different active-account counts", "severity": "Medium"},
     [(24, "sari", "accept", "Raised revision to domain owner.", "")]),
    (20, "budi", "A", {"target": "asset:AS-002", "purpose": "Account-level CASA behaviour for churn study.", "task": "Churn study",
                       "scope": "12 months", "duration_days": "90", "intended_use": "Ad-hoc analysis"},
     [(20, "dewi", "approve", "OK from domain side.", ""),
      (40, "yusuf", "reject", "Account-level table not needed — use aggregated data product AS-001 (data minimisation).", "")]),
    (18, "budi", "C", {"title": "Collectibility migration by region", "purpose": "Monthly migration of collectibility by region.",
                       "decision": "Regional collection focus", "audience": "Risk committee", "kpis": "Collectibility, NPL",
                       "refresh": "Monthly", "domain_id": "RSK", "confidentiality": "Internal", "priority": "Medium"},
     [(4, "maya", "reuse", "NPL Monitoring by Region already has a migration tab.", "dashboard:DB-002")]),
    (15, "rina", "A", {"target": "asset:AS-007", "purpose": "Understand digital adoption among funding customers.",
                       "task": "Digital funding campaign design", "scope": "Mobile channel, 6 months",
                       "duration_days": "90", "intended_use": "Ad-hoc analysis"},
     [(24, "dewi", "request_info", "Please confirm whether aggregated daily counts by channel are sufficient.", ""),
      (48, "rina", "respond", "Yes — aggregated daily by channel and feature is enough.", ""),
      (72, "dewi", "approve", "Approved for aggregated use.", "")]),
    (12, "budi", "D", {"title": "Branch deposit churn drivers", "purpose": "What drives deposit outflow at urban branches?",
                       "decision": "Retention programme targeting", "cohort": "Urban branches, 18 months",
                       "output": "Slide summary", "personal_data": "Aggregated only", "domain_id": "RET", "priority": "Medium"},
     [(24, "maya", "accept", "", ""), (48, "dewi", "approve", "Aggregated output only.", ""), (72, "maya", "start", "", "")]),
    (10, "rina", "B", {"title": "Merchant QRIS transactions dataset", "purpose": "Need merchant QR payments to see funding behaviour of merchants.",
                       "expected_outcome": "Merchant funding segment", "domain_id": "RET", "frequency": "Daily",
                       "grain": "Merchant × day", "consumers": "Funding & merchant teams", "sensitivity": "Unsure", "priority": "Medium"},
     [(48, "hendra", "request_info", "Which merchant attributes are needed, and is merchant × day aggregation enough?", "")]),
    (8, "budi", "A", {"target": "asset:AS-012", "purpose": "Link complaint categories to credit product issues.",
                      "task": "Product issue root-cause study", "scope": "Credit products, 12 months",
                      "duration_days": "90", "intended_use": "Ad-hoc analysis"},
     [(24, "dewi", "approve", "Approved; free-text already removed at source.", ""),
      (40, "yusuf", "approve", "OK.", ""), (44, "hendra", "provision", "", "")]),
    (6, "rina", "C", {"title": "Daily CASA by region for regional heads", "purpose": "Regional heads want daily CASA by region in one view.",
                      "decision": "Daily funding huddles", "audience": "Regional heads", "kpis": "CASA, DPK",
                      "dimensions": "Region, product", "refresh": "Daily", "domain_id": "RET",
                      "confidentiality": "Internal", "priority": "High"}, []),
    (5, "budi", "E", {"target": "asset:AS-001", "title": "Time deposit spikes at month-end",
                      "purpose": "Time deposit balances jump on the last business day, then drop.",
                      "impact": "Month-end funding figures overstated", "period": "Last 3 month-ends", "severity": "Medium"},
     [(24, "sari", "accept", "", ""), (72, "sari", "resolve", "Root cause: rollover booked T+0 and T+1; dedup rule added.", "")]),
    (4, "rina", "A", {"target": "dashboard:DB-005", "purpose": "See digital adoption trend for funding customers.",
                      "task": "Campaign design", "scope": "All channels", "duration_days": "90", "intended_use": "Management reporting"},
     [(24, "dewi", "approve", "Approved.", ""), (36, "maya", "provision", "", "")]),
    (3, "budi", "A", {"target": "asset:AS-011", "purpose": "Reconcile loan outstanding to GL for the portfolio pack.",
                      "task": "Portfolio reconciliation", "scope": "Loan GL accounts only", "duration_days": "30",
                      "intended_use": "Management reporting"}, []),
    (2, "rina", "D", {"title": "Rate change impact on TD rollover", "purpose": "Did the last rate change reduce time deposit rollover?",
                      "decision": "Next pricing decision", "cohort": "Time deposits, 6 months", "output": "Slide summary",
                      "personal_data": "Aggregated only", "domain_id": "RET", "priority": "High"}, []),
    (1, "budi", "B", {"title": "Daily ATM cash-out forecast feed", "purpose": "Need forecast-ready daily cash-out per ATM.",
                      "expected_outcome": "Cash replenishment optimisation", "domain_id": "OPS", "frequency": "Daily",
                      "grain": "Terminal × day", "consumers": "Channel operations", "sensitivity": "No personal data expected",
                      "priority": "Medium"}, []),
]

PENDING_REVISION = ("TM-006", "An account with at least one customer-initiated financial transaction in the last 3 months, "
                    "excluding interest credits and fee debits.", "",
                    "Align with funding reporting (3-month window) — raised from definition dispute.")


def seed(conn):
    conn.execute("BEGIN")
    _rows(conn)
    now = utcnow()
    audit.log(conn, "system", "system.seed", "database", "hub", details={"note": "synthetic PoC data"},
              at=now - timedelta(days=60))
    users = {u[0]: load_user(conn, u[0]) for u in USERS}
    for days, requester, rtype, data, steps in HISTORY:
        at = now - timedelta(days=days, hours=random.Random(days).randint(0, 6))
        req_id = create_request(conn, users[requester], rtype, dict(data), at=at)
        for hours, actor, action, note, result in steps:
            if req_id.endswith(f"{16:04d}") and action == "provision":
                conn.execute("UPDATE system_flags SET value='on' WHERE key='iam_outage'")
            jitter = timedelta(minutes=random.Random(days * 100 + hours).randint(3, 55))
            perform(conn, users[actor], req_id, action, note, result, at=at + timedelta(hours=hours) + jitter)
            conn.execute("UPDATE system_flags SET value='off' WHERE key='iam_outage'")
    term_id, definition, formula, note = PENDING_REVISION
    conn.execute("INSERT INTO term_revisions(term_id, version, definition, formula, change_note, status, author_id,"
                 " created_at) VALUES (?,?,?,?,?,?,?,?)",
                 (term_id, 2, definition, formula, note, "in_review", "sari", iso(now - timedelta(days=19))))
    rnd = random.Random(7)
    queries = ["npl", "casa", "kredit macet", "branch", "dpk", "atm", "complaint", "digital", "ldr", "loan",
               "nasabah", "sme", "fx", "p&l", "funding", "collectibility", "cost of fund", "umkm", "churn", "qris"]
    for i in range(140):
        q = rnd.choice(queries)
        conn.execute("INSERT INTO search_log(at, user_id, query, result_count, latency_ms, clicked) VALUES (?,?,?,?,?,?)",
                     (iso(now - timedelta(hours=rnd.randint(1, 1200))), rnd.choice(list(users)), q,
                      0 if q in ("churn", "qris") else rnd.randint(2, 12), round(rnd.uniform(2.5, 28), 1),
                      0 if q in ("churn", "qris") else int(rnd.random() < 0.78)))
    conn.execute("UPDATE notifications SET read=1 WHERE at < ?", (iso(now - timedelta(days=3)),))
    conn.commit()
