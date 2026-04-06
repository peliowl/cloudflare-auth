# bug修复类型任务
## 第三方登录认证
- [x] 修复bug：使用Google三方登录成功，且退出登录后并再次点击Google第三方登录，系统直接跳转到认证成功页面，没有跳转到Google的认证页面

- [x] 修复bug：在Google三方认证页面，选择账号并重定向到callback页面后，抛出异常：{
  "level": "error",
  "message": "pyodide.ffi.JsException: Error: D1_TYPE_ERROR: Type 'undefined' not supported for value 'undefined'",
  "$workers": {
    "truncated": false,
    "event": {
      "request": {
        "url": "https://auth.peliowl.asia/auth/oauth/callback/google?state=REDACTED&iss=https%3A%2F%2Faccounts.google.com&code=4%REDACTED&scope=email+profile+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.email+openid+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.profile&authuser=0&prompt=none",
        "method": "GET",
        "path": "/auth/oauth/callback/google",
        "search": {
          "state": "REDACTED",
          "iss": "https://accounts.google.com",
          "code": "4%REDACTED",
          "scope": "email profile https://www.googleapis.com/auth/userinfo.email openid https://www.googleapis.com/auth/userinfo.profile",
          "prompt": "none",
          "authuser": 0
        }
      }
    },
    "outcome": "ok",
    "scriptName": "cloudflare-auth",
    "eventType": "fetch",
    "executionModel": "stateless",
    "scriptVersion": {
      "id": "5ad48ac1-ed79-4f04-af85-8297c036ff33"
    },
    "requestId": "9e7a16351bbed903"
  },
  "$metadata": {
    "id": "01KNF967PW046K0G1K0V2PYX0X",
    "requestId": "9e7a16351bbed903",
    "trigger": "GET /auth/oauth/callback/google",
    "service": "cloudflare-auth",
    "level": "error",
    "error": "pyodide.ffi.JsException: Error: D1_TYPE_ERROR: Type 'undefined' not supported for value 'undefined'",
    "message": "pyodide.ffi.JsException: Error: D1_TYPE_ERROR: Type 'undefined' not supported for value 'undefined'",
    "account": "787a8f02cbf29fd64fa5eea4efd2af62",
    "type": "cf-worker",
    "fingerprint": "f3964d83fc255000a426ee3f216766bc",
    "origin": "fetch",
    "messageTemplate": "<DOMAIN>: Error: D1_TYPE_ERROR: Type 'undefined' not supported for value 'undefined'"
  }
}

## 个人信息
- [x] 修复bug：个人信息页面的国家、城市、时区信息没有正确显示出来


## 注册
- [x] 修复bug：注册页面点击发送验证码，调用发送验证码接口失败后，提示信息显示错误

- [x] 修复bug：注册页面点击发送验证码，调用/auth/send-verification-code接口抛出异常：{"detail":"人机验证失败，请重试"}

- [x] 修复bug：注册页面点击发送验证码，调用/auth/send-verification-code接口，抛出异常：{detail: "验证码已发送，请稍后再试"} detail: "验证码已发送，请稍后再试"，但查看Cloudflare KV无验证码

- [x] 修复bug：注册页面点击发送验证码，调用了两次
https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/flow/ov1接口，并且第二次接口返回401 Unauthorized

- [x] 修复bug：当浏览器视口高度不足时，注册页面没有出现滚动条，导致无法部分顶部、底部内容未完全显示出来，无法切换到登录页面
