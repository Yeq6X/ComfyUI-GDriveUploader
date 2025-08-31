# ComfyUI Google Drive Uploader (OAuth2.0版)

ComfyUIで生成した画像や動画をGoogle Driveに直接アップロードするカスタムノード。

## 特徴

- **OAuth2.0認証** - あなたのGoogle Driveを直接使用
- **容量制限なし** - Service Accountの制限を完全回避
- **フォルダ構造の維持** - 安全にフォルダを作成可能
- **zip圧縮アップロード** - 大量ファイルを1つのzipに
- **List Directory (ls)ノード** - ディレクトリ内容を文字列として出力

## インストール

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/yourusername/ComfyUI-GDriveUploader
cd ComfyUI-GDriveUploader
pip install -r requirements.txt
```

## セットアップ

### 1. OAuth2.0クライアントIDの作成

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. プロジェクトを作成または選択
3. **「APIとサービス」→「ライブラリ」**
   - 「Google Drive API」を検索して有効化
4. **「APIとサービス」→「認証情報」**
5. **「+ 認証情報を作成」→「OAuth クライアント ID」**
6. 初めての場合は「同意画面を構成」
   - ユーザータイプ: 外部
   - アプリ名: ComfyUI GDrive（任意）
   - ユーザーサポートメール: あなたのメール
   - デベロッパー連絡先: あなたのメール
7. OAuth クライアント IDの作成
   - アプリケーションの種類: **デスクトップアプリ**
   - 名前: ComfyUI-GDrive（任意）
8. **JSONをダウンロード**（credentials.json）

### 2. 初回認証

1. ComfyUIでノードを追加
2. **credentials_json**欄にダウンロードしたJSONの内容を貼り付け
3. ノードを実行すると**ブラウザが自動で開く**
4. Googleアカウントでログイン
5. 「このアプリは確認されていません」と表示された場合:
   - 「詳細」をクリック
   - 「ComfyUI GDrive（安全でないページ）に移動」をクリック
6. 「許可」をクリック
7. 「認証フローが完了しました」と表示されれば成功

### 3. 以降の使用

- トークンが`~/.comfyui-gdrive/token.pickle`に保存される
- **2回目以降は自動認証**（credentials_json欄は空でOK）
- トークンの有効期限が切れても自動更新

## 使い方

### ノードパラメータ

1. **path**: アップロードするファイルまたはディレクトリ
   - 例: `ComfyUI/output` (フォルダ全体)
   - 例: `ComfyUI/output/image.png` (単一ファイル)

2. **parent_folder_id**: アップロード先のフォルダID
   - 空欄: マイドライブのルート
   - フォルダID: 特定のフォルダ内にアップロード
   - フォルダIDの取得: Google DriveでフォルダのURLから
     - `https://drive.google.com/drive/folders/1AbC...` → `1AbC...`

3. **credentials_json**: OAuth2.0認証情報（初回のみ）
   - 初回: ダウンロードしたJSONを貼り付け
   - 2回目以降: 空欄でOK

4. **compress_folder**: フォルダをzipに圧縮
   - True: 1つのzipファイルとしてアップロード（推奨）
   - False: フォルダ構造を維持して個別ファイルをアップロード

5. **create_parent_folder**: アップロードフォルダ名で親フォルダを作成（**デフォルト: True**）
   - True: `video/` フォルダをアップロード → Drive上に `video/` フォルダを作成してその中に配置
   - False: 指定したフォルダに直接アップロード

## List Directory ノード

ディレクトリの内容を文字列として出力するユーティリティノード。

### パラメータ

- **path**: 対象ディレクトリのパス
- **use_ls_command**: 実際のlsコマンドを使用
- **show_hidden**: 隠しファイルを表示
- **show_details**: ファイル詳細を表示

## トラブルシューティング

### 「このアプリは確認されていません」または「Error 403: access_denied」

これは正常です。個人用アプリのため、Googleの確認を受けていません。

**解決方法1: テストユーザーに自分を追加**
1. Google Cloud Console → 「APIとサービス」→「OAuth同意画面」
2. **左メニューの「対象」**をクリック
3. **「テストユーザー」セクション**で「+ ADD USERS」
4. あなたのGmailアドレスを追加して保存

**解決方法2: 詳細から続行**
- 「詳細」→「安全でないページに移動」で続行（表示される場合）

### ブラウザが開かない

- ファイアウォールやセキュリティソフトが原因の可能性
- 表示されるURLを手動でブラウザにコピー＆ペースト

### トークンをリセットしたい

```bash
rm ~/.comfyui-gdrive/token.pickle
```

### 別のアカウントで使いたい

1. トークンを削除: `rm ~/.comfyui-gdrive/token.pickle`
2. ノードを再実行して新しいアカウントでログイン

## Service Account版からの移行

Service Account版（storageQuotaExceededエラーが出る）から移行する場合：

1. OAuth2.0クライアントIDを作成（上記手順）
2. ノードの入力を変更:
   - `service_account_json` → `credentials_json`に変更
   - フォルダの共有設定は不要
3. 初回実行時にブラウザでログイン

## セキュリティ

- credentials.jsonは初回のみ必要
- トークンはローカルに保存（`~/.comfyui-gdrive/`）
- ワークフロー共有時は`credentials_json`欄を空にする
- トークンファイルは共有しない

## メリット（Service Account版との比較）

| Service Account | OAuth2.0（本実装） |
|---|---|
| 容量制限あり（エラー多発） | **あなたのDrive容量を使用** |
| フォルダ作成不可 | **自由にフォルダ作成** |
| 共有設定が必要 | **共有不要** |
| 設定が複雑 | **初回ブラウザ認証のみ** |

## ライセンス

MIT License