# Panduan Demo — Bank Data & Analytics Hub (PoC)

**Durasi:** ±15 menit · **URL:** http://127.0.0.1:8000 · **Sebelum mulai:** `scripts\run.ps1 -Reset` supaya datanya bersih.

Tip: buka dua jendela browser (satu biasa, satu incognito) supaya bisa login sebagai dua persona sekaligus tanpa bolak-balik logout.

---

## Pesan utama (30 detik pembuka)

> "Hari ini user tidak tahu data atau dashboard apa yang sudah ada, definisi KPI bisa berbeda antar unit, dan request masuk lewat email/chat tanpa jejak. Hub ini satu pintu masuk untuk **mencari → meminta → memakai → mengawasi** data, **tanpa** menggantikan lakehouse, Tableau, atau IAM yang sudah ada, dan **tanpa** melemahkan kontrol akses."

---

## Babak 1 — Discover: "cari dulu sebelum minta" (3 menit)

Login sebagai **Rina Wulandari** (Business requester, clearance Internal).

1. Di beranda, ketik **`kredit macet`** → muncul istilah *Non-Performing Loan*, *NPL Monitoring Mart*, dan dashboard *NPL Monitoring by Region*.
   - Poin: pencarian mengerti bahasa bisnis (ID/EN), user tidak perlu tahu nama tabel.
2. Klik **Retail Funding Daily (CASA & Time Deposit)**: owner, steward, sumber, refresh terakhir, skor kualitas, permitted use.
   - Poin: bagian *Schema & fields* **terkunci** karena aset ini Confidential dan Rina belum punya akses. **Metadata bukan akses.**
3. Buka **Business Glossary** → *Active Account* berstatus **Under Review — not official**.
   - Poin: definisi yang belum disetujui owner ditandai dengan jelas, jadi tidak ada lagi dua angka "rekening aktif" yang berbeda.
4. Buka **Analytics Hub** → klik **Open in Tableau** pada *Retail Funding Performance* → terbuka.
   Lalu coba **NPL Monitoring by Region** → **"You don't have permission"**.
   - Poin: Hub hanya katalog dan tautan. **Tableau tetap menegakkan izinnya sendiri**, dan portal tidak memakai akun privileged bersama.

*(Opsional, untuk kepala wilayah)*: cari **`peta potensi`** → buka **Regional Potential Map (H3)** → **Open in Tableau**.
   - Peta hexagon H3 menunjukkan di mana potensi dana belum tergarap. Pilih **Wilayah Bekasi**, peta langsung zoom ke wilayah itu. Klik hexagon prioritas no. 1 untuk melihat angka dan H3 index-nya.
   - Poin: metodenya sama dengan Company Impact Map di Integrated Platform (h3 4.5.0, agregasi per hexagon, kelas quantile). Login sebagai **Budi** (Risk) → dashboard yang sama **ditolak**, karena Tableau tetap menegakkan izinnya sendiri.

## Babak 2 — Request: alur akses yang transparan (5 menit)

5. Dari halaman ditolak tadi, klik **Request access via Data & Analytics Hub** → isi tujuan bisnis → **Submit**.
   - Coba dulu ketik `NIK 3174012508900003` di kolom *Business purpose*, lalu submit → **form menolak** dan menunjukkan identitas yang terdeteksi. Hapus, lalu submit lagi.
   - Request mendapat nomor `REQ-2026-00xx`, plus timeline dan stepper status.
6. Logout → login **Agus Pratama** (Data owner Credit Risk). Lonceng notifikasi menunjukkan request baru (isinya hanya ID dan status, bukan detail bisnis).
   Buka request → isi rationale → **Approve**.
   - Poin: status menjadi **Approved – Awaiting Fulfilment**. *Approval ≠ access.* Kalau Rina mencoba buka Tableau sekarang, **tetap ditolak**.
7. Login **Maya Putri** (BI service owner) → buka request → **Provision access in system of record** → muncul evidence ref `TBL-GRP-…`.
8. Login **Rina** → buka *NPL Monitoring by Region* di Tableau → **sekarang terbuka**. Konfirmasi di request → **Closed**.

*(Opsional, untuk aset Confidential)*: buka `REQ-2026-0013` sebagai **Yusuf Hakim** (Security & Privacy). Data owner sudah approve, tapi request masih menunggu **review keamanan bersyarat**. Ini contoh kontrol berbasis risiko.

## Babak 3 — Mencegah duplikasi (2 menit)

9. Login **Rina** → Request Center → **New dashboard / report** → judul *"CASA funding performance by branch"*, KPI *CASA* → submit.
   - Hub menampilkan **"these existing assets may already answer your need"** → *Retail Funding Performance*.
