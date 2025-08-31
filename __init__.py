import os
import json
import mimetypes
from typing import Tuple, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class GDriveUpload:
    """
    Google Drive アップロードノード（Service Account JSON直接入力版）
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
                    "placeholder": "Google DriveフォルダID (例: 1AbCdEfG...)"
                }),
                "service_account_json": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "Service Account JSONの内容を貼り付け"
                }),
            },
            "optional": {
                "share_with_email": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "共有先メールアドレス（オプション）"
                }),
                "upload_subdirs": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING", "LIST")
    RETURN_NAMES = ("status", "uploaded_urls")
    FUNCTION = "upload"
    CATEGORY = "IO/Cloud"
    OUTPUT_NODE = True

    def _load_credentials(self, service_account_json: str):
        """Service Account JSONから認証情報を読み込み"""
        scopes = ["https://www.googleapis.com/auth/drive"]
        
        if not service_account_json.strip():
            raise ValueError("Service Account JSONが入力されていません")
        
        try:
            info = json.loads(service_account_json)
            return service_account.Credentials.from_service_account_info(info, scopes=scopes)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSONの解析に失敗しました: {e}")
        except Exception as e:
            raise ValueError(f"認証情報の読み込みに失敗しました: {e}")

    def _get_mime_type(self, path: str) -> str:
        """ファイルのMIMEタイプを推定"""
        mime_type, _ = mimetypes.guess_type(path)
        return mime_type or "application/octet-stream"

    def _get_upload_files(self, path: str, upload_subdirs: bool) -> List[str]:
        """アップロード対象のファイルリストを取得"""
        files = []
        
        # パスの正規化
        path = os.path.abspath(path)
        
        if os.path.isfile(path):
            files.append(path)
        elif os.path.isdir(path):
            if upload_subdirs:
                # サブディレクトリを含む全ファイル
                for root, _, filenames in os.walk(path):
                    for filename in filenames:
                        files.append(os.path.join(root, filename))
            else:
                # 直下のファイルのみ
                for filename in os.listdir(path):
                    filepath = os.path.join(path, filename)
                    if os.path.isfile(filepath):
                        files.append(filepath)
        
        return files

    def _share_file(self, drive_service, file_id: str, email: str):
        """ファイルを指定のメールアドレスと共有"""
        if not email:
            return
        
        try:
            permission = {
                "type": "user",
                "role": "writer",
                "emailAddress": email
            }
            drive_service.permissions().create(
                fileId=file_id,
                body=permission,
                sendNotificationEmail=False
            ).execute()
        except Exception as e:
            print(f"共有設定に失敗しました: {e}")

    def _create_folder_structure(self, drive_service, base_path: str, file_path: str, parent_id: str) -> str:
        """必要に応じてフォルダ構造を作成し、最終的な親フォルダIDを返す"""
        rel_path = os.path.relpath(os.path.dirname(file_path), base_path)
        
        if rel_path == ".":
            return parent_id
        
        folders = rel_path.split(os.sep)
        current_parent = parent_id
        
        for folder_name in folders:
            # 既存のフォルダを検索
            query = f"name='{folder_name}' and '{current_parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = drive_service.files().list(q=query, fields="files(id)").execute()
            
            if results.get("files"):
                current_parent = results["files"][0]["id"]
            else:
                # フォルダを作成
                folder_metadata = {
                    "name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [current_parent]
                }
                folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
                current_parent = folder["id"]
        
        return current_parent

    def upload(self, path: str, parent_folder_id: str, service_account_json: str,
               share_with_email: str = "", upload_subdirs: bool = True) -> Tuple[str, List]:
        """Google Driveへファイルをアップロード"""
        
        try:
            # 認証情報の読み込み
            credentials = self._load_credentials(service_account_json)
            drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
            
            if not parent_folder_id:
                return ("エラー: parent_folder_id が指定されていません", [])
            
            # アップロード対象ファイルの取得
            files_to_upload = self._get_upload_files(path, upload_subdirs)
            
            if not files_to_upload:
                return ("エラー: アップロード対象のファイルが見つかりません", [])
            
            uploaded_info = []
            base_path = path if os.path.isdir(path) else os.path.dirname(path)
            
            for file_path in files_to_upload:
                try:
                    # フォルダ構造を維持する場合は親フォルダを作成
                    if os.path.isdir(path) and upload_subdirs:
                        target_parent = self._create_folder_structure(
                            drive_service, base_path, file_path, parent_folder_id
                        )
                    else:
                        target_parent = parent_folder_id
                    
                    # ファイルのアップロード
                    file_metadata = {
                        "name": os.path.basename(file_path),
                        "parents": [target_parent]
                    }
                    
                    media = MediaFileUpload(
                        file_path,
                        mimetype=self._get_mime_type(file_path),
                        resumable=True
                    )
                    
                    uploaded_file = drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields="id,name,webViewLink,webContentLink"
                    ).execute()
                    
                    # 共有設定
                    self._share_file(drive_service, uploaded_file["id"], share_with_email)
                    
                    # アップロード情報を記録
                    uploaded_info.append({
                        "name": uploaded_file["name"],
                        "id": uploaded_file["id"],
                        "url": uploaded_file.get("webViewLink", uploaded_file.get("webContentLink", ""))
                    })
                    
                except Exception as e:
                    print(f"ファイル {file_path} のアップロードに失敗: {e}")
                    continue
            
            if uploaded_info:
                urls = [info["url"] for info in uploaded_info if info["url"]]
                status = f"成功: {len(uploaded_info)}個のファイルをアップロードしました"
                return (status, urls)
            else:
                return ("エラー: ファイルのアップロードに失敗しました", [])
            
        except ValueError as e:
            return (f"エラー: {e}", [])
        except Exception as e:
            return (f"エラー: {e}", [])


# ls_node.pyからインポート
from .ls_node import LS_NODE_CLASS_MAPPINGS, LS_NODE_DISPLAY_NAME_MAPPINGS

NODE_CLASS_MAPPINGS = {
    "GDriveUpload": GDriveUpload,
    **LS_NODE_CLASS_MAPPINGS
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GDriveUpload": "Google Drive Upload (Direct JSON)",
    **LS_NODE_DISPLAY_NAME_MAPPINGS
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]