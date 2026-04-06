/**
 * 登录页面逻辑 (ViewModel)
 * 职责：表单交互、API 调用、路由跳转
 */
(function () {
    // 已登录用户重定向到首页
    if (localStorage.getItem('access_token')) {
        window.location.replace('/');
        return;
    }

    var form = document.getElementById('login-form');
    var submitBtn = document.getElementById('submit-btn');

    // 检查 URL 参数中的 OAuth 错误回调
    var urlParams = new URLSearchParams(window.location.search);
    var errorParam = urlParams.get('error');
    if (errorParam) {
        var errorMessages = {
            'access_denied': '您已取消第三方登录授权',
            'oauth_failed': '第三方登录失败，请稍后重试',
            'invalid_state': '授权请求无效或已过期，请重新登录'
        };
        showAlert(errorMessages[errorParam] || '登录出错，请重试', 'error');
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();

        var email = document.getElementById('email').value.trim();
        var password = document.getElementById('password').value;

        submitBtn.disabled = true;
        submitBtn.textContent = '登录中...';

        fetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, password: password })
        })
        .then(function (res) {
            return res.json().then(function (data) {
                return { ok: res.ok, data: data };
            });
        })
        .then(function (result) {
            if (!result.ok) {
                var msg = '登录失败，请稍后重试';
                var data = result.data;
                if (typeof data === 'string') {
                    msg = data;
                } else if (typeof data.detail === 'string') {
                    msg = data.detail;
                } else if (Array.isArray(data.detail)) {
                    msg = data.detail.map(function (e) {
                        return (typeof e === 'string') ? e : (e.msg || e.message || JSON.stringify(e));
                    }).join('; ');
                } else if (data.detail && typeof data.detail === 'object') {
                    msg = data.detail.msg || data.detail.message || JSON.stringify(data.detail);
                }
                showAlert(msg, 'error');
                return;
            }

            localStorage.setItem('access_token', result.data.access_token);
            localStorage.setItem('refresh_token', result.data.refresh_token);
            window.location.replace('/');
        })
        .catch(function () {
            showAlert('网络错误，请检查连接后重试', 'error');
        })
        .finally(function () {
            submitBtn.disabled = false;
            submitBtn.textContent = '登录';
        });
    });
})();
