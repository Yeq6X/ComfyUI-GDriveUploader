import time
from comfy.utils import ProgressBar

class TestCounter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "count_to": ("INT", {"default": 10, "min": 1, "max": 100}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "unique_id": "UNIQUE_ID"
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("result",)
    FUNCTION = "count"
    CATEGORY = "Test"
    # OUTPUT_NODE = True  # テスト用にコメントアウト

    def count(self, count_to, prompt=None, extra_pnginfo=None, unique_id=None):
        print(f"カウント開始: {count_to}まで (unique_id: {unique_id})")
        
        pbar = ProgressBar(count_to)
        
        for i in range(1, count_to + 1):
            print(f"カウント: {i}")
            time.sleep(1)  # 1秒待機（中断のため）
            pbar.update(1)
        
        return (f"完了: {count_to}までカウントしました",)

# ノードマッピング
NODE_CLASS_MAPPINGS = {
    "TestCounter": TestCounter,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TestCounter": "Test Counter",
}