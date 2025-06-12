====================================================================================
annotation change_attributes_per_annotation
====================================================================================

Description
=================================
各アノテーションの属性値を変更します。

作業中状態のタスクに含まれるアノテーションは変更できません。


Examples
=================================

変更する属性値をJSON形式で指定する
---------------------------------------


引数 ``--json`` に、変更対象のアノテーションの情報（ ``task_id`` , ``input_data_id`` , ``annotation_id`` ）と変更後の属性値（ ``attributes`` ）をJSON形式で指定します。

``attributes`` のフォーマットは、 `Command line options <../../user_guide/command_line_options.html#annotation-query-aq>`_ の ``attributes`` キーの値と同じフォーマットです。
変更したい属性名と値を指定します。

.. code-block:: json
    :caption: annotations.json
    
    [
        {
            "task_id": "t1",
            "input_data_id": "i1",
            "annotation_id": "a1", 
            "attributes": {"occluded": true}
        }
    ]
    
    
.. code-block::

    $ annofabcli annotation change_attributes_per_annotation --project_id p1 \
     --json file://annotations.json \
     --backup backup_dir/ \


変更する属性値をCSVで指定する
---------------------------------------
引数 ``--csv`` に、変更対象のアノテーションの情報と変更後の属性値が記載されたCSVファイルのパスを指定します。

CSVのフォーマットは以下の通りです。

* ヘッダ行あり
* カンマ区切り

.. csv-table::
   :header: 列名,必須,備考

    task_id,Yes,
    input_data_id,Yes,
    annotation_id,Yes,
    attributes,Yes,変更したい属性名と値のオブジェクト（JSON形式）

以下はCSVファイルのサンプルです。

.. code-block::
    :caption: annotations.csv

    task_id,input_data_id,annotation_id,attributes
    t1,i1,a1,"{""comment"":""bar"",""number"":3}"


.. code-block::

    $ annofabcli annotation change_attributes_per_annotation --project_id p1 \
     --csv annotations.csv \
     --backup backup_dir/ \


その他のオプション
---------------------------------------

``--backup`` にディレクトリを指定すると、変更対象のフレームに含まれるアノテーション情報を、指定したディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。


.. note::

    間違えてアノテーションを変更したときに復元できるようにするため、``--backup`` を指定することを推奨します。


デフォルトでは完了状態のタスクに含まれるアノテーションは変更できません。完了状態のタスクに含まれるアノテーションも変更する場合は、 ``--force`` を指定してください。
ただし、オーナーロールのユーザーで実行する必要があります。



Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.change_annotation_attributes_per_annotation.add_parser
    :prog: annofabcli annotation change_attributes_per_annotation
    :nosubcommands:
    :nodefaultconst:


