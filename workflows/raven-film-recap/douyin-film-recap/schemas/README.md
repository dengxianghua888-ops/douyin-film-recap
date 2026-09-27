# Artifact Schemas

这些 JSON Schema 对应 Skill 的主要阶段产物。它们用于：

- 模型结构化输出约束
- 阶段缓存与兼容性检查
- 测试和回归
- 人工审查工具接入

运行以下命令重新生成：

```bash
PYTHONPATH=src python scripts/generate_schemas.py
```
