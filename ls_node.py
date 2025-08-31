import os
import subprocess
import platform
from typing import Tuple


class ListDirectory:
    """
    指定ディレクトリのファイル一覧を文字列として出力
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "path": ("STRING", {
                    "default": ".",
                    "multiline": False,
                    "placeholder": "ディレクトリパス (デフォルト: カレントディレクトリ)"
                }),
                "use_ls_command": ("BOOLEAN", {"default": False}),
                "show_hidden": ("BOOLEAN", {"default": False}),
                "show_details": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("file_list",)
    FUNCTION = "list_files"
    CATEGORY = "Utils/File"
    OUTPUT_NODE = True

    def list_files(self, path: str, use_ls_command: bool = False, 
                  show_hidden: bool = False, show_details: bool = False) -> Tuple[str]:
        """
        ディレクトリの内容を取得
        """
        
        # パスの正規化
        path = os.path.expanduser(path)
        path = os.path.abspath(path)
        
        if not os.path.exists(path):
            return (f"Error: Path does not exist: {path}",)
        
        if not os.path.isdir(path):
            return (f"Error: Path is not a directory: {path}",)
        
        try:
            if use_ls_command:
                # lsコマンドを使用（Unix系/Git Bash on Windows）
                result = self._run_ls_command(path, show_hidden, show_details)
            else:
                # Pythonのos.listdirを使用（クロスプラットフォーム）
                result = self._list_with_python(path, show_hidden, show_details)
            
            return (result,)
            
        except Exception as e:
            return (f"Error: {str(e)}",)
    
    def _run_ls_command(self, path: str, show_hidden: bool, show_details: bool) -> str:
        """
        lsコマンドを実行
        """
        # コマンドの構築
        cmd = ["ls"]
        
        if show_details:
            cmd.append("-l")
        
        if show_hidden:
            cmd.append("-a")
        
        cmd.append(path)
        
        # Windowsの場合、Git BashやWSLのlsを試す
        if platform.system() == "Windows":
            # Git Bashのlsを試す
            git_bash_ls = r"C:\Program Files\Git\usr\bin\ls.exe"
            if os.path.exists(git_bash_ls):
                cmd[0] = git_bash_ls
            else:
                # PowerShellのGet-ChildItemをlsエイリアスとして使用
                cmd = ["powershell", "-Command", f"Get-ChildItem '{path}'"]
                if show_hidden:
                    cmd[-1] += " -Force"
                if show_details:
                    cmd[-1] += " | Format-Table -AutoSize"
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=False,
                timeout=5
            )
            
            if result.returncode != 0:
                return f"Command failed: {result.stderr}"
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            return "Error: Command timed out"
        except FileNotFoundError:
            return "Error: ls command not found. Using Python fallback...\n" + self._list_with_python(path, show_hidden, show_details)
    
    def _list_with_python(self, path: str, show_hidden: bool, show_details: bool) -> str:
        """
        Pythonのos.listdirを使用してファイル一覧を取得
        """
        items = os.listdir(path)
        
        # 隠しファイルのフィルタリング
        if not show_hidden:
            items = [item for item in items if not item.startswith('.')]
        
        # ソート
        items.sort()
        
        if show_details:
            # 詳細情報を追加
            lines = []
            for item in items:
                item_path = os.path.join(path, item)
                try:
                    stat = os.stat(item_path)
                    
                    # ファイルタイプ
                    if os.path.isdir(item_path):
                        type_char = "d"
                    elif os.path.islink(item_path):
                        type_char = "l"
                    else:
                        type_char = "-"
                    
                    # サイズ（バイト）
                    size = stat.st_size
                    
                    # 最終更新時刻
                    import datetime
                    mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    
                    # フォーマット
                    lines.append(f"{type_char} {size:10d} {mtime} {item}")
                    
                except (OSError, IOError):
                    lines.append(f"? ?????????? ?????????? {item}")
            
            return "\n".join(lines)
        else:
            # シンプルなリスト
            return "\n".join(items)


# __init__.pyに追加するための定義
LS_NODE_CLASS_MAPPINGS = {
    "ListDirectory": ListDirectory
}

LS_NODE_DISPLAY_NAME_MAPPINGS = {
    "ListDirectory": "List Directory (ls)"
}