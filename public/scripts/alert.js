/**
 * Alert 组件 — 参考 Chakra UI Alert 设计规范
 * 全局函数 showAlert(message, type, duration)
 * type: 'error' | 'success' | 'warning' | 'info'
 * duration: 自动消失时长（毫秒），默认 2000，传 0 则不自动消失
 */
(function () {
  // SVG 图标
  const icons = {
    error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="9 12 11.5 14.5 16 9.5"/></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
  };

  var closeSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';

  // 确保页面有 alert 容器
  function getContainer() {
    var c = document.getElementById('m-alert-container');
    if (!c) {
      c = document.createElement('div');
      c.id = 'm-alert-container';
      c.className = 'm-alert-container';
      document.body.appendChild(c);
    }
    return c;
  }

  function removeAlert(el) {
    el.classList.remove('m-alert-show');
    el.classList.add('m-alert-hide');
    setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 300);
  }

  /**
   * @param {string} message - 提示消息
   * @param {'error'|'success'|'warning'|'info'} type - 提示类型
   * @param {number} [duration=2000] - 自动消失时长（毫秒），传 0 则不自动消失
   */
  window.showAlert = function (message, type, duration) {
    type = type || 'info';
    if (typeof duration === 'undefined' || duration === null) duration = 2000;
    var container = getContainer();

    var el = document.createElement('div');
    el.className = 'm-alert m-alert-' + type;

    // 图标
    var iconEl = document.createElement('span');
    iconEl.className = 'm-alert-icon';
    iconEl.innerHTML = icons[type] || icons.info;

    // 内容
    var contentEl = document.createElement('span');
    contentEl.className = 'm-alert-content';
    contentEl.textContent = message;

    // 关闭按钮
    var closeEl = document.createElement('button');
    closeEl.className = 'm-alert-close';
    closeEl.innerHTML = closeSvg;
    closeEl.setAttribute('aria-label', '关闭');
    closeEl.onclick = function () { removeAlert(el); };

    el.appendChild(iconEl);
    el.appendChild(contentEl);
    el.appendChild(closeEl);
    container.appendChild(el);

    // 触发动画
    requestAnimationFrame(function () { el.classList.add('m-alert-show'); });

    // 自动消失：默认 2 秒，传 0 则不自动消失
    if (duration > 0) {
      setTimeout(function () { removeAlert(el); }, duration);
    }
  };
})();
