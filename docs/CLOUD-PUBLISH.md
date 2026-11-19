# 班级成绩发布协议 v1

教师门户为所选班级生成一次性配对信息。在本地批改结果中打开「发布给学生」，粘贴并连接。选择本地批次、考试日期和每份答卷的收件学生，按学号核对同名学生。在预览中确认后发布。后续保存复核，再从同一入口预览并同步更正。已授权的本地连接保存在工作区权限为 0600 的私有文件中。学生答卷、模型对话和内部复核理由默认留在本地。

独立接收端可通过 HTTPS 实现以下 JSON 接口。本机开发也支持回环 HTTP。配对串为服务地址加 URL fragment 中的一次性码。工作台通过 `POST /api/pair` 发送 `{code}`，接收 `{token,classroom:{id,name}}`。后续以 Bearer token 访问所属班级。名册通过 `GET /api/device/roster` 返回 `{classroom,students:[{id,name,number}]}`。批次的稳定标识为本地任务 ID。

`GET /api/device/exams/{taskId}` 返回当前 version、active 和 papers。版本 0 表示首次发布。已发布的收件绑定返回 paperId、studentId、note、date。向同一地址 POST 下方结构可以发布。合成示例中的 source 代表不可变原评分点的 SHA-256，studentId 为名册返回的标识。

```json
{"schema":1,"baseVersion":0,"title":"合成测验","date":"2026-01-10","papers":[{"paperId":"paper-a","studentId":"00000000-0000-4000-8000-000000000001","note":"请再看一遍单位。","points":[{"question":"Q1","point":"单位","source":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","state":"scored","score":1,"max":2}]}]}
```

评分状态包括 scored、pending 和 feedback。后两者的 score 为 null。发布的单位为一次考试的完整收件人快照，服务端原子提交所有答卷并返回 `{id,version,replayed}`。当前内容一致的重传返回同一版本。过时且内容不同的发布返回 409。确认后的发布先落到本地待发送记录，网络断开或回执丢失后，重试会发送原快照。更换已发布的收件人需由老师在云端先撤回。
