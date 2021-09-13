==========================================
annotation dump
==========================================

Description
=================================
指定したタスク配下のアノテーション情報をディレクトリに保存します。アノテーションのバックアップなどに利用できます。



Examples
=================================


基本的な使い方
--------------------------


``--task_id`` に出力対象のタスクのtask_idを指定して、 ``--output_dir`` に出力先ディレクトリのパスを指定してください。

.. code-block::

    $ annofabcli annotation dump --project_id prj1 --task_id file://task.txt --output_dir backup-dir/



出力先ディレクトリの構成は以下の通りです。
``{input_data_id}.json`` のフォーマットは、https://annofab.com/docs/api/#operation/getEditorAnnotation APIのレスポンスと同じです。

.. code-block::

    ルートディレクトリ/
    ├── {task_id}/
    │   ├── {input_data_id}.json
    │   ├── {input_data_id}/
    │          ├── {annotation_id}............ 塗りつぶしPNG画像



アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.dump_annotation.add_parser
    :prog: annofabcli annotation dump
    :nosubcommands:


See also
=================================
*  `annofabcli annotation restore <../annotation/restore.html>`_

