==========================================
comment list_with_replies
==========================================

Description
=================================
ルートコメントに返信コメント一覧を付与して出力します。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、指定したタスクの最新コメントを取得し、ルートコメントに ``reply_comments`` として返信コメント一覧を付与したJSONが出力されます。

.. code-block::

    $ annofabcli comment list_with_replies --project_id prj1 --task_id task1 --format pretty_json


``--comment_type`` を指定すると、コメントの種類で絞り込めます。

.. code-block::

    $ annofabcli comment list_with_replies --project_id prj1 --task_id task1 \
     --comment_type inspection --format pretty_json


出力結果
=================================

``annofabcli comment list`` コマンドで出力されるルートコメントの構造に、返信コメント一覧の ``reply_comments`` が追加されます。
``reply_comments`` 配下の返信コメントには ``reply_count`` は含まれません。


.. code-block::

    [
      {
        "project_id": "project1",
        "task_id": "task1",
        "input_data_id": "input_data1",
        "comment_id": "root-comment1",
        "comment": "枠がずれています",
        "comment_node": {
          "status": "open",
          "_type": "Root"
        },
        "reply_count": 1,
        "reply_comments": [
          {
            "project_id": "project1",
            "task_id": "task1",
            "input_data_id": "input_data1",
            "comment_id": "reply-comment1",
            "comment": "修正しました",
            "comment_node": {
              "root_comment_id": "root-comment1",
              "_type": "Reply"
            }
          }
        ]
      }
    ]



Usage Details
=================================

.. argparse::
    :ref: annofabcli.comment.list_comment_with_replies.add_parser
    :prog: annofabcli comment list_with_replies
    :nosubcommands:
    :nodefaultconst:
