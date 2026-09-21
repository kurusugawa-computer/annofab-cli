# PR #1753 コードレビュー

対象: GitHub 上の PR head `34096632a89ba126b6595fddd3d894da609952ee`

ローカル HEAD `1946b317` には未 push の追加コミットがあるため、レビュー対象には含めていません。

## 判定

**修正が必要です。**

前回指摘した、アノテーション・コメント処理失敗時の担当者復元、ワーカーの未割当タスク、deprecated コマンドのロール制約、主要ドキュメントの説明は修正されています。一方、タスク状態変更コマンドと `update_onhold` にロール別要件の実装漏れが残り、簡易コメントの失敗経路には新しい実行時エラーがあります。また、同じコピー先を複数回指定する有効な入力では、古いタスク情報の再利用により2件目以降が失敗します。

## 指摘事項

### [P1] タスク状態変更後に元の担当者を復元してください

対象: `annofabcli/task/change_status_to_break.py:57-75`, `annofabcli/task/change_status_to_on_hold.py:88-158`

PR本文では、オーナー・チェッカーロールが他者担当タスクを処理する際は、必要に応じて担当者を一時変更し、処理後に元へ戻すことを要件としています。しかし両コマンドは、ワーカーだけを事前スキップした後、他者担当タスクをオーナー・チェッカーで処理する経路に復元処理がありません。固定依存の `annofabapi` では `change_task_status_to_working` / `break` / `on_hold` が `account_id=self.api.account_id` を送信し、`change_status_to_on_hold` はさらに明示的に `change_task_operator` を呼ぶため、成功後は実行者が担当者として残ります。途中で失敗した場合も同様です。

元の `account_id` を保存し、成功時・失敗時とも復元してください。ただし既存の `change_task_operator()` は状態を未着手へ変更するため、そのまま最後に呼ぶと目的の `break` / `on_hold` を失います。最終ステータスと元担当者を同時に指定できるタスク操作を共通化し、他者担当・未割当・途中失敗のテストを追加してください。

### [P2] 同じコピー先を複数回処理するときは最新のタスク情報を使ってください

対象: `annofabcli/annotation/copy_annotation.py:302-315`, `annofabcli/annotation/copy_annotation.py:342-360`

`copy_annotations()` は最大100件ごとにタスクを一括取得し、その同じ `task_dict` をバッチ内の全コピーへ渡します。チェッカーが他者担当のコピー先を処理すると、1件目で担当者を自分へ変更して元へ戻すため、タスクの `updated_datetime` は更新されます。しかし、たとえば `--input src1:dest src2:dest` の2件目も一括取得時の古い `updated_datetime` を `change_task_operator()` に渡すため、楽観的排他で失敗し、2件目以降をコピーできません。並列実行では同じコピー先に対する処理同士が同時に競合します。オプション削除後はこの担当者変更がチェッカーの通常経路になるため、要件上有効な複数入力データのコピーが完了しません。

コピー対象ごとにコピー先タスクを再取得するか、担当者復元後の戻り値で `task_dict` を更新してください。また、並列時は同じコピー先をコピー先単位で直列化し、同一タスク内の複数入力データを連続コピーするテストを追加してください。

### [P2] `update_onhold` にもワーカーロールの制約を適用してください

対象: `annofabcli/comment/put_comment.py:153-164`, `annofabcli/comment/update_onhold_comment.py:70`

追加された `can_change_other_operator` の既定値が `True` である一方、`comment update_onhold` はロールを取得せず、この引数も渡していません。ワーカーが他者担当タスクを入力すると `_can_change_other_operator()` を通過し、権限のない `change_task_operator()` を呼んでAPIエラーになります。これは、PR本文の「ワーカーは担当者を変更しない」「対象外タスクはAPIエラーにせず info ログでスキップする」というロール別動作から外れます。

`update_onhold` でもロールを反映してください。また、同じ指定漏れを再発させないため、権限の既定値 `True` を廃止し、`PutCommentMain` が `ProjectMemberRole` または必須の権限型から処理可否を導出する構造にしてください。

### [P2] 作業中遷移の失敗時に未代入変数を参照しないでください

対象: `annofabcli/comment/put_comment_simply.py:249-257`

`change_to_working_status()` がHTTPエラーなどを送出すると、`input_data_id` の代入前に `except` へ進みます。そこでログの f-string が `input_data_id` を参照するため、元の例外が `UnboundLocalError` に置き換わり、本来の失敗理由を記録せず、メソッドの `False` 戻り値契約も守れません。この経路は手元でも `UnboundLocalError: cannot access local variable 'input_data_id'` として再現しました。

`input_data_id` を状態遷移前に取得・検証するか、未取得でも安全にログ出力できるよう初期化してください。`PutCommentSimplyMain` でも作業中遷移失敗時の戻り値と担当者復元を検証するテストを追加してください。

### [P2] 保留コメント後の実際の最終状態をドキュメントに反映してください

対象: `docs/command_reference/comment/create_onhold.rst:58-60`, `annofabcli/comment/create_onhold_comment.py:138-141`, `annofabcli/comment/create_onhold_comment_simply.py:94-97`

文書とCLIヘルプは、保留中タスクを処理した後は一律に休憩中になると説明しています。しかしオーナー・チェッカーが他者担当または未割当タスクを処理すると、`_restore_task_after_comment()` は一度休憩中にした後で元担当者へ戻します。`annofabapi.change_task_operator()` はその操作で状態も未着手へ変更するため、実際の最終状態は未着手です。PR本文にもこの状態変化がリスクとして明記されています。

説明を、担当者変更がなければ休憩中、一時変更した担当者を復元する場合は未着手になる、と修正してください。あわせて、オーナー・チェッカーでは担当者を自動的に一時変更して元へ戻すことも明記してください。`create_onhold_simply` はこの共通説明を参照できます。

### [P2] 一時的な担当者変更と復元を共通インターフェースにしてください

対象: `annofabcli/annotation/copy_annotation.py:302-333`, `annofabcli/annotation/import_annotation.py:669-705`, `annofabcli/annotation/merge_segmentation.py:229-270`, `annofabcli/annotation/remove_segmentation_overlap.py:215-256`, `annofabcli/annotation/restore_annotation.py:214-245`

「元担当者を保存する → 自分へ変更する → 本処理を実行する → `finally` で元へ戻す」という同一の業務上の不変条件が、今回の差分だけでも5コマンドに個別実装されています。既存の3コマンドにも同種処理があり、変更フラグを立てる時点や `updated_datetime` の扱いが揃っていません。今回の前回レビューで複数箇所に復元漏れが生じたこと自体が、低水準APIを各コマンドへ公開する構造の具体的な保守上の不利益です。

一時的な担当者変更をコンテキストマネージャー等へ切り出し、元の `account_id`、変更後タスク、例外時の復元を一箇所で管理してください。各コマンドはそのスコープ内で本処理だけを実行する形にし、共通処理に成功時・失敗時の復元テストを持たせてください。

### [P3] 同一になったインポートテストを統合してください

対象: `tests/annotation/test_import_annotation.py:173-188`, `tests/annotation/test_import_annotation.py:241-256`

変更前はオプションなしのスキップとオプションありの処理を別々に検証していましたが、オプション削除後の2テストは、名前の「一時変更」と「一時的に変更」という差しかなく、入力・実行・アサーションが完全に同一です。重複したままでは仕様変更時の更新箇所を増やすだけです。

一方を削除するか、片方を作業失敗時にも元担当者を復元するケースへ置き換えてください。

## 検証結果

- GitHub 上の PR head を `/tmp` に展開して変更関連テストを実行: 89件成功
- GitHub 上の PR head に対する `ruff format --check`、`ruff check`、`mypy`: 成功
- 簡易コメントの作業中遷移失敗: `UnboundLocalError` を再現