10. Login **Maya** → My Workspace → antrean → `REQ-2026-0017` (*Daily CASA by region*) → **Close — existing asset fits** → `dashboard:DB-001`.
    - Poin: satu dashboard duplikat tidak perlu dibuat, dan ini dihitung di metrik *Duplicate requests prevented*.

## Babak 4 — Govern: bukti untuk Risk/Audit (4 menit)

11. Login **Tono Saputra** (Portal admin) → **Administration**:
    - Klik **Simulate outage** pada *Enterprise IAM* → buka request `REQ-2026-0016` sebagai **Hendra** → *Provision* → hasilnya **Provision Failed**, tidak ada akses yang diberikan (*fail closed*). Lalu **Restore**.
    - Poin segregation of duties: admin **tidak bisa** approve atau provisioning (antrean admin kosong, dan percobaannya tercatat sebagai *denied*).
12. Login **Lina Marlina** (Internal audit):
    - **Audit Trail** → banner **Integrity verified** (hash chain SHA-256, tabel tidak bisa di-UPDATE/DELETE) → **Export evidence (CSV)**.
    - **Service Metrics** → search-to-success, lead time, SLA, backlog, duplikat yang dicegah, efektivitas kontrol.
    - **Evidence Pack** → **44/44 tes lulus** (positif & negatif, ditautkan ke pasal PRD), checklist penerimaan PoC, dan **Production release gate: Blocked** sampai Legal, Arsitektur, Security, dan lainnya menandatangani.

## Penutup (30 detik)

> "PoC ini membuktikan alur end-to-end dan kontrolnya bekerja. Untuk masuk ke pilot, kita butuh keputusan Bank pada beberapa hal di bawah."

---

## Pertanyaan yang mungkin muncul

| Pertanyaan | Jawaban singkat |
|---|---|
| Apakah ini menggantikan Tableau / lakehouse / ITSM? | Tidak. Hub adalah lapisan pengalaman dan workflow. Sistem sumber tetap menjadi system of record. |
| Kalau user lihat di katalog, berarti boleh akses? | Tidak. Metadata ≠ akses. Akses diputuskan owner dan ditegakkan di sistem sumber (lihat demo Tableau tadi). |
| Bagaimana kalau IAM atau Tableau down? | Fail closed: tidak ada akses yang diberikan, status jelas (*Provision Failed* / *temporarily unavailable*). |
| Data nasabah masuk ke portal? | Tidak. Hanya metadata dan workflow. Teks bebas diperiksa NIK/rekening/kartu dan diblokir atau diredaksi. |
| Apakah auditnya bisa diubah? | Append-only + hash chain. Perubahan terdeteksi (ada tes otomatisnya). |
| Kenapa Tableau tidak di-embed? | Sesuai PRD: MVP pakai deep link (Level 1). Embedding (Level 2) menunggu konfirmasi versi, model identitas, dan lisensi Tableau. |

## Batasan PoC & keputusan yang dibutuhkan dari Bank (PRD §18)

1. **Sponsor, product owner, dan service owner.**
2. **Source of truth** untuk katalog, glossary, kepemilikan, dan approval: apakah Hub menjadi workflow-nya, atau terhubung ke ITSM yang ada?
3. **Tableau discovery**: Server atau Cloud, versi, IdP, lisensi, struktur site/project, dan API yang diizinkan.
4. **Domain pilot dan data owner** yang bersedia menyetujui definisi resmi. Glossary di PoC hanya contoh.
5. **Hosting dan integrasi SSO** di lingkungan non-produksi Bank.
6. **Matriks approval dan klasifikasi**: siapa menyetujui apa, dan metadata mana yang boleh dilihat oleh siapa.
7. **Delegate approver per domain**: PoC sudah mengalihkan request milik data owner ke *delegate approver* (contoh: Dewi ↔ Agus, terlihat di Administration → Routing). Siapa delegasi resminya per domain perlu ditetapkan Bank dalam matriks approval.

## Persona

| Persona | Peran | Clearance |
|---|---|---|
| Rina Wulandari | Business requester (Retail Funding) | Internal |
| Budi Santoso | Risk analyst / data consumer | Confidential |
| Dewi Lestari | Data owner: Retail, SME, Ops & Channels, CX | Restricted |
| Agus Pratama | Data owner: Credit Risk, Finance, Treasury, HC | Restricted |
| Sari Rahmawati | Data steward | Confidential |
| Hendra Wijaya | Data Platform Engineering (fulfilment dataset) | Confidential |
| Maya Putri | BI & Analytics service owner (fulfilment dashboard) | Confidential |
| Yusuf Hakim | Security & Privacy reviewer | Restricted |
| Tono Saputra | Portal admin (tanpa hak data/approval) | Internal |
| Lina Marlina | Internal audit (read-only) | Internal |
