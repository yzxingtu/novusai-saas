# 用户端视图目录

此目录包含租户用户端（C端）的页面组件。

## 目录结构

```
user/
├── dashboard/       # 用户首页
├── profile/         # 个人中心
├── order/           # 订单相关
└── authentication/  # 用户认证（如有独立登录页）
```

## 命名规范

- 目录名使用小写字母和连字符
- 组件文件使用 PascalCase 命名
- 页面入口文件统一命名为 `index.vue`
