const API = window.HR_HELP_API_BASE || 'http://localhost:8000';
const app = document.querySelector('#app');
const icons = {
  mark: '<svg viewBox="0 0 40 40" fill="none" aria-hidden="true"><path d="M8 7h10l5 10 5-10h5L22 33h-5L8 7Z" fill="currentColor"/><circle cx="31" cy="28" r="4" fill="#65C6A7"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke-linecap="round"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m5 12 4 4L19 6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  message: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l-2 2v-9.5a7.5 7.5 0 1 1 17 0Z" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M7 3h7l5 5v13H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" stroke-linejoin="round"/><path d="M14 3v6h5M9 14h6M9 18h6" stroke-linecap="round"/></svg>',
  shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m12 2 8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6l8-4Z" stroke-linejoin="round"/><path d="m9 12 2 2 4-4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5" stroke-linecap="round"/></svg>',
  chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

const state = {
  auth: readSession('hr_auth'),
  case: null,
  facts: null,
  answer: null,
  messages: [],
  busy: false,
  error: '',
  notice: '',
  tab: 'conversation',
  authMode: 'login',
  view: 'home',
  authDraft: {},
  caseDraft: {},
  caseId: location.hash.startsWith('#case/') ? location.hash.slice(6) : sessionStorage.getItem('hr_case_id'),
};

function readSession(key) {
  try { return JSON.parse(sessionStorage.getItem(key)); } catch { return null; }
}
function esc(value = '') {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function dateText(value) {
  if (!value) return '—';
  const [year, month, day] = value.split('-');
  return `${day}/${month}/${year}`;
}
function statusText(status) {
  return ({OPEN:'Mới mở',NEED_INFO:'Cần bổ sung',ANALYZED:'Đã phân tích',PENDING_LEGAL:'Chờ pháp chế',APPROVED:'Đã duyệt',REJECTED:'Cần chỉnh sửa',DECIDED:'Đã ban hành',CLOSED:'Đã đóng'})[status] || status;
}
function statusClass(status) {
  return status === 'PENDING_LEGAL' ? 'amber' : status === 'ANALYZED' ? 'green' : 'blue';
}
function roleText(role) { return ({HR:'Nhân sự',MANAGER:'Quản lý',LEGAL:'Pháp chế'})[role] || role; }
function buttonBusy(text) { return state.busy ? '<span class="spinner" aria-hidden="true"></span> Đang xử lý…' : text; }
function apiError(error) { return esc(error?.message || 'Không thể kết nối đến máy chủ. Vui lòng thử lại.'); }

async function request(path, options = {}, retry = true) {
  const headers = { ...(options.headers || {}) };
  if (state.auth?.access_token) headers.Authorization = `Bearer ${state.auth.access_token}`;
  if (!(options.body instanceof URLSearchParams) && options.body != null) headers['Content-Type'] = 'application/json';
  let response;
  try { response = await fetch(`${API}/api/v1${path}`, { ...options, headers }); }
  catch { throw new Error('Không thể kết nối API. Hãy kiểm tra backend ở cổng 8000.'); }
  if (response.status === 401 && retry && state.auth?.refresh_token && !path.startsWith('/auth/')) {
    try {
      const refreshed = await request('/auth/refresh', { method:'POST', body:JSON.stringify({refresh_token:state.auth.refresh_token}) }, false);
      state.auth = refreshed;
      sessionStorage.setItem('hr_auth', JSON.stringify(refreshed));
      return request(path, options, false);
    } catch { logout(); throw new Error('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'); }
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(x => x.msg).join(' · ') : `Yêu cầu không thành công (${response.status}).`);
  }
  return data;
}

function shell(content) {
  const role = state.auth?.roles?.[0] || 'HR';
  app.innerHTML = `<div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#" aria-label="HR Help — trang bắt đầu"><span class="brand-mark">${icons.mark}</span><span>HR<span class="brand-light">Help</span><small>WORKSPACE</small></span></a>
      <div class="sidebar-caption">KHÔNG GIAN LÀM VIỆC</div>
      <nav class="side-nav" aria-label="Điều hướng chính">
        <button class="nav-item ${!state.case ? 'active' : ''}" data-action="home">${icons.file}<span>Hồ sơ của tôi</span></button>
        ${state.case ? `<button class="nav-item ${state.tab === 'conversation' ? 'active' : ''}" data-action="tab" data-tab="conversation">${icons.message}<span>Trao đổi</span></button><button class="nav-item ${state.tab === 'facts' ? 'active' : ''}" data-action="tab" data-tab="facts">${icons.check}<span>Tình tiết</span></button><button class="nav-item ${state.tab === 'answer' ? 'active' : ''}" data-action="tab" data-tab="answer">${icons.shield}<span>Đề xuất</span></button>` : ''}
      </nav>
      <div class="sidebar-bottom"><div class="secure-card">${icons.shield}<div><strong>Dữ liệu có kiểm soát</strong><p>Chỉ người tạo hồ sơ có quyền xem và chỉnh sửa trong phiên bản hiện tại.</p></div></div><div class="profile"><span class="avatar">${esc(role[0])}</span><span><strong>${roleText(role)}</strong><small>Phiên làm việc của bạn</small></span><button class="text-button" data-action="logout">Đăng xuất</button></div></div>
    </aside>
    <div class="main-wrap"><header class="topbar"><button class="mobile-brand" data-action="home">${icons.mark}<strong>HR Help</strong></button><span class="breadcrumb">Không gian làm việc <span>/</span> ${state.case ? esc(state.case.case_code) : 'Hồ sơ'}</span><span class="topbar-right"><span class="online-dot"></span> Hệ thống hỗ trợ xử lý</span></header><main id="main" class="main-content">${content}</main></div>
  </div>`;
}

function render() {
  if (!state.auth) return renderAuth();
  if (!state.case) return shell(state.view === 'new-case' ? renderNewCase() : renderHome());
  shell(renderCase());
}

function renderAuth() {
  const register = state.authMode === 'register';
  app.innerHTML = `<main id="main" class="auth-layout"><section class="auth-story"><a class="brand auth-brand" href="#"> <span class="brand-mark">${icons.mark}</span><span>HR<span class="brand-light">Help</span><small>WORKSPACE</small></span></a><div class="story-content"><span class="eyebrow light">TRỢ LÝ NHÂN SỰ CÓ CĂN CỨ</span><h1>Mọi quyết định tốt bắt đầu từ tình tiết rõ ràng.</h1><p>Tập hợp thông tin, đối chiếu quy định theo ngày xảy ra vụ việc, và xem đề xuất có trích dẫn trong một không gian làm việc.</p><div class="story-steps"><span>01 <strong>Mở hồ sơ</strong></span><span>02 <strong>Xác nhận tình tiết</strong></span><span>03 <strong>Xem căn cứ</strong></span></div></div><div class="story-footer">HR HELP <span>© 2026</span></div></section><section class="auth-panel"><div class="auth-card"><span class="eyebrow">BẮT ĐẦU</span><h2>${register ? 'Tạo tài khoản' : 'Chào mừng trở lại'}</h2><p class="muted">${register ? 'Tạo không gian làm việc cho hồ sơ nhân sự của bạn.' : 'Đăng nhập để tiếp tục xử lý hồ sơ.'}</p>${state.error ? `<div class="alert error" role="alert">${esc(state.error)}</div>` : ''}<form id="auth-form" class="form-stack"><label>Email công việc<input name="email" type="email" autocomplete="email" required placeholder="ten@congty.vn" value="${esc(state.authDraft.email || '')}" /></label>${register ? `<label>Họ và tên<input name="full_name" type="text" autocomplete="name" placeholder="Nguyễn Minh Anh" value="${esc(state.authDraft.full_name || '')}" /></label><label>Vai trò<select name="role"><option value="HR" ${state.authDraft.role === 'MANAGER' ? '' : 'selected'}>Nhân sự</option><option value="MANAGER" ${state.authDraft.role === 'MANAGER' ? 'selected' : ''}>Quản lý</option></select></label>` : ''}<label>Mật khẩu<input name="password" type="password" autocomplete="${register ? 'new-password' : 'current-password'}" minlength="8" required placeholder="Tối thiểu 8 ký tự" /></label><button class="button primary full" type="submit" ${state.busy ? 'disabled' : ''}>${buttonBusy(register ? 'Tạo tài khoản' : 'Đăng nhập')} ${state.busy ? '' : icons.arrow}</button></form><div class="auth-switch">${register ? 'Đã có tài khoản?' : 'Chưa có tài khoản?'} <button class="link-button" data-action="auth-mode">${register ? 'Đăng nhập' : 'Tạo tài khoản'}</button></div></div></section></main>`;
}

function renderHome() {
  return `<div class="page-heading"><div><span class="eyebrow">KHÔNG GIAN XỬ LÝ</span><h1>Hồ sơ của tôi</h1><p>Khởi tạo vụ việc để ghi nhận tình tiết và đối chiếu căn cứ.</p></div><span class="heading-deco">${icons.file}</span></div>${state.notice ? `<div class="alert success" role="status">${esc(state.notice)}</div>` : ''}${state.error ? `<div class="alert error" role="alert">${esc(state.error)}</div>` : ''}<div class="home-grid"><section class="hero-card"><div><span class="pill light-pill">BẮT ĐẦU VỤ VIỆC MỚI</span><h2>Thông tin rõ ràng.<br />Quyết định vững vàng.</h2><p>Ghi nhận sự việc, để trợ lý hỏi thêm những tình tiết cần thiết trước khi đưa ra đề xuất.</p></div><button class="button white" data-action="new-case">${icons.plus} Mở hồ sơ mới</button><div class="hero-orbit orbit-one"></div><div class="hero-orbit orbit-two"></div></section><section class="flow-card"><div class="section-head"><span class="eyebrow">QUY TRÌNH</span><h2>Ba bước để có câu trả lời</h2></div><div class="flow-list"><div><span class="flow-index">01</span><span><strong>Mô tả vụ việc</strong><small>Nhân viên, ngày xảy ra và diễn biến chính.</small></span></div><div><span class="flow-index">02</span><span><strong>Hoàn thiện tình tiết</strong><small>Trả lời và xác nhận các dữ kiện bắt buộc.</small></span></div><div><span class="flow-index">03</span><span><strong>Đọc đề xuất có căn cứ</strong><small>Xem mức, quy trình, rủi ro và trích dẫn.</small></span></div></div></section></div><section class="recent-section"><div class="section-title-row"><div><span class="eyebrow">TIẾP TỤC</span><h2>Hồ sơ trong phiên này</h2></div></div>${state.caseId ? `<div class="resume-card"><span class="resume-icon">${icons.file}</span><div><strong>Tiếp tục hồ sơ đang làm</strong><p>Mã định danh: <span class="mono">${esc(state.caseId)}</span></p></div><button class="button secondary" data-action="resume">Mở hồ sơ ${icons.chevron}</button></div>` : `<div class="empty-state">${icons.file}<strong>Chưa có hồ sơ trong phiên này</strong><p>Bắt đầu với một hồ sơ mới để xem quy trình xử lý.</p></div>`}</section>`;
}

function renderNewCase() {
  return `<div class="page-heading"><div><button class="back-link" data-action="home">← Hồ sơ của tôi</button><span class="eyebrow">HỒ SƠ MỚI</span><h1>Ghi nhận vụ việc</h1><p>Bắt đầu bằng thông tin cơ bản. Bạn có thể bổ sung tình tiết trong bước trao đổi.</p></div></div><div class="form-layout"><form id="case-form" class="surface form-card"><div class="card-heading"><span class="step-badge">01</span><div><h2>Thông tin hồ sơ</h2><p>Các trường có dấu * là bắt buộc.</p></div></div>${state.error ? `<div class="alert error" role="alert">${esc(state.error)}</div>` : ''}<div class="field-grid"><label>Mã hồ sơ *<input name="case_code" maxlength="100" required placeholder="VD: HS-2026-001" value="${esc(state.caseDraft.case_code || '')}" /></label><label>Ngày xảy ra *<input name="incident_date" type="date" required value="${esc(state.caseDraft.incident_date || '')}" /></label><label>Mã nhân viên *<input name="employee_code" maxlength="100" required placeholder="VD: NV-0182" value="${esc(state.caseDraft.employee_code || '')}" /></label><label>Họ tên nhân viên *<input name="employee_name" maxlength="255" required placeholder="Họ và tên" value="${esc(state.caseDraft.employee_name || '')}" /></label></div><label>Mô tả sự việc *<textarea name="description" maxlength="8000" required rows="6" placeholder="Mô tả điều đã xảy ra, thời điểm và thông tin bạn hiện có…">${esc(state.caseDraft.description || '')}</textarea><small>Viết theo những gì đã biết. Trợ lý sẽ hỏi thêm khi thiếu tình tiết.</small></label><div class="form-actions"><button class="button ghost" type="button" data-action="home">Hủy</button><button class="button primary" type="submit" ${state.busy ? 'disabled' : ''}>${buttonBusy('Tạo hồ sơ và tiếp tục')} ${state.busy ? '' : icons.arrow}</button></div></form><aside class="tip-card">${icons.shield}<h3>Vì sao cần ngày xảy ra?</h3><p>Trợ lý dùng ngày này để tìm đúng phiên bản văn bản còn hiệu lực tại thời điểm vụ việc.</p><div class="tip-rule"></div><small>Mọi tình tiết trích xuất từ hội thoại cần được bạn xác nhận trước khi đưa vào đề xuất.</small></aside></div>`;
}

function renderCase() {
  const c = state.case;
  const tabs = [['conversation','Trao đổi'],['facts','Tình tiết'],['answer','Đề xuất']];
  return `<div class="case-head"><button class="back-link" data-action="home">← Hồ sơ của tôi</button><div class="case-head-row"><div><span class="eyebrow">HỒ SƠ ${esc(c.case_code)}</span><h1>${esc(c.employee_name || 'Vụ việc nhân sự')}</h1><p>${esc(c.description || '')}</p></div><span class="status-pill ${statusClass(c.status)}">${statusText(c.status)}</span></div><div class="case-meta"><span><strong>Mã nhân viên</strong>${esc(c.employee_code || '—')}</span><span><strong>Ngày xảy ra</strong>${dateText(c.incident_date)}</span><span><strong>Mã hồ sơ</strong>${esc(c.case_code)}</span></div></div><div class="case-tabs" role="tablist" aria-label="Nội dung hồ sơ">${tabs.map(([id,label]) => `<button role="tab" aria-selected="${state.tab === id}" class="${state.tab === id ? 'selected' : ''}" data-action="tab" data-tab="${id}">${label}${id === 'facts' && state.facts?.facts?.length ? `<span class="tab-count">${state.facts.facts.filter(f => f.confirmed).length}/${state.facts.facts.length}</span>` : ''}</button>`).join('')}</div>${state.notice ? `<div class="alert success" role="status">${esc(state.notice)}</div>` : ''}${state.error ? `<div class="alert error" role="alert">${esc(state.error)}</div>` : ''}${state.tab === 'conversation' ? renderConversation() : state.tab === 'facts' ? renderFacts() : renderAnswer()}`;
}

function renderConversation() {
  const c = state.case;
  const locked = !['OPEN','NEED_INFO','ANALYZED','REJECTED'].includes(c.status);
  return `<div class="workspace-grid"><section class="surface conversation-card"><div class="pane-title"><span class="pane-icon">${icons.message}</span><div><h2>Trao đổi về vụ việc</h2><p>Trợ lý sẽ hỏi từng phần cần làm rõ.</p></div></div><div class="conversation-body" aria-live="polite">${state.messages.length ? state.messages.map(m => `<div class="bubble-row ${m.role}"><span class="bubble-avatar">${m.role === 'user' ? 'B' : icons.mark}</span><div class="bubble"><small>${m.role === 'user' ? 'Bạn' : 'HR Help'}</small><p>${esc(m.text)}</p></div></div>`).join('') : `<div class="chat-intro"><span class="intro-icon">${icons.message}</span><h3>Bắt đầu bằng điều bạn biết</h3><p>Hồ sơ đã được tạo. Hãy bổ sung diễn biến, giấy tờ hoặc câu trả lời của bạn; trợ lý sẽ xác định thông tin còn thiếu.</p><div class="prompt-suggestion">“Nhân viên nghỉ không phép 3 ngày, đã lập biên bản…”</div></div>`}</div>${locked ? `<div class="chat-locked">Hồ sơ đang ở trạng thái ${statusText(c.status)} nên chưa nhận thêm tình tiết.</div>` : `<form id="chat-form" class="chat-compose"><label class="sr-only" for="chat-content">Nội dung tin nhắn</label><textarea id="chat-content" name="content" rows="2" maxlength="8000" required placeholder="Nhập tình tiết hoặc trả lời câu hỏi…"></textarea><button class="button primary icon-button" type="submit" aria-label="Gửi tin nhắn" ${state.busy ? 'disabled' : ''}>${state.busy ? '<span class="spinner"></span>' : icons.arrow}</button></form>`}</section><aside class="context-column"><section class="surface progress-card"><span class="eyebrow">TIẾN ĐỘ HỒ SƠ</span><h2>Từng bước có căn cứ</h2><div class="progress-list"><div class="done"><i>${icons.check}</i><span><strong>Hồ sơ đã mở</strong><small>Thông tin cơ bản đã ghi nhận</small></span></div><div class="${state.facts?.facts_locked ? 'done' : 'current'}"><i>${state.facts?.facts_locked ? icons.check : '2'}</i><span><strong>Xác nhận tình tiết</strong><small>${state.facts?.facts_locked ? 'Đã đủ tình tiết bắt buộc' : 'Cần kiểm tra thông tin'}</small></span></div><div class="${state.answer ? 'done' : ''}"><i>${state.answer ? icons.check : '3'}</i><span><strong>Đề xuất và căn cứ</strong><small>${state.answer ? 'Có kết quả để xem' : 'Sau khi xác nhận'}</small></span></div></div></section><section class="surface next-card"><span class="eyebrow">BƯỚC TIẾP THEO</span><h3>${state.answer ? 'Xem đề xuất' : 'Kiểm tra tình tiết'}</h3><p>${state.answer ? 'Xem mức đề xuất, quy trình và các đoạn văn bản liên quan.' : 'Những thông tin từ mô tả cần được xác nhận trước khi đối chiếu.'}</p><button class="inline-action" data-action="tab" data-tab="${state.answer ? 'answer' : 'facts'}">${state.answer ? 'Mở đề xuất' : 'Xem tình tiết'} ${icons.arrow}</button></section></aside></div>`;
}

function renderFacts() {
  const facts = state.facts;
  if (!facts) return `<div class="surface loading-card"><span class="spinner dark"></span> Đang tải tình tiết…</div>`;
  const locked = !['OPEN','NEED_INFO','ANALYZED','REJECTED'].includes(state.case.status);
  const confirmed = facts.facts.filter(f => f.confirmed).length;
  return `<div class="content-two-col"><section class="surface detail-card"><div class="detail-heading"><div><span class="eyebrow">XÁC NHẬN THÔNG TIN</span><h2>Tình tiết vụ việc</h2><p>Kiểm tra gợi ý từ nội dung đã nhập. Chỉnh lại thông tin trước khi xác nhận.</p></div><span class="count-ring">${confirmed}<small>/${facts.facts.length}</small></span></div><form id="facts-form"><div class="fact-list">${facts.facts.map((f,i) => `<div class="fact-row"><div class="fact-number">${String(i+1).padStart(2,'0')}</div><div class="fact-field"><label for="fact-${esc(f.fact_key)}">${esc(f.label)} <span class="fact-status ${f.confirmed ? 'confirmed' : ''}">${f.confirmed ? 'Đã xác nhận' : 'Chờ xác nhận'}</span></label><input id="fact-${esc(f.fact_key)}" name="${esc(f.fact_key)}" value="${esc(f.fact_value || '')}" placeholder="Nhập thông tin" ${locked ? 'disabled' : ''} /><label class="checkline"><input type="checkbox" name="confirm-${esc(f.fact_key)}" ${f.confirmed ? 'checked' : ''} ${locked ? 'disabled' : ''} /> Xác nhận thông tin này là đúng</label></div></div>`).join('')}</div>${!locked ? `<div class="form-actions"><span class="fine-print">Chỉ những tình tiết đã xác nhận mới được dùng trong đề xuất.</span><button class="button primary" type="submit" ${state.busy ? 'disabled' : ''}>${buttonBusy('Lưu tình tiết')} ${state.busy ? '' : icons.arrow}</button></div>` : ''}</form></section><aside class="surface insight-card">${icons.search}<span class="eyebrow">CÁCH HOẠT ĐỘNG</span><h3>Từ tình tiết đến căn cứ</h3><p>Khi toàn bộ tình tiết bắt buộc được xác nhận, hệ thống tìm văn bản có hiệu lực vào ngày xảy ra việc và tạo đề xuất kèm trích dẫn.</p>${facts.missing_fact_keys.length ? `<div class="info-box"><strong>Còn ${facts.missing_fact_keys.length} mục cần hoàn thiện</strong><p>Bạn có thể trả lời trong hội thoại hoặc điền trực tiếp tại đây.</p></div>` : `<div class="info-box positive"><strong>Đã đủ tình tiết</strong><p>Đề xuất sẽ xuất hiện sau khi lưu các xác nhận.</p></div>`}</aside></div>`;
}

function citationGroup(title, caption, items, cls) {
  return `<section class="citation-group ${cls}"><div class="citation-header"><div><h3>${title}</h3><p>${caption}</p></div><span class="citation-count">${items.length}</span></div>${items.length ? items.map(item => `<article class="citation"><div class="citation-source">${esc(item.policy_code || item.policy_name || 'Văn bản')} ${[item.article && `Điều ${item.article}`,item.clause && `Khoản ${item.clause}`,item.point && `Điểm ${item.point}`].filter(Boolean).map(esc).join(' · ')}</div><p>${esc(item.quote)}</p></article>`).join('') : '<p class="no-citations">Chưa có trích dẫn trong nhóm này.</p>'}</section>`;
}

function renderAnswer() {
  const a = state.answer;
  if (!a) return `<div class="surface empty-answer">${icons.shield}<h2>Chưa có đề xuất</h2><p>Xác nhận đủ tình tiết để hệ thống đối chiếu và tạo câu trả lời.</p><button class="button primary" data-action="tab" data-tab="facts">Xem tình tiết ${icons.arrow}</button></div>`;
  return `<div class="answer-layout"><section class="answer-main"><div class="surface answer-summary"><span class="eyebrow">KẾT QUẢ ĐỐI CHIẾU</span><div class="answer-title-row"><div><h2>${a.sanction_type ? 'Đề xuất xử lý' : 'Chưa đủ căn cứ chốt mức'}</h2><p>${esc(a.rationale || a.message)}</p></div><span class="risk-badge ${a.risk_level === 'HIGH' || a.risk_level === 'CRITICAL' ? 'high' : ''}">Rủi ro ${esc(a.risk_level || 'chưa rõ')}</span></div><div class="sanction-box"><small>MỨC ĐỀ XUẤT</small><strong>${esc(({WARNING:'Khiển trách',REPRIMAND:'Cảnh cáo',WAGE_POSTPONEMENT:'Kéo dài nâng lương',DEMOTION:'Cách chức',DISMISSAL:'Sa thải',TERMINATION:'Chấm dứt hợp đồng'})[a.sanction_type] || 'Chưa chốt mức')}</strong></div>${state.case.status === 'PENDING_LEGAL' ? '<div class="review-note">Đã tạo bản thảo và chuyển sang trạng thái chờ pháp chế. Giao diện duyệt pháp chế chưa có trong API hiện tại.</div>' : a.missing_internal_rule ? '<div class="review-note caution">Thiếu căn cứ nội quy nội bộ cho vụ việc này.</div>' : ''}</div><section class="surface citation-card"><div class="card-heading"><span class="pane-icon">${icons.file}</span><div><h2>Căn cứ được sử dụng</h2><p>Đọc từng lớp căn cứ để thấy vai trò của mỗi nguồn.</p></div></div>${citationGroup('Căn cứ pháp luật','Văn bản pháp luật liên quan đến xử lý kỷ luật.',a.legal_basis,'legal')}${citationGroup('Nội quy nội bộ','Quy định của doanh nghiệp áp dụng cho hành vi.',a.internal_rule,'internal')}${citationGroup('Tiền lệ','Các trường hợp trước để tham khảo, không tự nâng mức.',a.precedent,'precedent')}${citationGroup('Cảnh báo thanh tra','Rủi ro thủ tục, không phải mức kỷ luật.',a.inspection_risk,'inspection')}</section></section><aside class="answer-side"><section class="surface process-card"><span class="eyebrow">THỦ TỤC</span><h3>Các bước cần kiểm tra</h3>${a.process_steps.length ? `<div class="process-list">${a.process_steps.map(step => `<div><span class="process-check ${step.done ? 'done' : ''}">${step.done ? icons.check : ''}</span><span>${esc(step.label)}<small>${step.done ? 'Đã hoàn tất' : 'Chưa hoàn tất'}</small></span></div>`).join('')}</div>` : '<p>Chưa có bước thủ tục.</p>'}</section><section class="surface note-card"><span class="eyebrow">LƯU Ý</span><p>Đề xuất hỗ trợ người phụ trách xem xét. Quyết định kỷ luật cần được người có thẩm quyền kiểm tra và ban hành.</p></section></aside></div>`;
}

function logout() {
  sessionStorage.removeItem('hr_auth');
  state.auth = null; state.case = null; state.facts = null; state.answer = null; state.messages = []; state.error = '';
  render();
}
async function openCase(id) {
  state.busy = true; state.error = ''; render();
  try {
    const c = await request(`/cases/${encodeURIComponent(id)}`);
    const [facts, answer] = await Promise.all([
      request(`/cases/${encodeURIComponent(id)}/facts`).catch(() => null),
      request(`/cases/${encodeURIComponent(id)}/answer`).catch(() => null),
    ]);
    state.case = c; state.facts = facts; state.answer = answer; state.caseId = id;
    sessionStorage.setItem('hr_case_id', id); location.hash = `case/${id}`;
  } catch (error) { state.error = error.message; state.caseId = null; sessionStorage.removeItem('hr_case_id'); }
  finally { state.busy = false; render(); }
}

app.addEventListener('click', async event => {
  const target = event.target.closest('[data-action]');
  if (!target) return;
  const action = target.dataset.action;
  state.error = ''; state.notice = '';
  if (action === 'auth-mode') { state.authMode = state.authMode === 'login' ? 'register' : 'login'; render(); }
  if (action === 'logout') logout();
  if (action === 'home') { state.case = null; state.view = 'home'; location.hash = ''; render(); }
  if (action === 'new-case') { state.case = null; state.view = 'new-case'; render(); }
  if (action === 'resume' && state.caseId) await openCase(state.caseId);
  if (action === 'tab') { state.tab = target.dataset.tab; render(); }
});

app.addEventListener('submit', async event => {
  event.preventDefault();
  if (state.busy) return;
  const form = event.target;
  const data = new FormData(form);
  state.error = ''; state.notice = ''; state.busy = true;
  const submitButton = form.querySelector('[type="submit"]');
  if (submitButton) submitButton.disabled = true;
  try {
    if (form.id === 'auth-form') {
      const fields = Object.fromEntries(data);
      state.authDraft = {email:fields.email,full_name:fields.full_name,role:fields.role};
      const register = state.authMode === 'register';
      const payload = register ? await request('/auth/register', {method:'POST',body:JSON.stringify(fields)}) : await request('/auth/login', {method:'POST',body:new URLSearchParams({username:fields.email,password:fields.password})});
      state.auth = payload; sessionStorage.setItem('hr_auth', JSON.stringify(payload));
      if (state.caseId) await openCase(state.caseId);
    } else if (form.id === 'case-form') {
      state.caseDraft = Object.fromEntries(data);
      const created = await request('/cases', {method:'POST',body:JSON.stringify(state.caseDraft)});
      await openCase(created.case_id); state.notice = 'Hồ sơ đã được tạo. Bạn có thể bắt đầu trao đổi.';
    } else if (form.id === 'chat-form') {
      const content = String(data.get('content') || '').trim();
      const turn = await request(`/cases/${state.case.case_id}/messages`, {method:'POST',body:JSON.stringify({content})});
      state.messages.push({role:'user',text:content},{role:'assistant',text:turn.assistant_message});
      state.facts = {case_id:turn.case_id,case_status:turn.case_status,family:turn.family,facts:turn.facts,missing_fact_keys:turn.missing_fact_keys,facts_locked:turn.facts_locked};
      state.answer = turn.answer || (turn.case_status === 'NEED_INFO' ? null : state.answer);
      state.case.status = turn.case_status;
    } else if (form.id === 'facts-form') {
      const items = state.facts.facts.map(f => ({fact_key:f.fact_key,fact_value:String(data.get(f.fact_key) || '').trim() || null,confirmed:data.has(`confirm-${f.fact_key}`)})).filter(f => f.fact_value);
      if (!items.length) throw new Error('Nhập ít nhất một tình tiết trước khi lưu.');
      const turn = await request(`/cases/${state.case.case_id}/facts/confirm`, {method:'POST',body:JSON.stringify({facts:items})});
      state.facts = {case_id:turn.case_id,case_status:turn.case_status,family:turn.family,facts:turn.facts,missing_fact_keys:turn.missing_fact_keys,facts_locked:turn.facts_locked};
      if (turn.answer) { state.answer = turn.answer; state.tab = 'answer'; }
      else if (turn.case_status === 'NEED_INFO') state.answer = null;
      else state.notice = 'Tình tiết đã được lưu. Hoàn thiện các mục còn thiếu để xem đề xuất.';
      state.case.status = turn.case_status;
      if (turn.assistant_message) state.messages.push({role:'assistant',text:turn.assistant_message});
    }
  } catch (error) { state.error = error.message; }
  finally { state.busy = false; render(); }
});

if (state.auth && state.caseId) openCase(state.caseId);
else render();
