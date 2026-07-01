==========================
organization_plugin list
==========================

Description
=================================
組織プラグイン一覧を出力します。


Examples
=================================

基本的な使い方
--------------------------

以下のコマンドは、組織org1の組織プラグイン一覧をCSV形式で出力します。

.. code-block::

    $ annofabcli organization_plugin list --organization org1 --format csv --output out.csv

CSV形式の場合、 ``project_extra_data_kinds`` と ``detail`` はJSON文字列として出力します。


出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli organization_plugin list --organization org1 --format csv --output out.csv

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli organization_plugin list --organization org1 --format pretty_json --output out.json


.. code-block::
    :caption: out.json

    [
        {
            "organization_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "plugin_id": "plugin1",
            "plugin_name": "Custom Annotation Editor",
            "description": "独自のアノテーションエディタです。",
            "detail": {
                "type": "AnnotationEditor",
                "url": "https://example.com/editor?project_id={projectId}&task_id={taskId}",
                "auth_redirect_url": "https://example.com/oauth/callback",
                "compatible_input_data_types": [
                    "image"
                ]
            },
            "is_builtin": false,
            "project_extra_data_kinds": [],
            "created_datetime": "2026-01-23T03:02:56.478+09:00",
            "updated_datetime": "2026-01-23T03:02:56.478+09:00"
        },
        ...
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization_plugin.list_organization_plugin.add_parser
   :prog: annofabcli organization_plugin list
   :nosubcommands:
   :nodefaultconst:
