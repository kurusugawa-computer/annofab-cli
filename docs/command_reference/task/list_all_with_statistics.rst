==========================================
task list_all_with_statistics
==========================================

Description
=================================

全状態のタスクを対象に、タスク履歴に関する情報と生産量をまとめた一覧を出力します。
作業時間、担当者、アノテーション数、動画時間、区間アノテーションの長さを、タスクごとに比較できます。

``statistics visualize`` と異なり、コメント・タスク履歴イベントの取得や、ユーザー別・日別の集計、グラフ生成は行いません。
アノテーション数をZIPから取得する場合、件数と区間長さは一度の走査で集計します。
ZIPの取得・解析にかかる時間は残るため、プロジェクトの規模によって処理時間が変わります。

Examples
=================================

基本的な使い方
---------------------------------

.. code-block:: bash

    annofabcli task list_all_with_statistics --project_id prj1 --output task.csv

JSONで出力する場合は ``--format pretty_json`` を指定します。

.. code-block:: bash

    annofabcli task list_all_with_statistics --project_id prj1 --format pretty_json --output task.json

対象タスクを絞り込む
---------------------------------

デフォルトでは未着手・作業中も含めた全状態のタスクを出力します。
``--task_query`` と ``--task_id`` で絞り込めます。

.. code-block:: bash

    annofabcli task list_all_with_statistics --project_id prj1 \
      --task_query '{"phase":"annotation","status":"working"}' --output task.csv

    annofabcli task list_all_with_statistics --project_id prj1 \
      --task_id file://task_ids.txt --output task.csv

タスク履歴全件ファイルが更新される前に確認する
-------------------------------------------------------

通常はタスク履歴全件ファイルから作業時間や初回担当者などを取得します。
全件ファイルが更新される前に作業時間を確認したい場合は、``--get_task_histories_one_of_each`` を指定してください。
この場合、絞り込み後の各タスクの履歴をWebAPIで1件ずつ取得し、履歴全件ファイルは取得しません。
対象タスク数だけAPIを実行するため、処理時間が長くなります。

.. code-block:: bash

    annofabcli task list_all_with_statistics --project_id prj1 \
      --get_task_histories_one_of_each --latest --output task.csv

``--latest`` は、タスク全件ファイル・アノテーションZIP・入力データ全件ファイルのうち使用するファイルを更新します。
タスク履歴全件ファイルは更新できません。履歴の最新化には上記のオプションが必要です。
また、履歴をAPIで取得しても、タスク状態やZIPの生産量は最新化されないため、それらも更新したい場合は ``--latest`` を併用してください。
ファイルの更新には数分から数十分かかる場合があり、各データの取得時点が完全に一致することも保証されません。

アノテーション数の取得元と集計対象ラベル
-------------------------------------------------------

``--annotation_count_source`` の ``auto``・``zip``・``api`` は、
:doc:`../statistics/visualize` の「アノテーション数の取得元を指定する」と同じ動作です。
デフォルトの ``auto`` は、3Dインスタンスセグメントまたは3DセマンティックセグメントのラベルがあればAPI、それ以外はZIPを使用します。
APIの場合も、このコマンドで絞り込んだ全状態のタスクを集計します。
動画プロジェクトでは ``api`` 指定時も区間長さの集計用にZIPを取得します。

.. code-block:: bash

    annofabcli task list_all_with_statistics --project_id prj1 \
      --annotation_count_source zip --production_volume_include_label car person --output task.csv

``--production_volume_include_label`` は指定したラベルだけを集計し、
``--production_volume_exclude_label`` は指定したラベルを除外します。両者は同時に指定できません。
英語のラベル名を複数指定でき、``file://`` で改行区切りの一覧ファイルを1個だけ指定することもできます。
未指定なら全ラベルを集計します。

ラベル指定の適用先は ``annotation_count`` と ``annotation_duration_minute`` です。
作業時間・動画時間・入力データ数・対象タスクは変わりません。
したがって、ラベルを指定した場合も、作業時間はタスク全体の値です。

出力結果
=================================

CSVは1タスク1行で、0件でも固定47列のヘッダーを出力します。
列は :doc:`list_added_task_history` の44列を引き継ぎ、``input_data_count`` の直後に以下の3列を追加します。

.. list-table:: 追加する生産量の列
   :header-rows: 1

   * - 列名
     - 内容
   * - ``annotation_count``
     - アノテーション数。区間以外のアノテーションも含みます。
   * - ``video_duration_minute``
     - 動画の長さ（分）。
   * - ``annotation_duration_minute``
     - 区間アノテーションの長さの合計（分）。重なる区間もそれぞれ加算します。

タスクのメタデータは ``metadata.{key}`` 列として辞書順で末尾に追加します。
JSONでは同じ固定47項目と ``metadata`` オブジェクトを出力します。
指定日以降の ``since_*`` 列や、生産量あたり作業時間の比率列は出力しません。

動画以外のプロジェクトでは、動画時間・区間長さは空欄（JSONでは ``null``）です。
動画時間を取得できない場合や、ZIP内に対象タスクのJSONがない場合も、該当する生産量を空欄にします。
JSONが存在して集計対象アノテーションがない場合は、件数・区間長さを0にします。
APIから件数を取得する場合は、ZIP内のJSONの有無によらずAPIの件数を使用します。

``worktime_hour`` は通常、タスク全件ファイルの合計作業時間です。
``--get_task_histories_one_of_each`` 指定時は、APIで取得した教師付・検査・受入の作業時間の合計です。
フェーズ別作業時間や履歴由来のその他の項目も、指定した取得元のタスク履歴を使用します。

以下は動画プロジェクトの出力例です。

.. csv-table:: CSV出力例
   :header-rows: 1
   :file: list_all_with_statistics/task.csv

.. literalinclude:: list_all_with_statistics/task.json
   :language: json

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.list_all_with_statistics.create_parser
   :prog: annofabcli task list_all_with_statistics
   :nosubcommands:
   :nodefaultconst:
