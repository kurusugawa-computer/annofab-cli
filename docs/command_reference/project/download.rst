=====================
project download
=====================

Description
=================================
アノテーションzipやタスク全件ファイルなどをダウンロードします。



Examples
=================================

基本的な使い方
--------------------------
``annofabcli project download`` コマンドの位置引数にダウンロード対象を指定してください。

以下のコマンドは、プロジェクト"prj1"のアノテーションzipをダウンロードします。

.. code-block::

    $ annofabcli project download simple_annotation --project_id prj1 --output annotation.zip

位置引数に指定できる値は以下の通りです。

* ``simple_annotation`` : アノテーションzip
* ``full_annotation`` : Fullアノテーションzip（非推奨）
* ``task`` : タスク全件ファイル（すべてのタスク情報が記載されたJSON）
* ``input_data`` : 入力データ全件ファイルJSON（すべての入力データ情報が記載されたJSON）
* ``inspection_comment`` : 検査コメント全件ファイルJSON（すべての検査コメント情報が記載されたJSON）
* ``task_history`` : タスク履歴全件ファイルJSON（すべてのタスク履歴情報が記載されたJSON）
* ``task_history_event`` : タスク履歴イベント全件ファイルJSON（すべてのタスク履歴イベント情報が記載されたJSON。非推奨）


ダウンロード対象のファイルを最新にする
----------------------------------------------------
ダウンロード対象のファイルは基本的に1日1回しか更新されないので、最新の状態でない場合があります。
``--latest`` を指定すると、ダウンロード対象のファイルを最新にしてから、ファイルをダウンロードします。
ただし最新化できる場合は、ダウンロード対象が以下の場合のみです。

* ``simple_annotation``
* ``full_annotation``
* ``task``
* ``input_data``

.. code-block::

    $ annofabcli project download task --project_id prj1 --output task.json --latest


最新化完了の確認頻度や確認回数の上限を指定する場合は、``--wait_options`` を指定してください。
以下のコマンドは、最新化が完了したかを5分ごとに確認し、最大10回問い合わせます（50分間待つ）。

.. code-block::

    $ annofabcli project download simple_annotation --project_id prj1 --output annotation.zip \
    --latest --wait_options '{"interval":300, "max_tries":10}'



.. note::

   ダウンロード対象のファイルの最新化は時間がかかります。
   待ち時間はタスク数や入力データ数、コマンドを実行した時間帯にもよりますが、 ``simple_annotation`` だと長いときには2時間以上待つ場合もあります。
   ``task`` , ``input_data`` は、 ``simple_annotation`` と比較すると待ち時間は短いです。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.download.add_parser
   :prog: annofabcli project download
   :nosubcommands:

See also
=================================
* `annofabcli project update_annotation_zip <../project/update_annotation_zip.html>`_
* `annofabcli job wait <../job/wait.html>`_

