=================================
filesystem filter_annotation
=================================

Description
=================================
アノテーションzipから、特定のファイルを絞り込んでzip展開します。


Examples
=================================


基本的な使い方
--------------------------

``--annotation`` には、Annofabからダウンロードしたアノテーションzipか、アノテーションzipを展開したディレクトリを指定してください。
アノテーションzipは、`annofabcli annotation download <../annotation/download.html>`_ コマンドでダウンロードできます。


``--task_query`` を指定して、タスクのフェーズやステータスで絞り込むことができます。以下のコマンドは、完了状態のタスクのみzip展開します。

.. code-block::

    $ annofabcli filesystem filter_annotation  --annotation annotation.zip \
    --task_query '{"status":"complete"}' \
    --output_dir out/


特定のタスクのみ絞り込む場合は ``--task_id`` 、特定のタスクのみ除外する場合は ``--exclude_task_id`` を指定してください。以下のコマンドは、task1, task2以外の完了状態のタスクをzip展開します。

.. code-block::

    $ annofabcli filesystem filter_annotation  --annotation annotation.zip \
    --task_query '{"status":"complete"}' \
    --exclude_task_id task1 task2
    --output_dir out/

task_id以外にも ``--input_data_id`` , ``--input_data_name`` で絞り込むことができます。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.filesystem.filter_annotation.add_parser
   :prog: annofabcli filesystem filter_annotation
   :nosubcommands:
   :nodefaultconst:

