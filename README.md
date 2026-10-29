# Bank Data & Analytics Hub — Proof of Concept

PoC yang bisa dijalankan untuk PRD [v0.1](Data_Analytics_Hub_PoC_PRD.md) dan [v0.2](Data_Analytics_Hub_PoC_PRD_v0.2_Compliance.md): portal **Discover → Request → Govern → Generate → Review** di atas platform data dan Tableau yang sudah ada.

**v2** menambahkan **AI Dashboard Generator** (Phase 1, hanya metadata). Rinciannya ada di bagian [v2](#v2--ai-dashboard-generator-phase-1) di bawah.

> Lingkungan non-produksi. Semua orang, metadata, dan request adalah **sintetis**. Tidak ada data nasabah. SSO dan Tableau masih **disimulasikan**. "Bank" hanyalah nama placeholder; ini proyek portofolio pribadi dan tidak berafiliasi dengan bank mana pun.

## Cara menjalankan

```powershell
# sekali saja: venv + dependency (venv sudah dibuat di .venv)
py -3.13 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# jalankan aplikasi → http://127.0.0.1:8000
powershell -ExecutionPolicy Bypass -File scripts\run.ps1
# reset ke data demo awal
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Reset

# jalankan 58 skenario uji positif & negatif → hasilnya muncul di halaman /evidence
powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1
```

Login dengan memilih persona (mock IdP). Skenario demo langkah demi langkah ada di [DEMO_GUIDE.md](DEMO_GUIDE.md).

## Isi PoC

| Area PRD | Yang sudah jalan |
|---|---|
| §7.1 Homepage | Pencarian utama, "Needs your action", request terakhir, dashboard & data populer |
| §7.2 Catalog / FR-003, FR-004 | 16 aset (dataset/table/data product), owner, steward, klasifikasi, freshness, kualitas, lineage, permitted use |
| §7.3 Glossary / FR-005 | 15 istilah bisnis, status Approved/Draft/Under Review, versi, workflow revisi steward → owner |
| §7.4, §9 Tableau / FR-010, FR-011 | Galeri 14 dashboard, *deep link* (Level 1); Tableau tiruan yang menegakkan izinnya sendiri. Termasuk **Regional Potential Map (H3)** untuk kepala wilayah: potensi dana yang belum tergarap per hexagon H3 (r7–r9), filter per wilayah, dan daftar hexagon prioritas |
| §7.5, §8 Request Center / FR-006–FR-009 | Tipe A–E, form kondisional, routing, approval bersyarat (Security & Privacy untuk Confidential/Restricted), approval ≠ provisioning |
| §7.6 My Workspace | Request saya, antrean saya, entitlement saya, revoke oleh data owner |
| §7.7 Admin | Service catalog yang berversi, simulasi outage (fail-closed), sync metadata Tableau, outbox notifikasi |
| FR-012 Audit | Audit trail append-only dengan hash chain SHA-256, verifikasi integritas, ekspor CSV |
| FR-013 PII | Deteksi NIK, rekening/CIF, kartu (Luhn), NPWP, email, telepon di teks bebas → diblokir atau diredaksi |
| FR-015 Release gate | Sign-off per control owner; rilis produksi terkunci sampai semua item ditandatangani |
| FR-018 Metrics | Search-to-success, duplikat yang dicegah, lead time, SLA, backlog, coverage katalog, efektivitas kontrol |
| §15.3 Tests | 58 skenario pytest (19 positif, 39 negatif), ditautkan ke referensi PRD |
| SoD / delegasi | Data owner tidak pernah memutuskan request miliknya sendiri; otomatis dialihkan ke *delegate approver* domain |

## v2 — AI Dashboard Generator (Phase 1)

Menu **Generate → Dashboard Generator** (`/generator`). Alurnya:

1. User mengetik pertanyaan bisnis (Bahasa Indonesia atau Inggris), audiens, dan keputusan yang didukung, lalu memilih maksimal 3 aset.
2. Generator **hanya** memakai metadata yang boleh dilihat user tersebut. Aset Restricted dan kolom di atas clearance-nya tidak pernah masuk.
3. Planner deterministik (`rules-v1`) menyusun spec JSON (`dash-spec/1.0`): KPI, grafik line/bar, tabel, dan filter. Setiap tebakan ditulis sebagai *assumption*, dan setiap hal yang tidak ada di metadata ditulis sebagai *open question*.
4. Validator server-side menolak field yang tidak dikenal atau tersembunyi, agregasi yang tidak masuk akal (misalnya SUM atas rasio), tipe komponen di luar allow-list, markup atau kode, dan penggabungan lintas aset.
5. Template tepercaya menggambar preview dari **angka acak** berlabel `SYNTHETIC DATA — NOT Bank ACTUALS`.
6. User bisa mengedit spec. Setiap simpanan divalidasi ulang dan menjadi versi baru. Draft lalu diajukan sebagai **request Tipe C**, sehingga BI triage dan data owner yang memutuskan.

| PRD v0.2 | Implementasi |
|---|---|
| FR-023, FR-025 | `app/generator.py`: `metadata_package` → `plan` → `validate` |
| FR-024 | Banner sticky, watermark di setiap grafik, tag di setiap KPI dan tabel |
| FR-026, FR-033 | Assumptions, open questions, dan profil kualitas metadata per aset |
| FR-027 | Tidak ada model. `HUB_MODEL_PROVIDER` yang belum disetujui diabaikan dan user diberi tahu |
| FR-028 | Otorisasi diperiksa ulang setiap kali draft dibuka. Akses yang dicabut menyembunyikan spec |
| FR-029 | Teks berisi instruksi di pertanyaan diblokir. Deskripsi metadata yang berisi instruksi diabaikan |
| FR-030, FR-031 | Draft tetap `draft: true`, berversi, tercatat di audit, dan dikunci setelah diajukan |
| FR-032 | Tidak ada connector, SQL, ekspor, atau publikasi di kode (diuji juga lewat AST import check) |
| FR-034 | Kartu telemetri di Service Metrics (validitas, edit, ditolak, diblokir, latency) |
| §19 gate | Release gate baru G10 (metadata asli) dan G11 (model/provider + DPIA) |

Skema DB baru (`gen_drafts`, `gen_versions`) dibuat otomatis. Gate G10/G11 hanya muncul setelah reset data (`run.ps1 -Reset`).

## Struktur

```
app/
  main.py       rute web, error handling yang aman, halaman admin/audit/evidence
  workflow.py   state machine request, routing, SoD, provisioning (fail-closed)
  policy.py     aturan otorisasi (default deny, visibilitas berbasis klasifikasi)
  search.py     pencarian lintas katalog/glossary/Tableau + sinonim ID/EN
  audit.py      audit trail hash-chained
  pii.py        deteksi & redaksi identitas nasabah
  metrics.py    metrik layanan (PRD §16)
  generator.py  AI Dashboard Generator: metadata otorisasi, planner aturan, validator, preview sintetis
  geo.py        peta potensi H3 (agregasi hexagon, data sintetis) untuk dashboard DB-014
  seed.py       data demo sintetis (riwayat request diputar ulang lewat workflow engine)
  templates/, static/
tests/          skenario positif & negatif (evidence pack)
scripts/        run.ps1, run_tests.ps1
```

Stack: Python 3.13, FastAPI, Jinja2, SQLite, h3 4.5.0 (versi sama dengan Integrated Platform). Tanpa CDN atau layanan eksternal, jadi bisa jalan di jaringan internal tanpa internet. Satu-satunya pengecualian adalah basemap peta H3 (tile OSM, sama seperti Integrated Platform). Basemap ini hanya diizinkan di halaman peta, dan bisa diarahkan ke tile server internal atau dimatikan:

| Env var | Default | Keterangan |
|---|---|---|
| `HUB_TILE_URL` | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | tile server yang disetujui / self-hosted; kosongkan (`""`) untuk mode offline tanpa basemap |
| `HUB_TILE_ATTRIBUTION` | `© OpenStreetMap contributors` | atribusi sesuai provider tile |

## Yang sengaja disimulasikan (harus diganti sebelum pilot)

- **SSO**: pemilih persona → diganti integrasi IdP Bank (SAML/OIDC + MFA).
- **Tableau**: `/mock-tableau/...` → URL Tableau Server/Cloud asli. Discovery checklist di PRD §9.1 harus dijawab dulu.
- **IAM / provisioning**: tabel `entitlements` → sistem access-management resmi atau ITSM.
- **Metadata**: data seed → sumber katalog/glossary yang ditetapkan (keputusan terbuka PRD §18 no. 3).
- **Definisi glossary**: contoh umum industri, **bukan** definisi resmi Bank.
