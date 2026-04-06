/**
 * 个人信息页逻辑 (ViewModel)
 * 职责：认证检查、数据加载、Tab 切换、设置密码、退出登录
 */
(function () {
    var accessToken = localStorage.getItem('access_token');
    var refreshToken = localStorage.getItem('refresh_token');

    if (!accessToken) {
        window.location.replace('/login.html');
        return;
    }

    var redirecting = false;
    var userDetail = null;

    function handle401() {
        if (redirecting) return;
        redirecting = true;
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.replace('/login.html');
    }

    function authFetch(url, options) {
        var opts = Object.assign({
            headers: {
                'Authorization': 'Bearer ' + accessToken,
                'Accept': 'application/json'
            }
        }, options || {});
        if (options && options.headers) {
            opts.headers = Object.assign({}, opts.headers, options.headers);
            opts.headers['Authorization'] = 'Bearer ' + accessToken;
        }
        return fetch(url, opts).then(function (res) {
            if (res.status === 401) {
                handle401();
                throw new Error('unauthorized');
            }
            if (!res.ok) {
                return res.json().catch(function () { return {}; }).then(function (data) {
                    throw new Error(data.detail || 'request_failed');
                });
            }
            return res.json();
        });
    }

    /* ---- Tab 切换 ---- */
    function initTabs() {
        var tabs = document.querySelectorAll('#tab-nav .m-tab');
        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                var target = this.getAttribute('data-tab');
                tabs.forEach(function (t) { t.classList.remove('m-tab-active'); });
                this.classList.add('m-tab-active');
                document.querySelectorAll('.m-tab-panel').forEach(function (p) {
                    p.classList.remove('m-tab-panel-active');
                });
                var panel = document.getElementById('panel-' + target);
                if (panel) panel.classList.add('m-tab-panel-active');
            });
        });
    }

    /* ---- 渲染头像 ---- */
    function renderHeaderAvatar(detail) {
        var container = document.getElementById('header-avatar');
        var avatarUrl = null;
        if (detail.oauth_accounts && detail.oauth_accounts.length > 0) {
            for (var i = 0; i < detail.oauth_accounts.length; i++) {
                if (detail.oauth_accounts[i].provider_avatar_url) {
                    avatarUrl = detail.oauth_accounts[i].provider_avatar_url;
                    break;
                }
            }
        }
        if (avatarUrl) {
            container.innerHTML = '<img src="' + avatarUrl + '" alt="avatar" class="m-avatar" referrerpolicy="no-referrer">';
        } else {
            var initial = (detail.username || '?').charAt(0).toUpperCase();
            container.innerHTML = '<div class="m-avatar-placeholder">' + initial + '</div>';
        }
    }

    /* ---- 渲染 OAuth 账号 ---- */
    function renderOAuthAccounts(accounts) {
        var container = document.getElementById('oauth-accounts');
        if (!accounts || accounts.length === 0) {
            container.innerHTML = '<p class="text-sm text-slate-400 py-3">暂无关联的第三方账号</p>';
            return;
        }
        container.innerHTML = '';
        accounts.forEach(function (oa) {
            var row = document.createElement('div');
            row.className = 'flex items-center gap-3 py-3';
            var providerLabel = oa.provider === 'google' ? 'Google' : oa.provider;
            var avatarHtml = '';
            if (oa.provider_avatar_url) {
                avatarHtml = '<img src="' + oa.provider_avatar_url + '" alt="avatar" class="w-10 h-10 rounded-full object-cover flex-shrink-0" referrerpolicy="no-referrer">';
            } else {
                avatarHtml = '<div class="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0"><svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg></div>';
            }
            row.innerHTML = avatarHtml +
                '<div class="min-w-0 flex-1">' +
                '<div class="text-sm font-medium text-slate-900 truncate">' + (oa.provider_name || providerLabel) + '</div>' +
                '<div class="text-xs text-slate-400 truncate">' + (oa.provider_email || '-') + '</div>' +
                '</div>' +
                '<span class="text-xs text-slate-400 flex-shrink-0">' + providerLabel + '</span>';
            container.appendChild(row);
        });
    }

    /* ---- 渲染密码区域 ---- */
    function renderPasswordSection(hasPassword, hasOAuth) {
        var setSection = document.getElementById('set-password-section');
        var doneSection = document.getElementById('password-set-section');
        if (hasOAuth && !hasPassword) {
            setSection.classList.remove('hidden');
            doneSection.classList.add('hidden');
        } else if (hasOAuth && hasPassword) {
            setSection.classList.add('hidden');
            doneSection.classList.remove('hidden');
        } else {
            setSection.classList.add('hidden');
            doneSection.classList.add('hidden');
        }
    }

    /* ---- 加载用户信息 ---- */
    function loadUserInfo() {
        var loading = document.getElementById('loading');
        var mainContent = document.getElementById('main-content');
        loading.classList.remove('hidden');
        mainContent.classList.add('hidden');

        authFetch('/users/me/detail')
            .then(function (detail) {
                userDetail = detail;
                document.getElementById('header-username').textContent = detail.username;
                renderHeaderAvatar(detail);

                document.getElementById('info-username').textContent = detail.username;
                document.getElementById('info-email').textContent = detail.email;
                document.getElementById('info-role').textContent = detail.role;
                document.getElementById('info-created').textContent = detail.created_at;

                renderOAuthAccounts(detail.oauth_accounts);
                renderPasswordSection(detail.has_password, detail.oauth_accounts && detail.oauth_accounts.length > 0);

                loading.classList.add('hidden');
                mainContent.classList.remove('hidden');
                loadGeoInfo();
            })
            .catch(function (err) {
                if (err.message !== 'unauthorized') {
                    loading.classList.add('hidden');
                    showAlert('获取用户信息失败', 'error');
                }
            });
    }

    /* ---- 加载地理信息 ---- */
    function loadGeoInfo() {
        var geoLoading = document.getElementById('geo-loading');
        var geoContent = document.getElementById('geo-content');
        var geoError = document.getElementById('geo-error');
        geoLoading.classList.remove('hidden');
        geoContent.classList.add('hidden');
        geoError.classList.add('hidden');

        authFetch('/users/me/geo')
            .then(function (geo) {
                document.getElementById('geo-ip').textContent = geo.ip || '-';
                document.getElementById('geo-country').textContent = geo.country || '-';
                document.getElementById('geo-city').textContent = geo.city || '-';
                document.getElementById('geo-timezone').textContent = geo.timezone || '-';
                geoLoading.classList.add('hidden');
                geoContent.classList.remove('hidden');
            })
            .catch(function (err) {
                if (err.message !== 'unauthorized') {
                    geoLoading.classList.add('hidden');
                    showAlert('获取地理位置失败', 'error');
                    geoError.classList.remove('hidden');
                }
            });
    }

    /* ---- 事件绑定 ---- */
    document.getElementById('geo-retry-btn').addEventListener('click', loadGeoInfo);

    document.getElementById('set-password-form').addEventListener('submit', function (e) {
        e.preventDefault();
        var pw = document.getElementById('new-password').value;
        var cpw = document.getElementById('confirm-password').value;
        if (pw.length < 8) {
            showAlert('密码长度至少为 8 个字符', 'error');
            return;
        }
        if (pw !== cpw) {
            showAlert('两次输入的密码不一致', 'error');
            return;
        }
        var btn = this.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.textContent = '设置中...';
        authFetch('/users/me/password', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: pw })
        })
        .then(function () {
            showAlert('密码设置成功', 'success');
            renderPasswordSection(true, true);
        })
        .catch(function (err) {
            if (err.message !== 'unauthorized') {
                showAlert(err.message || '设置密码失败', 'error');
            }
        })
        .finally(function () {
            btn.disabled = false;
            btn.textContent = '设置密码';
        });
    });

    document.getElementById('logout-btn').addEventListener('click', function () {
        var btn = this;
        btn.disabled = true;
        btn.textContent = '退出中...';
        fetch('/auth/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + accessToken
            },
            body: JSON.stringify({ access_token: accessToken, refresh_token: refreshToken })
        })
        .catch(function () {})
        .finally(function () {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.replace('/login.html');
        });
    });

    initTabs();
    loadUserInfo();
})();
