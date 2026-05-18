# 闲鱼详情弹窗主题适配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让闲鱼详情弹窗的色系与全站主题保持一致，并保证浅色/深色主题下内容清晰可见。

**Architecture:** 仅调整 `web-vue/src/views/xianyu/index.vue` 中详情弹窗相关样式，不新增全局 token。通过收敛到已有 `--app-*` 主题变量与现有 `theme-surface-*` 层级，降低局部渐变/高光/亮色描边的权重。

**Tech Stack:** Vue 3、Element Plus、SCSS、ESLint

---

### Task 1: 为详情弹窗样式加回归测试

**Files:**
- Create: `backend/tests/test_xianyu_detail_theme_styles.py`
- Test: `backend/tests/test_xianyu_detail_theme_styles.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**

### Task 2: 收敛详情弹窗配色到现有主题体系

**Files:**
- Modify: `web-vue/src/views/xianyu/index.vue`
- Test: `backend/tests/test_xianyu_detail_theme_styles.py`

- [ ] **Step 1: 弱化详情概览卡的渐变和高光，统一到 surface/background 层级**
- [ ] **Step 2: 调整标签、元信息、统计卡、卖家 chips 的主题对比度**
- [ ] **Step 3: 去掉详情头像偏白描边，改为主题边框**
- [ ] **Step 4: 调整弹窗容器、描述、属性、空态的文字对比度**
- [ ] **Step 5: 跑测试与 ESLint 校验**
