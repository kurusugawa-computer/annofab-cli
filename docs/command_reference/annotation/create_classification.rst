==========================================
annotation create_classification
==========================================

Description
=================================
指定したラベルの全体アノテーション（Classification）を作成します。

既に全体アノテーションが存在する場合は、作成をスキップします。
作業中状態のタスクには作成できません。


利用用途
----------------------------------------------------

`annotation change_attributes <../annotation/change_attributes.html>`_ コマンドで全体アノテーションの属性値を変更するには、事前に全体アノテーションが存在している必要があります。
しかし、タスク作成直後は全体アノテーションが存在しません。アノテーションエディタ画面でアノテーションを保存して、初めて全体アノテーションが作成されます。
タスク作成直後に、全体アノテーションの属性値を `annotation change_attributes <../annotation/change_attributes.html>`_ コマンドで変更する際などに、有用なコマンドです。
すべての対象入力データに同じ初期値を設定する場合は、 ``--attributes`` を指定すると、作成と同時に属性値を設定できます。


Examples
=================================

基本的な使い方
----------------------------------------------------

``--task_id`` に全体アノテーションを作成するタスクのIDを指定し、 ``--label_name`` に作成する全体アノテーションのラベル名（英語）を指定してください。

.. code-block::

    $ annofabcli annotation create_classification --project_id prj1 \
    --task_id task1 task2 --label_name weather



複数のラベル名を指定することもできます。

.. code-block::

    $ annofabcli annotation create_classification --project_id prj1 \
    --task_id task1 --label_name weather season time_of_day


作成時に属性値を指定する
----------------------------------------------------

``--attributes`` に、新規作成する全体アノテーションの属性値をJSON形式で指定します。
属性名と選択肢名には英語名を使用します。指定形式は :doc:`change_attributes` の ``--attributes`` と同じです。

.. code-block:: console

    $ annofabcli annotation create_classification --project_id prj1 \
    --task_id task1 task2 --label_name weather --attributes '{"sunny": true}'

``file://`` を先頭に付けると、JSON形式のファイルから属性値を読み込めます。

.. code-block:: console

    $ annofabcli annotation create_classification --project_id prj1 \
    --task_id task1 --label_name weather --attributes file://attributes.json

``--attributes`` を指定する場合は、 ``--label_name`` にラベルを1個だけ指定してください。
新規作成するすべての対象入力データに同じ属性値を設定します。省略した属性値は設定しません。
既存の全体アノテーションは、属性値が異なっていてもスキップします。
既存アノテーションの属性値を変更するには、 :doc:`change_attributes` または :doc:`change_attributes_per_annotation` を使用してください。
入力データごとに異なる属性値で新規作成するには、 :doc:`create` を使用してください。


担当者の変更
----------------------------------------------------

オーナーロールでは、タスクの担当者や状態を変更せずに全体アノテーションを作成できます。
チェッカーロールで自身が担当者ではないタスクに作成する場合は、担当者を一時的に自分自身に変更して全体アノテーションを作成します。

.. code-block::

    $ annofabcli annotation create_classification --project_id prj1 \
    --task_id task1 --label_name weather


完了状態のタスクへの作成
----------------------------------------------------

デフォルトでは、完了状態のタスクには全体アノテーションを作成しません。
``--include_complete_task`` を指定すると、完了状態のタスクにも全体アノテーションを作成できます。
ただし、このオプションはプロジェクトのオーナーロールを持つユーザーでのみ実行できます。

.. code-block::

    $ annofabcli annotation create_classification --project_id prj1 \
    --task_id task1 --label_name weather --include_complete_task


休憩中状態のタスクへの作成
----------------------------------------------------

デフォルトでは、休憩中状態のタスクには全体アノテーションを作成しません。
``--include_break_task`` を指定すると、休憩中状態のタスクにも全体アノテーションを作成できます。

保留中状態のタスクへの作成
----------------------------------------------------

デフォルトでは、保留中状態のタスクには全体アノテーションを作成しません。
``--include_on_hold_task`` を指定すると、保留中状態のタスクにも全体アノテーションを作成できます。チェッカーロールで作成した場合、作成後は未着手状態になります。


並列処理
----------------------------------------------------

``--parallelism`` を指定すると、複数のタスクを並列で処理できます。
並列処理を使用する場合は、 ``--yes`` も指定してください。

.. code-block::

    $ annofabcli annotation create_classification --project_id prj1 \
    --task_id file://task_id.txt --label_name weather \
    --parallelism 4 --yes


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.create_classification_annotation.create_parser
    :prog: annofabcli annotation create_classification
    :nosubcommands:
    :nodefaultconst:
