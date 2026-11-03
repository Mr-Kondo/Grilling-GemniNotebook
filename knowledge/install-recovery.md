# K001: 配置の退避と復旧

## 対象版・根拠

- v0.3.0の配布処理。原資料は [install.sh](../scripts/install.sh) の `backup_target`・`cleanup` と [隔離テスト](../tests/test_install.py) の `test_later_swap_failure_rolls_back_all_targets`。
- 決定は [三層分離ADR](../adr/2026-11-03-update-knowledge-layers.md) と [PR #5](https://github.com/Mr-Kondo/Grilling-GemniNotebook/pull/5)。
- 所有権の根拠は同スクリプトのfrontmatter検査と同テストの `test_refuses_foreign_skill_on_update_and_uninstall`・`test_body_name_is_not_ownership`。v0.3.1でもこの配布処理は変更しない。

## 適用条件

既存の5配置を更新・撤去する改修を検討するとき。別スキルの所有権やユーザー独自変更を、名前だけから推測して上書きしない。

## 確認した知見

途中で交換に失敗するときは、先に更新した配置も含めて復旧する。交換前の配置はバックアップへ退避し、復旧・検証完了前に捨てない。配布ファイルと一致しない独自変更や余分なファイルがあるバックアップは、必要性を確認して保持する。

## 反例・限界

テストは制御されたコマンド失敗の検証であり、停電、同時実行、ファイルシステム故障時の完全な原子性を保証しない。アンインストールは配置を退避する処理であり、grillingやnlmの削除ではない。

## 採否

v0.3.0で採用。バックアップ失敗を無視して既存配置を消す方式は不採用。将来インストーラーを変更するときは、現行ソースと異常系テストを再確認する。この索引自体の品質向上効果は未検証。
