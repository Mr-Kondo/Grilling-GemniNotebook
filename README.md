# grilling-gemini-notebook

Gemini Notebook（NotebookLM等）内の指定ファイル（またはファイル群）について、インストール済みの既存 [`grilling`](https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling) スキルを呼び出して双方向に深掘りし、別のアナロジーを用いた回答・仮説の正確性を**対象ファイルの記述**および**外部文献・URL・Web記事のファクトチェック・引用箇所**とともに誠実に判定するスキルです。

## 主な特徴

1. **既存の `grilling` スキルを呼び出して深掘り（双方向対応）**
   - 対話進行は再実装せず、インストール済みの `grilling` スキル（論点ツリーとフロンティアのラウンド制質問 `❓ **Q1** ...` / `➡️ ...`）を呼び出して進行します。
   - **AI出題主導モード**（AIから質問ラウンドを出題）と**ユーザー起点・逆質問モード**（ユーザーの疑問やアナロジー仮説に回答・判定したうえで、次のフロンティア質問を逆質問）の両方に対応します。
2. **プライベートNotebookLM URL / 名前からの自動認証更新・原文取得（`scripts/notebook_client.py` & `gemini-notebook-mcp`）**
   - `notebooklm-mcp-cli`（`nlm` / `gemini-notebook-mcp`）と付属の読み取り専用クライアント `scripts/notebook_client.py` により、プライベートなNotebookLM URL（`https://notebooklm.google.com/notebook/<id>`）やノートブック名から直接ソース一覧・原文（SHA-256ダイジェスト付き）を取得します。
   - セッション期限切れ時は `nlm auth refresh` によるヘッドレス自動更新を行い、未認証時は `nlm login --storage protected`（macOSキーチェーン暗号化保存）による事前認証・再検証フローを提供します。
3. **別アナロジーの適合度判定 ＋ ファクトチェックと引用箇所の明記**
   - 適合度（`S / A / B / C / D` と `%`）、対応マップ、一致点、ズレと限界、補正案を提示します。
   - **Notebook（指定ファイル）側の根拠・引用箇所**と、**アナロジー・専門領域側の根拠（文献・URL・Web記事）のファクトチェック結果（`Verified` / `Partially Verified` / `Refuted` / `Unverified`）および引用箇所**を必ず明記します。
4. **誠実に回答すること ＆ ミス・不足判明時のGitHub Issue追加確認**
   - ユーザーへの忖度・迎合をせず、未確認事項を隠さず、AI側の誤りや不足が判明した際は率直に認めて訂正します。
   - 忖度、根拠・確認不足、AI側の誤り・不足などのミスが判明した場合は、**改善事項としてGitHub Issueに加えるかを常にユーザーへ確認**します。

## 前提条件

- [`grilling`](https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling) スキルがインストール済みであること（本リポジトリの `scripts/install.sh` が各エージェント環境からの参照リンクもあわせて確認・整備します）。
- `notebooklm-mcp-cli`（`uv tool install notebooklm-mcp-cli`）が導入され、`nlm login --storage protected` で認証済みであること。

## インストール・更新・検証

```bash
bash scripts/install.sh
bash scripts/install.sh --update
bash scripts/install.sh --verify
python3 scripts/verify_skill.py --check-live-auth
```

`--install`（省略時も同じ）と `--update` は同じ配布処理です。既存配置を退避してから交換し、途中失敗時は今回変更した全配置を復旧します。退避先は `~/.local/state/grilling-gemini-notebook/backups/` に表示されます。独自変更のあるバックアップは保持し、不要と確認したものだけ削除してください。

アンインストールは `bash scripts/install.sh --uninstall`。このスキルの配置だけを退避して撤去し、前提のgrillingやnlmは残します。

## 更新管理（WikiSkillの考え方を限定採用）

目的は、実行の記録と判断の根拠を残し、検証済みの手順だけをスキルに反映することです。`feedback/` に非公開の実行・検証結果、`knowledge/` に原資料への少数索引、`SKILL.md` と実行用参照に配布する手順を分けます。索引は通常利用では読み込みません。自動更新の有効性は未検証です。

更新作業ではソースリポジトリの `references/update-workflow.md` を使います。詳しい決定は[ADR](https://github.com/Mr-Kondo/Grilling-GemniNotebook/blob/main/adr/2026-11-03-update-knowledge-layers.md)を参照してください。索引・ADR・検証記録はインストールされません。

必要な場合はソースの[知識索引](https://github.com/Mr-Kondo/Grilling-GemniNotebook/blob/main/knowledge/index.md)から原資料へ進めます。現時点では「配置の復旧」「検証から主張できる範囲」の2件に限定します。索引だけで判断せず、現在のコード・対象版・反例を確認してください。

索引あり／なしの[限定比較](https://github.com/Mr-Kondo/Grilling-GemniNotebook/blob/main/adr/2026-11-03-index-comparison.md)では、原資料全文を与えた4課題各1回で、意味基準と原資料引用は両条件4/4でした。改善の証拠は得られず、任意索引のまま維持します。実検索・実際の更新提案・三環境の回答品質への効果は未確認です。自動更新には接続しません。ソース専用の `scripts/evaluate_knowledge.py` に再現手順を用意し、生データは非公開のfeedbackだけに保存します。

開発用の検証は `python3 -m unittest discover -s tests -v` と `python3 scripts/verify_skill.py`。インストーラーのテストは隔離したHOMEで実行し、実際のユーザー配置を変更しません。

## ライセンス（License）

本リポジトリは [MIT License](LICENSE) の下で公開されています。
- 連携する [`grilling`](https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling) スキル（`mattpocock/skills`）も **MIT License**（Copyright (c) 2026 Matt Pocock）であり、ライセンス上の互換性が完全に保たれています。
- 認証・取得で利用する [`gemini-notebook-mcp-cli` (`notebooklm-mcp-cli`)](https://github.com/jacob-bd/gemini-notebook-mcp-cli) も **MIT License**（Copyright (c) 2025 Jacob Ben David）です。

