# 私有评测材料

仓库的离线测试使用合成数据。运行 `npm run check` 即可验证安装、文件处理、评分契约与界面。

本地评测工具从 `evals/fixtures/<name>/input.json` 读取经授权的材料、页码与 SHA-256。
后验评分参考单独存放在同一目录的 `posthoc/`。只有任务已结束、冻结结果哈希通过检查后，评测器才读取评分参考。
自行准备的材料、运行目录和生成文件应保存在 Git 之外。

```sh
npm run fixtures:prepare -- --fixture NAME --output runs/prepared
npm run fixtures:check -- --fixture NAME
```
