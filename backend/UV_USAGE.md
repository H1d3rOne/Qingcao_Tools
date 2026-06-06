# 使用 uv 管理项目依赖

## 什么是 uv？

uv 是一个用 Rust 编写的极速 Python 包管理器和解析器，比 pip 快 10-100 倍。

## 安装 uv

```bash
# macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或使用 pip
pip install uv
```

## 项目配置

项目使用 `pyproject.toml` 配置文件，包含以下信息：

- 项目元数据（名称、版本、描述等）
- Python 版本约束（`requires-python = ">=3.10"`）
- 依赖列表（`dependencies`）
- 可选依赖（`project.optional-dependencies`）
- 工具配置（black、ruff、pytest）

## 常用命令

### 安装依赖

```bash
# 从 requirements.txt 安装
uv pip install -r requirements.txt

# 添加新依赖
uv add fastapi

# 更新依赖
uv sync
```

### 运行项目

```bash
# 运行应用
uv run uvicorn app.main:app --host 0.0.0.0 --port 3121 --reload

# 运行测试
uv run pytest

# 运行脚本
uv run python script.py
```

### Python 版本管理

```bash
# 查看当前 Python 版本
uv python list

# 固定 Python 版本（创建 .python-version 文件）
echo "3.14.3" > .python-version
uv python pin

# 切换到特定 Python 版本
uv python install 3.10
```

### 其他命令

```bash
# 查看已安装的包
uv pip list

# 查看依赖树
uv pip tree

# 清理缓存
uv cache clean

# 锁定依赖
uv lock
```

## 优势

1. **极速**：用 Rust 编写，比 pip 快 10-100 倍
2. **可靠**：自动生成 `uv.lock` 文件，确保可重现的构建
3. **简单**：自动管理虚拟环境，无需手动创建
4. **兼容**：完全兼容 pip 和 requirements.txt
5. **智能**：自动解析和解决依赖冲突

## 迁移说明

从 pip 迁移到 uv：

1. 项目已经配置了 `pyproject.toml` 文件
2. 创建了 `.python-version` 文件指定 Python 版本（3.14.3）
3. 使用 `uv pip install -r requirements.txt` 安装所有依赖
4. 使用 `uv run` 命令运行项目

## 注意事项

- `.python-version` 文件用于指定项目使用的 Python 版本
- `uv.lock` 文件会自动生成，包含精确的依赖版本
- 虚拟环境自动创建在 `.venv` 目录中
- 可以继续使用 `requirements.txt`，但建议迁移到 `pyproject.toml`
