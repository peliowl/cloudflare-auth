/**
 * OAuth 回调页面逻辑
 * 从 URL 中提取一次性授权码，通过 API 安全交换 JWT tokens
 */
(function () {
    var params = new URLSearchParams(window.location.search);
    var code = params.get('code');
    var error = params.get('error');

    if (error) {
        showAlert(decodeURIComponent(error), 'error', 0);
        setTimeout(function () {
            window.location.replace('/login.html');
        }, 2000);
        return;
    }

    if (!code) {
        showAlert('登录参数缺失，请重新登录', 'error', 0);
        setTimeout(function () {
            window.location.replace('/login.html');
        }, 2000);
        return;
    }

    // Exchange the one-time code for tokens via a secure POST request
    fetch('/auth/oauth/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code })
    })
    .then(function (res) {
        if (!res.ok) {
            return res.json().then(function (data) {
                throw new Error(data.detail || '登录失败');
            });
        }
        return res.json();
    })
    .then(function (data) {
        if (data.access_token && data.refresh_token) {
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
            window.location.replace('/');
        } else {
            throw new Error('令牌数据不完整');
        }
    })
    .catch(function (err) {
        showAlert(err.message || '登录失败，请重试', 'error', 0);
        setTimeout(function () {
            window.location.replace('/login.html');
        }, 2000);
    });
})();
