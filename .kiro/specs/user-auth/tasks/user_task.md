- [x] 修改specs中相关文档，更改项目中所有界面，使用极简、现代化的UI风格

- [x] 修改specs中的requirement、task、design文档及其它相关文档，要求项目中所有界面的消息提示都需要通过chakra-ui的Alert组件的方式进行展示，且UI风格样式需要与当前界面的UI风格样式统一

- [x] 修改specs中的requirement、task、design文档及其它相关文档，要求在登录成功后，如果访问登录页面或注册页面，需要重定向到首页

- [x] 修改specs中的requirement、design文档，增加任务，要求首页显示认证成功，原首页信息改为个人信息页（/profile），个人信息页面需要手动填写url进行访问

- [x] 修改specs中的requirement、task、design文档及其它相关文档，要求项目中所有界面的消息提示能够支持设置显示时长，默认显示2秒后消失

- [x] 使用安全的方式设置google的client secret，以实现google第三方认证

- [x] 修改specs中的requirement、task、design文档及其它相关文档，要求去除X平台三方认证

- [x] 修改specs中的requirement、task、design文档及其它相关文档，优化第三方平台认证登录：
  - 在google三方认证登录后，根据google返回的信息，发放Token，设置token过期时间（与google保持一致），兼容系统当前的token机制
  - 个人信息页面显示google账号的相关信息
  - 参考阿里巴巴、腾讯等顶级互联网公司的设计，新增一个第三方平台账号表，用于记录三方登录的账号
  - 第三方认证登录的用户，能够在个人信息页面设置密码。在设置密码后，注册为当前系统的普通用户

- [x] 修改specs中的requirement、task、design文档及其它相关文档，优化个人信息页面：
  - 使用分栏显示内容的方式，用户能够切换选择想要查看的内容或使用的功能
  - 优化空间布局，使其符合用户操作习惯，简化用户操作

- [x] 修改specs中的requirement、task、design文档及其它相关文档，优化个人信息页面：
  - 图示中红框部分固定在界面中适当位置，整体内容尽量保持垂直

- [x] 修改specs中的requirement、task、design文档及其它相关文档，新增用户登录历史记录表：
  - 新增一个登录历史记录表，记录用户登录登出操作
  - 需要记录登录ip、地区等相关信息
  - 该表数据用于安全审计及统计分析
  - 能够兼容三方平台及系统用户的登录/登出

- [ ] 修改specs中的requirement、task、design文档及其它相关文档，用户注册增加邮箱验证码验证功能：
  - 使用resend.com平台的邮件发送API
  - 使用安全的方式设置并管理resend的API KEY
  - 验证码有效时长为5分钟，不能重复生成验证码
  - 设计并使用一个与当前界面UI风格样式相同的界面作为邮件模板，参考X平台的邮件验证码模板
  - 在发送邮箱验证码前，需要用户做人机验证

- [x] 讲解在wrangler.jsonc等文件在脱敏后，推送到云端部署，是否会影响线上使用，如果影响，给出解决方案


