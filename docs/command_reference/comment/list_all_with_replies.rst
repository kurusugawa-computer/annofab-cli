==========================================
comment list_all_with_replies
==========================================

Description
=================================
すべてのルートコメントに返信コメント一覧を付与して出力します。


.. note::

    コメント一覧は、コマンドを実行した日の02:00(JST)頃の状態です。
    最新のコメント情報を取得したい場合は、 ``annofabcli comment list`` コマンドを実行してください。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、すべてのルートコメントに ``reply_comments`` として返信コメント一覧を付与したJSONが出力されます。

.. code-block::

    $ annofabcli comment list_all_with_replies --project_id prj1 --format pretty_json


``--comment_type`` を指定すると、コメントの種類で絞り込めます。

.. code-block::

    $ annofabcli comment list_all_with_replies --project_id prj1 \
     --comment_type inspection --format pretty_json


``annofabcli comment download`` コマンドの出力結果であるコメント全件ファイルも指定することができます。


.. code-block::

    $ annofabcli comment download --project_id prj1 --output comment.json

    $ annofabcli comment list_all_with_replies --project_id prj1 \
     --comment_json comment.json --format pretty_json


出力結果
=================================

``annofabcli comment list_all`` コマンドで出力されるルートコメントの構造に、返信コメント一覧の ``reply_comments`` が追加されます。


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
            },
            "reply_count": 0
          }
        ]
      }
    ]



Usage Details
=================================

.. argparse::
    :ref: annofabcli.comment.list_all_comment_with_replies.add_parser
    :prog: annofabcli comment list_all_with_replies
    :nosubcommands:
    :nodefaultconst:
