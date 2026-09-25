# AstrBot MCMod 搜索工具

只注册一个 LLM 工具 `mcmod_search`，直接请求 `search.mcmod.cn`，不启动本地 API、中转进程或监听端口。

## 工具参数

- `query`：搜索关键词
- `search_type`：`mod` 模组、`modpack` 整合包、`item` 物品、`post` 教程、`all` 综合搜索
- `page`：页码，1–20

模型根据用户问题选择类型。例如“查机械动力模组”传入 `mod`，“GTNH 是什么整合包”传入 `modpack`，“查钻石物品”传入 `item`。无法确定类型时使用 `all`。

## 特性

- 无固定命令前缀，仅作为 LLM 工具提供
- 直接请求 MCMod 搜索页
- 使用 `params` 编码查询参数
- 每次解析使用独立的去重集合，适合并发调用
- 请求连接、读取和总时长均有限制
- 查询长度、页码和结果数量有限制
- 返回 JSON 结构化结果
- 仅接受 `mcmod.cn` 域名链接，过滤分类导航链接

## 安装

在 AstrBot 插件目录安装依赖：

```bash
pip install -r requirements.txt
```
