// 全局工具：CSRF 读取、输入防抖、页码高亮
function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[2]) : null;
}

window.djangoCsrfToken = getCookie('csrftoken');

document.addEventListener('DOMContentLoaded', function () {
  // 筛选输入框回车即提交
  document.querySelectorAll('[data-filter-input]').forEach(function (input) {
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        input.closest('form').submit();
      }
    });
  });
});
/* ---------------- AI 解读：任何带 data-ai-explain 的按钮 ---------------- */
(function () {
  function ensurePanel() {
    var p = document.getElementById('ai-insight-panel');
    if (p) return p;
    p = document.createElement('div');
    p.id = 'ai-insight-panel';
    p.style.cssText = 'position:fixed;right:22px;bottom:22px;width:380px;max-height:60vh;overflow:auto;' +
      'z-index:2000;display:none;padding:14px 16px;border-radius:12px;' +
      'background:rgba(11,18,32,.97);border:1px solid rgba(34,211,238,.45);' +
      'box-shadow:0 12px 40px rgba(0,0,0,.5);color:#cbd5e1;font-size:13px;line-height:1.85;';
    p.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">' +
      '<b id="ai-insight-title" style="color:#a5f3fc;">AI 解读</b>' +
      '<span id="ai-insight-close" style="cursor:pointer;color:#64748b;">✕</span></div>' +
      '<div id="ai-insight-body" style="white-space:pre-wrap;"></div>';
    document.body.appendChild(p);
    p.querySelector('#ai-insight-close').addEventListener('click', function () { p.style.display = 'none'; });
    return p;
  }

  function show(title, text) {
    var p = ensurePanel();
    p.querySelector('#ai-insight-title').textContent = title || 'AI 解读';
    p.querySelector('#ai-insight-body').textContent = text;
    p.style.display = 'block';
  }

  document.addEventListener('click', async function (e) {
    var btn = e.target.closest('[data-ai-explain]');
    if (!btn) return;
    var scope = btn.dataset.aiExplain;
    var target = btn.dataset.aiTarget || '';
    var label = btn.dataset.aiTitle || btn.textContent;
    var old = btn.textContent;
    btn.disabled = true;
    btn.textContent = '解读中…';
    try {
      var resp = await fetch('/api/ai/explain/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.djangoCsrfToken || ''},
        body: JSON.stringify({scope: scope, target: target})
      });
      var data = await resp.json();
      show(label, data.ok ? data.text : (data.message || '失败'));
    } catch (err) {
      show(label, '请求失败：' + err);
    } finally {
      btn.disabled = false;
      btn.textContent = old;
    }
  });
})();
