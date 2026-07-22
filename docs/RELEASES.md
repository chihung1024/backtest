# 版本封存與還原

本專案以 `backend/app/__init__.py` 的 `__version__` 作為唯一版本來源，前端
`package.json` 應維持相同版本。採用語意化版本：

- 修正錯誤：增加 patch，例如 `0.1.0` → `0.1.1`。
- 向下相容的新功能：增加 minor，例如 `0.1.1` → `0.2.0`。
- 不相容變更：增加 major，例如 `0.2.0` → `1.0.0`。

功能 PR 的 CI 全數成功並合併至 `main` 後，`Release verified version` workflow
會再次確認主分支 CI 成功，再建立固定的 `vX.Y.Z` Tag 與 GitHub Release。
若該版本已存在，workflow 只回報既有 Release，不會移動 Tag。

## 從 Release 還原

先在本機取得所有 Tag，再從指定版本開新的修復分支：

```bash
git fetch origin --tags
git switch --create restore/v0.1.0 v0.1.0
```

確認內容後，以這個分支開 PR 回到 `main`。不要強制移動既有 Tag，也不要直接
覆寫 `main`，如此可保留完整稽核與還原歷史。
