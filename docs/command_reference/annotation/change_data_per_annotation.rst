====================================================================================
annotation change_data_per_annotation
====================================================================================

Description
=================================
各アノテーションの座標情報・形状情報を変更します。

属性値、ラベル、プロパティは変更しません。
作業中状態のタスクに含まれるアノテーションは変更できません。
保留中状態のタスクに含まれるアノテーションは、デフォルトでは変更できません。

外部ファイルが必要な塗りつぶしアノテーションなどは、このコマンドではサポートしていません。


Examples
=================================

変更するdataをJSON形式で指定する
---------------------------------------

引数 ``--json`` に、変更対象のアノテーションの情報（ ``task_id`` , ``input_data_id`` , ``annotation_id`` ）と変更後の ``data`` をJSON形式で指定します。

既存アノテーションと異なる ``data._type`` には変更できません。

.. code-block:: json
    :caption: annotations.json

    [
        {
            "task_id": "t1",
            "input_data_id": "i1",
            "annotation_id": "a1",
            "data": {
                "_type": "Range",
                "begin": 1000,
                "end": 5000
            }
        }
    ]


.. code-block::

    $ annofabcli annotation change_data_per_annotation --project_id p1 \
     --json file://annotations.json \
     --backup backup_dir/


変更するdataをCSVで指定する
---------------------------------------
引数 ``--csv`` に、変更対象のアノテーションの情報と変更後の ``data`` が記載されたCSVファイルのパスを指定します。

CSVのフォーマットは以下の通りです。

* ヘッダ行あり
* カンマ区切り

.. csv-table::
   :header: 列名,必須,備考

    task_id,Yes,
    input_data_id,Yes,
    annotation_id,Yes,
    data,Yes,変更後のアノテーションdata（JSON形式）

以下はCSVファイルのサンプルです。

.. code-block::
    :caption: annotations.csv

    task_id,input_data_id,annotation_id,data
    t1,i1,a1,"{""_type"":""Range"",""begin"":1000,""end"":5000}"


.. code-block::

    $ annofabcli annotation change_data_per_annotation --project_id p1 \
     --csv annotations.csv \
     --backup backup_dir/


サポート対象外のアノテーション
---------------------------------------

外部ファイルが必要なアノテーションは、このコマンドでは変更できません。
たとえば、以下の ``data._type`` はサポート対象外です。

* ``Segmentation``
* ``SegmentationV2``
* ``Outer``

これらのアノテーションは別コマンドで対応する想定です。


その他のオプション
---------------------------------------

``--backup`` にディレクトリを指定すると、変更対象のフレームに含まれるアノテーション情報を、指定したディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。


.. note::

    間違えてアノテーションを変更したときに復元できるようにするため、``--backup`` を指定することを推奨します。


デフォルトでは完了状態のタスクに含まれるアノテーションは変更できません。完了状態のタスクに含まれるアノテーションも変更する場合は、 ``--include_complete_task`` を指定してください。
ただし、オーナーロールのユーザーで実行する必要があります。

デフォルトでは保留中状態のタスクに含まれるアノテーションは変更できません。保留中状態のタスクに含まれるアノテーションも変更する場合は、 ``--include_on_hold_task`` を指定してください。



Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.change_annotation_data_per_annotation.add_parser
    :prog: annofabcli annotation change_data_per_annotation
    :nosubcommands:
    :nodefaultconst:
