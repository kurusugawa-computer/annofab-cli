=====================
input_data list_with_json
=====================

Description
=================================
入力データファイルから入力データ一覧を出力します。
10,000件以上の入力データを出力する際に利用できます。


Examples
=================================


  -p PROJECT_ID, --project_id PROJECT_ID
                        対象のプロジェクトのproject_idを指定します。 (default: None)
  -iq INPUT_DATA_QUERY, --input_data_query INPUT_DATA_QUERY
                        入力データの検索クエリをJSON形式で指定します。`file://`を先頭に付けると、JSON形式のファイルを指定できます。指定できるキーは、`input_data_name`, `input_data_path`です。 (default: None)
  -i INPUT_DATA_ID [INPUT_DATA_ID ...], --input_data_id INPUT_DATA_ID [INPUT_DATA_ID ...]
                        対象のinput_data_idを指定します。`file://`を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。 (default: None)
  --input_data_json INPUT_DATA_JSON
                        入力データ情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元に入力データ一覧を出力します。指定しない場合、全件ファイルをダウンロードします。JSONファイルは`$ annofabcli project download input_data`コマンドで取得できます。 (default: None)
  --latest              最新の入力データ一覧ファイルを参照します。このオプションを指定すると、入力データ一覧ファイルを更新するのに約5分以上待ちます。 (default: False)



```
# 全件の入力データを出力する
$ annofabcli input_data list_with_json --project_id prj1 --output input_data.csv

# 入力データ全件ファイルを最新化してから、出力する
$ annofabcli input_data list_with_json --project_id prj1 --output input_data.csv --latest
```


基本的な使い方
--------------------------

以下のコマンドは、入力データ全件ファイルをダウンロードしてから、入力データ一覧を出力します。

.. code-block::

    $ annofabcli input_data list_with_json --project_id prj1


入力データ全件ファイルを指定する場合は、``--input_data_json`` に入力データ全件ファイルのパスを指定してください。
入力データ全件ファイルは、`annofabcli project download <../project/download.html>`_ コマンドでダウンロードできます。


.. code-block::

    $ annofabcli input_data list_with_json --project_id prj1 --input_data_json input_data.json 



絞り込み
----------------------------------------------

``--input_data_query`` を指定すると、入力データの名前や入力データのパスで絞り込めます。


以下のコマンドは、入力データ名に"sample"を含む入力データの一覧を出力します。

.. code-block::

    $ annofabcli input_data list_with_json --project_id prj1  \
     --input_data_query '{"input_data_name": "sample"}' 



``--input_data_id`` を指定すると、input_data_idに合致する入力データの一覧を出力します。

.. code-block::

    $ annofabcli input_data list_with_json --project_id prj1 \
     --input_data_id file://input_data_id.txt




出力結果
=================================
`annofabcli input_data list <../input_data/list.html>`_ コマンドの出力結果と同じです。





See also
=================================
* `annofabcli project download <../project/download.html>`_
* `annofabcli input_data list <../input_data/list.html>`_
