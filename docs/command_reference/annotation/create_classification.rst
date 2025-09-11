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


担当者の変更
----------------------------------------------------

デフォルトでは、タスクの担当者を自分自身にしないとアノテーションを作成できないタスク（担当者が自分自身でない AND 過去に担当者が割り当てられたことがあるタスク）は、全体アノテーションの作成をスキップします。
``--change_operator_to_me`` を指定すると、担当者を一時的に自分自身に変更して、全体アノテーションを作成することができます。

.. code-block::

    $ annofabcli annotation create_classification --project_id prj1 \
    --task_id task1 --label_name weather --change_operator_to_me


完了状態のタスクへの作成
----------------------------------------------------

デフォルトでは、完了状態のタスクには全体アノテーションを作成しません。
``--include_completed`` を指定すると、完了状態のタスクにも全体アノテーションを作成できます。
ただし、このオプションはプロジェクトのオーナーロールを持つユーザーでのみ実行できます。

.. code-block::

    $ annofabcli annotation create_classification --project_id prj1 \
    --task_id task1 --label_name weather --include_completed


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
    :ref: annofabcli.annotation.create_classification_annotation.add_parser
    :prog: annofabcli annotation create_classification
    :nosubcommands:
    :nodefaultconst:
