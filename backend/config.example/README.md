# Qingcao_Tools 配置模板

这里的文件是可提交的安全模板，不包含真实 Cookie、API Key、设备指纹或账号信息。

首次 clone 后可以直接运行根目录 `./start.sh`，启动脚本会自动把模板初始化到：

```bash
backend/config/
```

也可以手动复制：

```bash
cp -R backend/config.example backend/config
```

约定：

- `backend/config.example/`：仓库模板，允许提交；
- `backend/config/`：本地私有运行态配置，已被 `.gitignore` 忽略；
- `backend/app/config/`：旧版配置目录，仅用于启动时迁移兼容；
- Cookie、AI 供应商 API Key、闲鱼指纹等敏感内容只放在 `backend/config/`；
- 关键配置写入时会维护同目录 `.bak`，误删或被空配置覆盖时可自动恢复或手动复制回来。
