==========================================
annotation dump
==========================================

Description
=================================
`annofabcli annotation restore <../annotation/restore.html>`_ コマンドに読み込ませることができるアノテーション情報を出力します。
アノテーションのバックアップ目的で利用することを想定しています。


Examples
=================================


基本的な使い方
--------------------------


``--task_id`` に出力対象のタスクのtask_idを指定して、 ``--output_dir`` に出力先ディレクトリのパスを指定してください。

.. code-block::

    $ annofabcli annotation dump --project_id prj1 --task_id file://task.txt --output_dir backup-dir/



出力先ディレクトリの構成は以下の通りです。
``{input_data_id}.json`` のフォーマットは、https://annofab.com/docs/api/#operation/getEditorAnnotation APIのレスポンス ``AnnotationV1`` と同じです。

.. code-block::

    ルートディレクトリ/
    ├── {task_id}/
    │   ├── {input_data_id}.json
    │   ├── {input_data_id}/
    │          ├── {annotation_id}............ 塗りつぶしPNG画像



アノテーション情報のリストアは、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。

.. code-block::

    $ annofabcli annotation restore --project_id prj1 --annotation backup-dir/


.. warning::

    ``annotation dump`` コマンドの出力結果は、``annotation restore`` コマンドに読み込ませることを目的として作られています。

    ``annotation dump`` コマンドの出力結果であるJSONの構造は、現在V1形式ですが今後V2形式へ移行する予定です。
    V1形式のJSON構造に依存したプログラムは、V2形式へ移行した際に動くなる可能性があります。
    ``annotation dump`` コマンドの出力結果であるJSONの構造に直接依存したプログラムを作成する場合は、ご注意ください。






Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.dump_annotation.add_parser
    :prog: annofabcli annotation dump
    :nosubcommands:
    :nodefaultconst:


See also
=================================
*  `annofabcli annotation restore <../annotation/restore.html>`_

