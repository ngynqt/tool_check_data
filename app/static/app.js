/* ============================================================
   DataCheck EDA Dashboard - JavaScript
   ============================================================ */

const API = 'http://127.0.0.1:5000/api';

// ─── Navigation ────────────────────────────────────────────────
const sectionMeta = {
  upload:  { title: 'Upload Files',           subtitle: 'Tải lên file dữ liệu để bắt đầu phân tích' },
  preview: { title: 'Xem dữ liệu',            subtitle: 'Dữ liệu hiện tại trong dataset' },
  summary: { title: 'Thống kê cột',           subtitle: 'Tóm tắt thông tin từng cột' },
  'viz-all': { title: 'Null Values - Tất cả cột', subtitle: 'Trực quan hóa giá trị null toàn dataset' },
  'viz-key': { title: 'Kiểm tra cột quan trọng',  subtitle: 'Layer 1: SĐT, Facebook, SĐT 2' },
  clean:   { title: 'Xóa dòng Null',          subtitle: 'Loại bỏ dòng rỗng ở cả 3 cột chính' }
};

function showSection(id) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

  const sec = document.getElementById('section-' + id);
  const btn = document.getElementById('nav-' + id);
  if (sec) sec.classList.add('active');
  if (btn) btn.classList.add('active');

  const meta = sectionMeta[id] || {};
  document.getElementById('page-title').textContent = meta.title || id;
  document.getElementById('page-subtitle').textContent = meta.subtitle || '';

  // Auto-load content when switching tabs
  if (id === 'preview') loadDatasetInfo();
  if (id === 'summary') loadSummary();
}

// ─── Toast ──────────────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type]}</span><span>${msg}</span>`;
  document.getElementById('toast-container').appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}

// ─── Spinner ────────────────────────────────────────────────────
function showSpinner() { document.getElementById('spinner').style.display = 'flex'; }
function hideSpinner() { document.getElementById('spinner').style.display = 'none'; }

// ─── Dataset Status ─────────────────────────────────────────────
function updateStatus(loaded, rows, cols) {
  const dot = document.querySelector('.status-dot');
  const txt = dot.nextElementSibling;
  const badge = document.getElementById('badge-rows');
  const resetBtn = document.getElementById('reset-btn');
  const topStatus = document.getElementById('top-status');

  if (loaded) {
    dot.className = 'status-dot online';
    txt.textContent = `${rows} dòng · ${cols} cột`;
    badge.textContent = rows;
    badge.style.display = 'inline-block';
    resetBtn.style.display = 'inline-flex';
    topStatus.innerHTML = `<span style="color:var(--accent-green)">●</span> Dataset: ${rows.toLocaleString()} dòng`;
  } else {
    dot.className = 'status-dot offline';
    txt.textContent = 'Chưa có dữ liệu';
    badge.style.display = 'none';
    resetBtn.style.display = 'none';
    topStatus.innerHTML = '';
  }
}

// ─── Upload ─────────────────────────────────────────────────────
let selectedFiles = [];

function handleFileSelect() {
  const input = document.getElementById('file-input');
  selectedFiles = Array.from(input.files);
  renderFileList();
}

function renderFileList() {
  const fileList = document.getElementById('file-list');
  const fileNames = document.getElementById('file-names');

  if (!selectedFiles.length) { fileList.style.display = 'none'; return; }

  fileList.style.display = 'block';
  fileNames.innerHTML = selectedFiles.map(f =>
    `<li>📄 <strong>${f.name}</strong> <span style="color:var(--text-muted);font-size:11px">${formatSize(f.size)}</span></li>`
  ).join('');
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

async function uploadFiles() {
  if (!selectedFiles.length) { showToast('Hãy chọn ít nhất một file!', 'error'); return; }

  const formData = new FormData();
  selectedFiles.forEach(f => formData.append('files', f));

  showSpinner();
  try {
    const res = await fetch(`${API}/upload`, { method: 'POST', body: formData });
    const data = await res.json();

    if (data.success) {
      renderUploadResult(data.info);
      updateStatus(true, data.info.rows, data.info.cols);
      showToast(`Đã tải ${data.info.files.length} file, ${data.info.rows} dòng dữ liệu`, 'success');
    } else {
      showToast(data.error || 'Lỗi upload', 'error');
      renderError(document.getElementById('upload-result'), data.error);
    }
  } catch (e) {
    showToast('Không kết nối được server', 'error');
  } finally {
    hideSpinner();
  }
}

function renderUploadResult(info) {
  const el = document.getElementById('upload-result');
  el.style.display = 'block';
  el.className = 'result-card success';

  let errHtml = '';
  if (info.errors && info.errors.length) {
    errHtml = `<div class="warning-box" style="margin-top:12px">⚠️ ${info.errors.join('<br>')}</div>`;
  }

  el.innerHTML = `
    <h3 style="font-size:16px;font-weight:700;margin-bottom:16px;color:var(--accent-green)">
      ✅ Tải thành công ${info.files.length} file
    </h3>
    <div class="info-grid">
      <div class="info-item">
        <div class="info-value">${info.rows.toLocaleString()}</div>
        <div class="info-label">Tổng số dòng</div>
      </div>
      <div class="info-item">
        <div class="info-value">${info.cols}</div>
        <div class="info-label">Số cột</div>
      </div>
      <div class="info-item">
        <div class="info-value">${info.files.length}</div>
        <div class="info-label">File đã gộp</div>
      </div>
      <div class="info-item">
        <div class="info-value">${Object.values(info.null_counts).reduce((a,b)=>a+b,0).toLocaleString()}</div>
        <div class="info-label">Tổng giá trị null</div>
      </div>
    </div>
    <div>
      <p style="font-size:12px;color:var(--text-muted);margin-bottom:8px">Các cột:</p>
      <div class="col-list">
        ${info.columns.map(c => `<span class="col-tag">${c}</span>`).join('')}
      </div>
    </div>
    ${errHtml}
    <div style="margin-top:16px">
      <button class="btn btn-secondary" onclick="showSection('preview')">
        👁️ Xem dữ liệu →
      </button>
    </div>
  `;
}

function renderError(el, msg) {
  el.style.display = 'block';
  el.className = 'result-card error-card';
  el.innerHTML = `<p style="color:var(--accent-red)">❌ ${msg}</p>`;
}

// ─── Drag & Drop ────────────────────────────────────────────────
const zone = document.getElementById('upload-zone');
zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
zone.addEventListener('drop', e => {
  e.preventDefault();
  zone.classList.remove('drag-over');
  selectedFiles = Array.from(e.dataTransfer.files).filter(f =>
    /\.(xlsx|xls|csv|xlsm|xlsb)$/i.test(f.name)
  );
  renderFileList();
  if (selectedFiles.length) showToast(`Đã chọn ${selectedFiles.length} file`, 'success');
  else showToast('Không tìm thấy file hợp lệ (.xlsx, .xls, .csv)', 'error');
});

// ─── Preview ─────────────────────────────────────────────────────
async function loadDatasetInfo() {
  const wrapper = document.getElementById('preview-table-wrapper');
  wrapper.innerHTML = '<p class="placeholder-text">⏳ Đang tải...</p>';

  try {
    const res = await fetch(`${API}/dataset_info`);
    const data = await res.json();

    if (!data.loaded) {
      wrapper.innerHTML = '<p class="placeholder-text">Upload file để xem dữ liệu</p>';
      return;
    }

    updateStatus(true, data.rows, data.cols);
    const rows = data.head;
    const cols = data.columns;

    wrapper.innerHTML = `
      <div style="padding:12px 16px;border-bottom:1px solid var(--border);font-size:12px;color:var(--text-muted)">
        Hiển thị 20 dòng đầu / ${data.rows.toLocaleString()} dòng
      </div>
      <div style="overflow-x:auto;">
        <table class="data-table">
          <thead>
            <tr>
              <th>#</th>
              ${cols.map(c => `<th title="${c}">${c}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
            ${rows.map((row, i) => `
              <tr>
                <td style="color:var(--text-muted);font-size:11px">${i + 1}</td>
                ${cols.map(c => {
                  const val = row[c];
                  const isEmpty = val === '' || val === null || val === undefined;
                  return isEmpty
                    ? `<td class="null-cell">null</td>`
                    : `<td title="${val}">${val}</td>`;
                }).join('')}
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    wrapper.innerHTML = '<p class="placeholder-text" style="color:var(--accent-red)">❌ Lỗi kết nối server</p>';
  }
}

// ─── Summary ──────────────────────────────────────────────────
async function loadSummary() {
  const el = document.getElementById('summary-content');
  el.innerHTML = '<p class="placeholder-text">⏳ Đang tải...</p>';

  try {
    const res = await fetch(`${API}/data_summary`);
    const data = await res.json();

    if (data.error) { el.innerHTML = `<p class="placeholder-text">${data.error}</p>`; return; }

    const dtypeIcon = d => {
      if (d.includes('int') || d.includes('float')) return '🔢';
      if (d.includes('datetime')) return '📅';
      return '🔤';
    };

    el.innerHTML = `
      <div style="margin-bottom:16px;font-size:13px;color:var(--text-secondary)">
        Tổng cộng <strong style="color:var(--text-primary)">${data.total_rows.toLocaleString()}</strong> dòng
      </div>
      <div class="summary-grid">
        ${Object.entries(data.summary).map(([col, s]) => {
          const pct = s.null_pct;
          const barColor = pct === 0 ? 'var(--accent-green)'
            : pct < 20 ? 'var(--accent-orange)'
            : 'var(--accent-red)';
          return `
            <div class="summary-card">
              <div class="summary-col-name">
                ${dtypeIcon(s.dtype)} ${col}
              </div>
              <div class="summary-row">
                <span class="summary-key">Không null</span>
                <span class="summary-val safe">${s.non_null.toLocaleString()}</span>
              </div>
              <div class="summary-row">
                <span class="summary-key">Null</span>
                <span class="summary-val ${s.null > 0 ? 'danger' : 'safe'}">${s.null.toLocaleString()}</span>
              </div>
              <div class="summary-row">
                <span class="summary-key">Null %</span>
                <span class="summary-val ${s.null_pct > 0 ? 'danger' : 'safe'}">${s.null_pct}%</span>
              </div>
              <div class="summary-row">
                <span class="summary-key">Unique</span>
                <span class="summary-val">${s.unique.toLocaleString()}</span>
              </div>
              <div class="summary-row">
                <span class="summary-key">Kiểu</span>
                <span class="summary-val">${s.dtype}</span>
              </div>
              <div class="null-bar-bg">
                <div class="null-bar-fill" style="width:${pct}%;background:${barColor}"></div>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  } catch (e) {
    el.innerHTML = '<p class="placeholder-text" style="color:var(--accent-red)">❌ Lỗi kết nối server</p>';
  }
}

// ─── Visualize Null All ──────────────────────────────────────────
async function visualizeNullAll() {
  const el = document.getElementById('viz-all-result');
  el.innerHTML = '<p class="placeholder-text">⏳ Đang vẽ biểu đồ...</p>';
  showSpinner();

  try {
    const res = await fetch(`${API}/visualize_null_all`, { method: 'POST' });
    const data = await res.json();

    if (data.error) { showToast(data.error, 'error'); el.innerHTML = ''; return; }

    const total = Object.values(data.null_counts).reduce((a, b) => a + b, 0);
    const colsWithNull = Object.entries(data.null_counts).filter(([, v]) => v > 0).length;

    el.innerHTML = `
      <div class="chart-container">
        <div class="null-stats-grid" style="margin-bottom:20px">
          <div class="null-stat-item">
            <div class="null-stat-col">Tổng null</div>
            <div class="null-stat-val ${total > 0 ? 'has-null' : 'zero'}">${total.toLocaleString()}</div>
          </div>
          <div class="null-stat-item">
            <div class="null-stat-col">Cột có null</div>
            <div class="null-stat-val ${colsWithNull > 0 ? 'has-null' : 'zero'}">${colsWithNull}</div>
          </div>
        </div>
        <img src="data:image/png;base64,${data.image}" alt="Null values chart" />
      </div>
    `;
    showToast('Đã vẽ biểu đồ', 'success');
  } catch (e) {
    el.innerHTML = '<p class="placeholder-text" style="color:var(--accent-red)">❌ Lỗi server</p>';
    showToast('Lỗi kết nối server', 'error');
  } finally {
    hideSpinner();
  }
}

// ─── Check Null Key Cols ─────────────────────────────────────────
async function checkNullKeyCols() {
  const el = document.getElementById('viz-key-result');
  el.innerHTML = '<p class="placeholder-text">⏳ Đang kiểm tra...</p>';
  showSpinner();

  try {
    const res = await fetch(`${API}/check_null_key_cols`, { method: 'POST' });
    const data = await res.json();

    if (data.error) { showToast(data.error, 'error'); el.innerHTML = ''; return; }

    const entries = Object.entries(data.null_counts);
    el.innerHTML = `
      <div class="chart-container">
        <div class="null-stats-grid" style="margin-bottom:20px">
          ${entries.map(([col, count]) => `
            <div class="null-stat-item">
              <div class="null-stat-col">${col}</div>
              <div class="null-stat-val ${count > 0 ? 'has-null' : 'zero'}">${count.toLocaleString()}</div>
              <div class="null-stat-pct">${((count / data.total_rows) * 100).toFixed(1)}% của ${data.total_rows.toLocaleString()} dòng</div>
            </div>
          `).join('')}
        </div>
        <img src="data:image/png;base64,${data.image}" alt="Key columns null chart" />
      </div>
    `;

    const hasNull = entries.some(([, v]) => v > 0);
    showToast(hasNull ? 'Phát hiện giá trị null!' : 'Không có giá trị null ✅', hasNull ? 'info' : 'success');
  } catch (e) {
    el.innerHTML = '<p class="placeholder-text" style="color:var(--accent-red)">❌ Lỗi server</p>';
    showToast('Lỗi kết nối server', 'error');
  } finally {
    hideSpinner();
  }
}

// ─── Evaluate Null (Clean) ───────────────────────────────────────
async function evaluateNull() {
  if (!confirm('Bạn có chắc muốn xóa các dòng null ở cả 3 cột (SĐT, Facebook, SĐT 2)?')) return;

  const el = document.getElementById('clean-result');
  showSpinner();

  try {
    const res = await fetch(`${API}/evaluate_null`, { method: 'POST' });
    const data = await res.json();

    if (data.error) { showToast(data.error, 'error'); return; }

    updateStatus(true, data.after, null);

    el.innerHTML = `
      <div class="result-card success">
        <h3 style="font-size:16px;font-weight:700;margin-bottom:20px;color:var(--accent-green)">
          ✅ Hoàn thành xử lý
        </h3>
        <div class="clean-stat-grid">
          <div class="clean-stat">
            <div class="clean-stat-val before">${data.before.toLocaleString()}</div>
            <div class="clean-stat-label">Dòng ban đầu</div>
          </div>
          <div class="clean-stat">
            <div class="clean-stat-val removed">${data.removed.toLocaleString()}</div>
            <div class="clean-stat-label">Dòng đã xóa</div>
          </div>
          <div class="clean-stat">
            <div class="clean-stat-val after">${data.after.toLocaleString()}</div>
            <div class="clean-stat-label">Dòng còn lại</div>
          </div>
        </div>
        <p style="color:var(--text-secondary);font-size:13.5px">${data.message}</p>
        <div style="margin-top:16px;display:flex;gap:10px">
          <button class="btn btn-secondary" onclick="showSection('preview')">👁️ Xem dữ liệu</button>
          <button class="btn btn-ghost" onclick="showSection('viz-key')">🔍 Kiểm tra lại</button>
        </div>
      </div>
    `;
    showToast(`Đã xóa ${data.removed} dòng`, 'success');
  } catch (e) {
    showToast('Lỗi kết nối server', 'error');
  } finally {
    hideSpinner();
  }
}

// ─── Reset ──────────────────────────────────────────────────────
async function resetDataset() {
  if (!confirm('Reset về dữ liệu gốc?')) return;
  showSpinner();
  try {
    const res = await fetch(`${API}/reset`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      updateStatus(true, data.rows, null);
      showToast('Đã reset về dữ liệu gốc', 'success');
      document.getElementById('clean-result').innerHTML = '';
    }
  } catch (e) {
    showToast('Lỗi kết nối server', 'error');
  } finally {
    hideSpinner();
  }
}

// ─── Init ────────────────────────────────────────────────────────
(async () => {
  try {
    const res = await fetch(`${API}/dataset_info`);
    const data = await res.json();
    if (data.loaded) updateStatus(true, data.rows, data.cols);
  } catch (_) {}
})();
