# grilling-gemini-notebook

Gemini Notebook（NotebookLM等）内の指定ファイル（またはファイル群）について、インストール済みの既存 [`grilling`](https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling) スキルを呼び出して双方向に深掘りし、別のアナロジーを用いた回答・仮説の正確性を**対象ファイルの記述**および**外部文献・URL・Web記事のファクトチェック・引用箇所**とともに誠実に判定するスキルです。

## 主な特徴

1. **既存の `grilling` スキルを呼び出して深掘り（双方向対応）**
   - 対話進行は再実装せず、インストール済みの `grilling` スキル（論点ツリーとフロンティアのラウンド制質問 `❓ **Q1** ...` / `➡️ ...`）を呼び出して進行します。
   - **AI出題主導モード**（AIから質問ラウンドを出題）と**ユーザー起点・逆質問モード**（ユーザーの疑問やアナロジー仮説に回答・判定したうえで、次のフロンティア質問を逆質問）の両方に対応します。
2. **指定ノートブック（URL / 名前）内の指定ファイル群をマルチ経路で確認**
   - MCP / CLI、ブラウザ操作（`/browser`）、ローカル同期・エクスポートファイルの順に対象ファイルを確認し、未確認のファイルを推測で断定しません。
3. **別アナロジーの適合度判定 ＋ ファクトチェックと引用箇所の明記**
   - 適合度（`S / A / B / C / D` と `%`）、対応マップ、一致点、ズレと限界、補正案を提示します。
   - **Notebook（指定ファイル）側の根拠・引用箇所**と、**アナロジー・専門領域側の根拠（文献・URL・Web記事）のファクトチェック結果（`Verified` / `Partially Verified` / `Refuted` / `Unverified`）および引用箇所**を必ず明記します。
4. **誠実に回答すること ＆ ミス・不足判明時のGitHub Issue追加確認**
   - ユーザーへの忖度・迎合をせず、未確認事項を隠さず、AI側の誤りや不足が判明した際は率直に認めて訂正します。
   - 忖度、根拠・確認不足、AI側の誤り・不足などのミスが判明した場合は、**改善事項としてGitHub Issueに加えるかを常にユーザーへ確認**します。

## 前提条件

- [`grilling`](https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling) スキルがインストール済みであること（本リポジトリの `scripts/install.sh` が各エージェント環境からの参照リンクもあわせて確認・整備します）。

## インストール・更新

```bash
bash scripts/install.sh
bash scripts/install.sh --verify
```
