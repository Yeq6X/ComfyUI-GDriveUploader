import os
import json
import mimetypes
import zipfile
import tempfile
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
                "compress_folder": ("BOOLEAN", {
                    "default": True,
                    "label": "フォルダをzipに圧縮してアップロード"
                }),
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

    def _create_zip_from_folder(self, folder_path: str) -> str:
        """フォルダをzipファイルに圧縮して一時ファイルパスを返す"""
        # 一時ファイルを作成
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_path = temp_file.name
        temp_file.close()
        
        # zipファイルを作成
        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # アーカイブ内のパスを相対パスにする
                    arcname = os.path.relpath(file_path, folder_path)
                    zipf.write(file_path, arcname)
        
        return temp_path

    def _get_zip_filename(self, folder_path: str) -> str:
        """フォルダ名からzipファイル名を生成"""
        folder_name = os.path.basename(folder_path)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{folder_name}_{timestamp}.zip"
    
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


    def upload(self, path: str, parent_folder_id: str, service_account_json: str,
               share_with_email: str = "", compress_folder: bool = True) -> Tuple[str, List]:
        """Google Driveへファイルをアップロード"""
        
        temp_zip_path = None
        
        try:
            # 認証情報の読み込み
            credentials = self._load_credentials(service_account_json)
            drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
            
            if not parent_folder_id:
                return ("エラー: parent_folder_id が指定されていません", [])
            
            # パスの正規化
            path = os.path.abspath(path)
            
            if not os.path.exists(path):
                return ("エラー: 指定されたパスが存在しません", [])
            
            # アップロードするファイルのパスとファイル名を決定
            if os.path.isdir(path) and compress_folder:
                # フォルダをzipに圧縮
                print(f"フォルダ '{path}' をzipに圧縮中...")
                temp_zip_path = self._create_zip_from_folder(path)
                upload_file_path = temp_zip_path
                upload_file_name = self._get_zip_filename(path)
            elif os.path.isdir(path) and not compress_folder:
                # フォルダだが圧縮しない場合（個別ファイルをアップロード）
                files_to_upload = []
                for root, _, filenames in os.walk(path):
                    for filename in filenames:
                        files_to_upload.append(os.path.join(root, filename))
                
                if not files_to_upload:
                    return ("エラー: フォルダ内にファイルが見つかりません", [])
                
                # 複数ファイルをアップロード
                uploaded_info = []
                for file_path in files_to_upload:
                    try:
                        file_metadata = {
                            "name": os.path.relpath(file_path, path).replace(os.sep, '_'),
                            "parents": [parent_folder_id]
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
                        
                        self._share_file(drive_service, uploaded_file["id"], share_with_email)
                        uploaded_info.append(uploaded_file.get("webViewLink", uploaded_file.get("webContentLink", "")))
                        
                    except Exception as e:
                        print(f"ファイル {file_path} のアップロードに失敗: {e}")
                        continue
                
                if uploaded_info:
                    return (f"成功: {len(uploaded_info)}個のファイルをアップロードしました", uploaded_info)
                else:
                    return ("エラー: ファイルのアップロードに失敗しました", [])
            else:
                # 単一ファイルをアップロード
                upload_file_path = path
                upload_file_name = os.path.basename(path)
            
            # 単一ファイル（またはzip）をアップロード
            try:
                file_metadata = {
                    "name": upload_file_name,
                    "parents": [parent_folder_id]
                }
                
                media = MediaFileUpload(
                    upload_file_path,
                    mimetype=self._get_mime_type(upload_file_path),
                    resumable=True
                )
                
                uploaded_file = drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id,name,webViewLink,webContentLink"
                ).execute()
                
                # 共有設定
                self._share_file(drive_service, uploaded_file["id"], share_with_email)
                
                # URL取得
                url = uploaded_file.get("webViewLink", uploaded_file.get("webContentLink", ""))
                
                if os.path.isdir(path) and compress_folder:
                    status = f"成功: フォルダ '{os.path.basename(path)}' をzipとしてアップロードしました"
                else:
                    status = f"成功: ファイル '{upload_file_name}' をアップロードしました"
                
                return (status, [url] if url else [])
            
            except Exception as e:
                return (f"エラー: アップロードに失敗しました: {e}", [])
            
        except ValueError as e:
            return (f"エラー: {e}", [])
        except Exception as e:
            return (f"エラー: {e}", [])
        finally:
            # 一時ファイルの削除
            if temp_zip_path and os.path.exists(temp_zip_path):
                try:
                    os.unlink(temp_zip_path)
                except:
                    pass


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