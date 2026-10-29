async page => {
  const B = 'http://127.0.0.1:8000';
  const OUT = 'demo-video/Data-Analytics-Hub-demo.webm';  // relative to the repo root
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screencast.start({ path: OUT, size: { width: 1440, height: 900 }, fps: 30 });
  await page.screencast.showActions({
    duration: 700,
    style: {
      point: 'width: 22px; height: 22px; border-radius: 50%; background: rgba(241, 90, 34, .55); box-shadow: 0 0 0 4px rgba(241,90,34,.2)',
      title: 'display: none',
    },
  });

  const wait = ms => page.waitForTimeout(ms);
  let cap = null;
  const caption = async (text, ms = 0) => {
    if (cap) await cap.dispose();
    cap = await page.screencast.showOverlay(`
      <div style="position:absolute;left:50%;bottom:28px;transform:translateX(-50%);max-width:1100px;
        background:rgba(10,30,34,.88);color:#fff;padding:12px 22px;border-radius:12px;
        font:500 19px/1.45 'Segoe UI',system-ui,sans-serif;text-align:center;box-shadow:0 8px 24px rgba(0,0,0,.25)">
        ${text}</div>`);
    if (ms) await wait(ms);
  };
  const clear = async () => { if (cap) { await cap.dispose(); cap = null; } };
  const chapter = async (title, description) => {
    await clear();
    await page.screencast.showChapter(title, { description, duration: 3200 });
  };
  const persona = async (uid, who) => {
    await page.goto(`${B}/login`);
    await caption(`Ganti persona → <b>${who}</b>`);
    await wait(900);
    await page.locator(`button[value=${uid}]`).click();
    await page.waitForLoadState();
    await wait(600);
  };
  const highlight = async (locator, label, ms = 3200) => {
    await locator.scrollIntoViewIfNeeded();
    await wait(300);
    const b = await locator.boundingBox();
    if (!b) return;
    await page.screencast.showOverlay(`
      <div style="position:absolute;top:${b.y - 6}px;left:${b.x - 6}px;width:${b.width + 12}px;height:${b.height + 12}px;
        border:3px solid #f15a22;border-radius:10px;box-shadow:0 0 0 9999px rgba(0,0,0,.18)"></div>
      <div style="position:absolute;top:${Math.max(b.y - 44, 8)}px;left:${b.x}px;background:#f15a22;color:#fff;
        padding:6px 12px;border-radius:8px;font:600 15px 'Segoe UI',system-ui,sans-serif">${label}</div>`, { duration: ms });
    await wait(ms);
  };
  const scrollBy = async (y, ms = 1200) => { await page.mouse.wheel(0, y); await wait(ms); };

  // ------------------------------------------------------------------ opening
  await page.goto(`${B}/login`);
  await page.screencast.showChapter('Bank Data & Analytics Hub', {
    description: 'Proof of Concept · Discover → Request → Consume → Govern · semua data sintetis', duration: 4200 });
  await caption('Satu pintu masuk untuk mencari, meminta, memakai, dan mengawasi data — tanpa menggantikan lakehouse, Tableau, atau IAM.', 4500);
  await caption('Login memakai <b>mock SSO</b>: pilih persona untuk menunjukkan perilaku berbasis peran. Produksi memakai SSO Bank + MFA.', 4000);
  await highlight(page.locator('.p-group').first(), 'Persona dikelompokkan sesuai perannya di alur: 1 Minta → 2 Setujui → 3 Kerjakan → 4 Awasi', 4200);

  // ------------------------------------------------------------------ Act 1: Discover
  await chapter('1 · Discover', 'Cari dulu sebelum meminta — sebagai Rina, Business requester (clearance Internal)');
  await page.locator('button[value=rina]').click();
  await page.waitForLoadState();
  await caption('Beranda: pencarian utama, panduan 4 langkah, dan pekerjaan yang menunggu Rina.', 2500);
  await highlight(page.locator('.journey'), 'Cari dulu → buka atau minta → pantau → pakai', 3600);
  await highlight(page.locator('.card', { hasText: 'Needs your action' }), 'Langkah berikutnya langsung terlihat, misalnya “Confirm access works”', 3800);
  await page.mouse.wheel(0, -2000);
  await wait(600);
  const hero = page.locator('.hero-search input');
  await hero.click();
  await hero.pressSequentially('kredit macet', { delay: 90 });
  await caption('Pencarian memahami istilah bisnis Bahasa Indonesia & Inggris — tidak perlu tahu nama tabel.');
  await hero.press('Enter');
  await page.waitForLoadState();
  await wait(1200);
  await highlight(page.locator('.result').first(), '“kredit macet” → Non-Performing Loan', 3200);
  await scrollBy(450, 1500);

  await caption('Halaman aset: owner, steward, sumber, refresh terakhir, kualitas data, dan aturan penggunaan.');
  await page.goto(`${B}/catalog`);
  await wait(1200);
  await page.getByRole('link', { name: 'Retail Funding Daily (CASA & Time Deposit)' }).click();
  await page.waitForLoadState();
  await wait(2500);
  await highlight(page.locator('.card', { hasText: 'Schema & fields' }), 'Metadata ≠ akses: detail kolom Confidential terkunci', 4000);
  await highlight(page.getByRole('link', { name: 'Request access' }).first(), 'Akses selalu lewat alur yang diatur', 2600);

  await caption('Glossary: definisi yang belum disetujui owner ditandai jelas sebagai <b>not official</b>.');
  await page.goto(`${B}/glossary/TM-006`);
  await wait(1500);
  await highlight(page.locator('.page-head .pill').first(), 'Under Review — belum resmi', 3000);
  await scrollBy(500, 1800);

  await caption('Analytics Hub: katalog dashboard Tableau yang sudah ada — owner, domain, sertifikasi, lalu dibuka di sumbernya.');
  await page.goto(`${B}/analytics`);
  await wait(3000);
  await caption('Contoh untuk <b>kepala wilayah</b>: cari dashboard “peta potensi”.');
  const top = page.locator('.top-search input');
  await top.click();
  await top.pressSequentially('peta potensi', { delay: 90 });
  await top.press('Enter');
  await page.waitForLoadState();
  await wait(900);
  await highlight(page.locator('.result').first(), 'Regional Potential Map (H3)', 3000);
  await page.goto(`${B}/mock-tableau/views/DB-014`);
  await wait(1200);
  await caption('Peta hexagon <b>H3</b>: setiap lokasi diindeks ke sel H3 lalu dijumlahkan, metode yang sama dengan Integrated Platform.', 4200);
  await highlight(page.locator('.hx-map'), 'Makin gelap = potensi dana yang belum tergarap makin besar', 3800);
  await caption('Kepala wilayah memilih wilayahnya, dan peta langsung zoom ke sana.');
  await wait(1200);
  await page.locator('#hx-wil').selectOption('Bekasi');
  await page.waitForLoadState();
  await wait(2000);
  await highlight(page.locator('.hx-pri'), 'Hexagon prioritas: potensi terbesar, sering belum ada outlet', 3800);
  await page.locator('.hx-pri button').first().click();
  await wait(900);
  await highlight(page.locator('.hx-detail'), 'Detail sel: potensi, pangsa Bank, outlet, H3 index', 3800);
  await caption('Tingkat detail bisa diubah: City (r7), Area (r8), Neighbourhood (r9).');
  await page.getByRole('link', { name: /Neighbourhood/ }).click();
  await page.waitForLoadState();
  await wait(3000);

  await caption('Dashboard yang memang boleh diakses Rina terbuka di Tableau…');
  await page.goto(`${B}/mock-tableau/views/DB-001`);
  await wait(3200);
  await caption('…tapi yang tidak diizinkan ditolak oleh <b>Tableau sendiri</b>. Hub hanya katalog + tautan, tidak memakai akun privileged bersama.');
  await page.goto(`${B}/mock-tableau/views/DB-002`);
  await wait(4200);

  // ------------------------------------------------------------------ Act 2: Request
  await chapter('2 · Request', 'Alur akses yang transparan: minta → putuskan → provisioning → dipakai');
  await caption('Dari halaman penolakan, Rina langsung mengajukan akses lewat Hub.');
  await page.getByRole('link', { name: 'Request access via Data & Analytics Hub' }).click();
  await page.waitForLoadState();
  await wait(1500);
  await page.locator('#f-purpose').pressSequentially('Cek nasabah NIK 3174012508900003 untuk review NPL', { delay: 35 });
  await page.locator('#f-task').pressSequentially('Paket komite risiko regional', { delay: 35 });
  await page.locator('#f-scope').pressSequentially('Semua wilayah, 12 bulan', { delay: 35 });
  await caption('Coba sengaja menulis NIK nasabah di kolom tujuan…');
  await page.getByRole('button', { name: 'Submit request' }).click();
  await page.waitForLoadState();
  await wait(800);
  await highlight(page.locator('.notice.bad'), 'Diblokir — tidak ada yang tersimpan', 4200);
  await caption('Hapus identitas nasabah, tulis kebutuhan bisnisnya saja, lalu submit.');
  await page.locator('#f-purpose').fill('');
  await page.locator('#f-purpose').pressSequentially('Review NPL bulanan per wilayah untuk komite risiko', { delay: 35 });
  await page.getByRole('button', { name: 'Submit request' }).click();
  await page.waitForLoadState();
  const reqId = page.url().split('/').pop();
  await wait(1200);
  await caption(`Request <b>${reqId}</b> tercatat, divalidasi, dan otomatis diteruskan ke data owner.`, 2800);
  await highlight(page.locator('.now'), 'Selalu jelas: request sedang di tangan siapa, dan apa artinya', 4200);
  await scrollBy(600, 2200);

  await persona('agus', 'Agus Pratama · Data owner Credit Risk');
  await highlight(page.locator('.nav-n'), 'Jumlah hal yang menunggu Agus', 2800);
  await caption('Notifikasi hanya berisi ID & status — detail bisnis tetap di dalam Hub.');
  await page.goto(`${B}/notifications`);
  await wait(2500);
  await page.goto(`${B}/requests/${reqId}`);
  await wait(800);
  await highlight(page.locator('.now'), 'Giliran Agus: approve atau reject', 3000);
  await caption('Data owner memutuskan dengan alasan — tercatat sebagai bukti keputusan (siapa, kapan, versi kebijakan).');
  await page.locator('form:has(input[value=approve]) textarea').pressSequentially('Sesuai tujuan pelaporan manajemen.', { delay: 35 });
  await page.locator('form:has(input[value=approve]) button').click();
  await page.waitForLoadState();
  await wait(800);
  await highlight(page.locator('.notice', { hasText: 'Approved is not provisioned' }), 'Approved ≠ akses. Belum ada akses sampai provisioning.', 4500);

  await persona('maya', 'Maya Putri · BI service owner');
  await page.goto(`${B}/requests/${reqId}`);
  await wait(1200);
  await caption('Tim BI menjalankan provisioning di system of record (Tableau group) — dengan evidence reference.');
  await page.locator('form:has(input[value=provision]) button').click();
  await page.waitForLoadState();
  await wait(800);
  await highlight(page.locator('.card', { hasText: 'Fulfilment' }).last(), 'Bukti provisioning: TBL-GRP-…', 4000);

  await persona('rina', 'Rina Wulandari · Business requester');
  await caption('Sekarang dashboard yang tadi ditolak bisa dibuka oleh Rina.');
  await page.goto(`${B}/mock-tableau/views/DB-002`);
  await wait(4000);
  await page.goto(`${B}/workspace`);
  await wait(1000);
  await caption('My Workspace memisahkan yang menunggu Rina, yang sedang dikerjakan orang lain, dan yang sudah selesai.');
  await highlight(page.locator('.ws-sec').first(), 'Needs you: satu tombol untuk langkah berikutnya', 3800);
  await page.locator(`.ws-sec a[href="/requests/${reqId}#act"]`).click();
  await page.waitForLoadState();
  await wait(1000);
  await caption('Rina mengonfirmasi akses berfungsi → request ditutup.');
  await page.locator('form:has(input[value=confirm]) button').click();
  await page.waitForLoadState();
  await wait(800);
  await highlight(page.locator('.now'), 'Selesai', 2600);

  // ------------------------------------------------------------------ Act 3: Duplicate prevention
  await chapter('3 · Mencegah duplikasi', 'Hub menyarankan aset yang sudah ada sebelum dashboard baru dibuat');
  await page.goto(`${B}/requests/new/C`);
  await wait(1000);
  await page.locator('#f-title').pressSequentially('CASA funding performance by branch', { delay: 45 });
  await caption('Saat mengetik, panel kanan sudah mencari dashboard serupa di katalog.', 2500);
  await page.locator('#f-purpose').pressSequentially('Pantau CASA per cabang untuk review mingguan.', { delay: 30 });
  await page.locator('#f-decision').pressSequentially('Alokasi target funding', { delay: 30 });
  await page.locator('#f-audience').pressSequentially('Kepala wilayah', { delay: 30 });
  await page.locator('#f-kpis').pressSequentially('CASA', { delay: 60 });
  await page.locator('#f-domain_id').selectOption('RET');
  await wait(800);
  await page.getByRole('button', { name: 'Submit request' }).click();
  await page.waitForLoadState();
  await wait(800);
  await highlight(page.locator('.notice', { hasText: 'may already answer your need' }), 'Sudah ada: Retail Funding Performance', 4500);

  await persona('maya', 'Maya Putri · BI service owner');
  await caption('Di antrean BI, request serupa yang sudah masuk ditutup dengan menautkan dashboard yang ada.');
  await page.goto(`${B}/workspace?tab=queue`);
  await wait(1200);
  await highlight(page.locator('table.t'), 'Antrean dengan langkah berikutnya yang disarankan', 3200);
  await page.goto(`${B}/requests/REQ-2026-0017`);
  await wait(1200);
  await caption('Pilihan utama terbuka; pilihan lain cukup satu klik.');
  await page.locator('details:has(input[value=reuse]) > summary').click();
  await wait(900);
  await page.locator('form:has(input[value=reuse]) input[name=result_ref]').pressSequentially('dashboard:DB-001', { delay: 45 });
  await page.locator('form:has(input[value=reuse]) textarea').pressSequentially('Sudah tersedia di Retail Funding Performance.', { delay: 30 });
  await page.locator('form:has(input[value=reuse]) button').click();
  await page.waitForLoadState();
  await wait(800);
  await highlight(page.locator('.pill', { hasText: 'Duplicate prevented' }), 'Satu dashboard duplikat tidak perlu dibangun', 4000);

  // ------------------------------------------------------------------ Act 4: Govern
  await chapter('4 · Govern', 'Kontrol yang bisa dibuktikan ke Risk, Security & Audit');
  await persona('tono', 'Tono Saputra · Portal administrator');
  await caption('Admin mengelola katalog layanan — tapi tidak punya hak approval atau akses data (segregation of duties).');
  await page.goto(`${B}/admin`);
  await wait(2500);
  await caption('Simulasi gangguan: sistem IAM / provisioning dimatikan.');
  await page.locator('form:has(input[value=iam_outage]) button').click();
  await page.waitForLoadState();
  await wait(2500);

  await persona('hendra', 'Hendra Wijaya · Data Platform Engineering');
  await page.goto(`${B}/requests/REQ-2026-0016`);
  await wait(1200);
  await caption('Saat IAM mati, provisioning <b>gagal dengan aman</b> — approval tetap, tapi tidak ada akses yang diberikan (fail closed).');
  await page.locator('form:has(input[value=provision]) button').click();
  await page.waitForLoadState();
  await wait(800);
  await highlight(page.locator('.flash').first(), 'Provision Failed — nothing granted', 4000);

  await persona('tono', 'Tono Saputra · Portal administrator');
  await page.goto(`${B}/admin`);
  await page.locator('form:has(input[value=iam_outage]) button').click();
  await page.waitForLoadState();
  await caption('IAM dipulihkan. Semua perubahan admin tercatat di audit trail.', 2500);

  await persona('lina', 'Lina Marlina · Internal audit');
  await caption('Audit trail: append-only dan ber-hash chain — perubahan atau penghapusan langsung terdeteksi.');
  await page.goto(`${B}/audit`);
  await wait(1200);
  await highlight(page.locator('.notice.good').first(), 'Integrity verified', 3500);
  await caption('Service metrics: search-to-success, duplikat dicegah, lead time, SLA, backlog, dan efektivitas kontrol.');
  await page.goto(`${B}/service/metrics`);
  await wait(3000);
  await scrollBy(700, 2500);
  await caption('Evidence pack: hasil tes positif & negatif otomatis yang ditautkan ke pasal PRD.');
  await page.goto(`${B}/evidence`);
  await wait(3500);
  await scrollBy(900, 2500);
  await page.locator('#gates').scrollIntoViewIfNeeded();
  await wait(800);
  await caption('Release gate produksi tetap <b>terkunci</b> sampai Legal, Arsitektur, Security, dan control owner lain menandatangani.', 5000);

  // ------------------------------------------------------------------ closing
  await clear();
  await page.screencast.showChapter('Langkah berikutnya', {
    description: 'Sponsor & product owner · source of truth katalog/approval · discovery Tableau · domain pilot · hosting & SSO non-produksi',
    duration: 5500 });
  await page.screencast.stop();
  return reqId;
}
