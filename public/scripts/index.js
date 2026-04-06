/**
 * 主页（认证成功页）逻辑 (ViewModel)
 * 职责：认证检查、用户信息加载、退出登录
 */
(function () {
    var accessToken = localStorage.getItem('access_token');
    var refreshToken = localStorage.getItem('refresh_token');

    if (!accessToken) {
        window.location.replace('/login.html');
        return;
    }

    var redirecting = false;

    function handle401() {
        if (redirecting) return;
        redirecting = true;
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.replace('/login.html');
    }

    function loadUserInfo() {
        var loading = document.getElementById('loading');
        var content = document.getElementById('content');

        loading.classList.remove('hidden');
        content.classList.add('hidden');

        fetch('/users/me', {
            headers: {
                'Authorization': 'Bearer ' + accessToken,
                'Accept': 'application/json'
            }
        })
        .then(function (res) {
            if (res.status === 401) {
                handle401();
                throw new Error('unauthorized');
            }
            if (!res.ok) throw new Error('request_failed');
            return res.json();
        })
        .then(function (user) {
            document.getElementById('username-display').textContent = user.username;
            loading.classList.add('hidden');
            content.classList.remove('hidden');
        })
        .catch(function (err) {
            if (err.message !== 'unauthorized') {
                loading.classList.add('hidden');
                showAlert('获取用户信息失败', 'error');
            }
        });
    }

    document.getElementById('logout-btn').addEventListener('click', function () {
        var btn = document.getElementById('logout-btn');
        btn.disabled = true;
        btn.textContent = '退出中...';
        fetch('/auth/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + accessToken
            },
            body: JSON.stringify({
                access_token: accessToken,
                refresh_token: refreshToken
            })
        })
        .catch(function () {})
        .finally(function () {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.replace('/login.html');
        });
    });

    loadUserInfo();
})();
