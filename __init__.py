import os
import json
import zipfile
import tempfile
import pickle
import webbrowser
from typing import Tuple, List, Optional
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ComfyUI ProgressBar
from comfy.utils import ProgressBar

# スコープ設定
SCOPES = ['https://www.googleapis.com/auth/drive']

# トークン保存先
TOKEN_DIR = os.path.expanduser("~/.comfyui-gdrive")
TOKEN_PATH = os.path.join(TOKEN_DIR, "token.pickle")
CREDENTIALS_PATH = os.path.join(TOKEN_DIR, "credentials.json")



class GDriveUploadOAuth:
    """
    Google Drive アップロードノード（OAuth2.0認証版）
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "path": ("STRING", {
                    "default": "ComfyUI/output",
                    "multiline": False,
                    "placeholder": "ファイルまたはディレクトリパス"
                }),
                "parent_folder_id": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Google DriveフォルダID (空欄でルート)"
                }),
            },
            "optional": {
                "credentials_json": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "OAuth2.0 credentials.json（初回のみ必要）"
                }),
                "compress_folder": ("BOOLEAN", {
                    "default": True,
                    "label": "フォルダをzipに圧縮"
                }),
                "create_parent_folder": ("BOOLEAN", {
                    "default": True,
                    "label": "アップロードフォルダ名で親フォルダを作成"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "LIST")
    RETURN_NAMES = ("status", "uploaded_urls")
    FUNCTION = "upload"
    CATEGORY = "IO/Cloud"
    OUTPUT_NODE = True

    def _get_credentials(self, credentials_json: str = "") -> Optional[Credentials]:
        """OAuth2.0認証情報を取得"""
        
        # トークンディレクトリの作成
        if not os.path.exists(TOKEN_DIR):
            os.makedirs(TOKEN_DIR)
        
        creds = None
        
        # 既存のトークンを読み込み
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, 'rb') as token:
                creds = pickle.load(token)
        
        # トークンが無効または存在しない場合
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # トークンをリフレッシュ
                print("認証トークンを更新中...")
                creds.refresh(Request())
            else:
                # 新規認証が必要
                if credentials_json.strip():
                    # UIから提供されたcredentials.jsonを使用
                    print("新しい認証情報で認証を開始...")
                    try:
                        credentials_info = json.loads(credentials_json)
                        # 一時ファイルに保存
                        temp_cred_path = os.path.join(TOKEN_DIR, "temp_credentials.json")
                        with open(temp_cred_path, 'w') as f:
                            json.dump(credentials_info, f)
                        
                        flow = InstalledAppFlow.from_client_secrets_file(
                            temp_cred_path, SCOPES
                        )
                        
                        # ローカルサーバーで認証（ポート0で自動選択）
                        creds = flow.run_local_server(port=0)
                        
                        # 永続的な場所に保存
                        with open(CREDENTIALS_PATH, 'w') as f:
                            json.dump(credentials_info, f)
                        
                        # 一時ファイルを削除
                        os.remove(temp_cred_path)
                        
                    except Exception as e:
                        return None
                        
                elif os.path.exists(CREDENTIALS_PATH):
                    # 保存済みのcredentials.jsonを使用
                    print("保存済みの認証情報で認証を開始...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        CREDENTIALS_PATH, SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                else:
                    print("エラー: credentials.jsonが必要です")
                    print(f"1. Google Cloud ConsoleでOAuth2.0クライアントIDを作成")
                    print(f"2. credentials.jsonをダウンロード")
                    print(f"3. ノードのcredentials_json欄に貼り付け")
                    return None
            
            # トークンを保存
            if creds:
                with open(TOKEN_PATH, 'wb') as token:
                    pickle.dump(creds, token)
                print("認証成功！トークンを保存しました")
        
        return creds

    def _create_zip_from_folder(self, folder_path: str) -> str:
        """フォルダをzipファイルに圧縮"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_path = temp_file.name
        temp_file.close()
        
        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, folder_path)
                    zipf.write(file_path, arcname)
        return temp_path

    def _get_zip_filename(self, folder_path: str) -> str:
        """zipファイル名を生成"""
        folder_name = os.path.basename(folder_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{folder_name}_{timestamp}.zip"

    def _create_folder_structure(self, drive_service, base_path: str, file_path: str, parent_id: str) -> str:
        """フォルダ構造を作成（OAuthなら安全）"""
        rel_path = os.path.relpath(os.path.dirname(file_path), base_path)
        
        if rel_path == ".":
            return parent_id if parent_id else "root"
        
        folders = rel_path.split(os.sep)
        current_parent = parent_id if parent_id else "root"
        
        for folder_name in folders:
            # 既存のフォルダを検索
            query = f"name='{folder_name}' and '{current_parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = drive_service.files().list(q=query, fields="files(id)").execute()
            
            if results.get("files"):
                current_parent = results["files"][0]["id"]
            else:
                # フォルダを作成（OAuthなので自分の容量を使用）
                folder_metadata = {
                    "name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [current_parent]
                }
                folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
                current_parent = folder["id"]
        
        return current_parent

    def upload(self, path: str, parent_folder_id: str = "", 
               credentials_json: str = "", compress_folder: bool = True, 
               create_parent_folder: bool = True) -> Tuple[str, List]:
        """Google Driveへアップロード"""
        
        temp_zip_path = None
        
        # VideoCombineと同じ：ファイル数を取得してProgressBar作成
        num_files = 0
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                num_files += len(files)
        else:
            num_files = 1
        pbar = ProgressBar(num_files)
        
        try:
            
            # 認証
            creds = self._get_credentials(credentials_json)
            if not creds:
                return ("エラー: 認証に失敗しました。credentials.jsonを確認してください", [])
            
            drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
            
            # パスの正規化
            path = os.path.abspath(path)
            
            if not os.path.exists(path):
                return ("エラー: 指定されたパスが存在しません", [])
            
            # parent_folder_idが空の場合はルートを使用
            if not parent_folder_id:
                parent_folder_id = "root"
            
            uploaded_info = []
            
            # ディレクトリの処理
            if os.path.isdir(path):
                # 親フォルダの決定
                if create_parent_folder:
                    # アップロードフォルダ名で親フォルダを作成
                    folder_name = os.path.basename(path)
                    
                    # 既存のフォルダを検索
                    query = f"name='{folder_name}' and '{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                    results = drive_service.files().list(q=query, fields="files(id)").execute()
                    
                    if results.get("files"):
                        # 既存のフォルダを使用
                        upload_parent_id = results["files"][0]["id"]
                    else:
                        # 新しいフォルダを作成
                        folder_metadata = {
                            "name": folder_name,
                            "mimeType": "application/vnd.google-apps.folder",
                            "parents": [parent_folder_id]
                        }
                        folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
                        upload_parent_id = folder["id"]
                else:
                    # 親フォルダを作成せず、指定されたフォルダに直接アップロード
                    upload_parent_id = parent_folder_id
                
                if compress_folder:
                    # zipに圧縮してアップロード
                    temp_zip_path = self._create_zip_from_folder(path)
                    
                    file_metadata = {
                        "name": self._get_zip_filename(path),
                        "parents": [upload_parent_id]
                    }
                    
                    media = MediaFileUpload(
                        temp_zip_path,
                        mimetype="application/zip",
                        resumable=True
                    )
                    
                    uploaded_file = drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields="id,name,webViewLink,webContentLink"
                    ).execute()
                    
                    print(f"アップロード完了: {uploaded_file['name']}")
                    url = uploaded_file.get("webViewLink", uploaded_file.get("webContentLink", ""))
                    return (f"成功: {uploaded_file['name']} をアップロードしました", [url] if url else [])
                    
                else:
                    # フォルダ構造を維持してアップロード
                    for root, _, filenames in os.walk(path):
                        for filename in filenames:
                            file_path = os.path.join(root, filename)
                            
                            # 親フォルダを作成
                            target_parent = self._create_folder_structure(
                                drive_service, path, file_path, upload_parent_id
                            )
                            
                            # ファイルをアップロード
                            file_metadata = {
                                "name": filename,
                                "parents": [target_parent]
                            }
                            
                            media = MediaFileUpload(
                                file_path,
                                resumable=True
                            )
                            
                            uploaded_file = drive_service.files().create(
                                body=file_metadata,
                                media_body=media,
                                fields="id,name,webViewLink"
                            ).execute()
                            
                            print(f"アップロード完了: {filename}")
                            uploaded_info.append(uploaded_file.get("webViewLink", ""))
                            pbar.update(1)  # VideoCombineと同じプログレスバー更新
                    
                    if uploaded_info:
                        return (f"成功: {len(uploaded_info)}個のファイルをアップロードしました", uploaded_info)
            else:
                # 単一ファイルをアップロード
                file_metadata = {
                    "name": os.path.basename(path),
                    "parents": [parent_folder_id]
                }
                
                media = MediaFileUpload(path, resumable=True)
                
                uploaded_file = drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id,name,webViewLink,webContentLink"
                ).execute()
                
                print(f"アップロード完了: {uploaded_file['name']}")
                url = uploaded_file.get("webViewLink", uploaded_file.get("webContentLink", ""))
                return (f"成功: {uploaded_file['name']} をアップロードしました", [url] if url else [])
            
            return ("エラー: アップロードに失敗しました", [])
            
        except Exception as e:
            return (f"エラー: {str(e)}", [])
        finally:
            # 一時ファイルの削除
            if temp_zip_path and os.path.exists(temp_zip_path):
                try:
                    os.unlink(temp_zip_path)
                except:
                    pass


# ls_node.pyからインポート
from .ls_node import LS_NODE_CLASS_MAPPINGS, LS_NODE_DISPLAY_NAME_MAPPINGS

# ノードマッピング
NODE_CLASS_MAPPINGS = {
    "GDriveUpload": GDriveUploadOAuth,
    **LS_NODE_CLASS_MAPPINGS
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GDriveUpload": "Google Drive Upload (OAuth2.0)",
    **LS_NODE_DISPLAY_NAME_MAPPINGS
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]