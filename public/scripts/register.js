/**
 * 注册页面逻辑 (ViewModel)
 * 职责：Turnstile 初始化、验证码发送、表单提交、路由跳转
 */

// Turnstile 全局状态（需在 SDK 加载前声明）
var turnstileSiteKey = '';
var turnstileWidgetId = null;
var turnstileReady = false;

function renderTurnstile() {
    if (turnstileWidgetId !== null || !turnstileSiteKey || !turnstileReady) return;
    turnstileWidgetId = turnstile.render('#turnstile-container', {
        sitekey: turnstileSiteKey,
        execution: 'execute',
        appearance: 'interaction-only',
        callback: function (token) {
            doSendCode(token);
        },
        'error-callback': function () {
            showAlert('人机验证失败，请重试', 'error');
            var btn = document.getElementById('send-code-btn');
            if (btn) { btn.disabled = false; btn.textContent = '发送验证码'; }
        }
    });
}

function onloadTurnstileCallback() {
    turnstileReady = true;
    renderTurnstile();
}

(function () {
    // 已登录用户重定向到首页
    if (localStorage.getItem('access_token')) {
        window.location.replace('/');
        return;
    }

    // 加载 Turnstile site key
    fetch('/auth/config')
        .then(function (res) { return res.json(); })
        .then(function (data) {
            turnstileSiteKey = data.turnstile_site_key || '';
            renderTurnstile();
        })
        .catch(function () {});

    var _sendCodeEmail = '';

    // 发送验证码（Turnstile 验证通过后调用）
    window.doSendCode = function (turnstileToken) {
        var sendCodeBtn = document.getElementById('send-code-btn');
        sendCodeBtn.disabled = true;
        sendCodeBtn.textContent = '发送中...';

        fetch('/auth/send-verification-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: _sendCodeEmail, turnstile_token: turnstileToken })
        })
        .then(function (res) {
            return res.json().then(function (data) {
                return { ok: res.ok, data: data };
            });
        })
        .then(function (result) {
            if (!result.ok) {
                var msg = '发送失败，请稍后重试';
                if (typeof result.data.detail === 'string') {
                    msg = result.data.detail;
                } else if (Array.isArray(result.data.detail)) {
                    msg = result.data.detail.map(function (e) { return e.msg || e.message || JSON.stringify(e); }).join('; ');
                }
                showAlert(msg, 'error');
                sendCodeBtn.disabled = false;
                sendCodeBtn.textContent = '发送验证码';
                return;
            }

            showAlert('验证码已发送到您的邮箱', 'success');

            // 60 秒倒计时
            var countdown = 60;
            sendCodeBtn.textContent = countdown + 's';
            var timer = setInterval(function () {
                countdown--;
                if (countdown <= 0) {
                    clearInterval(timer);
                    sendCodeBtn.disabled = false;
                    sendCodeBtn.textContent = '发送验证码';
                } else {
                    sendCodeBtn.textContent = countdown + 's';
                }
            }, 1000);
        })
        .catch(function () {
            showAlert('网络错误，请检查连接后重试', 'error');
            sendCodeBtn.disabled = false;
            sendCodeBtn.textContent = '发送验证码';
        });
    };

    // 发送验证码按钮 — 先触发 Turnstile
    document.getElementById('send-code-btn').addEventListener('click', function () {
        var email = document.getElementById('email').value.trim();
        if (!email) {
            showAlert('请先输入邮箱地址', 'warning');
            return;
        }
        if (turnstileWidgetId === null) {
            showAlert('人机验证加载中，请稍后重试', 'warning');
            return;
        }

        _sendCodeEmail = email;
        this.disabled = true;
        this.textContent = '验证中...';

        turnstile.reset(turnstileWidgetId);
        turnstile.execute(turnstileWidgetId);
    });

    // 注册表单提交
    var form = document.getElementById('register-form');
    var submitBtn = document.getElementById('submit-btn');

    form.addEventListener('submit', function (e) {
        e.preventDefault();

        var username = document.getElementById('username').value.trim();
        var email = document.getElementById('email').value.trim();
        var password = document.getElementById('password').value;
        var confirmPassword = document.getElementById('confirm-password').value;
        var verificationCode = document.getElementById('verification-code').value.trim();

        if (password !== confirmPassword) {
            showAlert('两次输入的密码不一致', 'error');
            return;
        }
        if (!verificationCode || verificationCode.length !== 6) {
            showAlert('请输入 6 位验证码', 'error');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = '注册中...';

        fetch('/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: username, email: email, password: password, verification_code: verificationCode })
        })
        .then(function (res) {
            return res.json().then(function (data) {
                return { ok: res.ok, data: data };
            });
        })
        .then(function (result) {
            if (!result.ok) {
                var msg = '注册失败，请稍后重试';
                if (typeof result.data.detail === 'string') {
                    msg = result.data.detail;
                } else if (Array.isArray(result.data.detail)) {
                    msg = result.data.detail.map(function (e) { return e.msg || e.message || JSON.stringify(e); }).join('; ');
                }
                showAlert(msg, 'error');
                return;
            }

            showAlert('注册成功，即将跳转到登录页面', 'success');
            setTimeout(function () { window.location.href = '/login.html'; }, 1500);
        })
        .catch(function () {
            showAlert('网络错误，请检查连接后重试', 'error');
        })
        .finally(function () {
            submitBtn.disabled = false;
            submitBtn.textContent = '注册';
        });
    });
})();
