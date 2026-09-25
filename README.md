# AstrBot MCMod 搜索与详情工具

只注册两个 LLM 工具 `mcmod_search` 和 `mcmod_detail`，直接请求 MCMod，不启动本地 API、中转进程或监听端口。

## 两个工具

### `mcmod_search`

搜索工具要求必填 `query`，可选 `search_type` 和 `page`：

```json
{"query":"机械动力","search_type":"mod","page":1}
```

### `mcmod_detail`

详情工具要求必填 MCMod 站内 URL：

```json
{"url":"https://www.mcmod.cn/class/2021.html"}
```

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
