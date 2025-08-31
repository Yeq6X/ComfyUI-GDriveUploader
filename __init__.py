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

# ComfyUIのinterrupt機能をインポート
try:
    import comfy.model_management as model_management
    COMFY_AVAILABLE = True
except ImportError:
    COMFY_AVAILABLE = False

# グローバル中断フラグ（ComfyUIのフラグと同期）
_interrupt_flag = False

# スコープ設定
SCOPES = ['https://www.googleapis.com/auth/drive']

# トークン保存先
TOKEN_DIR = os.path.expanduser("~/.comfyui-gdrive")
TOKEN_PATH = os.path.join(TOKEN_DIR, "token.pickle")
CREDENTIALS_PATH = os.path.join(TOKEN_DIR, "credentials.json")


# グローバルな中断フラグ
_should_interrupt = False

def set_interrupt():
    """中断フラグを設定"""
    global _should_interrupt
    _should_interrupt = True

def clear_interrupt():
    """中断フラグをクリア"""
    global _should_interrupt
    _should_interrupt = False

def check_interrupt():
    """ComfyUIの中断をチェック"""
    global _should_interrupt
    
    print(f"DEBUG: 中断チェック開始 - 独自フラグ: {_should_interrupt}")
    
    # 独自の中断フラグをチェック
    if _should_interrupt:
        print("DEBUG: 独自中断フラグがTrueのため中断")
        raise InterruptedError("アップロードが中断されました")
    
    # ComfyUIの正式なinterrupt機能を使用
    if COMFY_AVAILABLE:
        try:
            # model_management.processing_interrupted() が正式な方法
            if hasattr(model_management, 'processing_interrupted'):
                interrupted = model_management.processing_interrupted()
                print(f"DEBUG: ComfyUI中断フラグ: {interrupted}")
                if interrupted:
                    print("DEBUG: ComfyUI中断フラグがTrueのため中断")
                    raise InterruptedError("アップロードが中断されました")
                        
        except (AttributeError, NameError, TypeError, ImportError) as e:
            print(f"DEBUG: 中断チェックエラー: {e}")
            pass
    
    print("DEBUG: 中断チェック完了（中断なし）")

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
        
        print("DEBUG: zip圧縮開始")
        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            file_count = 0
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_count += 1
                    if file_count % 10 == 0:  # 10ファイルごとにチェック
                        check_interrupt()
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, folder_path)
                    zipf.write(file_path, arcname)
        
        print(f"DEBUG: zip圧縮完了 - {file_count}個のファイル")
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
        
        try:
            print("DEBUG: アップロード開始")
            
            # 処理開始時は中断フラグをクリア
            clear_interrupt()
            print("DEBUG: 独自中断フラグをクリア")
            
            # ComfyUIの中断フラグもリセット
            if COMFY_AVAILABLE:
                try:
                    if hasattr(model_management, 'interrupt_current_processing'):
                        model_management.interrupt_current_processing(False)
                        print("DEBUG: ComfyUI中断フラグをリセット")
                except (AttributeError, TypeError) as e:
                    print(f"DEBUG: 中断フラグリセットエラー: {e}")
            
            # 認証
            print("DEBUG: 認証開始前の中断チェック")
            check_interrupt()
            print("DEBUG: 認証開始")
            creds = self._get_credentials(credentials_json)
            if not creds:
                print("DEBUG: 認証失敗")
                return ("エラー: 認証に失敗しました。credentials.jsonを確認してください", [])
            print("DEBUG: 認証成功")
            
            check_interrupt()
            print("DEBUG: Drive APIサービス構築中")
            drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
            print("DEBUG: Drive APIサービス構築完了")
            
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
                    check_interrupt()
                    temp_zip_path = self._create_zip_from_folder(path)
                    
                    check_interrupt()
                    
                    file_metadata = {
                        "name": self._get_zip_filename(path),
                        "parents": [upload_parent_id]
                    }
                    
                    media = MediaFileUpload(
                        temp_zip_path,
                        mimetype="application/zip",
                        resumable=True
                    )
                    
                    check_interrupt()
                    
                    uploaded_file = drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields="id,name,webViewLink,webContentLink"
                    ).execute()
                    
                    url = uploaded_file.get("webViewLink", uploaded_file.get("webContentLink", ""))
                    return (f"成功: {uploaded_file['name']} をアップロードしました", [url] if url else [])
                    
                else:
                    # フォルダ構造を維持してアップロード
                    for root, _, filenames in os.walk(path):
                        check_interrupt()
                        for filename in filenames:
                            check_interrupt()
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
                            
                            check_interrupt()
                            
                            uploaded_file = drive_service.files().create(
                                body=file_metadata,
                                media_body=media,
                                fields="id,name,webViewLink"
                            ).execute()
                            
                            uploaded_info.append(uploaded_file.get("webViewLink", ""))
                    
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
                
                url = uploaded_file.get("webViewLink", uploaded_file.get("webContentLink", ""))
                return (f"成功: {uploaded_file['name']} をアップロードしました", [url] if url else [])
            
            return ("エラー: アップロードに失敗しました", [])
            
        except InterruptedError as e:
            print(f"DEBUG: InterruptedError発生: {e}")
            return (f"中断: {str(e)}", [])
        except KeyboardInterrupt:
            print("DEBUG: KeyboardInterrupt発生")
            return ("中断: キーボード割り込みが発生しました", [])
        except Exception as e:
            print(f"DEBUG: Exception発生: {e}")
            print(f"DEBUG: Exception type: {type(e)}")
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}")
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