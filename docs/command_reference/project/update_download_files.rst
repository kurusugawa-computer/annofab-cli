=================================
project update_download_files
=================================

Description
=================================
ダウンロード用ファイルをAnnofab上で並列に更新し、すべての更新完了を待ちます。
ローカルへのダウンロードは行いません。

``--target`` に更新対象を1個以上指定してください。

* ``task``: タスク全件JSON
* ``annotation``: アノテーションZIP
* ``input_data``: 入力データ全件JSON

同じ対象を重複指定した場合は、1回だけ更新します。
同種の更新ジョブが既に実行中の場合は、そのジョブの完了を待ちます。
待機間隔と上限は :doc:`../job/wait` と同じです。

一部の更新が失敗しても、ほかの対象の処理を継続します。
すべての更新が成功した場合のみ終了コード0とし、失敗またはタイムアウトがある場合は非0で終了します。
進捗と成功・失敗の件数はログに出力します。標準出力への結果出力は行いません。

Examples
=================================

タスク全件JSONとアノテーションZIPを並列に更新する
------------------------------------------------------------

.. code-block:: bash

    $ annofabcli project update_download_files -p PROJECT_ID --target task annotation

更新に成功した後、後続のコマンドでは ``--latest`` を付けずに更新済みのファイルを取得できます。
以下の例では、更新に成功した場合のみ次のコマンドを実行します。

.. code-block:: bash

    annofabcli project update_download_files -p PROJECT_ID --target task annotation && \
      annofabcli task list_all -p PROJECT_ID --output tasks.csv && \
      annofabcli annotation_zip list_bounding_box_annotation -p PROJECT_ID --output annotations.csv

入力データ全件JSONも更新する場合は、``--target task annotation input_data`` と指定してください。
1種類だけ更新する場合は、たとえば ``--target task`` と指定できます。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.update_download_files.add_parser
   :prog: annofabcli project update_download_files
   :nosubcommands:
   :nodefaultconst:
