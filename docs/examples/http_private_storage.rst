====================================================================================
ローカルのファイルをAnnoFabでアノテーションする（ビジネスプラン）
====================================================================================
AnnoFabはWebサーバを `プライベートストレージ <https://annofab.com/docs/faq/#ng10vo>`_ として利用することができます。
本ページでは、ローカルにあるファイルをAnnoFabでアノテーションするための環境構築方法を記載します。

なお、この手順で利用するAnnoFabプロジェクトは、**ビジネスプラン** の組織に所属している必要があります。


動作環境
=================================
* Webサーバ `Caddy <https://caddyserver.com/>`_ v2.4.5
* annofabcli v1.48.1

本ページではCaddyを利用しましたが、Caddy以外でもプライベートストレージ環境は構築できます。ご利用している環境に合わせて、適切なWebサーバをお使いください。



作業手順
=================================

Webサーバ"Caddy"の構築
--------------------------

1. https://github.com/caddyserver/caddy/releases から実行ファイルをダウンロードして、``caddy`` コマンドをインストールします。
2. アノテーション対象の画像を用意します。この手順では、以下のディレクトリを利用します。

.. code-block::

    /tmp/www
        img1.jpg
        img2.jpg
        …

3. ``Caddyfile`` を作成します。

.. code-block::
    :caption: Caddyfile


    localhost
    root * /tmp/images
    file_server browse
    
    header {
        Access-Control-Allow-Origin: https://annofab.com
        Access-Control-Allow-Headers: x-annofab-origin
        Access-Control-Allow-Credentials: true
        Access-Control-Max-Age: 86400
    }

4. Caddyを起動します。


.. code-block::

    $ caddy -config Caddyfile


5. https://localhost/img1.jpg にアクセスして、以下を確認します。

    * 画像が表示されている
    * ``Access-Control`` 関係のヘッダが付与されている



annofabcliでタスクの作成
--------------------------
1. 以下のコマンドを実行して、入力データを作成します。

.. code-block::

    # 入力データの作成
    $ annofabcli input_data put --project_id ${PRJ} \
    --json '[{"input_data_id":"input1", "input_data_name":"img1", "input_data_path":"https://localhost/img1.jpg"}]'


2. AnnoFabの入力データ画面を開いて、入力データが表示されていることを確認します。表示さていない場合は、ブラウザのコンソールでエラーメッセージを確認してください。

3. 以下のコマンドを実行して、タスクを作成します。

.. code-block::

    # タスクの作成
    $ annofabcli task put --project_id ${PRJ} \
    --json '{"task1": ["input1"]}'

4. アノテーションエディタ画面で作成したタスクを開き、画像が表示されていることを確認します。




