==========================================
annotation import
==========================================

Description
=================================
アノテーションをプロジェクトにインポートします。
アノテーシンzipまたはzipを展開したディレクトリをインポートできます。
作業中のタスクに対してはインポートできません。



Examples
=================================


インポート対象のアノテーションのフォーマット
----------------------------------------------------

インポート対象のアノテーションのフォーマットは、アノテーションzipまたはzipを展開したディレクトリと同じディレクトリ構成です。


.. code-block::
    :caption: annotation.zip

    ルートディレクトリ/
    ├── {task_id}/
    │   ├── {input_data_id}.json
    │   ├── {input_data_id}/
    │          ├── {annotation_id}............ 塗りつぶしPNG画像


``{input_data_id}.json`` のサンプルは以下の通りです。詳細は https://annofab.readme.io/docs/annotation-format を参照してください。

.. note::

    ``BoundingBox`` 、 ``Points`` 、 ``SinglePoint`` の2D座標値（ ``x`` , ``y`` ）に小数が指定された場合は、 ``round`` で整数に丸めてインポートします。

.. note::

    `annotation_specs list_annotation_import_info <../annotation_specs/list_annotation_import_info.html>`_ コマンドの出力結果をCoding Agentに渡すと、インポート先プロジェクトで利用できるラベル名、属性名、選択肢名を踏まえて、アノテーションを効率よく変換するスクリプトを書きやすくなります。

.. code-block::
    :caption: {input_data_id}.json

    {
        "details": [
            {
                "label": "car",
                "data": {
                    "left_top": {
                        "x": 878,
                        "y": 566
                    },
                    "right_bottom": {
                        "x": 1065,
                        "y": 701
                    },
                    "_type": "BoundingBox"
                },
                "attributes": {}
            },
            {
                "label": "road",
                "data": {
                    "data_uri": "b803193f-827f-4755-8228-e2c67d0786d9",
                    "_type": "SegmentationV2"
                },
                "attributes": {}
            },
            {
                "label": "weather",
                "data": {
                    "_type": "Classification"
                },
                "attributes": {
                    "sunny": true
                }
            }
        ]
    }




以下のように ``annotation_id`` が指定されている場合、``annotation_id`` もインポートされます。


.. code-block::
    :caption: {input_data_id}.json

    {
        "details": [
            {
                "label": "car",
                "annotation_id": "12345678-abcd-1234-abcd-1234abcd5678",
                "data": {
                    "left_top": {
                        "x": 878,
                        "y": 566
                    },
                    "right_bottom": {
                        "x": 1065,
                        "y": 701
                    },
                    "_type": "BoundingBox"
                },
                "attributes": {}
            },
            ...
        ]
    }


``attributes``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--merge`` を指定し、既存アノテーションと ``annotation_id`` が一致した場合、 ``attributes`` は部分更新されます。JSONに指定した属性だけを更新し、指定していない既存属性は維持します。

属性値に ``null`` を指定すると、その属性を削除します。 ``attributes`` を省略するか空のオブジェクトを指定した場合、既存属性は変更しません。

アノテーションのラベルを変更した場合は、変更後のラベルに紐づかない既存属性を削除します。


``editor_props``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


``editor_props`` が指定されている場合、 ``putAnnotation`` APIの ``editor_props`` としてインポートされます。
``editor_props`` はアノテーションエディタ用のプロパティです。たとえば ``can_delete`` に ``false`` を指定すると、対応しているエディタ上ではアノテーションを削除できなくなります。


``editor_props`` に指定できるキーは、 `putAnnotation API <https://annofab.com/docs/api/#operation/putAnnotation>`_ の ``AnnotationPropsForEditor`` を参照してください。

.. code-block::
    :caption: {input_data_id}.json

    {
        "details": [
            {
                "label": "car",
                "annotation_id": "12345678-abcd-1234-abcd-1234abcd5678",
                "data": {
                    "left_top": {
                        "x": 878,
                        "y": 566
                    },
                    "right_bottom": {
                        "x": 1065,
                        "y": 701
                    },
                    "_type": "BoundingBox"
                },
                "attributes": {},
                "editor_props": {
                    "can_delete": false,
                    "can_edit_data": false,
                    "can_edit_additional": false
                }
            },
            ...
        ]
    }


基本的な使い方
----------------------------------------------------

``--annotation`` に、アノテーションzipまたはzipを展開したディレクトリのパスを指定してください。

.. code-block::

    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip 


インポート対象のタスクを指定する場合は、``--task_id`` にインポート対象のタスクのtask_idを指定してください。

.. code-block::

    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip \
    --task_id file://task_id.txt

タスクの状態や担当者でインポート対象を絞り込む場合は、``--task_query`` にクエリ条件をJSON形式で指定してください。タスクの現在の状態と担当者を用いて絞り込みます。``--task_id`` と併用した場合は、両方の条件に一致するタスクを対象にします。

.. code-block::

    # 保留中状態のタスクだけにインポートする
    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip \
    --task_query '{"status": "on_hold"}' --include_on_hold_task

    # user_idがa@example.comの担当者であるタスクだけにインポートする
    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip \
    --task_query '{"user_id": "a@example.com"}'

``--task_query`` の条件に一致しても、完了・休憩中・保留中状態のタスクにインポートするには、それぞれ ``--include_complete_task`` 、 ``--include_break_task`` 、 ``--include_on_hold_task`` の指定が必要です。


デフォルトでは、すでにアノテーションが存在する場合はスキップします。
既存のアノテーションを残してインポートする場合は、 ``--merge`` を指定してください。
インポート対象のアノテーションのannotation_idが、既存のアノテーションのannotation_idに一致すれば、アノテーションのデータを更新し、属性は指定したキーだけ更新します。一致しなければアノテーションを追加します。


.. code-block::

    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip \
    --merge


既存のアノテーションを削除してからインポートする場合は、 ``--overwrite`` を指定してください。

.. code-block::

    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip \
    --overwrite


デフォルトでは、休憩中状態のタスクはアノテーションのインポートをスキップします。
休憩中状態のタスクにもインポートする場合は、 ``--include_break_task`` を指定してください。

完了状態のタスクにインポートするには、オーナーロールで ``--include_complete_task`` を指定してください。

デフォルトでは、保留中状態のタスクはアノテーションのインポートをスキップします。
保留中状態のタスクにもインポートする場合は、 ``--include_on_hold_task`` を指定してください。チェッカーロールでインポートした場合、インポート後は未着手状態になります。


オーナーロールでは、タスクの担当者や状態を変更せずにアノテーションをインポートできます。
チェッカーロールで自身が担当者ではないタスクにインポートするには、 ``--change_operator_to_me`` を指定してください。担当者を一時的に自分自身に変更してアノテーションをインポートします。オーナーロールで指定しても効果はありません。

.. code-block::

    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip \
    --change_operator_to_me



``editor_props`` をまとめて指定する
----------------------------------------------------


インポートする全アノテーションに同じ ``editor_props`` を付与する場合は、 ``--editor_props`` を指定してください。
``--editor_props`` で指定できるキーは、 :ref:`annotation_change_editor_props_editor_props_keys` を参照してください。

.. code-block::

    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip \
    --editor_props '{"can_delete": false, "can_edit_data": false}'


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.import_annotation.add_parser
    :prog: annofabcli annotation import
    :nosubcommands:
    :nodefaultconst:
