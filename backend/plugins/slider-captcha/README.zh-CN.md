# 滑动拼图验证码插件

English version: [README.md](./README.md)

这是一个用于 NovusAI 登录链路的滑动拼图验证码插件。

它会把 `slider` 注册为动态验证码提供方，可用于：

- 管理端登录
- 企业管理员登录
- 企业用户登录
- 企业用户自助注册

## 插件用途

这个插件的目标，是把滑动验证码的实现留在插件边界内，而不是写死在宿主工程里。

宿主只提供通用能力：

- 验证码提供方注册
- 登录前公共插件资源加载
- 登录页公开配置下发
- 通用插件配置表单渲染

真正的滑动拼图逻辑都在插件内部：

- 挑战生成与校验
- 前端滑块渲染
- 内置背景图
- 插件本地文案

## 作用域与覆盖端点

- 插件资源作用域：`global_shared`
- 验证码 provider code：`slider`
- 支持的公开端点：`admin`、`tenant`、`user`

配置映射关系：

| 使用场景 | 开关 / 前置条件 | Provider 配置键 |
|---|---|---|
| 管理端登录 | `login_captcha_enabled` | `captcha_provider` |
| 企业管理员登录 | `tenant_captcha_enabled` | `tenant_captcha_provider` |
| 企业用户登录 | `tenant_captcha_enabled` | `tenant_captcha_provider` |
| 企业用户注册 | 是否要求注册验证码由 `user_registration_captcha_enabled` 控制，但 provider 仍沿用企业登录配置 | `tenant_captcha_provider` |

说明：

- 因为插件作用域是 `global_shared`，所以管理端和全部企业都可以使用。
- 这个插件不需要做“分配企业”操作。

## 运行架构

运行链路如下：

1. `plugin.yaml` 通过 `extensions.custom[].type = captcha_provider` 声明 `slider` provider。
2. 宿主在插件启动时注册该 provider 的元数据。
3. 公开配置接口在当前 provider 生效时，把插件前端运行时信息返回给登录页。
4. 登录页通过宿主插件运行时动态加载前端资源。
5. 插件前端在运行时注册 `slider` 组件。
6. 滑块组件向 `/api/public/captcha/challenge` 发起请求，并带上 `provider_code=slider`。
7. 插件后端 provider 生成挑战，并把挑战暂存在进程内存中。
8. 登录表单提交 `captchaChallengeId`、`captchaSolution`、`captchaProviderCode=slider`。
9. 宿主认证服务在真正登录前，再通过注册的 provider 做服务端校验。

关键文件：

- `plugin.yaml`：插件清单、作用域、配置 schema、captcha_provider 扩展
- `backend/captcha_provider.py`：挑战生成与校验逻辑
- `frontend/src/SliderCaptcha.vue`：滑块 UI 与 challenge 请求
- `frontend/src/index.ts`：前端 provider 注册入口

## 部署限制

这一节非常重要。当前实现有真实的运行限制，不是“理论上可扩展”。

### 进程内内存挑战存储

当前 provider 把活跃 challenge 保存在进程内存里：

- 存储位置：`backend/captcha_provider.py`
- TTL：120 秒
- 不会跨 worker、跨实例共享

这会直接影响部署正确性：

- 单进程部署：正常可用
- 多 worker、多实例部署：必须保证粘性会话，否则 challenge 可能在 A worker 生成、在 B worker 校验，导致“前端拖动成功但后端校验失败”
- 热重载、worker 重启、滚动发布、Pod 调度迁移，都可能让未完成的 challenge 直接失效

当前建议：

- 本地开发：可以直接使用
- 单实例小规模部署：可接受
- 多 worker / 多实例生产部署：至少加粘性会话，或者在正式依赖前先把 challenge store 改成 Redis / 共享缓存

### 安全定位

当前实现更适合定位为“低到中等强度的登录防自动化摩擦层”，而不是高强度反机器人方案。

原因：

- challenge 状态只保存在内存里
- 前端基于 challenge payload 渲染拼图，再把解出的 offset 回传给宿主登录链路做服务端校验
- 它能提高自动化成本、改善交互体验，但并不是专门强化过的 bot-defense 产品

如果要继续增强，建议后续做这些演进：

- challenge state 改为 Redis 等共享存储
- 提升 proof 协议强度
- 增加抗重放、抗自动化的额外保护

## 开发态与发布态

这个插件有两种运行模式。

### 本地仓库 / DEBUG 运行

宿主在 DEBUG 模式下，可以直接从源码入口加载前端：

- `frontend/src/index.ts`

这适合本地仓库开发，通常不依赖 `frontend/dist`。

### 发布 / 生产运行

发布态当前要求前端编译产物位于：

- `frontend/dist/index.js`
- `frontend/dist/plugin.manifest.json`

当前约定的 UMD 全局变量名：

- `NovusPlugin_slider_captcha`

示例 manifest：

```json
{
  "format": "novus.plugin.release.v1",
  "entry": "index.js",
  "global_var": "NovusPlugin_slider_captcha",
  "css": [],
  "assets": [
    "assets/slider-bg-01.jpg",
    "assets/slider-bg-02.jpg",
    "assets/slider-bg-03.jpg",
    "assets/slider-bg-04.jpg"
  ]
}
```

如果发布态缺少这些文件，登录页将无法正确加载该插件前端资源。

## 构建与打包

### 前端构建

从仓库根目录执行：

```bash
cd backend/plugins/slider-captcha/frontend
pnpm install
pnpm build
```

构建产物目标位置：

- `frontend/dist/index.js`
- `frontend/dist/assets/`

如果要走生产发布链路，还需要确保存在并维护：

- `frontend/dist/plugin.manifest.json`

并且其中声明的 JS / 资源路径要与实际构建产物一致。

### 校验与打包

在前端发布产物准备好之后：

```bash
novusai plugin validate backend/plugins/slider-captcha
novusai plugin pack backend/plugins/slider-captcha
```

如果只是当前仓库下的本地 DEBUG 开发，一般可以不走发布打包，直接依赖源码加载。

## 安装与启用

### 仓库内开发模式

适用于插件已经位于 `backend/plugins/slider-captcha` 的场景。

1. 确保后端会扫描仓库里的插件目录
2. 如果插件是在服务启动后新增的，重启后端
3. 进入管理端 -> 插件管理
4. 确认可以看到 `slider-captcha`
5. 启用插件
6. 如果你改过 `plugin.yaml`，但管理端里仍显示旧 scope 或旧元数据，执行一次插件修复或重新启用，让 DEBUG 模式下的 DB 元数据重新同步

### ZIP / 发布包安装

适用于把插件作为安装包交付的场景。

1. 构建前端发布产物
2. 确保带上 `frontend/dist/index.js` 与 `frontend/dist/plugin.manifest.json`
3. 打包插件
4. 在管理端 -> 插件管理中上传安装
5. 启用插件

## 插件配置

在管理端 -> 插件管理 -> `slider-captcha` -> 配置 中设置以下可选参数。

### 配置项说明

| Key | 类型 | 允许值 | 默认值 | 说明 |
|---|---|---|---|---|
| `background_1` 到 `background_4` | string | 空字符串、公开附件 ID、直接可访问的图片 URL | 空 | 每个字段对应覆盖一张内置背景图；为空则继续使用内置图。 |
| `square_length` | integer | `36` 到 `54` | `42` | 拼图主体边长。数值越大，拼图轮廓越明显。 |
| `tolerance_px` | integer | `3` 到 `12` | `6` | 容许误差像素。值越大，越容易通过。 |

### 背景图覆盖规则

背景图字段支持三种写法：

- 空字符串：继续使用插件内置图
- 纯数字字符串，例如 `"123"`：按附件 ID 处理，解析为 `/api/public/attachments/{id}/image`
- 非数字字符串：按原始图片 URL 处理

操作建议：

- 优先通过宿主提供的插件配置图片选择器来配置，它会保存公开附件 ID，更适合登录前页面使用
- 如果手工填写附件 ID，必须确保该附件在登录前页面可公开读取
- 如果手工填写 URL，必须保证未登录也能访问到该地址；同源 URL 最稳妥
- 跨域图片如果没有合适的 CORS 响应头，画到 canvas 时可能失败

当自定义背景图加载失败时，前端会尽量回退到插件内置背景图。

## 如何启用到三端登录

### 管理端登录

在平台安全配置中：

1. 打开 `login_captcha_enabled`
2. 设置 `captcha_provider = slider`
3. 按需要调整 `captcha_enable_threshold_admin`

预期结果：

- 管理端登录页收到 `captcha_provider = slider`
- 平台公开配置里会包含 `captcha_plugin` 运行时信息

### 企业管理员登录与企业用户登录

在企业安全配置中：

1. 打开 `tenant_captcha_enabled`
2. 设置 `tenant_captcha_provider = slider`
3. 按需要调整 `tenant_captcha_enable_threshold`

预期结果：

- 企业管理员登录页使用滑块验证码
- 企业用户登录页也复用同一个 provider

### 企业用户注册

注册页是否需要验证码，单独由注册开关控制，但 provider 仍沿用企业侧 provider。

如需注册时启用验证码：

1. 开启企业注册
2. 开启 `user_registration_captcha_enabled`
3. 保持 `tenant_captcha_provider = slider`

预期结果：

- 注册页在要求验证码时，会使用同一套滑块 provider

## 验证清单

### 自动化验证

```bash
pytest backend/tests/plugins/test_slider_captcha_plugin.py
```

这组测试覆盖：

- provider 加载
- challenge 生成
- 背景图覆盖 URL 解析
- verify roundtrip
- 动态 provider 选项注入

### 手工 API 验证

获取平台公开配置：

```bash
curl http://localhost:8000/api/public/platform/config
```

获取企业公开配置：

```bash
curl http://localhost:8000/api/public/tenant/config
```

生效时应看到：

- `captcha_provider = slider`
- `captcha_plugin.plugin_name = slider-captcha`

请求 challenge：

```bash
curl -X POST http://localhost:8000/api/public/captcha/challenge \
  -H "Content-Type: application/json" \
  -d "{\"action\":\"login\",\"endpoint\":\"admin\",\"provider_code\":\"slider\"}"
```

生效时应看到：

- `data.type = "slider"`
- 返回 `challenge_id`
- 返回滑块 payload，例如 `canvas_width`、`piece_y`、背景图信息等

### 手工 UI 验证

至少验证以下路径：

1. 管理端登录页显示滑块验证码
2. 企业管理员登录页显示滑块验证码
3. 企业用户登录页显示滑块验证码
4. 企业用户注册页在要求验证码时显示滑块验证码
5. 点击刷新能够重新拉取 challenge
6. 自定义背景图失效时，仍能回退到内置背景图，不至于直接阻塞登录

## 回退与排错

### 配置下拉里没有 `slider`

现象：

- 验证码提供方下拉框里看不到 `slider`

优先检查：

- 插件是否已安装并启用
- manifest 元数据是否已经同步
- 当前端点是否包含在 `public_endpoints` 中

如果你改过 `scope` 或 manifest，但界面仍显示旧值，优先执行插件修复或重新启用，让元数据刷新。

### 登录页回退成内置图片验证码

现象：

- 配置里已经选了 `slider`，但登录页看到的还是内置图片验证码

含义：

- 宿主没能成功加载插件前端运行时，因此自动回退到了内置 `image`

优先检查：

- 浏览器控制台里的 captcha plugin loader 警告
- 公开配置接口里是否返回了 `captcha_plugin`
- 插件公开资源网络请求是否成功
- 生产模式下 `plugin.manifest.json` 和 `index.js` 是否存在

常见请求路径：

- `/plugin-public-assets/admin/slider-captcha/...`
- `/plugin-public-assets/tenant/slider-captcha/...`
- `/plugin-public-assets/user/slider-captcha/...`

### challenge 能生成，但校验偶发失败

现象：

- 前端拖动成功，但登录时提示验证码错误
- 失败不是必现，而是偶发

最常见原因：

- challenge 生成与 verify 命中了不同的 worker / 实例

优先检查：

- 后端 worker 数量
- 负载均衡是否开启粘性会话
- 是否有 Pod / worker 重启
- 用户是否在 120 秒 TTL 之后才提交

### 自定义背景图不生效

现象：

- 配置了背景图，但实际显示的仍是内置图
- 或登录页背景图渲染失败

优先检查：

- 附件是否为 public
- 手工 URL 是否可在未登录页面访问
- URL 是否同源或具备可用于 canvas 的 CORS 配置

### 建议先看的日志

优先看：

- `logs/captcha.log`
- `logs/auth.log`

这些日志最适合排查 challenge 生成、verify 失败、登录侧验证码强制启用等问题。

## 已知限制与后续演进

当前已知限制：

- 仅使用进程内内存存储 challenge
- challenge TTL 只有 120 秒
- 默认不适合无粘性的多实例扩容
- 背景图 URL 配置较宽松，依赖操作者自己提供可公开、可用于 canvas 的 URL
- 当前实现更偏向插件化接入与交互体验，不是强化过的反机器人方案

建议后续演进：

- challenge store 改为 Redis / 共享缓存
- 增加更强的 challenge proof 与抗重放能力
- 把 release manifest 生成正式纳入插件构建流程
- 增加针对公开登录页链路的插件前端测试
