==========================================
Optional arguments
==========================================

すべてのコマンドで利用可能なオプション引数
==================================================================


--disable_log
----------------------------------------------------------------
ログ出力を無効化します。


--endpoint_url
----------------------------------------------------------------
AnnoFab WebAPIのエンドポイントURLを指定します。デフォルトは https://annofab.com です。


### `-h` / `--help`
コマンドのヘルプを出力します。

```
# annofabcli全体のヘルプ
$ annofabcli -h

# project diff コマンドのヘルプ
$ annofabcli project diff -h
```


### `--logdir`
ログファイルを保存するディレクトリを指定します。指定しない場合、`.log`ディレクトリにログファイルを出力します。


### `--logging_yaml`
以下のような、ロギグングの設定ファイル(YAML)を指定します。指定した場合、`--logdir`オプションは無視されます。指定しない場合、デフォルトのロギング設定ファイルが読み込まれます。
設定ファイルの書き方は https://docs.python.org/ja/3/howto/logging.html を参照してください。

```yaml:logging-sample.yaml
# WARNINGレベル以上のログをコンソールに出力する

version: 1
handlers:
  consoleHandler:
    class: logging.StreamHandler
root:
  level: WARNING
  handlers: [consoleHandler]

# デフォルトのロガーを無効化しないようにする https://docs.djangoproject.com/ja/2.1/topics/logging/#configuring-logging
disable_existing_loggers: False
```


### `--yes`
処理中に現れる問い合わせに対して、常に'yes'と回答します。





Description
=================================
タスク配下のアノテーションを削除します。
ただし、作業中または完了状態のタスクのアノテーションは削除できません。




Examples
=================================


基本的な使い方
--------------------------

``--task_id`` に削除対象のタスクのtask_idを指定してください。

.. code-block::

    $ annofabcli annotation delete --project_id prj1 --task_id file://task.txt \
    --backup backup


``--backup`` にディレクトリを指定すると、削除対象のタスクのアノテーション情報を、バックアップとしてディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。


.. note::

    間違えてアノテーションを削除したときに復元できるようにするため、``--backup`` を指定することを推奨します。



削除するアノテーションを絞り込む場合は、``--annotation_query`` を指定してください。フォーマットは https://annofab.com/docs/api/#section/AnnotationQuery とほとんど同じです。
``--annotation_query`` のサンプルは、`annofabcli annotation list_count <../annotation/list_count.html>`_ を参照してください。

以下のコマンドは、ラベル名（英語）の値が"car"で、属性名(英語)が"occluded"である値をfalse（"occluded"チェックボックスをOFF）であるアノテーションを削除します。


.. code-block::

    $ annofabcli annotation delete --project_id prj1 --task_id file://task.txt \ 
    --annotation_query '{"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": false}]}' \
    --backup backup_dir/



See also
=================================
*  `annofabcli annotation restore <../annotation/restore.html>`_

