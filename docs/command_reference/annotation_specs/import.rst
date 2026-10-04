====================================================================================
annotation_specs import
====================================================================================

Description
=================================
アノテーション仕様の情報をJSON形式でインポートします。
``annotation_specs export`` コマンドで出力したJSONを利用できます。

既存アノテーションに影響する変更の場合は、デフォルトではインポートできません。
具体的な変更内容と許可する方法は、 :ref:`annotation_specs_import_allow_affecting_annotations` を参照してください。


Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli annotation_specs import --project_id prj1 --annotation_specs_json_file annotation_specs.json


``annotation_specs export`` と組み合わせる場合
------------------------------------------------------------


.. code-block::

    $ annofabcli annotation_specs export --project_id src_prj --output annotation_specs.json --format pretty_json
    $ annofabcli annotation_specs import --project_id dest_prj --annotation_specs_json_file annotation_specs.json


.. _annotation_specs_import_allow_affecting_annotations:

既存アノテーションに影響する変更を許可する場合
------------------------------------------------------------

インポート先のプロジェクトにあるアノテーション仕様と、インポートするJSONを比較し、以下のいずれかに該当する場合はインポートを中止します。

.. list-table:: インポートを中止する変更と具体例
   :header-rows: 1
   :widths: 45 55

   * - 変更内容・中止する条件
     - 具体例
   * - 既存アノテーションで使われているラベルを削除する
     - 「車」ラベルのアノテーションがある状態で、JSONから「車」ラベルを削除する。
   * - 既存アノテーションで使われているラベルのアノテーションの種類を変更する
     - 「車」ラベルのアノテーションがある状態で、「車」の種類を矩形からポリゴンに変更する。
   * - 既存アノテーションで使われているラベルに紐づく属性定義を削除する
     - 「車」ラベルに「遮蔽」属性が紐づいていて、「車」のアノテーションがある状態で、「遮蔽」の属性定義をJSONから削除する。
   * - 既存アノテーションで使われているラベルに紐づく属性の種類を変更する
     - 「車」ラベルに「遮蔽」属性が紐づいていて、「車」のアノテーションがある状態で、「遮蔽」の種類をラジオボタンからドロップダウンに変更する。
   * - 既存アノテーションで使われているラベルから属性の紐づけを削除する
     - 「車」ラベルのアノテーションがある状態で、「遮蔽」の属性定義は残したまま、「車」から「遮蔽」属性の紐づけを削除する。
   * - 既存アノテーションの属性値として使われている選択肢を削除する
     - 「遮蔽」属性で「あり」を選択しているアノテーションがある状態で、「あり」の選択肢をJSONから削除する。

属性定義の削除・属性の種類変更は、その属性が紐づくラベルのいずれかが既存アノテーションで使われていれば中止します。
ラベルからの属性の紐づけの削除は、そのラベルが既存アノテーションで使われていれば中止します。
これらは、個々のアノテーションに属性値が入力されているかどうかにかかわらず中止します。
一方、選択肢の削除は、その選択肢を属性値として使っているアノテーションがある場合に中止します。

ラベル・属性・選択肢は名前ではなくIDで比較します。
そのため、名前が同じでもIDが異なるJSONをインポートすると、元の定義の削除と新しい定義の追加として扱われ、上記の条件に該当する場合は中止します。

ラベルの色や名前の変更、ラベル・属性・選択肢の追加、上記の利用条件に該当しない削除・種類変更では、このオプションは不要です。

上記の変更を既存アノテーションへの影響を理解した上で適用する場合は、 ``--allow_affecting_annotations`` を指定してください。
このオプションを指定すると、該当する変更内容を警告ログに出力した上でインポートします。

.. code-block::

    $ annofabcli annotation_specs import --project_id prj1 --annotation_specs_json_file annotation_specs.json --allow_affecting_annotations


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.import_annotation_specs.add_parser
   :prog: annofabcli annotation_specs import
   :nosubcommands:
   :nodefaultconst:
