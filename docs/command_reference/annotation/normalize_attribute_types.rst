==========================================
annotation normalize_attribute_types
==========================================

Description
=================================
アノテーションの属性値の型を、現在のアノテーション仕様に合わせるコマンドです。
たとえば、アノテーション仕様で属性の種類を自由記述1行（ ``text`` ）から自由記述複数行（ ``comment`` ）に変更した直後は、
属性値の型がアノテーション仕様と一致していないため、
アノテーションエディタ画面やダウンロードしたアノテーションZIPでは、属性値が空欄になっている可能性があります。
そのようなアノテーションの属性値を修正するコマンドです。


対応する変換
---------------------------------------

.. list-table::
   :header-rows: 1

   * - 保存型 → 現行仕様の型
     - 変換内容
   * - ``Choice`` → ``select`` / ``Select`` → ``choice``
     - 選択肢IDを保持して保存型を変更します。選択肢IDが現行仕様に存在しない場合はスキップします。
   * - ``Text`` → ``comment`` / ``Comment`` → ``text``
     - 文字列を保持して保存型を変更します。``Text`` → ``comment`` で改行（CRまたはLF）を含む値はスキップします。
   * - ``Text`` → ``integer``
     - Pythonの ``int()`` 関数で変換します。先頭のゼロや前後の空白など、文字列表記は保持されません。
   * - ``Integer`` → ``text``
     - Pythonの ``str()`` 関数で整数値を文字列に変換します。

``int()`` では、たとえば ``"04"``、``"+4"``、``" 4 "`` は整数の ``4`` になります。
``"4.0"``、空文字、数値以外など変換できない値は、変更せずスキップします。
未対応の組み合わせや現行仕様のラベルに存在しない属性も、値を保持してスキップし、理由をログに出力します。
型が一致する属性値と未設定（``null``）の属性値は更新しません。属性の追加・削除や初期値の補完は行いません。

作業中状態のタスクはスキップします。
保留中状態のタスクの扱いは :ref:`include-on-hold-task-for-annotation-updates` を参照してください。
完了状態のタスクも処理する場合は、オーナーロールで ``--include_complete_task`` を指定してください。

Examples
=================================

更新せずに確認する
---------------------------------------

.. code-block:: console

    $ annofabcli annotation normalize_attribute_types \
     --project_id p1 --task_id t1 t2 --dry_run

正規化予定の属性値数とスキップ理由をログに出力します。バックアップは作成しません。

属性を絞り込んで修復する
---------------------------------------

.. code-block:: console

    $ annofabcli annotation normalize_attribute_types \
     --project_id p1 --task_id t1 t2 \
     --attribute_name_en note --backup backup_dir/

``--attribute_id`` または ``--attribute_name_en`` で対象属性を指定できます。省略すると全属性が対象です。
``--task_id`` の代わりに ``--all_tasks`` を指定すると全タスクを対象にします。

変更する入力データのEditor形式アノテーションと外部リソースを、更新前に ``--backup`` のディレクトリへ保存します。
バックアップの形式は :doc:`dump`、復元方法は :doc:`restore` を参照してください。
再実行しても、型がすでに一致する属性値は更新しません。

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.normalize_attribute_types.add_parser
    :prog: annofabcli annotation normalize_attribute_types
    :nosubcommands:
    :nodefaultconst:
