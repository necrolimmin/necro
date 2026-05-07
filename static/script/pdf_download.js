/**
 * =====================================================================
 *  Hisobot №1 — PDF yuklab olish funksiyasi
 *  Ishlatilgan kutubxonalar (CDN orqali):
 *    - html2canvas  v1.4.1
 *    - jsPDF        v2.5.1
 *
 *  Bu faylni <body> oxiriga yoki Django template ichiga qo'shing.
 *  Tugma allaqachon mavjud:  id="t1DownloadPdfBtn"
 * =====================================================================
 */

/* ---------- 1. CDN kutubxonalarni dinamik yuklash ---------- */
(function loadLibsAndInit() {
  function loadScript(src, cb) {
    if (document.querySelector('script[src="' + src + '"]')) { cb(); return; }
    const s = document.createElement('script');
    s.src = src;
    s.onload = cb;
    s.onerror = () => console.error('Script yuklanmadi:', src);
    document.head.appendChild(s);
  }

  // html2canvas → jsPDF ketma-ket yuklanadi
  loadScript(
    'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js',
    () => loadScript(
      'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
      initPdfButton
    )
  );
})();


/* ---------- 2. Tugmani ulash ---------- */
function initPdfButton() {
  const btn = document.getElementById('t1DownloadPdfBtn');
  if (!btn) return;

  btn.addEventListener('click', async function () {
    // Tugmani bloklash + loading holati
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '⏳ Tayyorlanmoqda...';

    try {
      await generateTablePdf();
    } catch (err) {
      console.error('PDF xatosi:', err);
      alert('PDF yaratishda xatolik yuz berdi. Konsolni tekshiring.');
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalHTML;
    }
  });
}


/* ---------- 3. Asosiy PDF generatsiya funksiyasi ---------- */
async function generateTablePdf() {
  const { jsPDF } = window.jspdf;

  /* --- 3.1  Capture qilinadigan element --- */
  const panel   = document.querySelector('.t1a-panel');
  const wrapper = document.querySelector('.t1a-wrap');
  const scroll  = document.querySelector('.t1a-scroll');
  const table   = document.getElementById('t1admin');

  if (!table) { alert("Jadval topilmadi!"); return; }

  /* --- 3.2  Scroll konteynerini vaqtincha kengaytirish
             (html2canvas sticky / overflow elementlarini to'liq ushlab olishi uchun) --- */
  const prevMaxH    = scroll.style.maxHeight;
  const prevOverflX = scroll.style.overflowX;
  const prevOverflY = scroll.style.overflowY;

  scroll.style.maxHeight  = 'none';
  scroll.style.overflowX  = 'visible';
  scroll.style.overflowY  = 'visible';

  /* --- 3.3  Sahifa sarlavhasi matni --- */
  const headerEl = document.querySelector('.t1a-hdr');
  const titleEl  = document.querySelector('.t1a-titlebox h2');
  const headerTxt = headerEl  ? headerEl.textContent.trim()  : '';
  const titleTxt  = titleEl   ? titleEl.textContent.trim()   : 'Hisobot №1';

  /* --- 3.4  html2canvas bilan rasmga olish --- */
  const canvas = await html2canvas(wrapper, {
    scale          : 2,          // 2× o'lcham — aniq piksellar
    useCORS        : true,
    allowTaint     : true,
    backgroundColor: '#ffffff',
    logging        : false,
    scrollX        : 0,
    scrollY        : -window.scrollY,
    windowWidth    : wrapper.scrollWidth  + 40,
    windowHeight   : wrapper.scrollHeight + 40,
    onclone(clonedDoc) {
      /* Klonlangan hujjatda scroll cheklovlarini olib tashlaymiz */
      const cs = clonedDoc.querySelector('.t1a-scroll');
      if (cs) {
        cs.style.maxHeight  = 'none';
        cs.style.overflowX  = 'visible';
        cs.style.overflowY  = 'visible';
      }
      /* Sticky ustunlarni normal holatga qaytaramiz (clonda sticky ishlamaydi) */
      clonedDoc.querySelectorAll('.t1a-stickyA, .t1a-stickyB, .t1a-stickyC').forEach(el => {
        el.style.position = 'static';
      });
    }
  });

  /* --- 3.5  Scroll holatini qaytarish --- */
  scroll.style.maxHeight  = prevMaxH;
  scroll.style.overflowX  = prevOverflX;
  scroll.style.overflowY  = prevOverflY;

  /* --- 3.6  PDF o'lchamlari hisoblash --- */
  const imgW  = canvas.width;
  const imgH  = canvas.height;

  // A4 landscape: 297 × 210 mm  → jsPDF pt: 1mm ≈ 2.835 pt
  const pageW = 297;  // mm
  const pageH = 210;  // mm
  const margin = 8;   // mm — chetdan masofa

  // Rasm eni sahifaga sig'adigan koeffitsient
  const availableW = pageW - margin * 2;          // mm
  const ratio      = availableW / (imgW / 2);      // mm/px  (scale=2 bo'lgani uchun /2)

  const scaledImgW = availableW;                   // mm
  const scaledImgH = (imgH / 2) * ratio;           // mm

  /* --- 3.7  Ko'p sahifalik PDF yaratish --- */
  const pdf = new jsPDF({
    orientation : 'landscape',
    unit        : 'mm',
    format      : 'a4',
    compress    : true,
  });

  // Sarlavha va sana uchun yuqori bo'sh joy
  const headerReserved = 14;   // mm
  const availableH     = pageH - margin - headerReserved - margin; // bir sahifadagi rasm uchun balandlik

  const totalPages = Math.ceil(scaledImgH / availableH);

  for (let page = 0; page < totalPages; page++) {

    if (page > 0) pdf.addPage('a4', 'landscape');

    /* --- Sarlavha (har sahifada) --- */
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(9);
    pdf.setTextColor(30, 30, 30);
    pdf.text(titleTxt, margin, margin + 4);

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(7);
    pdf.setTextColor(80, 80, 80);
    // Uzun sarlavhani 2 qatorga sig'dirish
    const splitHeader = pdf.splitTextToSize(headerTxt, availableW);
    pdf.text(splitHeader, margin, margin + 9);

    // Sahifa raqami (o'ng tomonda)
    pdf.setFontSize(7);
    pdf.setTextColor(120, 120, 120);
    pdf.text(`${page + 1} / ${totalPages}`, pageW - margin, margin + 4, { align: 'right' });

    // Ajratuvchi chiziq
    pdf.setDrawColor(180, 180, 180);
    pdf.setLineWidth(0.3);
    pdf.line(margin, margin + headerReserved - 2, pageW - margin, margin + headerReserved - 2);

    /* --- Rasmni kesib joylashtirish --- */
    const srcYpx  = (page * availableH / ratio) * 2;   // canvas px (scale=2)
    const srcHpx  = Math.min((availableH / ratio) * 2, imgH - srcYpx);
    const dstH    = srcHpx / 2 * ratio;                 // mm

    // Canvas bo'lagini alohida canvasga ko'chiramiz
    const sliceCanvas  = document.createElement('canvas');
    sliceCanvas.width  = imgW;
    sliceCanvas.height = srcHpx;
    const ctx = sliceCanvas.getContext('2d');
    ctx.drawImage(canvas, 0, srcYpx, imgW, srcHpx, 0, 0, imgW, srcHpx);

    const sliceDataUrl = sliceCanvas.toDataURL('image/jpeg', 0.92);

    pdf.addImage(
      sliceDataUrl,
      'JPEG',
      margin,
      margin + headerReserved,
      scaledImgW,
      dstH,
      '',
      'FAST'
    );
  }

  /* --- 3.8  Fayl nomini dinamik yaratish va saqlash --- */
  // Sana: {{ date|date:"d.m.Y" }} HTML dagi titlebox dan o'qiymiz
  const dateMatch = titleTxt.match(/\d{2}\.\d{2}\.\d{4}/);
  const dateStr   = dateMatch ? dateMatch[0].replace(/\./g, '-') : 'hisobot';
  const fileName  = `Hisobot_1_${dateStr}.pdf`;

  pdf.save(fileName);
}