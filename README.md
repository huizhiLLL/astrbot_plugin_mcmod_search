# AstrBot MCMod 搜索与详情工具

只注册一个 LLM 工具 `mcmod_search`，直接请求 MCMod，不启动本地 API、中转进程或监听端口。

## 两种操作

### 搜索页面

```json
{"operation":"search","query":"机械动力","search_type":"mod","page":1}
```

返回匹配结果的名称和 MCMod URL。`search_type` 支持 `mod` 模组、`modpack` 整合包、`item` 物品、`post` 教程、`all` 综合搜索。

### 读取详情

```json
{"operation":"detail","url":"https://www.mcmod.cn/class/2021.html"}
```

返回页面标题、类型、简介、支持的 Minecraft 版本、作者、更新日志条目和长度受限的正文摘要。详情操作只接受 `mcmod.cn` 站内的 `/class/`、`/modpack/`、`/item/`、`/post/` 页面。

## 安全与稳定性

- 使用 `params` 编码搜索参数
- 每次解析使用独立去重集合，支持并发调用
- 请求连接、读取和总时长均有限制
- 限制查询长度、页码、结果数量和详情正文长度
- 严格校验详情 URL，避免请求外部地址
- 只返回结构化 JSON，不把整页导航直接交给模型

## 安装

```bash
pip install -r requirements.txt
```
