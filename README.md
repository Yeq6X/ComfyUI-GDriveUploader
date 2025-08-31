# ComfyUI Google Drive Uploader

ComfyUIで生成した画像や動画をGoogle Driveに直接アップロードするカスタムノード。

## 特徴

- **Service Account JSONを直接UIに貼り付け**（コンソール作業不要）
- **フォルダをzipに圧縮してアップロード**（容量エラー回避）
- 単一ファイルのアップロード
- 任意のメールアドレスへの共有設定
- **List Directory (ls)ノード** - ディレクトリ内容を文字列として出力

## インストール

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/yourusername/ComfyUI-GDriveUploader
cd ComfyUI-GDriveUploader
pip install -r requirements.txt
```

## セットアップ

### 1. Service Accountの作成

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. プロジェクトを作成または選択
3. 「APIとサービス」→「認証情報」へ移動
4. 「認証情報を作成」→「サービスアカウント」を選択
5. サービスアカウント名を入力して作成
6. 作成したサービスアカウントをクリック
7. 「キー」タブ→「鍵を追加」→「新しい鍵を作成」→「JSON」を選択
8. JSONファイルがダウンロードされます

### 2. Google Drive APIの有効化

1. 「APIとサービス」→「ライブラリ」へ移動
2. 「Google Drive API」を検索
3. 「有効にする」をクリック

### 3. Google Driveフォルダの共有設定

**重要**: Service Accountには独自のストレージ容量がないため、**必ず既存のGoogle Driveフォルダを共有**してください。

1. **あなたの個人Google Drive**でフォルダを作成（または既存フォルダを使用）
2. フォルダを右クリック→「共有」
3. Service AccountのメールアドレスをEditor権限で追加
   - メールアドレスは `xxxxx@project-name.iam.gserviceaccount.com` の形式
   - JSONファイルの `client_email` フィールドに記載されています
4. **フォルダのオーナーはあなたのまま**（あなたのDrive容量を使用）

### 4. フォルダIDの取得

1. Google Driveでアップロード先フォルダを開く
2. URLから folder ID をコピー
   - URL例: `https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz`
   - フォルダID: `1AbCdEfGhIjKlMnOpQrStUvWxYz`

## 使い方

### ノードの設定

1. **path**: アップロードするファイルまたはディレクトリのパス
   - 例: `ComfyUI/output` (ディレクトリ全体をzipに)
   - 例: `ComfyUI/output/image.png` (単一ファイル)

2. **parent_folder_id**: Google DriveのフォルダID
   - 上記で取得したフォルダIDを入力

3. **service_account_json**: Service Account JSONの内容
   - ダウンロードしたJSONファイルの内容を**そのまま貼り付け**

4. **share_with_email** (オプション): 共有先のメールアドレス
   - アップロード後に自動的に共有されます

5. **compress_folder**: フォルダをzipに圧縮するか（**デフォルト: True**）
   - True: フォルダを1つのzipファイルとしてアップロード（推奨）
   - False: フォルダ内のファイルを個別にアップロード

## セキュリティに関する注意

- **Service Account JSONには機密情報が含まれています**
- ワークフローを共有する際は、`service_account_json`フィールドを**必ず空にして**から共有してください
- JSONファイルは安全な場所に保管し、公開リポジトリにコミットしないでください

## トラブルシューティング

### 「storageQuotaExceeded」エラーが発生する場合

**原因**: Service Accountには独自のストレージ容量がありません。

**解決方法**:
1. **あなたの個人Google Drive**でフォルダを作成
2. そのフォルダをService Accountと**共有**（編集者権限）
3. フォルダのオーナーはあなたのままにする
4. **フォルダはzipに圧縮されてアップロード**されるため、フォルダ構造の問題を回避できます

### アップロードが失敗する場合

1. Service Account JSONが正しく貼り付けられているか確認
2. Google Drive APIが有効になっているか確認
3. フォルダがService Accountと共有されているか確認
4. フォルダIDが正しいか確認

### 権限エラーが発生する場合

- Service AccountにEditor権限が付与されているか確認
- 共有設定で「リンクを知っている全員」ではなく、Service Accountのメールアドレスを直接追加

## List Directory ノード

ディレクトリの内容を文字列として出力するユーティリティノード。

### 入力パラメータ

- **path**: 対象ディレクトリのパス
- **use_ls_command**: 実際のlsコマンドを使用するか（False時はPython実装）
- **show_hidden**: 隠しファイルを表示
- **show_details**: ファイルサイズや更新日時などの詳細情報を表示

### 出力

- **file_list**: ファイル一覧の文字列（他のテキストプレビューノードで表示可能）

## ライセンス

MIT License