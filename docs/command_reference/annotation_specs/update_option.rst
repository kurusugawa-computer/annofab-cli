==================================================
annotation_specs update_option
==================================================

Description
=================================
動画プロジェクトのアノテーション仕様の ``option`` を更新します。
``--option_json`` には ``option`` の中身をJSONオブジェクトで指定します。
指定したキーだけ更新し、省略したキーやほかのアノテーション仕様は保持します。

現在対応しているキーは ``can_overwrap`` のみです。
``true`` は動画の区間の重なりを許容し、 ``false`` は許容しません。
空のオブジェクト、未知のキー、boolean以外の値はエラーになります。
動画プロジェクト以外を指定した場合もエラーになります。

現在値と指定値が同じ場合は、アノテーション仕様を更新せずスキップします。
更新前には変更内容を表示して確認します。 ``--yes`` を指定すると確認を省略します。
``--comment`` を省略すると、変更コメントを自動生成します。


Examples
=================================

区間の重なりを許容しない場合
----------------------------------------------

.. code-block:: bash

    annofabcli annotation_specs update_option \
      --project_id prj1 \
      --option_json '{"can_overwrap": false}'


JSONファイルから指定する場合
----------------------------------------------

.. code-block:: json
    :caption: option.json

    {
      "can_overwrap": true
    }

.. code-block:: bash

    annofabcli annotation_specs update_option \
      --project_id prj1 \
      --option_json file://option.json \
      --comment '動画の区間の重なりを許容する'


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.update_option.add_parser
    :prog: annofabcli annotation_specs update_option
    :nosubcommands:
    :nodefaultconst:
