=================================================================
annotation list_attribute_restriction_violation
=================================================================

アノテーション仕様の属性制約に違反する、保存済みアノテーションを出力します。
「アノテーション × 違反した制約」で1件を出力するため、同じアノテーションが複数行に現れることがあります。
``task_id`` と ``input_data_id`` で、違反を含む入力データを特定できます。

Examples
=================================

.. code-block:: bash

    $ annofabcli annotation list_attribute_restriction_violation --project_id prj1 \
        --task_id file://task.txt --output violations.csv

.. csv-table:: violations.csv
    :file: list_attribute_restriction_violation/violations.csv
    :header-rows: 1

JSON形式でも出力できます。

.. code-block:: bash

    $ annofabcli annotation list_attribute_restriction_violation --project_id prj1 \
        --task_id task1 --format pretty_json --output violations.json

.. literalinclude:: list_attribute_restriction_violation/violations.json
    :language: json

プロジェクトの全タスクを対象にする場合は、``--task_id`` の代わりに ``--all_tasks`` を指定してください。

出力内容
=================================

* ``label_name_en``、``attribute_name_en``: ラベル名と属性名（英語）。
* ``attribute_value``: 保存されている属性値。未設定の場合はJSONではnull、CSVでは空欄です。
* ``restriction_index``: 取得した仕様の ``restrictions`` 内の0始まりの位置。
* ``restriction_type``: 制約の種類。属性間制約の場合は ``Imply`` です。
* ``restriction_text``: 制約を読みやすい文字列にしたもの。
* ``restriction``: 元の制約。CSVではJSON文字列です。
* ``annotation_editor_url``: 対象アノテーションを開くURL。

CSVは違反0件でもヘッダを出力します。JSONは空配列を出力します。

判定仕様
=================================

実行開始時に取得した現在のアノテーション仕様を使用します。
``Equals``、``NotEquals``、``Matches``、``NotMatches``、``Imply``、``HasLabel`` を検証します。
``Imply`` は前提が成立した場合のみ後続条件を検証します。
``HasLabel`` のリンク先は、同一タスク・同一入力データ内のアノテーションから解決します。

読取専用属性も検証対象です。結論が ``CanInput`` の制約は検証対象外です。
欠落値とnullは空値として扱い、フラグ属性ではfalseとして扱います。デフォルト値は補完しません。
正規表現はPythonの ``re.fullmatch`` を使用します。
Annofab提出時の検証を完全に再現するものではありません。

取得失敗、存在しないリンク先、未対応条件などで検証できなかった入力データは、違反なしとは扱いません。
警告を出して残りの処理を続行し、成功した入力データの違反一覧を出力した後、終了コード1で終了します。
タスクの取得失敗も終了コード1になります。
検証がすべて成功した場合は、違反の有無にかかわらず終了コード0です。

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.list_attribute_restriction_violation.create_parser
    :prog: annofabcli annotation list_attribute_restriction_violation
    :nosubcommands:
    :nodefaultconst:
