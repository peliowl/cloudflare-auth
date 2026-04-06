# 基础任务
## 归档及经验沉淀
- 在以上整个过程中，请将你遇到的问题及对应的解决方案，使用专业的词汇及清晰的话语分别整理输出到docs文件夹中

- 将Python集成google第三方登录（认证）的步骤，包括示例代码、遇到的问题、注意事项、解决方案等内容整理并使用专业的词汇及清晰的脉络输出到docs文件夹下

- 使用专业的词汇及清晰的脉络，以markdown文档的形式，将遇到的所有问题及对策整理输出到docs目录中，要求格式统一、逻辑严谨

- 使用专业的词汇及清晰的脉络，以markdown文档的形式，将以上的问题及解决方案整理输出到docs目录中，要求格式统一、逻辑严谨

- 使用专业的词汇及清晰的脉络，以markdown文档的形式，将敏感信息的传输方案及存储方案整理输出到docs目录中，要求格式统一、逻辑严谨

## 流水线
- [ ] 执行部署脚本 `scripts\deploy.bat`，自动还原真实配置 → 部署到 Cloudflare → 恢复脱敏配置

- [ ] 执行命令`npx wrangler deploy`，部署项目到cloudflare云端，并检查部署是否成功

- [ ] 执行ddl语句，更新cloudflare云端数据库表为最新的状态

- [ ] 检查specs中的requirement、design文档关于项目结构、技术栈的内容是否符合当前项目的最新情况，如果不符合，则更新使文档与项目最新情况保持一致

- [ ] 更新.gitignore文件，忽略与项目无关的文件

- [ ] 检查项目中是否存在敏感信息，并提醒我是否需要脱敏

- [-] 将修改的文件从工作区添加到暂存区，并且提交到版本库，在提交前向我确认提交信息是否合理

- [ ] 将版本库中的文件推送到远程仓库master

- [x] 删除远程仓库的main分支

- [x] 添加README.md文件，使用专业的词汇及清晰严谨的脉络介绍该项目，并且推送到远程仓库

- [ ] 根据.dev.vars中的配置信息，设置TURNSTILE_SECRET_KEY和RESEND_API_KEY到云端cloudflare secrets

- [x] 根据.dev.vars中的配置信息，更新TURNSTILE_SECRET_KEY到云端cloudflare secrets

- [x] 将wrangler.jsonc中新增的内容项，添加到wrangler.jsonc.bak中，然后对wrangler.jsonc进行脱敏，并且参考.dev.vars的方式，提供脱敏的wrangler.jsonc.example加入版本管理，wrangler.jsonc使用真实的数据用于本地调试和deploy线上使用，同时更新deploy.bat脚本

- [x] 检查并去除前端界面中用于debug的内容
